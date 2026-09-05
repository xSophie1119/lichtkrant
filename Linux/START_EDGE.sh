#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for c in microsoft-edge-stable microsoft-edge microsoft-edge-beta microsoft-edge-dev; do
  if command -v "$c" >/dev/null 2>&1; then
    export P2000_BROWSER="$c"
    exec "$ROOT/START_P2000.sh"
  fi
done
echo '[FOUT] Microsoft Edge voor Linux is niet gevonden.' >&2
exit 1
