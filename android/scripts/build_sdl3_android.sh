#!/usr/bin/env bash
# Build SDL3 3.4.18 for Android arm64-v8a and install it under .dreamcomp/android-deps/sdl3.
# The source is the same tarball the Windows cross build uses, so no second download normally.
set -euo pipefail

ANDROID_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ANDROID_ROOT/.." && pwd)"
source "$ANDROID_ROOT/scripts/android_env.sh"

VERSION="${SDL_VERSION:-3.4.18}"
PREFIX="$REPO/.dreamcomp/android-deps/sdl3"
BUILD="$REPO/.dreamcomp/android-deps/build-sdl3"
SRC="$REPO/.dreamcomp/win-deps/src/SDL3-$VERSION"

if [ ! -f "$PREFIX/lib/libSDL3.so" ] || [ "${FORCE:-0}" = "1" ]; then
    if [ ! -f "$SRC/CMakeLists.txt" ]; then
        mkdir -p "$REPO/.dreamcomp/android-deps/src"
        echo "== downloading SDL3 $VERSION"
        curl -L --fail -o "$REPO/.dreamcomp/android-deps/src/SDL3-$VERSION.tar.gz" \
            "https://github.com/libsdl-org/SDL/releases/download/release-$VERSION/SDL3-$VERSION.tar.gz"
        tar -xf "$REPO/.dreamcomp/android-deps/src/SDL3-$VERSION.tar.gz" \
            -C "$REPO/.dreamcomp/android-deps/src"
        SRC="$REPO/.dreamcomp/android-deps/src/SDL3-$VERSION"
    fi

    echo "== SDL3 $VERSION for Android arm64-v8a"
    "$ANDROID_CMAKE" -S "$SRC" -B "$BUILD" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF \
        -DSDL_INSTALL_TESTS=OFF -DSDL_INSTALL_DOCS=OFF
    "$ANDROID_CMAKE" --build "$BUILD" --parallel "${JOBS:-8}"
    "$ANDROID_CMAKE" --install "$BUILD"
fi

[ -f "$PREFIX/lib/libSDL3.so" ] || { echo "SDL3 Android build produced no libSDL3.so" >&2; exit 1; }
echo "SDL3 ready: $PREFIX/lib/libSDL3.so"
