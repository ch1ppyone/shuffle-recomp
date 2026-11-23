#!/usr/bin/env bash
# Build a self-contained macOS .app and a DMG for Sonic Shuffle Recompiled.
#
# The native game is linked against Homebrew's SDL3, Vulkan loader and MoltenVK.
# This script copies those libraries into the app, rewrites the game's install
# names to @executable_path, and bundles a MoltenVK ICD JSON so the result does
# not depend on /opt/homebrew on the player's Mac.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Sonic Shuffle Recompiled"
BUNDLE_ID="com.chippyone.sonicshuffle"
VERSION="1.1"
OUT="${1:-$ROOT/dist-macos}"
GAME="$ROOT/build-macos/game/sonic-shuffle-recomp"
CDIRIP="${CDIRIP:-$ROOT/.deps/cdirip/cdirip}"
ICON="$ROOT/launcher/icons/SonicShuffleLauncher.icns"
VENV="${VENV:-$ROOT/.venv-macos}"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"

for path in "$GAME" "$CDIRIP" "$ICON" "$PYTHON"; do
    if [[ ! -e "$path" ]]; then
        echo "missing required file: $path" >&2
        exit 1
    fi
done

if [[ ! -x "$VENV/bin/python" ]]; then
    uv venv --python "$PYTHON" "$VENV"
fi
uv pip install --python "$VENV/bin/python" --upgrade \
    "PyQt6>=6.7,<6.8" "pyinstaller>=6.10,<7"

rm -rf "$OUT"
mkdir -p "$OUT"

"$VENV/bin/python" -m PyInstaller \
    --noconfirm --clean --windowed --onedir \
    --name "$APP_NAME" \
    --icon "$ICON" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --hidden-import pkgutil \
    --collect-all PyQt6 \
    --distpath "$OUT" \
    --workpath "$OUT/.pyinstaller" \
    --specpath "$OUT/.pyinstaller" \
    "$ROOT/launcher/launcher.py"

APP="$OUT/$APP_NAME.app"
RES="$APP/Contents/Resources"
GAME_DIR="$RES/game"
TOOLS="$RES/tools"
if [[ ! -d "$APP" ]]; then
    echo "PyInstaller did not create $APP" >&2
    exit 1
fi
mkdir -p "$GAME_DIR" "$TOOLS"

cp -f "$GAME" "$GAME_DIR/sonic-shuffle-recomp"
cp -f "$ROOT/game/sonicshuffle.toml" "$GAME_DIR/sonicshuffle.toml"
cp -f "$CDIRIP" "$TOOLS/cdirip"
chmod +x "$GAME_DIR/sonic-shuffle-recomp" "$TOOLS/cdirip"

# Runtime libraries, placed beside the game. @executable_path is Contents/Resources/game.
cp -Lf /opt/homebrew/opt/sdl3/lib/libSDL3.0.dylib "$GAME_DIR/libSDL3.0.dylib"
cp -Lf /opt/homebrew/opt/vulkan-loader/lib/libvulkan.1.dylib "$GAME_DIR/libvulkan.1.dylib"
cp -Lf /opt/homebrew/opt/molten-vk/lib/libMoltenVK.dylib "$GAME_DIR/libMoltenVK.dylib"
chmod u+w "$GAME_DIR"/*.dylib "$GAME_DIR/sonic-shuffle-recomp"

install_name_tool \
    -change /opt/homebrew/opt/sdl3/lib/libSDL3.0.dylib \
    @executable_path/libSDL3.0.dylib \
    "$GAME_DIR/sonic-shuffle-recomp"
install_name_tool \
    -change /opt/homebrew/opt/vulkan-loader/lib/libvulkan.1.dylib \
    @executable_path/libvulkan.1.dylib \
    "$GAME_DIR/sonic-shuffle-recomp"
install_name_tool -id @executable_path/libSDL3.0.dylib "$GAME_DIR/libSDL3.0.dylib"
install_name_tool -id @executable_path/libvulkan.1.dylib "$GAME_DIR/libvulkan.1.dylib"
install_name_tool -id @executable_path/libMoltenVK.dylib "$GAME_DIR/libMoltenVK.dylib"

cat > "$GAME_DIR/MoltenVK_icd.json" <<'JSON'
{
    "file_format_version": "1.0.0",
    "ICD": {
        "library_path": "libMoltenVK.dylib",
        "api_version": "1.4.0",
        "is_portability_driver": true
    }
}
JSON

# Finder metadata and version strings.
"$VENV/bin/python" - "$APP" "$APP_NAME" "$BUNDLE_ID" "$VERSION" <<'PY'
import plistlib
import sys
from pathlib import Path

app = Path(sys.argv[1])
name = sys.argv[2]
bundle_id = sys.argv[3]
version = sys.argv[4]
plist = app / "Contents/Info.plist"
with plist.open("rb") as stream:
    info = plistlib.load(stream)
info.update(
    {
        "CFBundleDisplayName": name,
        "CFBundleName": name,
        "CFBundleIdentifier": bundle_id,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.games",
    }
)
with plist.open("wb") as stream:
    plistlib.dump(info, stream)
PY

mkdir -p "$RES/licenses"
for file in LICENSE THIRD_PARTY_NOTICES.md; do
    if [[ -f "$ROOT/$file" ]]; then
        cp -f "$ROOT/$file" "$RES/licenses/$file"
    fi
done
if [[ -f "$ROOT/third_party/cdirip/COPYING" ]]; then
    cp -f "$ROOT/third_party/cdirip/COPYING" "$RES/licenses/cdirip-COPYING"
fi

chmod -R u+w "$APP"
xattr -cr "$APP" 2>/dev/null || true
# Sign nested code explicitly. Without this, dyld on current macOS kills the
# game when it is launched from inside the sealed app bundle.
for file in \
    "$GAME_DIR/sonic-shuffle-recomp" \
    "$GAME_DIR/libSDL3.0.dylib" \
    "$GAME_DIR/libvulkan.1.dylib" \
    "$GAME_DIR/libMoltenVK.dylib" \
    "$TOOLS/cdirip"; do
    codesign --force --sign - "$file"
done
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# A simple drag-to-Applications DMG.
STAGE="$OUT/dmg"
DMG="$OUT/$APP_NAME.dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/README.txt" <<'EOF'
Sonic Shuffle Recompiled 1.1 — macOS arm64

1. Drag "Sonic Shuffle Recompiled.app" to Applications.
2. Start the app.
3. Select your legally obtained CHD, GDI, CUE, or CDI image.
4. Press Prepare image, then Launch Game.

The app does not include a disc image. It writes logs to:
  ~/Library/Application Support/SonicShuffle/logs

This build is ad-hoc signed but not notarized. On first launch, macOS may ask
you to right-click the app and choose Open. A public release should be signed
with an Apple Developer ID and notarized.
EOF
rm -f "$DMG"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
hdiutil verify "$DMG" >/dev/null
echo "App: $APP"
echo "DMG: $DMG"
