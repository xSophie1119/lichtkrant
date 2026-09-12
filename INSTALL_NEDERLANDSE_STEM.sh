#!/usr/bin/env bash
set -u
check(){ command -v espeak-ng >/dev/null 2>&1 || command -v espeak >/dev/null 2>&1; }
show(){
  if command -v espeak-ng >/dev/null 2>&1; then echo "OK: eSpeak NG: $(command -v espeak-ng)"; espeak-ng --voices=nl 2>/dev/null | head -n 8 || true; return 0; fi
  if command -v espeak >/dev/null 2>&1; then echo "OK: eSpeak: $(command -v espeak)"; espeak --voices=nl 2>/dev/null | head -n 8 || true; return 0; fi
  return 1
}
run_privileged(){ if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then "$@"; else command -v sudo >/dev/null 2>&1 && sudo "$@"; fi; }
if check; then show; exit 0; fi
if [[ "${1:-}" == '--install' ]]; then
  if command -v apt-get >/dev/null 2>&1; then run_privileged apt-get install -y espeak-ng || true
  elif command -v dnf >/dev/null 2>&1; then run_privileged dnf install -y espeak-ng || true
  elif command -v zypper >/dev/null 2>&1; then run_privileged zypper --non-interactive install espeak-ng || true
  elif command -v pacman >/dev/null 2>&1; then run_privileged pacman -S --needed --noconfirm espeak-ng || true
  fi
  hash -r 2>/dev/null || true
  if check; then show; exit 0; fi
fi
cat <<'TXT'
Geen lokale Nederlandse eSpeak-stem gevonden.
Aanbevolen:
  ./INSTALL_NEDERLANDSE_STEM.sh --install
Of handmatig:
  Ubuntu/Debian: sudo apt install espeak-ng
  Fedora: sudo dnf install espeak-ng
  Arch: sudo pacman -S espeak-ng
Zonder eSpeak probeert P2000 Monitor de online Nederlandse TTS-fallback.
TXT
exit 2
