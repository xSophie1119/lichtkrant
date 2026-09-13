"""Regression tests against the actual server, isolated from installation data."""
from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import http.client
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='p2000-test-')
        cls.root = Path(cls.tmp.name) / 'app'
        shutil.copytree(ROOT, cls.root, ignore=shutil.ignore_patterns('.git', 'data', 'config', '__pycache__', 'node_modules'))
        cls.module = m = load('p2000_test_runtime', cls.root / 'backend/server.py')
        m.SAFE_MODE = True
        config = m.load_config(); config.update(bind='0.0.0.0', startup_selftest=False)
        cls.state = m.AppState(config); cls.state.init_db()
        cls.state.feed_status = 'disabled'
        class LocalHandler(m.Handler):
            state = cls.state
        class PhoneHandler(LocalHandler):
            def setup(self):
                super().setup()
                self.client_address = ('192.168.1.200', self.client_address[1])
        cls.auth_headers = {'Cookie': ''}
        cls.servers = []
        for handler in (LocalHandler, PhoneHandler):
            server = m.QuietThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            cls.servers.append(server)
        client=cls()
        invitation=m._REMOTE_ACCESS.invite('Regression controller')
        status,_,headers=client.request('/api/remote/session', {}, phone=True, headers={'X-P2000-Admin-Token': invitation['token']})
        assert status==200
        cls.auth_headers={'Cookie': headers['Set-Cookie'].split(';',1)[0]}

    @classmethod
    def tearDownClass(cls):
        cls.state.stop_event.set()
        for server in cls.servers:
            server.shutdown(); server.server_close()
        cls.tmp.cleanup()

    def request(self, path, payload=None, *, phone=False, token=False, headers=None):
        server = self.servers[int(phone)]
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        fields = dict(headers or {})
        if token:
            if path == '/api/remote/session': fields['X-P2000-Admin-Token'] = self.module._REMOTE_ACCESS.invite('Test phone')['token']
            else: fields.update(self.auth_headers)
        if payload is not None: fields['Content-Type'] = 'application/json'
        connection.request('GET' if payload is None else 'POST', path, body=json.dumps(payload) if payload is not None else None, headers=fields)
        response = connection.getresponse(); status = response.status; response_headers = dict(response.getheaders()); raw = response.read(); connection.close()
        return status, json.loads(raw) if response_headers.get('Content-Type', '').startswith('application/json') else raw, response_headers

    def test_phone_pairing_and_full_settings(self):
        self.assertEqual(self.request('/api/settings', phone=True)[0], 401)
        self.assertEqual(self.request('/api/settings', {'name': 'unauthorized'}, phone=True)[0], 401)
        status, _, headers = self.request('/api/remote/session', {}, phone=True, token=True)
        self.assertEqual(status, 200); self.assertIn('HttpOnly', headers['Set-Cookie']); self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        status, result, _ = self.request('/api/settings', {'name': 'Phone test'}, phone=True, headers={'Cookie': cookie})
        self.assertEqual(status, 200); self.assertEqual(result['settings']['name'], 'Phone test')
        self.assertEqual(self.request('/api/setup', phone=True, headers={'Cookie': cookie})[0], 200)
        self.assertIn('Max-Age=0', self.request('/api/remote/logout', {}, phone=True, headers={'Cookie': cookie})[2]['Set-Cookie'])

    def test_remote_token_not_exposed(self):
        status, data, _ = self.request('/api/remote/info', phone=True, token=True)
        self.assertEqual(status, 200); self.assertNotIn('token', data)
        self.assertEqual(self.request('/api/remote/config', {'enabled': False}, phone=True, token=True)[0], 403)
        self.assertEqual(self.request('/api/settings', phone=True, headers={'X-P2000-Admin-Token': 'wrong'})[0], 401)

    def test_local_pair_info(self):
        status, data, _ = self.request('/api/remote/info')
        self.assertEqual(status, 200); self.assertTrue(data['local']); self.assertNotIn('token', data)

    def test_origin_and_host_guards(self):
        for headers in ({'Origin': 'https://example.com'}, {'Sec-Fetch-Site': 'cross-site'}, {'Host': 'attacker.example:8765'}):
            self.assertEqual(self.request('/api/settings', {'masterVolume': 1}, headers=headers)[0], 403)
            self.assertEqual(self.request('/api/remote/info', headers=headers)[0], 403)
        self.assertEqual(self.request('/api/settings', headers={'Host': 'localhost:8765'})[0], 200)

    def test_disabled_lan_stays_disabled(self):
        original = self.state.config['bind']; self.state.config['bind'] = '127.0.0.1'
        try: self.assertEqual(self.request('/api/settings', phone=True, token=True)[0], 401)
        finally: self.state.config['bind'] = original

    def test_remote_enable_persists_and_restarts(self):
        with patch.object(self.module, 'schedule_self_restart') as restart:
            status, data, _ = self.request('/api/remote/config', {'enabled': True})
            self.assertEqual(status, 200); self.assertTrue(data['restarting']); restart.assert_called_once()
            self.assertEqual(json.loads(self.module.CONFIG_PATH.read_text())['bind'], '0.0.0.0')
        with patch.object(self.module, 'schedule_self_restart'):
            self.assertEqual(self.request('/api/remote/config', {'enabled': False})[0], 200)
            self.assertEqual(json.loads(self.module.CONFIG_PATH.read_text())['bind'], '127.0.0.1')
        self.assertEqual(self.request('/api/remote/config', {'enabled': 'yes'})[0], 400)

    def test_settings_partial_saves_are_durable_and_independent(self):
        self.state.save_display_settings({'cities': ['Tilburg'], 'mapEnabled': True, 'dispatchTuneDefault': 'builtin:double', 'speechEngine': 'native'})
        def save(item): return self.request('/api/settings', item, phone=True, token=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(save, [{'masterVolume': 37}, {'name': 'Concurrency'}, {'mapEnabled': False}, {'nightStart': '22:30'}]))
        self.assertTrue(all(row[0] == 200 for row in results))
        settings = self.state.get_display_settings()
        for key, value in {'masterVolume': 37, 'name': 'Concurrency', 'mapEnabled': False, 'nightStart': '22:30', 'cities': ['Tilburg'], 'dispatchTuneDefault': 'builtin:double', 'speechEngine': 'native'}.items(): self.assertEqual(settings[key], value)
        restored = self.module.AppState(self.state.config)
        self.assertEqual(restored.get_display_settings()['masterVolume'], 37)
        settings['cities'].append('MUTATION')
        self.assertEqual(self.state.get_display_settings()['cities'], ['Tilburg'])

    def test_quick_actions_only_send_the_changed_fields(self):
        with patch.object(self.state, 'save_display_settings', return_value={}) as save:
            self.assertEqual(self.request('/api/quick-action', {'action': 'volume', 'value': 23})[0], 200)
            save.assert_called_once_with({'masterVolume': 23})
        with patch.object(self.state, 'save_display_settings', return_value={}) as save:
            self.assertEqual(self.request('/api/quick-action', {'action': 'speech-priority'})[0], 200)
            save.assert_called_once_with({'speechMode': 'priority', 'speechEnabled': True})

    def test_settings_cache_reduces_db_reads(self):
        self.state.settings_cache = None
        with patch.object(self.state, '_load_display_settings', wraps=self.state._load_display_settings) as read:
            for _ in range(50): self.state.get_display_settings()
            self.assertEqual(read.call_count, 1)
        with patch.object(self.state, 'broadcast') as broadcast:
            self.state.save_display_settings(self.state.get_display_settings())
            broadcast.assert_not_called()

    def test_health_gate_is_cached_but_force_rechecks(self):
        self.state.health_gate_cache = None
        with patch.object(self.module, '_v457_eval_health', wraps=self.module._v457_eval_health) as gate:
            for _ in range(20): self.assertTrue(self.state.health_snapshot()['ok'])
            self.assertEqual(gate.call_count, 1)
            self.state.health_snapshot(force=True); self.assertEqual(gate.call_count, 2)

    def test_actual_http_health_and_dashboard(self):
        self.assertTrue(self.request('/api/health')[1]['ok'])
        code, data, _ = self.request('/api/remote/status', phone=True, token=True)
        self.assertEqual(code, 200); self.assertEqual(data['version'], (self.root/'VERSION').read_text(encoding='utf-8').strip()); self.assertIsInstance(data['displays'], list)
        for path in ['/remote', '/remote.js', '/auth.js', '/control', '/setup.html']:
            self.assertEqual(self.request(path)[0], 200)

    def test_test_command_reaches_polling_display(self):
        self.state.record_display_client('test-screen', {'audio_unlocked': True})
        code, data, _ = self.request('/api/test-message', {'token': 'phone-test', 'mode': 'speech-only', 'speech_text': 'Test', 'speak': True, 'host_speak': False}, phone=True, token=True)
        self.assertEqual(code, 200)
        batch = self.request('/api/display-commands?after=0')[1]
        self.assertTrue(any(row.get('payload', {}).get('token') == 'phone-test' for row in batch['commands']))
        self.assertEqual(self.request('/api/test-status?token=phone-test')[0], 200)

    def test_replay_queued_without_sse_is_success(self):
        with patch.object(self.module, 'query_messages', return_value=[{'id': 'test', 'title': 'Test'}]):
            code, data, _ = self.request('/api/quick-action', {'action': 'replay-last'})
        self.assertEqual(code, 200); self.assertTrue(data['queued']); self.assertTrue(data['ok'])

    def test_id_lookup_uses_primary_key_and_finds_older_messages(self):
        with self.state.connect() as con:
            columns = {row[1]: row for row in con.execute('PRAGMA table_info(messages)')}
            row = {name: '' for name, meta in columns.items() if meta[3]}
            row.update(id='old-map', published='2020-01-01T00:00:00+00:00', units_json='[]', categories_json='[]', scale_score=0, parser_confidence=0, parser_notes_json='[]')
            names = ','.join(row); placeholders = ','.join('?' for _ in row)
            con.execute(f'INSERT OR REPLACE INTO messages({names}) VALUES({placeholders})', list(row.values()))
            plan = str(con.execute('EXPLAIN QUERY PLAN SELECT * FROM messages WHERE id = ?', ('old-map',)).fetchall()[0][3])
            self.assertIn('INDEX', plan)
        self.assertEqual(self.module.query_messages(self.state, {'id': ['old-map']})[0]['id'], 'old-map')
        with patch.object(self.state, 'geocode_incident', return_value={'lat': 51.5, 'lon': 5.0}):
            self.assertEqual(self.module.map_context_view(self.state, 'old-map')['message_id'], 'old-map')

    def test_parser_does_not_invent_fire_units(self):
        for raw in ['P 1 386198 Letsel Beethovenlaan Tilburg', 'A1 209432 Hoofdstraat Tilburg']:
            code, data, _ = self.request('/api/parser/debug', {'raw': raw})
            self.assertEqual(code, 200); self.assertEqual(data['parse'].get('units') or [], [], raw)

    def test_backoff_is_not_reported_as_a_healthy_primary_feed(self):
        poller = self.module.FeedPoller(self.state)
        old_config = dict(self.state.config)
        self.state.config.update(feed_urls=['https://primary.test/rss'], supplemental_feed_urls=[], fallback_feed_urls=['https://backup.test/rss'])
        def fetch(url, *args):
            self.state.feed_diag[url] = {'status': 'backoff' if 'primary' in url else 'online', 'last_success': '2020-01-01', 'error': 'timeout' if 'primary' in url else ''}
            return 0, 0, 0
        try:
            with patch.object(self.state, 'race_feed_urls', return_value=[]), patch.object(poller, 'fetch_url', side_effect=fetch):
                poller.fetch_once()
            self.assertEqual(self.state.feed_status, 'fallback')
        finally: self.state.config = old_config

    def test_corrupt_recovery_marker_cannot_restore_the_installation_over_itself(self):
        recovery = load('recovery_safe_test', self.root/'tools/recovery_bootstrap.py')
        marker = self.root/'test-pending.json'; marker.write_text('{}')
        recovery.ROOT = self.root; recovery.PENDING = marker; recovery.JOURNAL = self.root/'test-journal.json'
        self.assertFalse(recovery.recover_pending()['ok']); self.assertTrue(marker.exists())
        with self.assertRaises(ValueError): recovery.mirror_restore(self.root, self.root)

    def test_atomic_journal_writer(self):
        file = self.root / 'journal.json'; self.module._atomic_json_write(file, {'state': 'applying'})
        self.assertEqual(json.loads(file.read_text()), {'state': 'applying'})
        self.assertFalse(list(self.root.glob('.p2000-*.tmp')))

    def test_maintenance_queue_no_overwrite(self):
        helper = load('commands_test', self.root / 'tools/supervisor_commands.py')
        a = self.module.queue_supervisor_command('restart-kiosk'); b = self.module.queue_supervisor_command('restart-backend')
        self.assertEqual(helper.claim_next(self.module.DATA_DIR)['token'], a['token'])
        self.assertEqual(helper.claim_next(self.module.DATA_DIR)['token'], b['token'])
        self.assertIsNone(helper.claim_next(self.module.DATA_DIR))

    def test_maintenance_executor_calls_the_correct_platform_helper(self):
        helper = load('commands_execute_test', self.root / 'tools/supervisor_commands.py')
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"display":{"selected_monitor":{"x":1920,"y":0,"width":1920,"height":1080}}}'
        with patch.object(helper.urllib.request, 'urlopen', return_value=Response()), patch.object(helper.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr=b'')) as run:
            self.assertTrue(helper.execute(self.root, {'action': 'restart-kiosk'})['ok'])
            self.assertIn('stop-kiosk', run.call_args_list[0].args[0]); self.assertIn('launch', run.call_args_list[1].args[0]); self.assertIn('1920,0', run.call_args_list[1].args[0])

    def test_release_archive_extracts_verifies_and_boots(self):
        manifest = json.loads((self.root/'release-manifest.json').read_text())
        archive = self.root.parent/'release.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in [*manifest['files'], 'release-manifest.json']:
                bundle.write(self.root/name, 'lichtkrant-release/'+name)
        package, version = self.module._validate_and_extract_update(archive)
        try:
            self.assertEqual(version, (self.root/'VERSION').read_text(encoding='utf-8').strip())
            self.assertTrue(self.module._preflight_staged_update(package, version)['ok'])
        finally:
            stage = package.parent if (package.parent/'.p2000-update-stage').exists() else package
            shutil.rmtree(stage)

    def test_linux_settings_opener_and_probe_commands_exist(self):
        helper = load('linux_commands_test', self.root/'tools/linux_desktop.py')
        with patch.object(helper.shutil, 'which', return_value='/usr/bin/xdg-open'), patch.object(helper.subprocess, 'Popen') as launch:
            self.assertEqual(helper.open_page('http://127.0.0.1:8765/control'), 0)
            self.assertNotIn('--kiosk', launch.call_args.args[0])
            self.assertEqual(helper.open_page('file:///etc/passwd'), 2)
        result = subprocess.run([sys.executable,str(self.root/'tools/linux_desktop.py'),'probe'], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0); self.assertIn('candidates', json.loads(result.stdout))

    def test_update_upload_remains_disabled(self):
        self.assertEqual(self.request('/api/update/upload', {})[0], 403)

    def test_fresh_checkout_starts_without_mutating_sources(self):
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        before = hashlib.sha256((self.root / 'backend/server.py').read_bytes()).hexdigest()
        started = time.monotonic()
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen([sys.executable, '-u', str(self.root / 'backend/server.py'), '--safe-mode', '--no-poll', '--bind', '127.0.0.1', '--port', str(port)], cwd=self.root, stdout=output, stderr=output)
            try:
                healthy = False
                while time.monotonic() - started < 10:
                    if process.poll() is not None: break
                    try:
                        con = http.client.HTTPConnection('127.0.0.1', port, timeout=.5); con.request('GET', '/api/health'); response = con.getresponse(); data = json.loads(response.read()); con.close()
                        if data.get('ok'): healthy = True; break
                    except (OSError, ValueError): time.sleep(.05)
                output.seek(0)
                self.assertTrue(healthy, output.read().decode())
                self.assertEqual(hashlib.sha256((self.root / 'backend/server.py').read_bytes()).hexdigest(), before)
                print(f'\nClean startup healthy in {time.monotonic() - started:.3f}s', flush=True)
            finally:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)


if __name__ == '__main__': unittest.main(verbosity=2)
