#!/usr/bin/env bash
# Install the debug APK and push a disc image if CHD=... is set.
#
#   android/scripts/install_android.sh
#   CHD="iso/Sonic Shuffle (USA).chd" android/scripts/install_android.sh
#
# The app's data and CHD live in its external files directory, which adb can write without any
# storage permission:
#   /sdcard/Android/data/dev.ch1ppy.sonicshuffle/files/iso/
set -euo pipefail

ANDROID_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ANDROID_ROOT/.." && pwd)"
source "$ANDROID_ROOT/scripts/android_env.sh"

PKG=dev.ch1ppy.sonicshuffle
APK="$ANDROID_ROOT/app/build/outputs/apk/debug/app-debug.apk"
[ -x "$ANDROID_ADB" ] || { echo "adb not found at $ANDROID_ADB" >&2; exit 1; }
[ -f "$APK" ] || { echo "APK not built: $APK" >&2; exit 1; }

"$ANDROID_ADB" get-state >/dev/null
"$ANDROID_ADB" install -r "$APK"

# First launch creates the external files directory. Wait for it before pushing into it.
"$ANDROID_ADB" shell am start -n "$PKG/.MainActivity" >/dev/null
for _ in $(seq 1 20); do
    if "$ANDROID_ADB" shell "[ -d /sdcard/Android/data/$PKG/files/iso ]" 2>/dev/null; then break; fi
    sleep 0.5
done

if [ -n "${CHD:-}" ]; then
    [ -f "$CHD" ] || CHD="$REPO/$CHD"
    [ -f "$CHD" ] || { echo "no disc image at $CHD" >&2; exit 1; }
    echo "== pushing $(basename "$CHD")"
    "$ANDROID_ADB" push "$CHD" "/sdcard/Android/data/$PKG/files/iso/"
fi

"$ANDROID_ADB" shell am force-stop "$PKG" 2>/dev/null || true
"$ANDROID_ADB" shell am start -n "$PKG/.MainActivity" >/dev/null
echo "== launched $PKG"
