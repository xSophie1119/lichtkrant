#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
echo '=== P2000 Linux herstel ==='
find "$ROOT" -maxdepth 1 -type f -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
find "$ROOT/tools" -maxdepth 1 -type f -name '*.py' -exec chmod +x {} + 2>/dev/null || true
mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs" "$HOME/.local/share/applications" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart" 2>/dev/null || true
if [[ -x "$ROOT/INSTALL_AUTOSTART.sh" ]]; then "$ROOT/INSTALL_AUTOSTART.sh" || true; fi
if [[ "$ROOT" == "${P2000_INSTALL_DIR:-$HOME/.local/share/p2000-monitor}" ]]; then
  "$ROOT/INSTALL_P2000.sh" --no-start || true
fi
echo '[OK] Rechten, autostart en Linux-shortcuts opnieuw opgebouwd.'
echo 'Voer nu ./LINUX_CHECK.sh uit.'
