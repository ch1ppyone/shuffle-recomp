#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m pip install -r "$ROOT/launcher/requirements.txt"
python3 "$ROOT/scripts/make-icons.py"
"$ROOT/scripts/build-macos.sh"
"$ROOT/scripts/build-cdirip.sh"
python3 "$ROOT/launcher/package.py" --game "$ROOT/build-macos/game/sonic-shuffle-recomp" \
  --cdirip "${CDIRIP:-$ROOT/.deps/cdirip/cdirip}"
