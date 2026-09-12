"""Phone pairing shared by the mobile dashboard, settings and wizard."""
from __future__ import annotations

import ipaddress
import json
import os
import secrets
import socket
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlparse


class RemoteAccess:
    COOKIE = 'p2000_admin'

    def __init__(self, token_path: Path):
        token_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self.token = token_path.read_text(encoding='utf-8').strip()
            if len(self.token) < 32:
                raise RuntimeError('Ongeldig admin-token; herstel data/secrets/admin-token.txt')
        else:
            self.token = secrets.token_urlsafe(32)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(self.token + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        self.hostnames = {'localhost', socket.gethostname().lower(), socket.gethostname().lower() + '.local'}

    @staticmethod
    def is_loopback(value: str) -> bool:
        try:
            addr = ipaddress.ip_address(str(value).split('%', 1)[0])
            return addr.is_loopback or bool(getattr(addr, 'ipv4_mapped', None) and addr.ipv4_mapped.is_loopback)
        except ValueError:
            return False

    def valid_request(self, handler) -> bool:
        """Refuse cross-site browser traffic and arbitrary DNS rebinding hosts."""
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
                origin_url = urlparse(origin)
                if origin_url.scheme not in {'http', 'https'} or origin_url.netloc.lower() != host:
                    return False
            except ValueError:
                return False
        return True

    def authorized(self, handler) -> bool:
        if self.is_loopback(handler.client_address[0]):
            return True
        # The primary listener stays local until the owner explicitly enables LAN.
        if self.is_loopback(handler.state.config.get('bind', '127.0.0.1')):
            return False
        token = handler.headers.get('X-P2000-Admin-Token') or ''
        if not token:
            try:
                cookies = SimpleCookie(handler.headers.get('Cookie') or '')
                token = cookies[self.COOKIE].value if self.COOKIE in cookies else ''
            except CookieError:
                return False
        return bool(token and secrets.compare_digest(token.encode('utf-8'), self.token.encode('utf-8')))

    def _cookie_response(self, handler, value: str, max_age: int):
        body = json.dumps({'ok': True}).encode('utf-8')
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Set-Cookie', f'{self.COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}')
        handler._short_response_connection()
        handler.end_headers()
        handler._safe_write(body)

    def login(self, handler):
        self._cookie_response(handler, self.token, 30 * 24 * 3600)

    def logout(self, handler):
        self._cookie_response(handler, '', 0)
