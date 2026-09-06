#!/usr/bin/env python3
"""Cross-platform lifecycle probe for P2000 Monitor.

The probe is deliberately conservative: it only terminates Python processes whose
command line resolves to a project containing VERSION, backend/server.py and
frontend/index.html. It never uses broad process-name kills.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8765/api/runtime"
PORT = "8765"
INSTALL_ID = hashlib.sha256(os.path.realpath(str(ROOT)).encode("utf-8")).hexdigest()[:16]
SUPERVISOR_STALE_SECONDS = 15.0


def runtime(timeout: float = .8) -> dict | None:
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "P2000-Launcher/4.5.6"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", "replace"))
    except Exception:
        return None


def is_current(expected: str) -> bool:
    obj = runtime()
    return bool(
        obj
        and obj.get("app") == "P2000 Monitor"
        and str(obj.get("version")) == expected
        and str(obj.get("install_id") or "") == INSTALL_ID
    )


def _run(argv, timeout: float = 8):
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None


def _which(name: str):
    return shutil.which(name)


def _proc_cmdline(pid: int) -> str:
    if pid <= 0:
        return ""
    if os.name == "nt":
        ps = (
            f'$p=Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" '
            '-ErrorAction SilentlyContinue; if($p.CommandLine){[Console]::Out.Write($p.CommandLine)}'
        )
        cp = _run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps])
        if cp and cp.returncode == 0 and cp.stdout.strip():
            return cp.stdout.strip()
        cp = _run(["wmic", "process", "where", f"processid={int(pid)}", "get", "CommandLine", "/value"])
        if cp and cp.returncode == 0:
            for line in cp.stdout.splitlines():
                if line.lower().startswith("commandline="):
                    return line.split("=", 1)[1].strip()
        return ""
    try:
        return (
            (Path("/proc") / str(pid) / "cmdline")
            .read_bytes()
            .replace(b"\x00", b" ")
            .decode("utf-8", "replace")
            .strip()
        )
    except Exception:
        return ""


def _script_path_tokens(cmdline: str, suffix: str) -> list[str]:
    """Extract quoted or bare script paths, including paths containing spaces."""
    if not cmdline:
        return []
    suffix_rx = re.escape(suffix.replace("\\", "/")).replace("/", r"[\\/]")
    rx = re.compile(rf'(?i)(?:"([^"\r\n]*{suffix_rx})"|([^\s"\r\n]*{suffix_rx}))')
    out: list[str] = []
    for quoted, bare in rx.findall(cmdline):
        value = (quoted or bare).strip()
        if value and value not in out:
            out.append(value)
    return out


def _project_root_from_script(token: str, suffix_parts: tuple[str, str]) -> Path | None:
    try:
        script = Path(token).expanduser().resolve()
        if script.name.casefold() != suffix_parts[1].casefold():
            return None
        if script.parent.name.casefold() != suffix_parts[0].casefold():
            return None
        return script.parent.parent
    except Exception:
        return None


def _valid_p2000_root(project: Path | None) -> bool:
    if project is None:
        return False
    try:
        return (
            (project / "VERSION").is_file()
            and (project / "backend" / "server.py").is_file()
            and (project / "frontend" / "index.html").is_file()
        )
    except Exception:
        return False


def _process_project(cmdline: str, kind: str) -> Path | None:
    if kind == "backend":
        suffix, parts = "backend/server.py", ("backend", "server.py")
    elif kind == "supervisor":
        suffix, parts = "tools/supervisor.py", ("tools", "supervisor.py")
    else:
        return None
    for token in _script_path_tokens(cmdline, suffix):
        project = _project_root_from_script(token, parts)
        if _valid_p2000_root(project):
            return project.resolve()
    return None


def _iter_candidate_processes() -> list[tuple[int, str]]:
    me = os.getpid()
    rows: list[tuple[int, str]] = []
    if os.name == "nt":
        ps = (
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object {$_.CommandLine -and ($_.CommandLine -match 'backend[\\\\/]server\\.py' -or "
            "$_.CommandLine -match 'tools[\\\\/]supervisor\\.py')} | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        cp = _run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps], 10)
        if cp and cp.returncode == 0 and cp.stdout.strip():
            try:
                data = json.loads(cp.stdout)
                if not isinstance(data, list):
                    data = [data]
                for row in data:
                    pid = int(row.get("ProcessId") or 0)
                    cmd = str(row.get("CommandLine") or "")
                    if pid > 0 and pid != me:
                        rows.append((pid, cmd))
            except Exception:
                pass
        return rows
    proc = Path("/proc")
    if not proc.is_dir():
        return rows
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me:
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
        except Exception:
            continue
        cmd = _proc_cmdline(pid)
        normalized = cmd.replace("\\", "/").casefold()
        if "backend/server.py" in normalized or "tools/supervisor.py" in normalized:
            rows.append((pid, cmd))
    return rows


def p2000_processes(kind: str) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for pid, cmd in _iter_candidate_processes():
        project = _process_project(cmd, kind)
        if project is not None:
            out[pid] = project
    return out


def _proc_listener_pids(port: str) -> set[int]:
    if os.name == "nt" or not os.path.isdir("/proc"):
        return set()
    try:
        port_hex = f"{int(port):04X}"
    except Exception:
        return set()
    inodes: set[str] = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for line in Path(table).read_text(encoding="ascii", errors="ignore").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 10 and parts[3] == "0A" and parts[1].rsplit(":", 1)[-1].upper() == port_hex:
                    inodes.add(parts[9])
        except Exception:
            pass
    if not inodes:
        return set()
    out: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            for link in (entry / "fd").iterdir():
                try:
                    target = os.readlink(link)
                except OSError:
                    continue
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    out.add(int(entry.name))
                    break
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue
    return out


def listener_pids() -> set[int]:
    if os.name == "nt":
        cp = _run(["netstat", "-ano", "-p", "tcp"])
        result: set[int] = set()
        if not cp:
            return result
        for raw in cp.stdout.splitlines():
            parts = raw.split()
            if len(parts) >= 4 and parts[0].upper() == "TCP" and parts[1].endswith(":" + PORT) and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid > 0:
                    result.add(pid)
        return result
    result: set[int] = set()
    cp = _run(["ss", "-ltnp"]) if _which("ss") else None
    if cp:
        for line in cp.stdout.splitlines():
            if re.search(rf":{PORT}\b", line):
                result.update(int(x) for x in re.findall(r"pid=(\d+)", line))
    if not result and _which("fuser"):
        cp = _run(["fuser", "-n", "tcp", PORT])
        if cp:
            result.update(int(x) for x in re.findall(r"\b\d+\b", cp.stdout + " " + cp.stderr))
    if not result:
        result.update(_proc_listener_pids(PORT))
    return {p for p in result if p > 0}


def describe_pids(pids: set[int]) -> str:
    rows = []
    for pid in sorted(pids):
        cmd = _proc_cmdline(pid)
        rows.append(f"PID {pid}" + (f": {cmd[:260]}" if cmd else ""))
    return "; ".join(rows) if rows else "geen proces gevonden"


def terminate_pids(pids: set[int]) -> bool:
    ok = True
    pids = {int(pid) for pid in pids if int(pid) > 1 and int(pid) != os.getpid()}
    for pid in sorted(pids):
        try:
            if os.name == "nt":
                cp = _run(["taskkill", "/PID", str(pid), "/F"])
                ok = ok and bool((cp and cp.returncode == 0) or not _proc_cmdline(pid))
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except (PermissionError, OSError):
            ok = False
    if os.name != "nt" and pids:
        end = time.monotonic() + 2.5
        alive: list[int] = []
        while time.monotonic() < end:
            alive = []
            for pid in pids:
                try:
                    os.kill(pid, 0)
                    alive.append(pid)
                except OSError:
                    pass
            if not alive:
                break
            time.sleep(.1)
        for pid in alive:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    time.sleep(.15)
    return ok


def _iso_age(value: str) -> float:
    if not value:
        return 10**9
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return 10**9


def _read_supervisor_status(project: Path) -> dict:
    try:
        return json.loads((project / "data" / "supervisor-status.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def reconcile_supervisors(expected: str, preserve_same_healthy: bool = True) -> bool:
    """Stop supervisors from other installs and stale/old supervisors in this one."""
    current_root = ROOT.resolve()
    victims: set[int] = set()
    for pid, project in p2000_processes("supervisor").items():
        project = project.resolve()
        if project != current_root:
            victims.add(pid)
            continue
        if not preserve_same_healthy:
            victims.add(pid)
            continue
        status = _read_supervisor_status(project)
        fresh = _iso_age(str(status.get("heartbeat_at") or "")) <= SUPERVISOR_STALE_SECONDS
        same_version = str(status.get("version") or "") == str(expected or "")
        same_pid = int(status.get("pid") or 0) in (0, pid)
        if not (fresh and same_version and same_pid):
            victims.add(pid)
    if victims:
        print(f"Oude/stale P2000 supervisor(s) stoppen: {', '.join(map(str, sorted(victims)))}")
        return terminate_pids(victims)
    return True


def _backend_processes_to_stop(*, keep_current_listener: bool) -> set[int]:
    all_backends = p2000_processes("backend")
    listeners = listener_pids()
    current_root = ROOT.resolve()
    victims: set[int] = set()
    for pid, project in all_backends.items():
        project = project.resolve()
        if project != current_root:
            victims.add(pid)
        elif not keep_current_listener:
            victims.add(pid)
        elif pid not in listeners:
            # A same-root non-listener can be the v4.5 compatibility parent while
            # a healthy child owns the port. Preserve it only when runtime proves
            # that exact install is already healthy.
            if not is_current((ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").is_file() else ""):
                victims.add(pid)
    return victims


def stop_supervisors(expected: str = "") -> bool:
    return reconcile_supervisors(expected, preserve_same_healthy=False)


def stop_backends_all() -> bool:
    ok = True
    for attempt in range(2):
        victims = set(p2000_processes("backend"))
        if victims:
            print(f"P2000 backendproces(sen) stoppen: {describe_pids(victims)}")
            ok = terminate_pids(victims) and ok
        time.sleep(.2 if attempt == 0 else .05)
    remaining = set(p2000_processes("backend"))
    if remaining:
        print(f"P2000 backendproces(sen) bleven actief: {describe_pids(remaining)}")
        return False
    return ok


def stop_all_p2000() -> bool:
    # Critical ordering: watchdog first, backend second. Otherwise the watchdog
    # can respawn the backend while STOP/rollback is still in progress.
    ok = stop_supervisors("")
    time.sleep(.2)
    ok = stop_backends_all() and ok
    return ok


def kill_stale(expected: str) -> bool:
    # Always reconcile supervisors BEFORE the healthy-backend fast path. This is
    # what prevents two extracted P2000 folders from fighting over port 8765.
    if not reconcile_supervisors(expected, preserve_same_healthy=True):
        return False

    current_ok = is_current(expected)
    backends = p2000_processes("backend")
    listeners = listener_pids()
    current_root = ROOT.resolve()
    victims: set[int] = set()

    for pid, project in backends.items():
        project = project.resolve()
        if project != current_root:
            victims.add(pid)
        elif not current_ok:
            # No healthy same-install runtime: clean both listeners and pre-bind
            # orphan processes before starting a fresh backend.
            victims.add(pid)

    if victims:
        print(f"Oude/orphan P2000 backendproces(sen) stoppen: {describe_pids(victims)}")
        if not terminate_pids(victims):
            return False
        time.sleep(.2)
        listeners = listener_pids()

    if current_ok:
        # A current healthy listener is allowed. Any other non-P2000 listener is
        # reported below only if the runtime stopped being healthy in the meantime.
        return True

    obj = runtime()
    listeners = listener_pids()
    if obj and obj.get("app") == "P2000 Monitor":
        ours = {pid for pid in listeners if pid in p2000_processes("backend")}
        if ours:
            print(f"Oude P2000 backend v{obj.get('version')} op poort 8765 stoppen: {describe_pids(ours)}")
            if not terminate_pids(ours):
                return False
            listeners = listener_pids()
    if not listeners:
        return True

    recognized = set(p2000_processes("backend")) & listeners
    if recognized:
        print(f"Vastgelopen P2000 backend op poort 8765 herstellen: {describe_pids(recognized)}")
        if not terminate_pids(recognized):
            return False
        listeners = listener_pids()
        if not listeners:
            return True

    print(f"Poort 8765 is bezet door een ander proces: {describe_pids(listeners)}")
    return False


def stop_any() -> bool:
    # Safe all-P2000 backend stop. No process is touched unless its command line
    # resolves to a project with the required P2000 markers.
    return stop_backends_all()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="")
    ap.add_argument("--wait", type=float, default=0)
    ap.add_argument("--kill-stale", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--stop-all", action="store_true")
    ap.add_argument("--stop-supervisors", action="store_true")
    ap.add_argument("--describe-port", action="store_true")
    a = ap.parse_args()

    if a.stop_all:
        return 0 if stop_all_p2000() else 2
    if a.stop_supervisors:
        return 0 if stop_supervisors(a.version) else 2
    if a.stop:
        return 0 if stop_any() else 2
    if a.describe_port:
        pids = listener_pids()
        print(describe_pids(pids))
        return 0 if not pids else 1
    if not a.version:
        ap.error("--version is required unless --stop/--stop-all/--stop-supervisors/--describe-port is used")
    if a.kill_stale:
        if not kill_stale(a.version):
            return 3
        if a.wait <= 0:
            return 0
    if a.wait > 0:
        end = time.monotonic() + a.wait
        while time.monotonic() < end:
            if is_current(a.version):
                return 0
            time.sleep(.3)
        return 1
    return 0 if is_current(a.version) else 1


if __name__ == "__main__":
    raise SystemExit(main())
