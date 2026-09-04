#!/usr/bin/env bash
# P2000 Monitor Linux launcher - v4.4.14
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
VERSION="$(tr -d '\r\n ' < VERSION 2>/dev/null || printf '4.4.14')"
LOGROOT="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs"
BASE_RUNTIME="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime}"
if [[ ! -d "$BASE_RUNTIME" || ! -w "$BASE_RUNTIME" || ! -x "$BASE_RUNTIME" ]]; then
  BASE_RUNTIME="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime"
fi
RUNDIR="$BASE_RUNTIME/p2000-monitor-${UID:-$(id -u)}"
mkdir -p "$LOGROOT" "$RUNDIR" 2>/dev/null || true
chmod 700 "$RUNDIR" 2>/dev/null || true
export P2000_RUNTIME_DIR="$RUNDIR"
START_LOG="$LOGROOT/startup.log"
BROWSER_LOG="$LOGROOT/browser.log"
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
log(){ printf '[%s] %s\n' "$(stamp)" "$*" | tee -a "$START_LOG"; }
notify_error(){
  local msg="$1"
  if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    notify-send -u critical 'P2000 Monitor kon niet starten' "$msg" >/dev/null 2>&1 || true
  fi
  if command -v zenity >/dev/null 2>&1 && [[ ! -t 0 ]] && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    zenity --error --title='P2000 Monitor' --text="$msg\n\nLog: $START_LOG" >/dev/null 2>&1 || true
  fi
}
pause_on_error(){
  [[ "${P2000_NO_PAUSE:-0}" == "1" ]] && return 0
  if [[ -t 0 ]]; then
    printf '\nLogbestand: %s\n' "$START_LOG" >&2
    read -r -p 'Druk op Enter om dit venster te sluiten...' _ || true
  fi
}
die(){
  local code="$1"; shift; local msg="$*"
  printf '[FOUT] %s\n' "$msg" >&2
  printf '[%s] [FOUT] %s\n' "$(stamp)" "$msg" >> "$START_LOG"
  notify_error "$msg"
  pause_on_error
  exit "$code"
}
if [[ "${EUID:-$(id -u)}" -eq 0 && "${P2000_ALLOW_ROOT_RUN:-0}" != 1 ]]; then
  die 2 'Start P2000 op Linux niet met sudo/root. Chromium blokkeert root zonder onveilige --no-sandbox. Start gewoon als je normale desktopgebruiker.'
fi
if [[ ! -f backend/server.py || ! -f frontend/index.html || ! -f tools/linux_desktop.py ]]; then
  die 2 'De P2000 Monitor is niet volledig uitgepakt.'
fi
# shellcheck source=/dev/null
source "$ROOT/ENSURE_PYTHON.sh" || die 3 'Python 3.10 of nieuwer ontbreekt.'
log "[1/4] Python: $P2000_PYTHON"
mkdir -p "$ROOT/data" "$ROOT/config" 2>/dev/null || true
WRITE_PROBE="$ROOT/data/.write-test-$$"
if ! ( umask 077; : > "$WRITE_PROBE" ) 2>/dev/null; then
  die 4 "Backend kan niet schrijven naar $ROOT/data. Waarschijnlijk zijn bestanden ooit met sudo/root aangemaakt. Herstel met: sudo chown -R $(id -un):$(id -gn) '$ROOT'"
fi
rm -f "$WRITE_PROBE" 2>/dev/null || true
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$START_LOG" 2>&1; then
  "$P2000_PYTHON" tools/runtime_probe.py --describe-port 2>&1 | tee -a "$START_LOG" >&2 || true
  die 4 'Poort 8765 is bezet en kon niet veilig worden vrijgemaakt. Zie startup.log voor PID/proces.'
fi
start_backend_once(){
  : > "$LOGROOT/backend.log" 2>/dev/null || true
  nohup "$P2000_PYTHON" "$ROOT/backend/server.py" >>"$LOGROOT/backend.log" 2>&1 </dev/null &
  local pid=$!
  echo "$pid" > "$RUNDIR/backend.pid" 2>/dev/null || true
  sleep .25
  kill -0 "$pid" 2>/dev/null
}
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" >/dev/null 2>&1; then
  log '[2/4] Backend starten...'
  start_backend_once || log '[WAARSCHUWING] Backendproces stopte direct; herstelpoging volgt.'
else
  log '[2/4] Backend draait al.'
fi
log '[3/4] Wachten op backend...'
if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 10 >/dev/null 2>&1; then
  log '[HERSTEL] Eerste backendstart niet gezond; stale proces/poort opnieuw controleren en één keer opnieuw starten.'
  tail -n 80 "$LOGROOT/backend.log" 2>/dev/null | tee -a "$START_LOG" >&2 || true
  "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --kill-stale >>"$START_LOG" 2>&1 || true
  sleep .35
  start_backend_once || true
  if ! "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" --wait 12 >/dev/null 2>&1; then
    tail -n 120 "$LOGROOT/backend.log" 2>/dev/null | tee -a "$START_LOG" >&2 || true
    "$P2000_PYTHON" tools/runtime_probe.py --describe-port 2>&1 | tee -a "$START_LOG" >&2 || true
    die 4 "Backend start niet na automatische herstelpoging. Zie: $LOGROOT/backend.log"
  fi
fi
if [[ "${P2000_SUPERVISED:-0}" != "1" ]]; then
  if ! "$P2000_PYTHON" tools/supervisor.py --status >/dev/null 2>&1; then
    nohup "$P2000_PYTHON" "$ROOT/tools/supervisor.py" >>"$LOGROOT/supervisor.log" 2>&1 </dev/null &
  fi
fi
if ! eval "$("$P2000_PYTHON" tools/kiosk_display.py --shell sh 2>>"$START_LOG")"; then
  log '[WAARSCHUWING] Schermdetectie mislukt; primair scherm wordt gebruikt.'
fi
log "[4/4] Lichtkrant op ${P2000_DISPLAY_DEVICE:-primary} (${P2000_WINDOW_POSITION:-0,0} / ${P2000_WINDOW_SIZE:-1920,1080})"
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  die 5 'Geen grafische Linux-sessie gevonden. Start P2000 vanuit je desktop/gebruikerssessie, niet via SSH of een root-service.'
fi
KIOSK_EXTRA=()
if [[ "${P2000_DISPLAY_PRIMARY:-1}" == "0" ]]; then KIOSK_EXTRA+=(--prefer-x11); fi
# A manual start after an installer/update must never reuse an old renderer.
# Stop only our dedicated kiosk profile; control/wizard browser windows are untouched.
"$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" stop-kiosk --rundir "$RUNDIR" >>"$START_LOG" 2>&1 || true
sleep 0.25
DETAIL="$("$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" kiosk \
  --url 'http://127.0.0.1:8765/' \
  --position "${P2000_WINDOW_POSITION:-0,0}" \
  --size "${P2000_WINDOW_SIZE:-1920,1080}" \
  --rundir "$RUNDIR" "${KIOSK_EXTRA[@]}" 2>>"$BROWSER_LOG")"
RC=$?
if [[ $RC -ne 0 ]]; then
  tail -n 80 "$BROWSER_LOG" 2>/dev/null | tee -a "$START_LOG" >&2 || true
  die 6 "Geen browser kon de lichtkrant openen. Voer ./LINUX_CHECK.sh uit."
fi
log "Kiosk gestart via ${DETAIL:-browser}."
exit 0
