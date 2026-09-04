#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import socket
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks: list[str] = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    checks.append(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = load("p2000_runtime_probe_v4412", ROOT / "tools" / "runtime_probe.py")
desktop = load("p2000_linux_desktop_v4412", ROOT / "tools" / "linux_desktop.py")
supervisor = load("p2000_supervisor_v4412", ROOT / "tools" / "supervisor.py")
server = load("p2000_server_v4412", ROOT / "backend" / "server.py")

version = tuple(int(x) for x in (ROOT / "VERSION").read_text().strip().split("."))
check(version >= (4, 4, 12), "version is 4.4.12+")

# A hung backend must still be recoverable when /api/runtime does not answer.
old_cmdline = probe._proc_cmdline
old_runtime = probe.runtime
old_listener_pids = probe.listener_pids
old_terminate = probe.terminate_pids
try:
    backend_path = str((ROOT / "backend" / "server.py").resolve())
    probe._proc_cmdline = lambda pid: f'python "{backend_path}"'
    check(probe._is_this_p2000_backend(321), "exact backend command line is recognized")
    probe._proc_cmdline = lambda pid: "python unrelated/server.py"
    check(not probe._is_this_p2000_backend(321), "unrelated listener is rejected")
    stopped = []
    probe.runtime = lambda: None
    probe.listener_pids = lambda: {321}
    probe._is_this_p2000_backend = lambda pid: pid == 321
    probe.terminate_pids = lambda pids: stopped.append(set(pids)) or True
    check(probe.stop_any() and stopped == [{321}], "unresponsive P2000 listener is stopped safely")
finally:
    probe._proc_cmdline = old_cmdline
    probe.runtime = old_runtime
    probe.listener_pids = old_listener_pids
    probe.terminate_pids = old_terminate

# Kiosk shutdown must not close the settings/control browser profile.
kiosk_cmd = "chromium --user-data-dir=/home/u/.config/p2000-monitor/browser-chromium-kiosk --kiosk http://127.0.0.1:8765/"
control_cmd = "chromium --user-data-dir=/home/u/.config/p2000-monitor/browser-chromium-control --new-window http://127.0.0.1:8765/control"
firefox_cmd = "firefox --profile /home/u/.config/p2000-monitor/browser-firefox-kiosk --kiosk http://127.0.0.1:8765/"
check(desktop._is_p2000_kiosk_cmd(kiosk_cmd), "Chromium kiosk profile is recognized")
check(desktop._is_p2000_kiosk_cmd(firefox_cmd), "Firefox kiosk profile is recognized")
check(not desktop._is_p2000_kiosk_cmd(control_cmd), "control browser is excluded from kiosk shutdown")

with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    (td_path / "browser.pid").write_text("111", encoding="ascii")
    old_runtime_dir = desktop.runtime_dir
    old_rows = desktop._proc_cmdlines
    old_kill = desktop.os.kill
    old_sleep = desktop.time.sleep
    signals = []
    try:
        desktop.runtime_dir = lambda explicit="": td_path
        desktop._proc_cmdlines = lambda: iter(((111, control_cmd), (222, kiosk_cmd)))
        desktop.os.kill = lambda pid, sig: signals.append((pid, sig))
        desktop.time.sleep = lambda seconds: None
        desktop.stop_kiosk(str(td_path))
        check(all(pid == 222 for pid, _ in signals), "stale/control PID is never killed")
    finally:
        desktop.runtime_dir = old_runtime_dir
        desktop._proc_cmdlines = old_rows
        desktop.os.kill = old_kill
        desktop.time.sleep = old_sleep

# Browser success is reported only after the complete survival probe.
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    candidate = desktop.Candidate("fake-browser", "chromium", "Fake", ["fake-browser"])
    elapsed = {"value": 0.0}

    class FakeProc:
        pid = 9876

        @staticmethod
        def poll():
            return None

    old_popen = desktop.subprocess.Popen
    old_matching = desktop.matching_pids
    old_mono = desktop.time.monotonic
    old_sleep = desktop.time.sleep
    old_log_dir = desktop.LOG_DIR
    try:
        desktop.subprocess.Popen = lambda *a, **k: FakeProc()
        desktop.matching_pids = lambda *a, **k: []
        desktop.time.monotonic = lambda: elapsed["value"]
        desktop.time.sleep = lambda seconds: elapsed.__setitem__("value", elapsed["value"] + seconds)
        desktop.LOG_DIR = td_path
        ok, _ = desktop._launch(candidate, td_path / "profile-kiosk", "http://127.0.0.1:8765/", True, "0,0", "800,600", 1.2, td_path, td_path / "browser.log")
        check(ok and elapsed["value"] >= 1.2, "browser survives the full startup probe")
    finally:
        desktop.subprocess.Popen = old_popen
        desktop.matching_pids = old_matching
        desktop.time.monotonic = old_mono
        desktop.time.sleep = old_sleep
        desktop.LOG_DIR = old_log_dir

# A recycled PID from a stale supervisor.pid may not block startup or be killed.
old_process_cmdline = supervisor.process_cmdline
try:
    supervisor.process_cmdline = lambda pid: "python unrelated_service.py"
    check(not supervisor.pid_is_this_supervisor(444), "recycled supervisor PID is rejected")
finally:
    supervisor.process_cmdline = old_process_cmdline

# Parallel PATCH-like settings saves must execute as one read/merge/write unit.
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    old_db = server.DB_PATH
    old_tune_dir = server.TUNE_DIR
    old_tune_settings = server.TUNE_SETTINGS_PATH
    try:
        server.DB_PATH = td_path / "settings.sqlite3"
        server.TUNE_DIR = td_path / "tunes"
        server.TUNE_SETTINGS_PATH = server.TUNE_DIR / "settings.json"
        state = server.AppState({})
        state.init_db()
        original_read = state._read_display_settings_db
        counter_lock = threading.Lock()
        active = {"now": 0, "max": 0}

        def slow_read():
            with counter_lock:
                active["now"] += 1
                active["max"] = max(active["max"], active["now"])
            time.sleep(0.04)
            try:
                return original_read()
            finally:
                with counter_lock:
                    active["now"] -= 1

        state._read_display_settings_db = slow_read
        start = threading.Barrier(3)
        errors = []

        def save(payload):
            start.wait()
            try:
                state.save_display_settings(payload)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=save, args=({"name": "Post Noord"},)), threading.Thread(target=save, args=({"masterVolume": 47},))]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(3)
        saved = state.get_display_settings()
        check(not errors and active["max"] == 1, "settings read/merge/write transactions do not overlap")
        check(saved.get("name") == "Post Noord" and saved.get("masterVolume") == 47, "parallel partial settings saves preserve both fields")
    finally:
        server.DB_PATH = old_db
        server.TUNE_DIR = old_tune_dir
        server.TUNE_SETTINGS_PATH = old_tune_settings

# Identical concurrent online TTS cache misses must make one render and both win.
with tempfile.TemporaryDirectory() as td:
    old_cache = server.TTS_CACHE_DIR
    old_gtts = sys.modules.get("gtts")
    calls = []

    class FakeGtts:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def write_to_fp(self, fp):
            time.sleep(0.08)
            fp.write(b"I" * 256)

    try:
        server.TTS_CACHE_DIR = Path(td)
        sys.modules["gtts"] = types.SimpleNamespace(gTTS=FakeGtts)
        results = []
        errors = []

        def render():
            try:
                results.append(server.generate_online_tts("Gelijktijdige testmelding"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=render) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)
        check(not errors and len(results) == 2 and results[0] == results[1], "concurrent TTS requests both succeed")
        check(len(calls) == 1, "concurrent identical TTS is rendered once")
    finally:
        server.TTS_CACHE_DIR = old_cache
        if old_gtts is None:
            sys.modules.pop("gtts", None)
        else:
            sys.modules["gtts"] = old_gtts

# Accepted client sockets receive a finite timeout against slow/stalled bodies.
httpd = server.QuietThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
client = socket.create_connection(httpd.server_address, timeout=2)
accepted = None
try:
    accepted, _ = httpd.get_request()
    check(accepted.gettimeout() == server.QuietThreadingHTTPServer.client_timeout_seconds, "HTTP clients have a finite socket timeout")
finally:
    client.close()
    if accepted is not None:
        accepted.close()
    httpd.server_close()

app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
control = (ROOT / "frontend" / "control.js").read_text(encoding="utf-8")
start_win = (ROOT / "START_P2000.bat").read_text(encoding="utf-8")
stop_win = (ROOT / "STOP_P2000.bat").read_text(encoding="utf-8")
stop_linux = (ROOT / "STOP_P2000.sh").read_text(encoding="utf-8")
autostart = (ROOT / "START_P2000_AUTOSTART.sh").read_text(encoding="utf-8")

check("AbortController" in app and "timeoutMs=12000" in app and "monitorRuntimePromise" in app and "refreshPromise" in app, "kiosk HTTP calls are bounded and deduplicated")
check("AbortController" in control and "timeoutMs=12000" in control and "timeoutMs:install?120000:45000" in control, "control HTTP calls have bounded operation-specific timeouts")
check(start_win.count(":ensure_backend") >= 2 and "--wait 18" in start_win and ":any_kiosk_running" in start_win, "Windows launcher retries backend without replacing a healthy kiosk")
check("supervisor.py\" --stop" in stop_win and "Stop-Process -Id $id" not in stop_win, "Windows stop rejects stale supervisor PID files")
check('kill "$spid"' not in stop_linux and "control-browser.pid" not in stop_linux, "Linux stop rejects stale/control PID files")
loop = autostart[autostart.index("for ((waited="):autostart.index("sleep \"${P2000_AUTOSTART_DELAY")]
check("hydrate_graphics_env" in loop, "Linux autostart rehydrates graphics environment while waiting")
check("with self.config_lock:" in server.AppState.save_display_settings.__code__.co_consts or "_save_display_settings_locked" in (ROOT / "backend" / "server.py").read_text(), "settings save is serialized")

print(f"v4.4.12 stability tests: {len(checks)}/{len(checks)} OK")
