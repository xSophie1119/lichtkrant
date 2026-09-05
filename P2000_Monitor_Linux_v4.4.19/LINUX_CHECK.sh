#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT" || exit 1
LOGROOT="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs"
BASE_RUNTIME="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime}"
if [[ ! -d "$BASE_RUNTIME" || ! -w "$BASE_RUNTIME" || ! -x "$BASE_RUNTIME" ]]; then BASE_RUNTIME="${XDG_CACHE_HOME:-$HOME/.cache}/p2000-monitor/runtime"; fi
RUNDIR="$BASE_RUNTIME/p2000-monitor-${UID:-$(id -u)}"
export P2000_RUNTIME_DIR="$RUNDIR"
echo '=== P2000 Monitor Linux-check ==='
echo "Versie: $(tr -d '\r\n ' < VERSION 2>/dev/null || echo '?')"
echo "Pad: $ROOT"
echo "Gebruiker: $(id -un 2>/dev/null || echo '?') uid=$(id -u 2>/dev/null || echo '?')"
echo "Sessie: type=${XDG_SESSION_TYPE:-onbekend} desktop=${XDG_CURRENT_DESKTOP:-onbekend} DISPLAY=${DISPLAY:-} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
echo "Runtime: $RUNDIR"
fail=0
if source "$ROOT/ENSURE_PYTHON.sh" >/dev/null 2>&1; then
  echo "Python: OK - $($P2000_PYTHON --version 2>&1) ($P2000_PYTHON)"
else
  echo 'Python: FOUT - Python 3.10+ ontbreekt'; fail=1
fi
for f in START_P2000.sh START_P2000_AUTOSTART.sh CONFIGURATIE_WIZARD.sh OPEN_INSTELLINGEN.sh STOP_P2000.sh INSTALL_P2000.sh; do
  if [[ -x "$ROOT/$f" ]]; then echo "Rechten: OK - $f"; else echo "Rechten: FOUT - $f is niet uitvoerbaar"; fail=1; fi
done
if [[ -w "$ROOT/config" && -w "$ROOT/data" ]]; then echo 'Schrijfrechten: OK - config/data'; else echo 'Schrijfrechten: FOUT - config of data is niet schrijfbaar'; fail=1; fi
if [[ -n "${P2000_PYTHON:-}" ]]; then
  echo '--- Browserdetectie ---'
  "$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" probe 2>&1 | sed -n '1,180p'
fi
if command -v espeak-ng >/dev/null 2>&1; then echo 'Lokale Nederlandse TTS: OK - espeak-ng'; elif command -v espeak >/dev/null 2>&1; then echo 'Lokale Nederlandse TTS: OK - espeak'; else echo 'Lokale TTS: niet gevonden; online Nederlandse fallback blijft beschikbaar'; fi
if [[ -n "${WAYLAND_DISPLAY:-}" ]] && command -v wlr-randr >/dev/null 2>&1; then echo 'Schermdetectie: wlroots Wayland via wlr-randr'; elif [[ -n "${DISPLAY:-}" ]] && command -v xrandr >/dev/null 2>&1; then echo 'Schermdetectie: XRandR/XWayland'; else echo 'Schermdetectie: fallback; monitorpositie kan beperkt zijn'; fi
if [[ -n "${P2000_PYTHON:-}" ]]; then
  VERSION="$(tr -d '\r\n ' < VERSION 2>/dev/null || echo '?')"
  if "$P2000_PYTHON" tools/runtime_probe.py --version "$VERSION" >/dev/null 2>&1; then
    echo 'Backend: ONLINE'
    if command -v curl >/dev/null 2>&1; then
      curl -fsS http://127.0.0.1:8765/api/setup >/dev/null 2>&1 && echo 'Wizard API: OK' || { echo 'Wizard API: FOUT'; fail=1; }
      curl -fsS http://127.0.0.1:8765/setup.html >/dev/null 2>&1 && echo 'Wizard pagina: OK' || { echo 'Wizard pagina: FOUT'; fail=1; }
      curl -fsS http://127.0.0.1:8765/setup.js >/dev/null 2>&1 && echo 'Wizard JavaScript: OK' || { echo 'Wizard JavaScript: FOUT'; fail=1; }
    else
      "$P2000_PYTHON" - <<'PY' || fail=1
import urllib.request
for u in ('http://127.0.0.1:8765/api/setup','http://127.0.0.1:8765/setup.html','http://127.0.0.1:8765/setup.js'):
    with urllib.request.urlopen(u,timeout=3) as r:
        assert r.status==200
print('Wizard HTTP: OK')
PY
    fi
  else
    echo 'Backend: offline (dit is niet fout als de monitor nu niet draait)'
  fi
fi
AUTO="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/p2000-monitor.desktop"
[[ -f "$AUTO" ]] && echo "Autostart: OK - $AUTO" || echo 'Autostart: niet geïnstalleerd'
echo
for f in startup backend browser supervisor autostart; do
  file="$LOGROOT/$f.log"
  if [[ -f "$file" ]]; then
    echo "--- laatste regels $file ---"
    tail -n 18 "$file" 2>/dev/null || true
  fi
done
echo
if [[ "$fail" == 0 ]]; then echo '[OK] Geen harde Linux-fouten gevonden.'; else echo '[FOUT] Er zijn Linux-problemen gevonden. Voer ./LINUX_REPAIR.sh uit en daarna deze check opnieuw.'; fi
exit "$fail"
