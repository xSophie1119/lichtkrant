#!/usr/bin/env bash
# Can be executed directly or sourced. Optional installer mode is enabled by
# P2000_TRY_INSTALL_PYTHON=1 (used only by INSTALL_P2000.sh).
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOGROOT="${XDG_STATE_HOME:-$HOME/.local/state}/p2000-monitor/logs"
mkdir -p "$LOGROOT" 2>/dev/null || true
_p2000_sourced=0
[[ "${BASH_SOURCE[0]}" != "$0" ]] && _p2000_sourced=1
check_py(){
  local py="$1"
  "$py" -c 'import sys,sqlite3,ssl,urllib.request; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1
}
find_py(){
  local py
  if [[ -n "${P2000_PYTHON:-}" ]] && command -v "$P2000_PYTHON" >/dev/null 2>&1 && check_py "$P2000_PYTHON"; then
    export P2000_PYTHON; return 0
  fi
  for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null 2>&1 && check_py "$py"; then
      export P2000_PYTHON="$(command -v "$py")"; return 0
    fi
  done
  return 1
}
run_privileged(){
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then "$@"; return $?; fi
  command -v sudo >/dev/null 2>&1 || return 127
  sudo "$@"
}
try_install_python(){
  echo '[INFO] Geschikte Python ontbreekt; automatische installatie proberen...'
  if command -v apt-get >/dev/null 2>&1; then
    run_privileged apt-get update && run_privileged apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then
    run_privileged dnf install -y python3
  elif command -v zypper >/dev/null 2>&1; then
    run_privileged zypper --non-interactive install python3
  elif command -v pacman >/dev/null 2>&1; then
    run_privileged pacman -Sy --needed --noconfirm python
  else
    return 1
  fi
}
if find_py; then
  if ((_p2000_sourced)); then return 0; else exit 0; fi
fi
if [[ "${P2000_TRY_INSTALL_PYTHON:-0}" == 1 ]]; then
  try_install_python || true
  hash -r 2>/dev/null || true
  if find_py; then
    echo "[OK] Python geïnstalleerd: $P2000_PYTHON"
    if ((_p2000_sourced)); then return 0; else exit 0; fi
  fi
fi
cat >&2 <<'TXT'
[FOUT] Geen geschikte Python gevonden. P2000 Monitor heeft Python 3.10 of nieuwer nodig.
Ubuntu/Debian: sudo apt install python3
Fedora:        sudo dnf install python3
Arch:          sudo pacman -S python
OpenSUSE:      sudo zypper install python3
Daarna START_P2000.sh opnieuw uitvoeren.
TXT
if ((_p2000_sourced)); then return 1; else exit 1; fi
