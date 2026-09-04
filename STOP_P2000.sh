#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_RUNTIME="${XDG_RUNTIME_DIR:-/tmp}"
if [[ ! -d "$BASE_RUNTIME" || ! -w "$BASE_RUNTIME" ]]; then BASE_RUNTIME=/tmp; fi
RUNDIR="$BASE_RUNTIME/p2000-monitor-${UID:-$(id -u)}"
source "$ROOT/ENSURE_PYTHON.sh" >/dev/null 2>&1 || true
if [[ -f "$ROOT/data/supervisor.pid" ]]; then
  spid="$(cat "$ROOT/data/supervisor.pid" 2>/dev/null || true)"
  [[ "$spid" =~ ^[0-9]+$ ]] && kill "$spid" 2>/dev/null || true
  rm -f "$ROOT/data/supervisor.pid"
fi
if [[ -n "${P2000_PYTHON:-}" && -f "$ROOT/tools/linux_desktop.py" ]]; then
  "$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" stop-kiosk --rundir "$RUNDIR" >/dev/null 2>&1 || true
fi
for f in "$RUNDIR/browser.pid" "$RUNDIR/control-browser.pid" "$RUNDIR/backend.pid"; do
  [[ -f "$f" ]] || continue
  pid="$(cat "$f" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" 2>/dev/null || true
  rm -f "$f"
done
if [[ -n "${P2000_PYTHON:-}" ]]; then "$P2000_PYTHON" "$ROOT/tools/runtime_probe.py" --stop >/dev/null 2>&1 || true; fi
echo 'P2000 Monitor gestopt.'
