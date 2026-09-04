#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT" || exit 1
source "$ROOT/ENSURE_PYTHON.sh" || exit 1
VERSION="$(tr -d '\r\n ' < "$ROOT/VERSION" 2>/dev/null || printf '4.4.15')"
mkdir -p "$ROOT/data" "$ROOT/config" 2>/dev/null || true
probe="$ROOT/data/.write-test-$$"
if ! ( umask 077; : > "$probe" ) 2>/dev/null; then
  echo "[FOUT] Backend kan niet schrijven naar $ROOT/data" >&2
  echo "Herstel eigendom/rechten en probeer opnieuw. Bijvoorbeeld:" >&2
  echo "  sudo chown -R \"$(id -un):$(id -gn)\" \"$ROOT\"" >&2
  exit 4
fi
rm -f "$probe" 2>/dev/null || true
if "$P2000_PYTHON" "$ROOT/tools/runtime_probe.py" --version "$VERSION" >/dev/null 2>&1; then
  echo "[OK] P2000 backend v$VERSION draait al op http://127.0.0.1:8765"
  exit 0
fi
if ! "$P2000_PYTHON" "$ROOT/tools/runtime_probe.py" --version "$VERSION" --kill-stale; then
  echo '[FOUT] Poort 8765 kon niet veilig worden vrijgemaakt.' >&2
  "$P2000_PYTHON" "$ROOT/tools/runtime_probe.py" --describe-port 2>&1 || true
  exit 5
fi
exec "$P2000_PYTHON" "$ROOT/backend/server.py" "$@"
