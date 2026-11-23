#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.deps/cdirip}"
mkdir -p "$OUT"
cc -O2 -std=c99 -Wall -Wextra \
  "$ROOT/third_party/cdirip/cdirip.c" \
  "$ROOT/third_party/cdirip/buffer.c" \
  "$ROOT/third_party/cdirip/cdi.c" \
  "$ROOT/third_party/cdirip/common.c" \
  "$ROOT/third_party/cdirip/audio.c" \
  -o "$OUT/cdirip"
echo "Built: $OUT/cdirip"
