"""Per-device sessions, one-use pairing invitations and LAN request guards."""
from __future__ import annotations
import hashlib
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlparse
from remote_storage import atomic_json


class RemoteAccess:
    COOKIE = 'p2000_admin'
    VIEW_PATHS = {'/api/remote/session', '/api/remote/info', '/api/remote/status',
                  '/api/remote/events', '/api/remote/preview', '/api/remote/archive',
                  '/api/remote/command', '/api/remote/map', '/api/map-context', '/api/geocode'}

    def __init__(self, token_path: Path):
        # The old shared admin token is intentionally no longer a credential.
        self.path = token_path.parent / 'devices.json'
        self.lock = threading.RLock()
        self.load_warning = ''
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or not isinstance(data.get('devices'), dict):
                    raise ValueError('het hoofdniveau bevat geen apparatenlijst')
                self.devices = data['devices']
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                # Device credentials fail closed: LAN sessions are not recreated
                # or guessed, while the local monitor can still start and repair.
                stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
                damaged=self.path.with_name(f'{self.path.stem}.beschadigd-{stamp}{self.path.suffix}')
                try: os.replace(self.path,damaged); kept=f' Bewaard als {damaged.name}.'
                except OSError: kept=' Het oorspronkelijke bestand is niet overschreven.'
                self.devices = {}
                self.load_warning='Apparaattoegang is veilig uitgeschakeld omdat devices.json beschadigd is.'+kept
        else:
            self.devices = {}
        self.invites = {}
        self.hostnames = {'localhost', socket.gethostname().lower(), socket.gethostname().lower() + '.local'}

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def save(self):
        atomic_json(self.path, {'devices': self.devices}, private=True)

    @staticmethod
    def is_loopback(value: str) -> bool:
        try:
            addr = ipaddress.ip_address(str(value).split('%', 1)[0])
            return addr.is_loopback or bool(getattr(addr, 'ipv4_mapped', None) and addr.ipv4_mapped.is_loopback)
        except ValueError:
            return False

    def valid_request(self, handler) -> bool:
        host = (handler.headers.get('Host') or '').lower()
        try:
            parsed = urlparse('http://' + host)
            hostname = parsed.hostname
            if not hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                return False
            if hostname not in self.hostnames:
                ipaddress.ip_address(hostname.split('%', 1)[0])
            if parsed.port is not None and not 0 < parsed.port < 65536:
                return False
        except ValueError:
            return False
        if handler.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        origin = handler.headers.get('Origin')
        if origin:
            try:
                parsed = urlparse(origin)
                if parsed.scheme not in {'http', 'https'} or parsed.netloc.lower() != host:
                    return False
            except ValueError:
                return False
        return True

    def credential(self, handler):
        value = handler.headers.get('X-P2000-Admin-Token') or ''
        if not value:
            try:
                cookies = SimpleCookie(handler.headers.get('Cookie') or '')
                value = cookies[self.COOKIE].value if self.COOKIE in cookies else ''
            except CookieError:
                return ''
        return value[:512]

    def identity(self, handler):
        if self.is_loopback(handler.client_address[0]):
            return {'id': 'local', 'role': 'admin', 'name': 'Lichtkrant-pc', 'local': True}
        if self.is_loopback(handler.state.config.get('bind', '127.0.0.1')):
            return None
        hashed = self.digest(self.credential(handler))
        with self.lock:
            for key, device in self.devices.items():
                if device['expires_at'] > time.time() and secrets.compare_digest(device['hash'], hashed):
                    device['last_seen'] = time.time()
                    return {k: v for k, v in dict(device, id=key, local=False).items() if k != 'hash'}
        return None

    def authorized(self, handler):
        return self.identity(handler) is not None

    def permitted(self, handler, path, method):
        who = self.identity(handler)
        if not who:
            return False
        if who['role'] != 'viewer':
            return True
        return (method == 'GET' and path in self.VIEW_PATHS) or (method == 'POST' and path == '/api/remote/logout')

    def invite(self, name='Telefoon', role='controller'):
        if role not in {'viewer', 'controller'}:
            raise ValueError('Kies alleen kijken of bedienen')
        with self.lock:
            self.invites = {k: v for k, v in self.invites.items() if v['expires_at'] > time.time()}
            if len(self.invites) >= 20:
                raise ValueError('Er staan al 20 koppelcodes open; wacht tot ze verlopen')
            token = secrets.token_urlsafe(32)
            row = {'name': str(name).strip()[:80] or 'Telefoon', 'role': role, 'expires_at': time.time() + 300}
            self.invites[self.digest(token)] = row
            return dict(row, token=token)

    def pair(self, handler):
        if self.is_loopback(handler.state.config.get('bind', '127.0.0.1')) and not self.is_loopback(handler.client_address[0]):
            return handler.send_json({'ok': False, 'error': 'Telefoontoegang staat uit'}, 401)
        with self.lock:
            key = self.digest(handler.headers.get('X-P2000-Admin-Token') or '')
            invite = self.invites.get(key)
            if not invite or invite['expires_at'] <= time.time():
                return handler.send_json({'ok': False, 'error': 'Koppelcode verlopen of al gebruikt; maak op de pc een nieuwe'}, 401)
            self.devices = {k: v for k, v in self.devices.items() if v['expires_at'] > time.time()}
            if len(self.devices) >= 100:
                return handler.send_json({'ok': False, 'error': 'Apparatenlijst vol; verwijder eerst een apparaat'}, 409)
            token = secrets.token_urlsafe(32)
            device_id = secrets.token_hex(12)
            self.devices[device_id] = dict(invite, hash=self.digest(token), created_at=time.time(), last_seen=time.time(), expires_at=time.time() + 30 * 86400)
            try:
                self.save()
            except OSError:
                del self.devices[device_id]
                raise
            del self.invites[key]
        return self._cookie_response(handler, token, 30 * 86400, {'role': invite['role'], 'local': False, 'id': device_id})

    def list_devices(self):
        with self.lock:
            return [dict({k: v for k, v in row.items() if k != 'hash'}, id=key) for key, row in self.devices.items() if row['expires_at'] > time.time()]

    def revoke(self, device_id):
        with self.lock:
            old = self.devices.pop(device_id, None)
            try:
                self.save()
            except OSError:
                if old: self.devices[device_id] = old
                raise

    def _cookie_response(self, handler, value, max_age, extra=None):
        body = json.dumps({'ok': True, **(extra or {})}).encode('utf-8')
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Set-Cookie', f'{self.COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}')
        handler._short_response_connection()
        handler.end_headers()
        handler._safe_write(body)

    def logout(self, handler):
        who = self.identity(handler)
        if who and not who['local']:
            self.revoke(who['id'])
        self._cookie_response(handler, '', 0)
