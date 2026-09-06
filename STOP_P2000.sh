#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo '[FOUT] python3 ontbreekt; uit veiligheid worden geen willekeurige processen gestopt.' >&2
  exit 2
fi
if [[ -n "${P2000_RUNTIME_DIR:-}" ]]; then
  RUNDIR="$P2000_RUNTIME_DIR"
elif [[ -n "${XDG_RUNTIME_DIR:-}" && -w "${XDG_RUNTIME_DIR:-/nonexistent}" ]]; then
  RUNDIR="$XDG_RUNTIME_DIR/p2000-monitor-$(id -u)"
else
  RUNDIR="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime/p2000-monitor-$(id -u)"
fi
echo '[1/4] Supervisor(s) stoppen...'
"$PYTHON" tools/runtime_probe.py --stop-supervisors >/dev/null 2>&1 || true
echo '[2/4] Backend(s) stoppen...'
"$PYTHON" tools/runtime_probe.py --stop >/dev/null 2>&1 || true
echo '[3/4] Tweede backendcontrole...'
sleep 1
"$PYTHON" tools/runtime_probe.py --stop >/dev/null 2>&1 || true
echo '[4/4] Dedicated kiosk sluiten...'
"$PYTHON" tools/linux_desktop.py stop-kiosk --rundir "$RUNDIR" >/dev/null 2>&1 || true
echo 'Klaar.'
