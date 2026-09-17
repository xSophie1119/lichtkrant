"""HTTP endpoints for the phone dashboard; no platform process logic here."""
from __future__ import annotations
import base64
import json
import time
from datetime import datetime
from urllib.parse import parse_qs


def get(handler, parsed, runtime):
    state, access = handler.state, runtime._REMOTE_ACCESS
    dash = state.dashboard
    qs = parse_qs(parsed.query)
    value = lambda name, default='': qs.get(name, [default])[0]
    path = parsed.path
    if path.startswith('/api/remote/studio/'):
        return runtime.studio_api.handle(handler, path, query=qs)
    if path == '/api/remote/events':
        return events(handler, runtime)
    try:
        if path == '/api/remote/devices':
            if not access.is_loopback(handler.client_address[0]): return handler.send_json({'ok': False, 'error': 'Beheer apparaten op de lichtkrant-pc'}, 403)
            return handler.send_json({'ok': True, 'devices': access.list_devices()})
        if path == '/api/remote/history':
            return handler.send_json({'ok': True, 'points': dash.history_view()})
        if path == '/api/remote/restore-preview':
            return handler.send_json({'ok': True, 'preview': dash.restore_preview(value('id'))})
        if path == '/api/remote/preview':
            with dash.lock:
                row = dash.previews.get(value('client_id'))
                data = {k: v for k, v in row.items() if k != 'captured_monotonic'} if row else None
            return handler.send_json({'ok': True, 'preview': data})
        if path == '/api/remote/map':
            rows = runtime.query_messages(state, {'id': [value('id')[:240]], 'limit': ['1']})
            if not rows: raise ValueError('Melding niet gevonden')
            message = rows[0]
            return handler.send_json({'ok': True, 'map': state.geocode_incident(message.get('city', ''), message.get('location', ''), 14)})
        if path == '/api/remote/archive':
            query = {k: [value(k)[:240]] for k in ('q', 'city', 'service', 'priority') if value(k)}
            for key in ('since', 'until'):
                if value(key):
                    # A timestamp must include a timezone; the UI supplies UTC.
                    parsed_date = datetime.fromisoformat(value(key).replace('Z', '+00:00'))
                    if parsed_date.tzinfo is None: raise ValueError('Datum moet een tijdzone bevatten')
                    query[key] = [parsed_date.isoformat()]
            if value('cursor'):
                decoded = json.loads(base64.urlsafe_b64decode(value('cursor')[:2048]).decode())
                if not isinstance(decoded, list) or len(decoded) != 2 or not all(isinstance(x, str) and len(x) < 300 for x in decoded):
                    raise ValueError('Ongeldige archiefcursor')
                query['before_published'], query['before_id'] = [decoded[0]], [decoded[1]]
            query.update(limit=['51'], archive=['1'])
            rows = runtime.query_messages(state, query)
            cursor = base64.urlsafe_b64encode(json.dumps([rows[49]['published'], rows[49]['id']]).encode()).decode() if len(rows) > 50 else None
            return handler.send_json({'ok': True, 'messages': rows[:50], 'next_cursor': cursor})
        if path == '/api/remote/command':
            return handler.send_json({'ok': True, 'commands': dash.commands()})
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        return handler.send_json({'ok': False, 'error': str(exc)}, 400)
    except (OSError, RuntimeError) as exc:
        return handler.send_json({'ok': False, 'error': str(exc)}, 503)
    return handler.send_json({'ok': False, 'error': 'Onbekende dashboardfunctie'}, 404)


def post(handler, path, payload, runtime):
    state, access = handler.state, runtime._REMOTE_ACCESS
    dash = state.dashboard
    if path.startswith('/api/remote/studio/'):
        return runtime.studio_api.handle(handler, path, payload)
    try:
        if path in {'/api/remote/invite', '/api/remote/revoke'}:
            if not access.is_loopback(handler.client_address[0]):
                return handler.send_json({'ok': False, 'error': 'Beheer apparaten op de lichtkrant-pc'}, 403)
            if path.endswith('/invite'):
                return handler.send_json({'ok': True, 'invite': access.invite(payload.get('name', 'Telefoon'), payload.get('role', 'controller'))})
            access.revoke(str(payload.get('id', '')))
            dash.notify()
            return handler.send_json({'ok': True})
        if path == '/api/remote/profile':
            return handler.send_json({'ok': True, 'settings': dash.profile(str(payload.get('id', '')))})
        if path == '/api/remote/apply-standard':
            return handler.send_json({'ok': True, **dash.apply_standard(str(payload.get('kind', '')))})
        if path == '/api/remote/checkpoint':
            with state.config_lock:
                point_id = dash.checkpoint(payload.get('description', 'Handmatig herstelpunt'), state.get_display_settings())
            return handler.send_json({'ok': True, 'id': point_id})
        if path == '/api/remote/restore':
            return handler.send_json({'ok': True, 'settings': dash.restore(str(payload.get('id', '')), payload.get('expected'))})
        if path == '/api/remote/receipt':
            dash.receipt(payload)
            return handler.send_json({'ok': True})
        if path == '/api/remote/preview':
            dash.preview(payload)
            return handler.send_json({'ok': True})
        if path == '/api/remote/message-action':
            action = payload.get('action')
            if action not in {'pin', 'unpin', 'replay'}: raise ValueError('Onbekende meldingsactie')
            message = {}
            if action != 'unpin':
                rows = runtime.query_messages(state, {'id': [str(payload.get('id', ''))[:240]], 'limit': ['1']})
                if not rows: raise ValueError('Melding niet gevonden')
                message = rows[0]
            target = str(payload.get('client_id', ''))[:120]
            if target and not any(x['client_id'] == target and x['online'] for x in state.display_clients_view()):
                raise ValueError('Het gekozen scherm is niet verbonden')
            count, seq = state.publish_display_command({'type': 'remote-message', 'action': action, 'message': message, 'target_client_id': target, 'speak': action == 'replay', 'duration_ms': 300000})
            return handler.send_json({'ok': True, 'command_seq': seq, 'queued': count == 0})
    except (ValueError, TypeError) as exc:
        return handler.send_json({'ok': False, 'error': str(exc)}, 400)
    except OSError:
        return handler.send_json({'ok': False, 'error': 'Opslaan mislukt; controleer vrije schijfruimte en schrijfrechten'}, 500)
    return handler.send_json({'ok': False, 'error': 'Onbekende dashboardfunctie'}, 404)


def events(handler, runtime):
    """Separate stream: phones never count as screens. Coalesce bursts to 1 Hz."""
    dash = handler.state.dashboard
    with dash.lock:
        if dash.streams >= 20:
            return handler.send_json({'ok': False, 'error': 'Te veel open bedienpanelen'}, 429)
        dash.streams += 1
    try:
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        handler.send_header('Cache-Control', 'no-store, no-transform')
        handler.send_header('X-Accel-Buffering', 'no')
        handler.end_headers()
        revision, last_sent, last_heartbeat = -1, 0.0, 0.0
        while not handler.state.stop_event.is_set():
            if not runtime._REMOTE_ACCESS.permitted(handler, '/api/remote/events', 'GET'):
                handler.wfile.write(b'event: revoked\ndata: {}\n\n'); handler.wfile.flush(); break
            now = time.monotonic()
            with dash.changed:
                current = dash.revision
            if (current != revision and now - last_sent >= 1) or now - last_sent >= 10:
                data = dash.snapshot(runtime)
                handler.wfile.write(('data: ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n\n').encode())
                handler.wfile.flush()
                revision, last_sent, last_heartbeat = current, now, now
            elif now - last_heartbeat >= 10:
                handler.wfile.write(b': heartbeat\n\n'); handler.wfile.flush(); last_heartbeat = now
            with dash.changed:
                dash.changed.wait(timeout=1)
    except (OSError, ValueError):
        pass
    finally:
        with dash.lock: dash.streams -= 1
        handler.close_connection = True
