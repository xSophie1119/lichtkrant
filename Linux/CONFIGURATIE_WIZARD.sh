#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/LINUX_OPEN_PAGE.sh" 'http://127.0.0.1:8765/setup.html?edit=1' 'P2000 Configuratiewizard'
