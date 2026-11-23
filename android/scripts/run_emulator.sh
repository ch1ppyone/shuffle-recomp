#!/usr/bin/env bash
# Boot the Android emulator with the host GPU, install the debug APK and start the game.
#
#   android/scripts/run_emulator.sh
#   CHD="iso/Sonic Shuffle (USA).chd" android/scripts/run_emulator.sh
#
# -gpu host is deliberate: with -gpu auto the emulator may hand the guest llvmpipe/SwiftShader
# (software Vulkan) and the game crawls, while host mode exposes Metal as the Vulkan device on
# Apple Silicon. Keep the emulator window open for the session; Ctrl-C stops it.
set -euo pipefail

ANDROID_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ANDROID_ROOT/.." && pwd)"
source "$ANDROID_ROOT/scripts/android_env.sh"

AVD="${AVD:-Pixel_9_Pro}"
PKG=dev.ch1ppy.sonicshuffle
APK="$ANDROID_ROOT/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || { echo "APK not built: $APK (run scripts/build_android.sh)" >&2; exit 1; }

"$ANDROID_SDK/emulator/emulator" -avd "$AVD" -no-snapshot -no-boot-anim -no-audio \
    -gpu host >"$REPO/.dreamcomp/emulator.log" 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

echo "== waiting for $AVD"
"$ANDROID_ADB" wait-for-device
for _ in $(seq 1 120); do
    [ "$("$ANDROID_ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
    sleep 2
done

"$ANDROID_ADB" install -r "$APK"
"$ANDROID_ADB" shell am start -n "$PKG/.MainActivity" >/dev/null
for _ in $(seq 1 20); do
    "$ANDROID_ADB" shell "[ -d /sdcard/Android/data/$PKG/files/iso ]" 2>/dev/null && break
    sleep 0.5
done

if [ -n "${CHD:-}" ]; then
    [ -f "$CHD" ] || CHD="$REPO/$CHD"
    [ -f "$CHD" ] || { echo "no disc image at $CHD" >&2; exit 1; }
    echo "== pushing $(basename "$CHD")"
    "$ANDROID_ADB" push "$CHD" "/sdcard/Android/data/$PKG/files/iso/"
    "$ANDROID_ADB" shell am force-stop "$PKG"
    "$ANDROID_ADB" shell am start -n "$PKG/.MainActivity" >/dev/null
fi

echo "== $PKG running; log: /sdcard/Android/data/$PKG/files/sonicshuffle.log"
wait "$EMU_PID"
