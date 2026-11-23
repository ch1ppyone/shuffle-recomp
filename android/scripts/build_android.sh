#!/usr/bin/env bash
# Build the Android arm64 APK end to end.
#
#   android/scripts/build_android.sh
#
# Needs the Android SDK with NDK 28.2.13676358, platform 35 and CMake 3.31.6 (Android Studio's
# SDK Manager installs all four), JDK 17, and the desktop tree's extracted data. The host
# dream-translate is built once in build-host and runs at Gradle's CMake time; the game C is the
# same output as the desktop ports, just compiled with the NDK.
set -euo pipefail

ANDROID_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ANDROID_ROOT/.." && pwd)"
source "$ANDROID_ROOT/scripts/android_env.sh"

[ -x "$ANDROID_CMAKE" ] || command -v "$ANDROID_CMAKE" >/dev/null || {
    echo "CMake 3.31.6 is not installed in the SDK" >&2; exit 1; }
[ -f "$REPO/game/extracted/fs/1ST_READ.BIN" ] || {
    echo "game/extracted/fs/1ST_READ.BIN missing: run the desktop extraction first" >&2; exit 1; }

"$ANDROID_ROOT/scripts/build_sdl3_android.sh"

# The translator is a host tool: the NDK cannot run it, and its output is ordinary C++.
HOST_TRANSLATE="$REPO/build-host/dreamcomp/engine/translator/dream-translate"
if [ ! -x "$HOST_TRANSLATE" ]; then
    echo "== host dream-translate"
    cmake -S "$REPO" -B "$REPO/build-host" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DDREAM_RENDERER=OFF -DDREAMCOMP_FRONTEND=OFF -DDREAM_BUILD_TESTS=OFF -DDREAM_WERROR=OFF
    cmake --build "$REPO/build-host" --target dream-translate --parallel
fi
export DREAM_TRANSLATE_TOOL="$HOST_TRANSLATE"
export SDL3_ANDROID_ROOT="$REPO/.dreamcomp/android-deps/sdl3"

# --- assets ----------------------------------------------------------------------------------
# The same files the desktop TOML names: boot binary and SUBPROG overlays.
# The disc image is never bundled.
ASSETS="$ANDROID_ROOT/app/src/main/assets/data"
rm -rf "$ASSETS"
mkdir -p "$ASSETS/game/extracted/fs" "$ASSETS/extracted/disc/fs/SUBPROG"
cp "$REPO/game/sonicshuffle.toml" "$ASSETS/game/"
cp "$REPO/game/extracted/fs/1ST_READ.BIN" "$ASSETS/game/extracted/fs/"
cp "$REPO"/extracted/disc/fs/SUBPROG/*.BIN "$ASSETS/extracted/disc/fs/SUBPROG/"
printf 'Prepared by android/scripts/build_android.sh from the desktop tree.\n' > "$ASSETS/README.txt"
find "$ASSETS" -type f -print \
  | sed "s#^$ASSETS/##" \
  | sort > "$ANDROID_ROOT/app/src/main/assets/data-manifest.txt"

printf 'sdk.dir=%s\n' "$ANDROID_SDK" > "$ANDROID_ROOT/local.properties"

# Android Gradle Plugin can reuse a native CMake cache created by an earlier renderer-off build.
# That produces a valid APK whose game exits at runtime with "this build has no renderer" even
# though build.gradle requests DREAM_RENDERER=ON. Remove only generated native state so the
# renderer choice is configured again for every release build.
rm -rf "$ANDROID_ROOT/app/.cxx"

cd "$ANDROID_ROOT"
./gradlew :app:assembleDebug --console=plain

APK="$ANDROID_ROOT/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || { echo "Gradle finished without $APK" >&2; exit 1; }
echo
echo "APK: $APK"
