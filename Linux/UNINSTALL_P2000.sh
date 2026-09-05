#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${P2000_INSTALL_DIR:-$HOME/.local/share/p2000-monitor}"
"$ROOT/STOP_P2000.sh" 2>/dev/null || true
"$ROOT/REMOVE_AUTOSTART.sh" 2>/dev/null || true
rm -f "$HOME/.local/bin/p2000-monitor" "$HOME/.local/share/applications/p2000-monitor.desktop"
if [[ "${1:-}" == '--purge' ]]; then rm -rf "$DEST"; echo 'P2000 Monitor inclusief data verwijderd.'; exit 0; fi
BACKUP="$HOME/.local/share/p2000-monitor-userdata-$(date +%Y%m%d-%H%M%S)";mkdir -p "$BACKUP"
[[ -d "$DEST/data" ]] && cp -a "$DEST/data" "$BACKUP/data"
[[ -f "$DEST/config/config.json" ]] && { mkdir -p "$BACKUP/config"; cp -a "$DEST/config/config.json" "$BACKUP/config/config.json"; }
rm -rf "$DEST";echo "P2000 Monitor verwijderd. Instellingenbackup: $BACKUP"
