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

The same PyQt6 launcher is used on macOS, Windows and Linux. On macOS you can also open
`launcher/SonicShuffle.command`; Linux and Windows have equivalent scripts in `launcher/`.
Choose the original disc image in the launcher and press **Launch Game**. The in-game
framework frontend is disabled, so **Esc** does not open a hidden settings overlay.

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
