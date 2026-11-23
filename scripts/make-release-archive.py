#!/usr/bin/env python3
"""Create a release archive from a packaged launcher directory.

The archive contains only the launcher, native executable and port config. Disc
images and extracted game data are rejected before archiving.
"""
from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path


FORBIDDEN = {".chd", ".gdi", ".cdi", ".cue", ".iso", ".bin", ".pvr", ".mdl"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    output = args.output.resolve()
    if not directory.is_dir():
        parser.error(f"not a directory: {directory}")
    forbidden = [p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in FORBIDDEN]
    if forbidden:
        raise SystemExit("refusing to archive disc/game data: " + ", ".join(map(str, forbidden)))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".zip":
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in directory.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(directory.parent))
    else:
        with tarfile.open(output, "w:gz") as archive:
            archive.add(directory, arcname=directory.name)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
