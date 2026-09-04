#!/usr/bin/env bash
# Shared Linux launcher for configuratiewizard/settings pages.
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
URL="${1:-http://127.0.0.1:8765/control}"
LABEL="${2:-P2000 Monitor}"
VERSION="$(tr -d '\r\n ' < VERSION 2>/dev/null || printf '4.4.14')"
LOGROOT="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs"
BASE_RUNTIME="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime}"
if [[ ! -d "$BASE_RUNTIME" || ! -w "$BASE_RUNTIME" || ! -x "$BASE_RUNTIME" ]]; then BASE_RUNTIME="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime"; fi
RUNDIR="$BASE_RUNTIME/p2000-monitor-${UID:-$(id -u)}"
mkdir -p "$LOGROOT" "$RUNDIR" 2>/dev/null || true
chmod 700 "$RUNDIR" 2>/dev/null || true
export P2000_RUNTIME_DIR="$RUNDIR"
LOG="$LOGROOT/startup.log"
hydrate_graphics_env(){
  [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && return 0
  command -v systemctl >/dev/null 2>&1 || return 0
  while IFS='=' read -r key value; do
    case "$key" in
      DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|DBUS_SESSION_BUS_ADDRESS|XDG_SESSION_TYPE|XDG_CURRENT_DESKTOP)
        [[ -n "$value" ]] && export "$key=$value" ;;
    esac
  done < <(systemctl --user show-environment 2>/dev/null || true)
}
hydrate_graphics_env
stamp(){ date '+%Y-%m-%d %H:%M:%S'; }
pause_error(){
  [[ "${P2000_NO_PAUSE:-0}" == 1 ]] && return 0
  if [[ -t 0 ]]; then
    printf '\nLogbestand: %s\n' "$LOG" >&2
    read -r -p 'Druk op Enter om dit venster te sluiten...' _ || true
  fi
}
die(){
  local code="$1"; shift; local msg="$*"
  printf '[FOUT] %s\n' "$msg" >&2
  printf '[%s] [FOUT] %s\n' "$(stamp)" "$msg" >> "$LOG"
  if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    notify-send -u critical "$LABEL" "$msg" >/dev/null 2>&1 || true
  fi
  if command -v zenity >/dev/null 2>&1 && [[ ! -t 0 ]] && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    zenity --error --title="$LABEL" --text="$msg\n\nLog: $LOG" >/dev/null 2>&1 || true
  fi
  pause_error
  exit "$code"
}
if [[ "${EUID:-$(id -u)}" -eq 0 && "${P2000_ALLOW_ROOT_RUN:-0}" != 1 ]]; then
  die 2 'Start P2000 op Linux niet met sudo/root. Chromium blokkeert root zonder onveilige --no-sandbox. Start gewoon als je normale desktopgebruiker.'
fi
# shellcheck source=/dev/null
source "$ROOT/ENSURE_PYTHON.sh" || die 2 'Python 3.10 of nieuwer ontbreekt.'
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$LOG" 2>&1; then
  "$P2000_PYTHON" tools/runtime_probe.py --describe-port >>"$LOG" 2>&1 || true
  die 3 'Poort 8765 is bezet en kon niet veilig worden vrijgemaakt.'
fi
start_backend_once(){
  nohup "$P2000_PYTHON" "$ROOT/backend/server.py" >>"$LOGROOT/backend.log" 2>&1 </dev/null &
  echo $! > "$RUNDIR/backend.pid" 2>/dev/null || true
}
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" >/dev/null 2>&1; then
  start_backend_once
fi
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 12 >/dev/null 2>&1; then
  tail -n 60 "$LOGROOT/backend.log" 2>/dev/null | tee -a "$LOG" >&2 || true
  "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$LOG" 2>&1 || die 3 'Mislukte backend kon niet veilig worden gestopt.'
  start_backend_once
  if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 15 >/dev/null 2>&1; then
    tail -n 100 "$LOGROOT/backend.log" 2>/dev/null | tee -a "$LOG" >&2 || true
    die 3 "Backend start niet na de herstelpoging. Zie $LOGROOT/backend.log"
  fi
fi
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  printf '%s\n' "Open handmatig in een browser: $URL"
  die 4 'Geen grafische Linux-sessie gevonden (DISPLAY/WAYLAND_DISPLAY ontbreken).'
fi
DETAIL="$("$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" open --url "$URL" --rundir "$RUNDIR" 2>>"$LOGROOT/browser.log")"
RC=$?
if [[ $RC -ne 0 ]]; then
  printf '%s\n' "Open handmatig in een browser: $URL"
  tail -n 50 "$LOGROOT/browser.log" 2>/dev/null >&2 || true
  die 5 "$LABEL kon geen browser openen. Voer ./LINUX_CHECK.sh uit."
fi
printf '[OK] %s geopend via %s\n' "$LABEL" "${DETAIL:-browser}"
exit 0
