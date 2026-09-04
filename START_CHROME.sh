#!/usr/bin/env bash
set -u
for c in google-chrome-stable google-chrome chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then export P2000_BROWSER="$c"; exec "$(dirname "$0")/START_P2000.sh"; fi
done
echo '[FOUT] Geen Chrome/Chromium gevonden.' >&2; exit 1
