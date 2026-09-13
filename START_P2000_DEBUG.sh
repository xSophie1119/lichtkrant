#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT" || exit 1
export P2000_NO_PAUSE=1
"$ROOT/START_P2000.sh"
rc=$?
echo
echo "START_P2000.sh eindigde met code $rc"
echo '=== Linux diagnose ==='
"$ROOT/LINUX_CHECK.sh" || true
echo
read -r -p 'Druk op Enter om dit diagnosevenster te sluiten...' _ || true
exit "$rc"
