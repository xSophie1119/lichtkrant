#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
source "$ROOT/ENSURE_PYTHON.sh" || exit 1
exec "$P2000_PYTHON" "$ROOT/tools/run_tests.py"
