#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT" || exit 1
source "$ROOT/ENSURE_PYTHON.sh" || exit 2
"$P2000_PYTHON" tools/rollback_latest.py || exit 3
exec "$ROOT/START_P2000.sh"
