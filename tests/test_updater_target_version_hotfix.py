#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import backend.server as mod

orig = {
    'UPDATE_DIR': mod.UPDATE_DIR,
    'UPDATE_STATUS_PATH': mod.UPDATE_STATUS_PATH,
    '_github_latest_software': mod._github_latest_software,
    '_read_installed_github_marker': mod._read_installed_github_marker,
    '_github_update_available': mod._github_update_available,
    '_download_github_asset': mod._download_github_asset,
    '_validate_and_extract_update': mod._validate_and_extract_update,
    'Thread': mod.threading.Thread,
}

class DummyThread:
    def __init__(self, *args, **kwargs):
        self.args=args; self.kwargs=kwargs
    def start(self):
        return None

try:
    with TemporaryDirectory() as td:
        td = Path(td)
        mod.UPDATE_DIR = td / 'updates'
        mod.UPDATE_STATUS_PATH = mod.UPDATE_DIR / 'status.json'
        incoming = td / 'incoming.zip'
        incoming.write_bytes(b'fake')
        package_root = td / 'package'
        package_root.mkdir()
        release = {
            'version': '9.9.9', 'tag': 'v9.9.9', 'revision': 'abcdef1234567890',
            'source_kind': 'release', 'html_url': 'https://github.com/example/example/releases/tag/v9.9.9',
            'name': 'test', 'published_at': '2026-09-04T00:00:00Z',
            'asset': {'name': 'P2000_Monitor_MultiPlatform_v9.9.9.zip', 'size': 123, 'url': 'https://github.com/example.zip'},
        }
        mod._github_latest_software = lambda *a, **k: release
        mod._read_installed_github_marker = lambda: {}
        mod._github_update_available = lambda *a, **k: (True, 'version')
        mod._download_github_asset = lambda *a, **k: incoming
        mod._validate_and_extract_update = lambda *a, **k: (package_root, '9.9.9')
        mod.threading.Thread = DummyThread
        mod._UPDATE_ACTIVE = False

        state = SimpleNamespace(config={'github_repo':'example/example','github_branch':'main','github_branch_updates':True})
        result = mod.github_check_and_maybe_install(state, install=True)
        status = mod.update_runtime_status()
        checks = {
            'no_duplicate_keyword_exception': True,
            'staged_target_version': status.get('target_version') == '9.9.9',
            'staged_state': status.get('state') == 'staged',
            'slot_claimed_until_apply_thread': mod._UPDATE_ACTIVE is True,
            'runtime_result_target': result.get('target_version') == '9.9.9',
        }
        failed=[k for k,v in checks.items() if not v]
        print(f'Updater target_version hotfix: {len(checks)-len(failed)}/{len(checks)}')
        for k,v in checks.items(): print(('OK ' if v else 'FAIL ')+k)
        if failed: raise SystemExit(1)
finally:
    mod.UPDATE_DIR = orig['UPDATE_DIR']
    mod.UPDATE_STATUS_PATH = orig['UPDATE_STATUS_PATH']
    mod._github_latest_software = orig['_github_latest_software']
    mod._read_installed_github_marker = orig['_read_installed_github_marker']
    mod._github_update_available = orig['_github_update_available']
    mod._download_github_asset = orig['_download_github_asset']
    mod._validate_and_extract_update = orig['_validate_and_extract_update']
    mod.threading.Thread = orig['Thread']
    mod._UPDATE_ACTIVE = False
