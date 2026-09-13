"""Execute queued local maintenance commands without blocking watchdog heartbeats."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def claim_next(data_dir: Path):
    paths = sorted((data_dir / 'supervisor-commands').glob('*.json'))
    legacy = data_dir / 'supervisor-command.json'
    if legacy.exists(): paths.insert(0, legacy)
    for path in paths:
        claimed = path.with_suffix('.processing')
        try: path.replace(claimed)
        except FileNotFoundError: continue
        try:
            row = json.loads(claimed.read_text(encoding='utf-8'))
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['created_at'])).total_seconds()
            if not 0 <= age < 120 or row.get('action') not in {'restart-kiosk', 'restart-backend'}:
                continue
            return row
        except (OSError, KeyError, ValueError, TypeError):
            continue
        finally:
            claimed.unlink(missing_ok=True)
    return None


def execute(root: Path, command: dict) -> dict:
    action = command['action']
    if action == 'restart-backend':
        request = urllib.request.Request('http://127.0.0.1:8765/api/system/restart', data=b'{}', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
        return {'ok': result.get('ok') is True, 'action': action, 'token': command.get('token')}
    if action != 'restart-kiosk': raise ValueError('Onbekende supervisoractie')
    helper = root / 'tools' / ('windows_desktop.py' if os.name == 'nt' else 'linux_desktop.py')
    extra = []
    if os.name != 'nt':
        base = Path(os.environ.get('XDG_RUNTIME_DIR') or Path.home() / '.cache/p2000-monitor/runtime')
        rundir = os.environ.get('P2000_RUNTIME_DIR') or str(base / f'p2000-monitor-{os.getuid()}')
        extra = ['--rundir', rundir]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    stopped = subprocess.run([sys.executable, str(helper), 'stop-kiosk', *extra], timeout=15, capture_output=True, creationflags=flags)
    if stopped.returncode: raise RuntimeError('Lichtkrantscherm kon niet worden gesloten')
    with urllib.request.urlopen('http://127.0.0.1:8765/api/display/info', timeout=5) as response:
        monitor = (json.load(response).get('display') or {}).get('selected_monitor') or {}
    position = f"{int(monitor.get('x', 0))},{int(monitor.get('y', 0))}"
    size = f"{max(320, int(monitor.get('width', 1920)))},{max(240, int(monitor.get('height', 1080)))}"
    result = subprocess.run([sys.executable, str(helper), 'launch', '--url', 'http://127.0.0.1:8765/', '--position', position, '--size', size, *extra], timeout=120, capture_output=True, creationflags=flags)
    return {'ok': result.returncode == 0, 'action': action, 'token': command.get('token'), 'error': result.stderr.decode('utf-8', 'replace')[-400:] if result.returncode else ''}
