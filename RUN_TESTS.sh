#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo '[FOUT] python3 ontbreekt.' >&2
  exit 1
fi
exec "$PYTHON" -u "$ROOT/tools/run_tests.py"
