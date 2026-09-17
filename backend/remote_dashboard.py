"""Mobile dashboard state: bounded telemetry, screen receipts and restore points.

Kept separate from feed parsing, HTTP transport and platform process management.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import math
import os
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from remote_storage import atomic_json

PROFILES = {
    'normal': {'label': 'Normaal', 'description': 'Je opgeslagen normale volume en weergave.', 'settings': {}},
    'night': {'label': 'Nacht', 'description': 'Zacht volume, nachtregeling en alleen urgente omroep.', 'settings': {'masterVolume': 25, 'speechMode': 'priority', 'nightMode': True, 'displaySleep': True, 'idleDimEnabled': True, 'urgentOnly': False, 'exerciseMode': False}},
    'exercise': {'label': 'Oefening', 'description': 'Alleen handmatige tests op het scherm; live meldingen blijven in het archief.', 'settings': {'masterVolume': 50, 'speechMode': 'normal', 'nightMode': False, 'displaySleep': False, 'urgentOnly': False, 'exerciseMode': True}},
    'urgent': {'label': 'Alleen urgent', 'description': 'Alleen P1/A0/A1, MMT en opgeschaalde meldingen tonen en omroepen.', 'settings': {'masterVolume': 100, 'speechMode': 'priority', 'urgentOnly': True, 'exerciseMode': False}},
}
PROFILE_KEYS = {'masterVolume', 'speechMode', 'speechEnabled', 'nightMode', 'displaySleep', 'idleDimEnabled', 'urgentOnly', 'exerciseMode'}
PROFILE_DEFAULTS = {'masterVolume': 100, 'speechMode': 'normal', 'speechEnabled': True, 'nightMode': True, 'displaySleep': False, 'idleDimEnabled': True, 'urgentOnly': False, 'exerciseMode': False}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def fingerprint(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _load_restore_history(path):
    """Read optional restore data without allowing a damaged convenience file to stop the monitor."""
    if not path.exists():
        return [], ""
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, list):
            raise ValueError('het hoofdniveau is geen lijst')
        return [row for row in value if isinstance(row, dict) and isinstance(row.get('settings'), dict)][:40], ""
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        quarantined = path.with_name(f'{path.stem}.beschadigd-{stamp}{path.suffix}')
        try:
            os.replace(path, quarantined)
            kept = f' Bewaard als {quarantined.name}.'
        except OSError:
            kept = ' Het oorspronkelijke bestand is niet overschreven.'
        return [], f'Herstelpunten konden niet worden gelezen en zijn overgeslagen ({str(exc)[:120]}).{kept}'


def measured(name):
    def decorate(fn):
        @wraps(fn)
        def call(self, *args, **kwargs):
            started = time.perf_counter()
            try:
                return fn(self, *args, **kwargs)
            finally:
                state = getattr(self, 'state', self)
                dashboard = getattr(state, 'dashboard', None)
                if dashboard:
                    dashboard.measure(name, (time.perf_counter() - started) * 1000)
        return call
    return decorate


def process_memory():
    """Current resident memory where available, explicitly labelled peak fallback."""
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(k, ctypes.c_size_t) for k in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
            row = Counters(); row.cb = ctypes.sizeof(row)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(row), row.cb):
                raise OSError('GetProcessMemoryInfo')
            return row.WorkingSetSize, 'resident'
        with open('/proc/self/statm') as stream:
            return int(stream.read().split()[1]) * os.sysconf('SC_PAGE_SIZE'), 'resident'
    except (OSError, ValueError, AttributeError, IndexError):
        return None, 'unavailable'


class Dashboard:
    def __init__(self, state, data_dir):
        self.state = state
        self.path = data_dir / 'remote' / 'restore-points.json'
        self.profile_path = data_dir / 'remote' / 'normal-profile.json'
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.revision = 0
        self.streams = 0
        self.preview_until = 0.0
        self.previews = {}
        self.receipts = {}
        self.timings = {}
        self.samples = deque(maxlen=360)  # one hour, independent of installation age
        self.last_sample = time.monotonic()
        self.last_cpu = time.process_time()
        self.history, self.history_error = _load_restore_history(self.path)

    def notify(self):
        with self.changed:
            self.revision += 1
            self.changed.notify_all()

    def measure(self, stage, milliseconds):
        if not isinstance(milliseconds, (int, float)) or not math.isfinite(milliseconds): return
        with self.lock:
            self.timings.setdefault(stage, deque(maxlen=240)).append(round(max(0, milliseconds), 3))

    def sample(self, force=False):
        with self.lock:
            now, cpu = time.monotonic(), time.process_time()
            interval = now - self.last_sample
            if interval < 10 and not force: return
            memory, kind = process_memory()
            self.samples.append({'at': now_iso(), 'cpu_percent': round(max(0, cpu - self.last_cpu) / max(.001, interval) * 100, 2), 'rss_bytes': memory, 'memory_kind': kind, 'threads': threading.active_count()})
            self.last_sample, self.last_cpu = now, cpu

    def start_sampler(self):
        def loop():
            while not self.state.stop_event.wait(10): self.sample()
        threading.Thread(target=loop, name='dashboard-metrics', daemon=True).start()

    def metrics(self):
        self.sample()
        with self.lock:
            stages = {}
            for name, values in self.timings.items():
                rows = sorted(values)
                if rows:
                    stages[name] = {'samples': len(rows), 'p50_ms': rows[len(rows)//2], 'p95_ms': rows[min(len(rows)-1, math.ceil(len(rows)*.95)-1)], 'max_ms': rows[-1]}
            return {'stages': stages, 'process': list(self.samples), 'window_seconds': 3600}

    def _studio_snapshot(self):
        studio = getattr(self.state, 'studio', None)
        return studio.snapshot() if studio is not None else None

    def _restore_bundle(self):
        return {'settings': self.state.get_display_settings(), 'studio': self._studio_snapshot()}

    def checkpoint(self, label, settings):
        studio = self._studio_snapshot()
        with self.lock:
            if self.history and self.history[0].get('settings') == settings and self.history[0].get('studio') == studio:
                return self.history[0]['id']
            row = {
                'id': secrets.token_hex(12), 'created_at': now_iso(), 'description': str(label)[:160],
                'settings': copy.deepcopy(settings), 'studio': copy.deepcopy(studio),
            }
            history = [row, *self.history][:40]
            atomic_json(self.path, history, private=True)
            self.history = history
            return row['id']

    def history_view(self):
        with self.lock:
            return [{**{k: v for k, v in row.items() if k not in {'settings', 'studio'}}, 'includes_studio': isinstance(row.get('studio'), dict)} for row in self.history]

    def restore_preview(self, point_id):
        current = self._restore_bundle()
        with self.lock:
            row = next((copy.deepcopy(x) for x in self.history if x.get('id') == point_id), None)
        if not row: raise ValueError('Herstelpunt bestaat niet meer')
        saved_settings = row.get('settings') or {}
        changes = [{'key': key, 'before': current['settings'].get(key), 'after': saved_settings.get(key)} for key in sorted(set(current['settings']) | set(saved_settings)) if current['settings'].get(key) != saved_settings.get(key)]
        studio_changes = []
        saved_studio = row.get('studio')
        if isinstance(saved_studio, dict) and saved_studio != current['studio']:
            old = (current['studio'] or {}).get('config', {})
            new = saved_studio.get('config', {})
            labels = [('layout', 'Studio-ontwerp'), ('rules', 'Studio-regels'), ('speech', 'Studio-omroep'), ('corrections', 'Studio-correcties'), ('examples', 'Studio-testvoorbeelden')]
            studio_changes = [label for key, label in labels if old.get(key) != new.get(key)] or ['Studio-inrichting']
        return dict(row, changes=changes, studio_changes=studio_changes, expected=fingerprint(current), includes_studio=isinstance(saved_studio, dict))

    def restore(self, point_id, expected):
        with self.state.config_lock:
            current = self._restore_bundle()
            preview = self.restore_preview(point_id)
            if preview['expected'] != expected:
                raise ValueError('Instellingen of Studio zijn intussen gewijzigd; bekijk de voorvertoning opnieuw')
            # Preserve a coherent return point before either persistent store changes.
            self.checkpoint('Vóór terugzetten herstelpunt', current['settings'])
            previous_studio, restored_studio = current['studio'], None
            try:
                if preview.get('includes_studio'):
                    restored_studio = self.state.studio.restore_snapshot(preview['studio'], expected=(previous_studio or {}).get('revision'))
                result = self.state.save_display_settings(preview['settings'], replace=True)
            except Exception:
                # Both stores are local and independent. Compensate a partial restore
                # so a failed action never silently leaves settings and Studio apart.
                if restored_studio is not None and previous_studio is not None:
                    try: self.state.studio.restore_snapshot(previous_studio)
                    except Exception: pass
                try: self.state.save_display_settings(current['settings'], replace=True)
                except Exception: pass
                raise
            if restored_studio is not None:
                self.state.broadcast({'type': 'studio', 'design': restored_studio})
            return result

    def profile(self, key):
        if key not in PROFILES: raise ValueError('Onbekend profiel')
        with self.state.config_lock:
            current = self.state.get_display_settings()
            if current.get('activeProfile', 'normal') == 'normal':
                base = {k: current.get(k, PROFILE_DEFAULTS[k]) for k in PROFILE_KEYS}
                atomic_json(self.profile_path, base, private=True)
            base = json.loads(self.profile_path.read_text()) if self.profile_path.exists() else dict(PROFILE_DEFAULTS)
            patch = {**base, **PROFILES[key]['settings'], 'activeProfile': key, 'speechEnabled': True}
            if key == 'normal': patch['speechEnabled'] = base.get('speechEnabled', True)
            self.checkpoint('Vóór profiel ' + PROFILES[key]['label'], current)
            return self.state.save_display_settings(patch)

    def apply_standard(self, kind):
        if kind not in {'layout', 'speech'}:
            raise ValueError('Onbekende standaardinstelling')
        patch = {'messageDisplayMode': 'parsed'} if kind == 'layout' else {'speechEnabled': True, 'speechMode': 'normal'}
        label = 'Rustige schermweergave' if kind == 'layout' else 'Standaardomroep'
        with self.state.config_lock:
            before_settings = self.state.get_display_settings()
            before_studio = self.state.studio.snapshot()
            config = copy.deepcopy(before_studio['config'])
            config[kind]['enabled'] = False
            self.checkpoint('Vóór ' + label, before_settings)
            saved_studio = None
            try:
                saved_studio = self.state.studio.save(config, before_studio['revision'])
                result = self.state.save_display_settings(patch)
            except Exception:
                if saved_studio is not None:
                    try: self.state.studio.restore_snapshot(before_studio)
                    except Exception: pass
                try: self.state.save_display_settings(before_settings, replace=True)
                except Exception: pass
                raise
            self.state.broadcast({'type': 'studio', 'design': saved_studio})
            return {'settings': result, 'studio': saved_studio}

    def expect(self, seq, action, target=''):
        with self.lock:
            self.receipts[str(seq)] = {'seq': seq, 'action': action, 'target': target, 'created_at': now_iso(), 'created_monotonic': time.monotonic(), 'results': {}}
            for key in list(self.receipts)[:-100]: self.receipts.pop(key, None)
        self.notify()

    def receipt(self, payload):
        seq = str(payload.get('seq', ''))
        cid = str(payload.get('client_id', ''))[:120]
        status = payload.get('status')
        if status not in {'received', 'displayed', 'completed', 'error'}: raise ValueError('Ongeldige opdrachtstatus')
        if not any(row['client_id'] == cid and row['online'] for row in self.state.display_clients_view()):
            raise ValueError('Scherm is niet verbonden')
        with self.lock:
            row = self.receipts.get(seq)
            if not row or time.monotonic() - row['created_monotonic'] > 180: raise ValueError('Opdracht is verlopen')
            if row['target'] and row['target'] != cid: raise ValueError('Opdracht hoort bij een ander scherm')
            previous = row['results'].get(cid, {})
            ranks = {'received': 0, 'displayed': 1, 'completed': 2, 'error': 2}
            if ranks.get(previous.get('status'), -1) <= ranks[status]:
                row['results'][cid] = {'status': status, 'detail': str(payload.get('detail', ''))[:240], 'at': now_iso()}
        self.notify()

    def commands(self):
        with self.lock:
            return [dict({k: copy.deepcopy(v) for k, v in x.items() if k != 'created_monotonic'}, expired=time.monotonic()-x['created_monotonic']>60) for x in list(self.receipts.values())[-8:]][::-1]

    def preview(self, payload):
        cid = str(payload.get('client_id', ''))[:120]
        if not any(row['client_id'] == cid and row['online'] for row in self.state.display_clients_view()): raise ValueError('Scherm is niet verbonden')
        encoded = payload.get('image', '')
        if not isinstance(encoded, str) or not encoded.startswith('data:image/jpeg;base64,') or len(encoded) > 60000:
            raise ValueError('Voorvertoning moet een kleine JPEG zijn')
        try: raw = base64.b64decode(encoded.split(',', 1)[1], validate=True)
        except ValueError as exc: raise ValueError('Ongeldige JPEG') from exc
        if not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'): raise ValueError('Ongeldige JPEG')
        with self.lock:
            self.previews[cid] = {'image': encoded, 'at': now_iso(), 'captured_monotonic': time.monotonic(), 'message': str(payload.get('message', ''))[:1000], 'map_visible': bool(payload.get('map_visible')), 'mode': str(payload.get('mode', ''))[:30]}
            for key in list(self.previews)[:-20]: self.previews.pop(key, None)
        self.notify()

    def screen_view(self):
        with self.lock:
            return {key: {**{k: v for k, v in row.items() if k not in {'image', 'captured_monotonic'}}, 'age_seconds': round(time.monotonic()-row['captured_monotonic'], 1)} for key, row in self.previews.items()}

    def snapshot(self, runtime):
        state = self.state
        with self.lock: self.preview_until = time.monotonic() + 25
        displays = state.display_clients_view()
        messages = runtime.query_messages(state, {'limit': ['8']})
        feeds = list(state.feed_diag.values())
        successes = [str(x.get('last_success', '')) for x in feeds if x.get('last_success')]
        return {'ok': True, 'version': runtime.APP_VERSION, 'settings': state.get_display_settings(), 'feed_status': state.feed_status,
                'last_error': state.last_error, 'displays': displays, 'messages': messages, 'display_power': state.display_power_status,
                'server_instance': state.server_instance, 'screens': self.screen_view(), 'commands': self.commands(),
                'profiles': [{'id': k, 'label': v['label'], 'description': v['description']} for k, v in PROFILES.items()],
                'diagnostics': {'source_last_success': max(successes, default=None), 'last_message': messages[0]['published'] if messages else None,
                                'sources': [{'status': x.get('status'), 'role': x.get('role'), 'error': x.get('error'), 'fetch_ms': x.get('fetch_ms'), 'last_success': x.get('last_success')} for x in feeds]},
                'metrics': self.metrics(), 'restore_warning': self.history_error,
                'audio_runtime': runtime.tts_runtime_status()}
