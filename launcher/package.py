#!/usr/bin/env python3
"""Build a redistributable launcher around an already-built native port.

The native game is deliberately copied beside the launcher; the original disc
image is never copied or embedded. Run this on the target OS so PyInstaller
bundles that platform's Qt and Python runtime.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, required=True, help="built native game executable")
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    parser.add_argument("--cdirip", type=Path, help="optional cdirip executable for CDI images")
    args = parser.parse_args()
    game = args.game.resolve()
    output = args.output.resolve()
    if not game.is_file():
        parser.error(f"game executable does not exist: {game}")

    output.mkdir(parents=True, exist_ok=True)
    work = output / ".pyinstaller"
    icon: Path | None = None
    if sys.platform == "darwin" and (ROOT / "launcher/icons/SonicShuffleLauncher.icns").is_file():
        icon = ROOT / "launcher/icons/SonicShuffleLauncher.icns"
    elif sys.platform == "win32" and (ROOT / "launcher/icons/SonicShuffleLauncher.ico").is_file():
        icon = ROOT / "launcher/icons/SonicShuffleLauncher.ico"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--hidden-import",
        "pkgutil",
        "--collect-all",
        "PyQt6",
        "--name",
        "SonicShuffleLauncher",
        "--distpath",
        str(output),
        "--workpath",
        str(work),
        "--specpath",
        str(work),
        str(ROOT / "launcher" / "launcher.py"),
    ]
    if icon is not None:
        command[command.index(str(ROOT / "launcher" / "launcher.py")):command.index(str(ROOT / "launcher" / "launcher.py"))] = ["--icon", str(icon)]
    subprocess.run(command, check=True, cwd=ROOT)

    bundle = output / "SonicShuffleLauncher.app" if sys.platform == "darwin" else output / "SonicShuffleLauncher"
    if sys.platform == "darwin":
        game_dir = bundle / "Contents" / "Resources" / "game"
    else:
        game_dir = output / "game"
        bundle = output / ("SonicShuffleLauncher.exe" if sys.platform == "win32" else "SonicShuffleLauncher")
    icon_source = ROOT / "launcher" / "icon.svg"
    if icon_source.is_file():
        shutil.copy2(icon_source, game_dir.parent / "icon.svg")
    icon_files = ROOT / "launcher" / "icons"
    if icon_files.is_dir():
        shutil.copytree(icon_files, game_dir.parent / "icons", dirs_exist_ok=True)
    game_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(game, game_dir / game.name)
    config = ROOT / "game" / "sonicshuffle.toml"
    shutil.copy2(config, game_dir / config.name)
    if args.cdirip:
        cdirip = args.cdirip.resolve()
        if not cdirip.is_file():
            parser.error(f"cdirip executable does not exist: {cdirip}")
        tools_dir = (bundle / "Contents" / "Resources" / "tools") if sys.platform == "darwin" else output / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cdirip, tools_dir / cdirip.name)
        if sys.platform != "win32":
            (tools_dir / cdirip.name).chmod((tools_dir / cdirip.name).stat().st_mode | 0o111)
    if sys.platform != "win32":
        (game_dir / game.name).chmod((game_dir / game.name).stat().st_mode | 0o111)
    shutil.rmtree(work, ignore_errors=True)
    print(f"Release bundle: {bundle}")
    print("No disc image or extracted game data was copied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
