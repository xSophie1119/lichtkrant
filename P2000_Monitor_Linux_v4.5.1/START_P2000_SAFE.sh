#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
PY="$(command -v python3 || true)"; [[ -n "$PY" ]] || { echo 'Python 3 ontbreekt'; exit 1; }
export P2000_SAFE_MODE=1
"$PY" backend/server.py --safe-mode >/tmp/p2000-safe.log 2>&1 &
for _ in $(seq 1 40); do curl -fsS http://127.0.0.1:8765/api/runtime >/dev/null 2>&1 && break; sleep .25; done
if command -v xdg-open >/dev/null; then xdg-open http://127.0.0.1:8765/control.html >/dev/null 2>&1 || true; fi
echo 'P2000 Monitor draait in veilige modus: http://127.0.0.1:8765/control.html'
