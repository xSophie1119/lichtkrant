#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${P2000_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo '[FOUT] python3 is niet gevonden.' >&2
  exit 1
fi
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor"
mkdir -p "$STATE_HOME"
LOG="$STATE_HOME/backend.log"
if [[ -f "$LOG" ]] && [[ $(wc -c <"$LOG" 2>/dev/null || echo 0) -gt 5242880 ]]; then
  rm -f "$LOG.1"
  mv "$LOG" "$LOG.1"
fi
{
  echo
  echo "==== P2000 backend gestart $(date -Is) ===="
  echo "Python: $PYTHON"
  echo "Server: $ROOT/backend/server.py"
} >>"$LOG"
set +e
"$PYTHON" -u -X faulthandler "$ROOT/backend/server.py" >>"$LOG" 2>&1
rc=$?
set -e
printf '==== Backend exitcode %s op %s ====\n' "$rc" "$(date -Is)" >>"$LOG"
exit "$rc"
