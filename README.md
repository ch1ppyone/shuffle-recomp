# Sonic Shuffle Recompiled

![Sonic Shuffle Recompiled](docs/images/logo.png)

Native ports of **Sonic Shuffle** for macOS, Windows, Linux and Android, built with
[dreamcomp](https://github.com/danielgomesvieira2000/dreamcomp).

This repository contains the buildable port source and the recompiler framework. It does not
contain the original game image or extracted game files. You must own a compatible copy of the
game and provide its disc image locally.

## Supported platforms

- macOS arm64 and x86_64
- Windows x64
- Linux x86_64
- Android arm64-v8a

## macOS quick start

Requirements: Xcode Command Line Tools, CMake, Ninja, Python 3, SDL3, Vulkan headers and a
MoltenVK-capable Vulkan loader.

```sh
python3 dreamcomp/tools/dc.py setup . --disc "/path/to/Sonic Shuffle.chd"
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DDREAM_RENDERER=ON -DDREAMCOMP_FRONTEND=OFF
cmake --build build --parallel
python3 -m pip install -r launcher/requirements.txt
python3 launcher/launcher.py
```

The same PyQt6 launcher is used on macOS, Windows and Linux. To create a release bundle,
run the platform-specific `scripts/package-launcher-*` script. It produces a macOS `.app`,
a Windows launcher executable, or a Linux executable bundle with the native game beside it.
Choose the original disc image in the launcher and press **Launch Game**. The in-game
framework frontend is disabled, so **Esc** does not open a hidden settings overlay.

The launcher icon is the project card mark: a white **S** inside a blue playing-card square.
`launcher/icon.svg` is the source artwork; `scripts/make-icons.py` generates the PNG, ICO and
ICNS variants used by desktop releases.

The launcher file picker accepts CHD, GDI, CDI and CUE images. CHD, GDI and CUE are read
directly by the native runtime. CDI images are converted at launch with the bundled `cdirip`
helper into a temporary CUE/GDI-compatible track set; the temporary files are deleted when
the game exits. CDI support requires packaging a platform-native `cdirip` executable:

```sh
python3 launcher/package.py --game build-macos/game/sonic-shuffle-recomp \
  --cdirip /path/to/cdirip --output release
```

`cdirip` is GPL-2.0 software by DeXT/Lawrence Williams. Its source and license must accompany
any release containing its executable.

## Other platforms

Platform-specific build helpers live in `scripts/` and `android/scripts/`. Android builds require
the Android SDK, NDK and JDK 17. The Android build prepares only local, generated assets from the
disc supplied by the owner; no game image is bundled in the repository.

## Legal and provenance

Sonic Shuffle and its original assets are property of their respective rights holders. This
project distributes only original port code and framework code. Do not publish disc images,
extracted binaries or generated assets.

## License

GPL-2.0. See [LICENSE](LICENSE) and the notices in `dreamcomp/`.
