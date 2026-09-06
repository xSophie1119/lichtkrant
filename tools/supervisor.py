#!/usr/bin/env python3
"""Cross-platform P2000 supervisor/watchdog.

Keeps the backend and dedicated kiosk alive, consumes control-page restart
commands, and performs automatic rollback when a freshly installed build never
becomes healthy. Browser lifecycle is delegated to the platform desktop helpers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UPDATES = DATA / "updates"
STATUS = DATA / "supervisor-status.json"
COMMAND = DATA / "supervisor-command.json"
PIDFILE = DATA / "supervisor.pid"
LOCKFILE = DATA / "supervisor.lock"
PENDING = UPDATES / "pending-health.json"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "4.5.6"
LOG = DATA / "supervisor.log"
_explicit_runtime = os.environ.get("P2000_RUNTIME_DIR")
_runtime_env = os.environ.get("XDG_RUNTIME_DIR")
_runtime_base = Path(_runtime_env) if _runtime_env else Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "p2000-monitor" / "runtime"
if _runtime_env and (not _runtime_base.exists() or not os.access(_runtime_base, os.W_OK | os.X_OK)):
    _runtime_base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "p2000-monitor" / "runtime"
RUNDIR = Path(_explicit_runtime) if _explicit_runtime else _runtime_base / f"p2000-monitor-{getattr(os, 'getuid', lambda: 0)()}"
STARTED = time.monotonic()
INSTALL_ID = hashlib.sha256(os.path.realpath(str(ROOT)).encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    line = f"[{now_iso()}] {message}"
    print(line, flush=True)
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            rotated = LOG.with_suffix(".log.1")
            rotated.unlink(missing_ok=True)
            LOG.replace(rotated)
        with LOG.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        pass


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def process_cmdline(pid: int) -> str:
    try:
        if pid <= 0:
            return ""
        if os.name == "nt":
            ps = (
                f'$p=Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" '
                '-ErrorAction SilentlyContinue; if($p.CommandLine){[Console]::Out.Write($p.CommandLine)}'
            )
            cp = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return cp.stdout.strip() if cp.returncode == 0 else ""
        return (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except Exception:
        return ""


def pid_is_this_supervisor(pid: int) -> bool:
    cmd = process_cmdline(pid)
    if not cmd:
        return False
    expected = str((ROOT / "tools" / "supervisor.py").resolve()).replace("\\", "/")
    normalized = cmd.replace("\\", "/")
    if os.name == "nt":
        expected = expected.casefold()
        normalized = normalized.casefold()
    return expected in normalized


def existing_supervisor() -> int:
    try:
        pid = int(PIDFILE.read_text(encoding="ascii").strip())
    except Exception:
        return 0
    return pid if pid != os.getpid() and pid_is_this_supervisor(pid) else 0


_SUPERVISOR_LOCK_HANDLE = None


def claim_pidfile() -> int:
    global _SUPERVISOR_LOCK_HANDLE
    DATA.mkdir(parents=True, exist_ok=True)
    handle = LOCKFILE.open("a+b")
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError):
        handle.close()
        return existing_supervisor() or -1
    _SUPERVISOR_LOCK_HANDLE = handle
    tmp = PIDFILE.with_name(f"{PIDFILE.name}.{os.getpid()}.tmp")
    tmp.write_text(str(os.getpid()), encoding="ascii")
    os.replace(tmp, PIDFILE)
    if os.name != "nt":
        try:
            os.chmod(PIDFILE, 0o600)
        except OSError:
            pass
    return 0


def release_pidfile() -> None:
    global _SUPERVISOR_LOCK_HANDLE
    try:
        if PIDFILE.exists() and PIDFILE.read_text(encoding="ascii").strip() == str(os.getpid()):
            PIDFILE.unlink()
    except OSError:
        pass
    handle = _SUPERVISOR_LOCK_HANDLE
    _SUPERVISOR_LOCK_HANDLE = None
    if not handle:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, ImportError):
        pass
    try:
        handle.close()
    except OSError:
        pass


def stop_supervisor() -> bool:
    try:
        pid = int(PIDFILE.read_text(encoding="ascii").strip())
    except Exception:
        return True
    if pid <= 1 or pid == os.getpid() or not pid_is_this_supervisor(pid):
        try:
            PIDFILE.unlink()
        except OSError:
            pass
        return True
    try:
        if os.name == "nt":
            cp = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ok = cp.returncode == 0
        else:
            os.kill(pid, signal.SIGTERM)
            ok = True
            end = time.monotonic() + 3
            while time.monotonic() < end and process_cmdline(pid):
                time.sleep(.1)
            if process_cmdline(pid):
                os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        ok = True
    except Exception:
        ok = False
    if ok:
        try:
            PIDFILE.unlink()
        except OSError:
            pass
    return ok


def api(path: str, timeout: float = 1.2):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:8765{path}", headers={"User-Agent": "P2000-Supervisor/4.5.6"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return None


def iso_age(value) -> float:
    if not value:
        return 10**9
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return 10**9


def runtime_probe(*args: str, timeout: float = 12) -> int:
    try:
        cp = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "runtime_probe.py"), *args],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return cp.returncode
    except Exception:
        return 2


def terminate_backend() -> None:
    runtime_probe("--stop", timeout=12)


def start_backend() -> bool:
    env = os.environ.copy()
    env["P2000_SUPERVISED"] = "1"
    if os.name == "nt":
        cmd = ["cmd.exe", "/c", str(ROOT / "RUN_BACKEND.bat")]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        cmd = ["bash", str(ROOT / "RUN_BACKEND.sh")]
        flags = 0
    try:
        with LOG.open("a", encoding="utf-8") as out:
            subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                start_new_session=(os.name != "nt"),
            )
    except Exception as exc:
        log(f"Backendlauncher kon niet starten: {exc}")
        return False
    end = time.monotonic() + 18
    while time.monotonic() < end:
        row = api("/api/runtime", 1)
        if row and row.get("app") == "P2000 Monitor" and str(row.get("version")) == VERSION and str(row.get("install_id") or "") == INSTALL_ID:
            return True
        time.sleep(.5)
    return False


def _desktop_helper() -> Path:
    return ROOT / "tools" / ("windows_desktop.py" if os.name == "nt" else "linux_desktop.py")


def kill_kiosk() -> None:
    helper = _desktop_helper()
    if not helper.is_file():
        return
    args = [sys.executable, str(helper), "stop-kiosk"]
    if os.name != "nt":
        args += ["--rundir", str(RUNDIR)]
    try:
        subprocess.run(args, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def start_kiosk() -> bool:
    env = os.environ.copy()
    env["P2000_SUPERVISED"] = "1"
    if os.name == "nt":
        cmd = ["cmd.exe", "/c", str(ROOT / "START_P2000.bat")]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        cmd = ["bash", str(ROOT / "START_P2000.sh")]
        flags = 0
    try:
        with LOG.open("a", encoding="utf-8") as out:
            subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, creationflags=flags, start_new_session=(os.name != "nt"))
        return True
    except Exception as exc:
        log(f"Kiosklauncher kon niet starten: {exc}")
        return False


def kiosk_process_alive():
    helper = _desktop_helper()
    if not helper.is_file():
        return None
    args = [sys.executable, str(helper), "status" if os.name == "nt" else "kiosk-status"]
    if os.name != "nt":
        args += ["--rundir", str(RUNDIR)]
    try:
        cp = subprocess.run(args, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return cp.returncode == 0
    except Exception:
        return None


def restart_budget_available(history: list[float], now: float, limit: int = 3, window_seconds: int = 900) -> bool:
    history[:] = [value for value in history if now - value < window_seconds]
    return len(history) < limit


def kiosk_missing_evidence(missing_hits: int, probe_fresh: bool, process_alive, heartbeat_age: float, sse_clients: int = 0, required_probes: int = 3):
    if heartbeat_age < 90 or int(sse_clients or 0) > 0:
        return 0, False
    if not probe_fresh:
        return missing_hits, False
    missing_hits = missing_hits + 1 if process_alive is False else 0
    return missing_hits, missing_hits >= required_probes


def rollback_if_pending() -> bool:
    if not PENDING.exists():
        return False
    meta = read_json(PENDING, {})
    age = iso_age(meta.get("started_at") or meta.get("created_at"))
    if age > 900:
        try:
            PENDING.unlink()
        except Exception:
            pass
        return False
    log(f"Nieuwe build bleef ongezond; automatische rollback ({meta.get('target_version', '?')}).")
    try:
        cp = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "rollback_latest.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        log((cp.stdout or cp.stderr or "").strip()[-1200:])
        try:
            PENDING.unlink()
        except Exception:
            pass
        return cp.returncode == 0
    except Exception as exc:
        log(f"Rollback fout: {exc}")
        return False


def selected_display_state(display) -> tuple[str, bool, tuple[int, int, int, int]]:
    try:
        row = (display or {}).get("display", {}) or {}
        monitor = row.get("selected_monitor", {}) or {}
        selector = str(row.get("selected_monitor_id") or monitor.get("selector") or monitor.get("device") or "")
        connected = bool(row.get("selection_connected", row.get("connected", False)))
        geometry = (int(monitor.get("x", 0)), int(monitor.get("y", 0)), int(monitor.get("width", 0)), int(monitor.get("height", 0)))
        return selector, connected, geometry
    except Exception:
        return "", False, (0, 0, 0, 0)


def consume_command() -> str:
    if not COMMAND.exists():
        return ""
    obj = read_json(COMMAND, {})
    try:
        COMMAND.unlink()
    except Exception:
        pass
    return str(obj.get("action") or obj.get("command") or "").strip().lower()


def status_is_fresh(row: dict, max_age: float = 15.0) -> bool:
    return str(row.get("version") or "") == VERSION and iso_age(row.get("heartbeat_at")) <= max_age


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-kiosk", action="store_true")
    args = ap.parse_args()

    if args.stop:
        return 0 if stop_supervisor() else 2
    RUNDIR.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(RUNDIR, 0o700)
        except OSError:
            pass

    old = existing_supervisor()
    if args.status:
        if not old:
            return 1
        return 0 if status_is_fresh(read_json(STATUS, {})) else 2

    old = old or claim_pidfile()
    if old:
        print("P2000 supervisor draait al" + (f" (PID {old})." if old > 0 else " of wordt al gestart."))
        return 0

    counters = {"backend_restarts": 0, "kiosk_restarts": 0, "rollbacks": 0}
    state = "starting"
    last_action = ""
    last_error = ""
    backend_failures = 0
    backend_unhealthy_since = 0.0
    backend_restart_times: list[float] = []
    kiosk_missing_hits = 0
    kiosk_restart_times: list[float] = []
    last_kiosk_restart = 0.0
    kiosk_grace_until = STARTED + 150
    setup_was_incomplete = False
    setup_completed_grace_until = 0.0
    last_display_report = ""
    last_selector = ""
    health = {}
    health_checked = 0.0
    setup_row = {}
    setup_checked = 0.0
    display = {}
    display_checked = 0.0
    kiosk_alive = None
    kiosk_checked = 0.0

    log(f"P2000 supervisor v{VERSION} gestart (PID {os.getpid()}).")
    try:
        while True:
            command = consume_command()
            if command == "restart-backend":
                last_action = "Backend handmatig herstart"
                log(last_action)
                terminate_backend()
                time.sleep(.4)
                start_backend()
                counters["backend_restarts"] += 1
                backend_failures = 0
                backend_unhealthy_since = 0.0
            elif command == "restart-kiosk" and not args.no_kiosk:
                last_action = "Kiosk handmatig herstart"
                log(last_action)
                kill_kiosk()
                time.sleep(.4)
                start_kiosk()
                counters["kiosk_restarts"] += 1
                last_kiosk_restart = time.monotonic()
                kiosk_grace_until = last_kiosk_restart + 150
                kiosk_missing_hits = 0

            loop_now = time.monotonic()
            runtime = api("/api/runtime", 2.0)
            backend_ok = bool(runtime and runtime.get("app") == "P2000 Monitor" and str(runtime.get("version")) == VERSION and str(runtime.get("install_id") or "") == INSTALL_ID)
            if backend_ok and (not health or loop_now - health_checked >= 10):
                fresh = api("/api/health", 1.2)
                if fresh:
                    health = fresh
                    health_checked = loop_now
            if backend_ok:
                backend_failures = 0
                backend_unhealthy_since = 0.0
                state = "healthy"
                last_error = ""
            else:
                backend_failures += 1
                if not backend_unhealthy_since:
                    backend_unhealthy_since = loop_now
                unhealthy_for = max(0, loop_now - backend_unhealthy_since)
                state = "backend-unhealthy"
                last_error = f"Backend runtimecheck mislukt ({backend_failures}/5, {unhealthy_for:.0f}s)"

            if backend_failures >= 5 and loop_now - backend_unhealthy_since >= 20:
                if restart_budget_available(backend_restart_times, loop_now, 3, 600):
                    rolled = rollback_if_pending()
                    if rolled:
                        counters["rollbacks"] += 1
                    terminate_backend()
                    time.sleep(.5)
                    ok = start_backend()
                    backend_restart_times.append(time.monotonic())
                    counters["backend_restarts"] += 1
                    last_action = "Rollback + backend herstart" if rolled else "Backend automatisch herstart"
                    log(f"{last_action}: {'OK' if ok else 'MISLUKT'}")
                    backend_failures = 0
                    backend_unhealthy_since = 0.0
                    backend_ok = ok
                else:
                    state = "backend-restart-paused"
                    last_error = "Automatische backendherstart gepauzeerd: 3 pogingen in 10 minuten"
                    backend_failures = 4

            kiosk_age = 10**9
            selector = ""
            display_connected = False
            if backend_ok:
                if not setup_row or loop_now - setup_checked >= 10:
                    setup_row = api("/api/setup", 1.0) or setup_row or {}
                    setup_checked = loop_now
                setup_complete = bool((setup_row.get("setup") or {}).get("setup_complete"))
                if not setup_complete:
                    setup_was_incomplete = True
                    kiosk_missing_hits = 0
                    state = "setup-required"
                else:
                    if setup_was_incomplete:
                        setup_was_incomplete = False
                        setup_completed_grace_until = time.monotonic() + 150
                        kiosk_missing_hits = 0
                        last_action = "Configuratiewizard afgerond; kiosk krijgt 150s opstartgrace"
                        log(last_action)
                    h = (health or {}).get("health") or {}
                    display_report = str((h.get("display_client") or {}).get("reported_at") or "")
                    kiosk_age = iso_age(display_report)
                    if display_report and display_report != last_display_report:
                        last_display_report = display_report
                        if kiosk_age < 75:
                            kiosk_missing_hits = 0
                    display_probe_fresh = False
                    if not display or loop_now - display_checked >= 15:
                        display = api("/api/display/info", 1.5) or display or {}
                        display_checked = loop_now
                        display_probe_fresh = True
                    kiosk_probe_fresh = False
                    if kiosk_alive is None or loop_now - kiosk_checked >= 15:
                        kiosk_alive = kiosk_process_alive()
                        kiosk_checked = loop_now
                        kiosk_probe_fresh = True
                    selector, display_connected, _geometry = selected_display_state(display)
                    if display_probe_fresh and selector:
                        last_selector = selector
                    grace = max(kiosk_grace_until, setup_completed_grace_until)
                    sse_clients = int(h.get("sse_clients") or 0)
                    eligible = display_connected and time.monotonic() > grace
                    kiosk_missing_hits, should_restart = kiosk_missing_evidence(kiosk_missing_hits, kiosk_probe_fresh and eligible, kiosk_alive, kiosk_age, sse_clients)
                    if should_restart and not args.no_kiosk and time.monotonic() - last_kiosk_restart > 90:
                        now = time.monotonic()
                        if restart_budget_available(kiosk_restart_times, now):
                            last_action = "Kioskproces ontbreekt volgens 3 losse controles; browser automatisch herstart"
                            log(last_action)
                            kill_kiosk()
                            time.sleep(.3)
                            start_kiosk()
                            counters["kiosk_restarts"] += 1
                            last_kiosk_restart = time.monotonic()
                            kiosk_restart_times.append(last_kiosk_restart)
                            kiosk_grace_until = last_kiosk_restart + 150
                            kiosk_missing_hits = 0
                            kiosk_alive = None
                        else:
                            state = "kiosk-restart-paused"
                            last_error = "Automatische kioskherstart gepauzeerd: 3 pogingen in 15 minuten"
                            kiosk_missing_hits = 0

            write_json(
                STATUS,
                {
                    "version": VERSION,
                    "pid": os.getpid(),
                    "heartbeat_at": now_iso(),
                    "state": state,
                    "backend_ok": backend_ok,
                    "kiosk_heartbeat_age_seconds": None if kiosk_age >= 10**8 else round(kiosk_age, 1),
                    "kiosk_process_alive": kiosk_alive,
                    "display_selector": selector or last_selector,
                    "display_connected": display_connected,
                    **counters,
                    "last_action": last_action,
                    "last_error": last_error,
                },
            )
            if args.once:
                return 0 if backend_ok else 2
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
    finally:
        release_pidfile()


if __name__ == "__main__":
    raise SystemExit(main())
