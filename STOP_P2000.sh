#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_RUNTIME="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime}"
if [[ ! -d "$BASE_RUNTIME" || ! -w "$BASE_RUNTIME" || ! -x "$BASE_RUNTIME" ]]; then BASE_RUNTIME="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime"; fi
RUNDIR="$BASE_RUNTIME/p2000-monitor-${UID:-$(id -u)}"
export P2000_RUNTIME_DIR="$RUNDIR"
source "$ROOT/ENSURE_PYTHON.sh" >/dev/null 2>&1 || true
if [[ -n "${P2000_PYTHON:-}" ]]; then
  "$P2000_PYTHON" "$ROOT/tools/supervisor.py" --stop >/dev/null 2>&1 || true
fi
if [[ -n "${P2000_PYTHON:-}" && -f "$ROOT/tools/linux_desktop.py" ]]; then
  "$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" stop-kiosk --rundir "$RUNDIR" >/dev/null 2>&1 || true
fi
if [[ -n "${P2000_PYTHON:-}" ]]; then "$P2000_PYTHON" "$ROOT/tools/runtime_probe.py" --stop >/dev/null 2>&1 || true; fi
rm -f "$RUNDIR/browser.pid" "$RUNDIR/backend.pid" 2>/dev/null || true
echo 'P2000 Monitor gestopt.'
