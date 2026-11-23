#!/usr/bin/env python3
"""Generate platform icon files from the hand-authored launcher SVG."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "launcher" / "icon.svg"
OUT = ROOT / "launcher" / "icons"
SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pngs = []
        for size in SIZES:
            png = tmp_path / f"icon-{size}.png"
            subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), str(SVG), "-o", str(png)], check=True)
            shutil.copy2(png, OUT / png.name)
            pngs.append(png)
        Image.open(tmp_path / "icon-1024.png").save(OUT / "SonicShuffleLauncher.ico", sizes=[(s, s) for s in SIZES])
        # macOS iconutil requires an iconset directory with exact filenames.
        iconset = tmp_path / "SonicShuffleLauncher.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            source = Image.open(tmp_path / f"icon-{size}.png")
            source.save(iconset / f"icon_{size}x{size}.png")
            source.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "SonicShuffleLauncher.icns")], check=True)
    print(f"Generated icons in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
