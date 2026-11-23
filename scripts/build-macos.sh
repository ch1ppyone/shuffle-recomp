#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cmake -S "$ROOT" -B "$ROOT/build-macos" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DDREAM_RENDERER=ON \
  -DDREAMCOMP_FRONTEND=OFF -DDREAM_BUILD_TESTS=OFF -DDREAM_WERROR=OFF
cmake --build "$ROOT/build-macos" --parallel
echo "Built: $ROOT/build-macos/game/sonic-shuffle-recomp"
