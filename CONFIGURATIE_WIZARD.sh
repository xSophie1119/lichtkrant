#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo '[FOUT] python3 ontbreekt.' >&2
  exit 1
fi
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || printf '4.5.6')"
if ! "$PYTHON" tools/runtime_probe.py --version "$VERSION" >/dev/null 2>&1; then
  P2000_SUPERVISED=1 bash "$ROOT/START_P2000.sh" >/dev/null 2>&1 || true
fi
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open 'http://127.0.0.1:8765/setup.html' >/dev/null 2>&1 &
else
  echo 'Open http://127.0.0.1:8765/setup.html in je browser.'
fi
