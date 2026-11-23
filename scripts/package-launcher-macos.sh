#!/usr/bin/env bash
# Build the native macOS game and a self-contained launcher .app + DMG.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/build-macos.sh"
"$ROOT/scripts/build-cdirip.sh"
"$ROOT/scripts/package-macos-app.sh"
