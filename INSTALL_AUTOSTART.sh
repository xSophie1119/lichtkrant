#!/usr/bin/env bash
set -eu
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$DIR"
FILE="$DIR/p2000-monitor.desktop"
# Desktop Entry Exec accepts double-quoted executable paths; escape backslashes/quotes.
desktop_quote(){
  local s="$1"; s=${s//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"
}
EXEC_PATH="$(desktop_quote "$ROOT/START_P2000_AUTOSTART.sh")"
PATH_VALUE=${ROOT//\\/\\\\}
cat > "$FILE" <<EOF
[Desktop Entry]
Type=Application
Name=P2000 Monitor
Comment=Start de P2000 lichtkrant na aanmelden
Exec=$EXEC_PATH
Path=$PATH_VALUE
Terminal=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
StartupNotify=false
EOF
chmod 600 "$FILE"
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$FILE" >/dev/null 2>&1 || true
fi
echo "Autostart geïnstalleerd: $FILE"
