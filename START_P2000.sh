#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
[[ -n "$PYTHON" ]] || { echo '[FOUT] python3 ontbreekt.' >&2; exit 1; }
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || printf '4.5.7')"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor";mkdir -p "$STATE_HOME"
if [[ -n "${P2000_RUNTIME_DIR:-}" ]]; then RUNDIR="$P2000_RUNTIME_DIR"; elif [[ -n "${XDG_RUNTIME_DIR:-}" && -w "${XDG_RUNTIME_DIR:-/nonexistent}" ]]; then RUNDIR="$XDG_RUNTIME_DIR/p2000-monitor-$(id -u)"; else RUNDIR="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime/p2000-monitor-$(id -u)"; fi
mkdir -p "$RUNDIR";chmod 700 "$RUNDIR" 2>/dev/null || true
printf '\n==== P2000 start v%s %s ====\n' "$VERSION" "$(date -Is)" >>"$STATE_HOME/startup.log"
echo '[1/3] Recovery + geserialiseerde backendstart...'
"$PYTHON" "$ROOT/tools/startup_guard.py" >>"$STATE_HOME/startup.log" 2>&1 || { echo "[FOUT] Startup/recovery mislukt. Zie $STATE_HOME/startup.log" >&2; exit 1; }
echo '[2/3] Backend semantisch gezond.'
URL="http://127.0.0.1:8765/?v=$VERSION"
eval "$("$PYTHON" tools/kiosk_display.py --shell sh 2>>"$STATE_HOME/startup.log")"
: "${P2000_WINDOW_POSITION:=0,0}";: "${P2000_WINDOW_SIZE:=1920,1080}"
echo '[3/3] Lichtkrant openen...'
"$PYTHON" tools/linux_desktop.py launch --url "$URL" --position "$P2000_WINDOW_POSITION" --size "$P2000_WINDOW_SIZE" --browser "${P2000_BROWSER:-}" --rundir "$RUNDIR" >>"$STATE_HOME/startup.log" 2>&1 || exit 2
