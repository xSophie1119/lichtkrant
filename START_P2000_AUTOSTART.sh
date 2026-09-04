#!/usr/bin/env bash
# Login-safe launcher: waits for the graphical session before starting the kiosk.
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOGROOT="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs"
mkdir -p "$LOGROOT" 2>/dev/null || true
LOG="$LOGROOT/autostart.log"
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
exec >>"$LOG" 2>&1
printf '\n[%s] Autostart gestart. session=%s display=%s wayland=%s\n' "$(date '+%F %T')" "${XDG_SESSION_TYPE:-}" "${DISPLAY:-}" "${WAYLAND_DISPLAY:-}"
# Desktop environment can invoke autostart entries before XWayland/Wayland is fully usable.
for _ in $(seq 1 30); do
  [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && break
  sleep 1
  # Environment variables cannot appear later in this process, but this delay still
  # helps file-manager/session races when they are already set but the compositor is busy.
done
sleep "${P2000_AUTOSTART_DELAY:-4}"
export P2000_NO_PAUSE=1
for attempt in 1 2 3; do
  echo "Autostart poging $attempt"
  "$ROOT/START_P2000.sh" && exit 0
  sleep $((attempt * 4))
done
if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  notify-send -u critical 'P2000 Monitor' 'Autostart is na 3 pogingen mislukt. Open P2000 Linux Diagnose.' >/dev/null 2>&1 || true
fi
exit 1
