#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${SUDO_USER:-}" && "${P2000_ALLOW_ROOT_INSTALL:-0}" != 1 ]]; then
  echo '[FOUT] Start deze installer zonder sudo. Hij installeert per gebruiker in ~/.local/share.' >&2
  echo 'Gebruik: ./INSTALL_P2000.sh' >&2
  exit 2
fi
DEST="${P2000_INSTALL_DIR:-$HOME/.local/share/p2000-monitor}"
VERSION="$(tr -d '\r\n ' < "$SRC/VERSION" 2>/dev/null || echo '?')"
echo "P2000 Monitor v$VERSION installeren naar: $DEST"
if [[ "$SRC" != "$DEST" ]]; then
  mkdir -p "$DEST"
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  [[ -f "$DEST/config/config.json" ]] && { mkdir -p "$tmp/config"; cp -a "$DEST/config/config.json" "$tmp/config/config.json"; }
  [[ -d "$DEST/data" ]] && cp -a "$DEST/data" "$tmp/data"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '/data/' --exclude '/config/config.json' "$SRC/" "$DEST/"
  else
    find "$DEST" -mindepth 1 -maxdepth 1 ! -name data ! -name config -exec rm -rf {} +
    cp -a "$SRC"/. "$DEST"/
  fi
  [[ -f "$tmp/config/config.json" ]] && { mkdir -p "$DEST/config"; cp -a "$tmp/config/config.json" "$DEST/config/config.json"; }
  [[ -d "$tmp/data" ]] && { rm -rf "$DEST/data"; cp -a "$tmp/data" "$DEST/data"; }
fi
find "$DEST" -maxdepth 1 -type f -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
find "$DEST/tools" -maxdepth 1 -type f -name '*.py' -exec chmod +x {} + 2>/dev/null || true
P2000_TRY_INSTALL_PYTHON=1 "$DEST/ENSURE_PYTHON.sh"
# shellcheck source=/dev/null
source "$DEST/ENSURE_PYTHON.sh"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sfn "$DEST/START_P2000.sh" "$HOME/.local/bin/p2000-monitor"
desktop_quote(){ local s="$1"; s=${s//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
write_desktop(){
  local file="$1" name="$2" comment="$3" exec_path="$4" terminal="$5"
  cat > "$HOME/.local/share/applications/$file" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Comment=$comment
Exec=$(desktop_quote "$exec_path")
Terminal=$terminal
Categories=Utility;
StartupNotify=true
EOF
  chmod 644 "$HOME/.local/share/applications/$file"
}
write_desktop p2000-monitor.desktop 'P2000 Monitor' 'P2000 lichtkrant openen' "$DEST/START_P2000.sh" false
write_desktop p2000-monitor-settings.desktop 'P2000 Instellingen' 'Mobiele/desktop instellingen openen' "$DEST/OPEN_INSTELLINGEN.sh" false
write_desktop p2000-monitor-wizard.desktop 'P2000 Configuratiewizard' 'Regio, discipline en standplaats instellen' "$DEST/CONFIGURATIE_WIZARD.sh" false
write_desktop p2000-monitor-debug.desktop 'P2000 Linux Diagnose' 'Start P2000 met zichtbare diagnose' "$DEST/START_P2000_DEBUG.sh" true
write_desktop p2000-monitor-stop.desktop 'P2000 Monitor stoppen' 'Backend, watchdog en kiosk stoppen' "$DEST/STOP_P2000.sh" false
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true; fi
"$DEST/INSTALL_AUTOSTART.sh" || true
# Optional quality checks: do not make installation fail when TTS is absent.
if ! "$DEST/INSTALL_NEDERLANDSE_STEM.sh" >/dev/null 2>&1; then
  echo '[TIP] Offline Nederlandse stem ontbreekt. Installeer later met: ./INSTALL_NEDERLANDSE_STEM.sh --install'
fi
if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  if ! "$P2000_PYTHON" -c 'import json,subprocess,sys; d=json.loads(subprocess.check_output([sys.executable,sys.argv[1],"probe"],text=True)); raise SystemExit(0 if d.get("candidates") else 1)' "$DEST/tools/linux_desktop.py"; then
    echo '[WAARSCHUWING] Geen Chrome/Chromium/Brave/Edge/Firefox gevonden. Installeer een browser voordat je de kiosk start.'
  fi
else
  echo '[WAARSCHUWING] Geen grafische sessie gedetecteerd tijdens installatie. De kiosk start zodra je hem vanuit de desktop opent.'
fi
echo '[OK] Geïnstalleerd. Instellingen/data zijn behouden.'
echo "Appmap: $DEST"
echo 'Je vindt nu P2000 Monitor, Instellingen, Configuratiewizard en Linux Diagnose in het applicatiemenu.'
if [[ "${1:-}" != '--no-start' ]]; then
  "$DEST/START_P2000.sh"
fi
