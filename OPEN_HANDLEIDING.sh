#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$ROOT/LEES_MIJ_EERST.html"
URL="file://$TARGET"
if source "$ROOT/ENSURE_PYTHON.sh" >/dev/null 2>&1; then
  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    "$P2000_PYTHON" "$ROOT/tools/linux_desktop.py" open --url "$URL" >/dev/null 2>&1 && exit 0
  fi
fi
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$TARGET" && exit 0; fi
if command -v gio >/dev/null 2>&1; then gio open "$TARGET" && exit 0; fi
echo "Open handmatig: $TARGET"
exit 1
