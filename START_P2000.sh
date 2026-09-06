#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
for required in backend/server.py frontend/index.html tools/runtime_probe.py tools/linux_desktop.py; do
  if [[ ! -f "$required" ]]; then
    echo "[FOUT] P2000 Monitor is niet volledig uitgepakt: $required ontbreekt." >&2
    exit 1
  fi
done
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || printf '4.5.6')"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo '[FOUT] python3 is niet gevonden. Installeer Python 3.10 of nieuwer.' >&2
  exit 1
fi
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor"
mkdir -p "$STATE_HOME"
STARTUP_LOG="$STATE_HOME/startup.log"
printf '\n==== P2000 start v%s %s ====\n' "$VERSION" "$(date -Is)" >>"$STARTUP_LOG"
URL="http://127.0.0.1:8765/?v=$VERSION"

if [[ -n "${P2000_RUNTIME_DIR:-}" ]]; then
  RUNDIR="$P2000_RUNTIME_DIR"
elif [[ -n "${XDG_RUNTIME_DIR:-}" && -w "${XDG_RUNTIME_DIR:-/nonexistent}" ]]; then
  RUNDIR="$XDG_RUNTIME_DIR/p2000-monitor-$(id -u)"
else
  RUNDIR="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime/p2000-monitor-$(id -u)"
fi
mkdir -p "$RUNDIR"
chmod 700 "$RUNDIR" 2>/dev/null || true

echo '[1/4] Python-runtime gecontroleerd.'
echo '[2/4] Oude instanties opruimen en backend controleren...'
if ! "$PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$STARTUP_LOG" 2>&1; then
  "$PYTHON" tools/runtime_probe.py --describe-port >>"$STARTUP_LOG" 2>&1 || true
  echo "[FOUT] Backendherstel mislukt. Zie $STARTUP_LOG" >&2
  exit 1
fi
if ! "$PYTHON" tools/runtime_probe.py --version "$VERSION" >/dev/null 2>&1; then
  nohup bash "$ROOT/RUN_BACKEND.sh" >>"$STARTUP_LOG" 2>&1 &
  if ! "$PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 18 >/dev/null 2>&1; then
    echo '[HERSTEL] Eerste backendstart niet gezond; gecontroleerde herstart.' >>"$STARTUP_LOG"
    "$PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$STARTUP_LOG" 2>&1 || exit 1
    nohup bash "$ROOT/RUN_BACKEND.sh" >>"$STARTUP_LOG" 2>&1 &
    "$PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 20 >/dev/null 2>&1 || {
      echo "[FOUT] Backend start niet. Zie $STATE_HOME/backend.log" >&2
      exit 1
    }
  fi
fi
echo '[3/4] Backend is bereikbaar op http://127.0.0.1:8765/'

if [[ "${P2000_SUPERVISED:-0}" != "1" ]]; then
  if ! "$PYTHON" tools/supervisor.py --status >/dev/null 2>&1; then
    "$PYTHON" tools/supervisor.py --stop >/dev/null 2>&1 || true
    nohup "$PYTHON" tools/supervisor.py >>"$STATE_HOME/supervisor-launch.log" 2>&1 &
  fi
fi

echo '[4/4] Lichtkrant openen...'
eval "$("$PYTHON" tools/kiosk_display.py --shell sh 2>>"$STARTUP_LOG")"
: "${P2000_WINDOW_POSITION:=0,0}"
: "${P2000_WINDOW_SIZE:=1920,1080}"
"$PYTHON" tools/linux_desktop.py launch --url "$URL" --position "$P2000_WINDOW_POSITION" --size "$P2000_WINDOW_SIZE" --browser "${P2000_BROWSER:-}" --rundir "$RUNDIR" >>"$STARTUP_LOG" 2>&1 || {
  echo "[WAARSCHUWING] Dedicated kiosk kon niet worden bevestigd. Zie $STATE_HOME/browser.log" >&2
}
