#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m pip install -r "$ROOT/launcher/requirements.txt"
python3 "$ROOT/scripts/make-icons.py"
cmake -S "$ROOT" -B "$ROOT/build-linux" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DDREAM_RENDERER=ON -DDREAMCOMP_FRONTEND=OFF -DDREAM_BUILD_TESTS=OFF -DDREAM_WERROR=OFF
cmake --build "$ROOT/build-linux" --parallel
"$ROOT/scripts/build-cdirip.sh"
python3 "$ROOT/launcher/package.py" --game "$ROOT/build-linux/game/sonic-shuffle-recomp" \
  --cdirip "${CDIRIP:-$ROOT/.deps/cdirip/cdirip}"
