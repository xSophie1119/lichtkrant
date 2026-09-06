#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)";cd "$ROOT"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}";[[ -n "$PYTHON" ]] || exit 2
if [[ -n "${P2000_RUNTIME_DIR:-}" ]]; then RUNDIR="$P2000_RUNTIME_DIR"; elif [[ -n "${XDG_RUNTIME_DIR:-}" && -w "${XDG_RUNTIME_DIR:-/nonexistent}" ]]; then RUNDIR="$XDG_RUNTIME_DIR/p2000-monitor-$(id -u)"; else RUNDIR="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime/p2000-monitor-$(id -u)"; fi
rc=0
"$PYTHON" tools/runtime_probe.py --stop-supervisors || rc=1
"$PYTHON" tools/runtime_probe.py --stop || rc=1
sleep 1
"$PYTHON" tools/runtime_probe.py --stop || rc=1
"$PYTHON" tools/linux_desktop.py stop-kiosk --rundir "$RUNDIR" || rc=1
"$PYTHON" tools/stop_verify.py || rc=1
[[ $rc -eq 0 ]] && echo 'Klaar.' || echo '[FOUT] Niet alle P2000-processen zijn gestopt.' >&2
exit $rc
