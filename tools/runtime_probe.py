#!/usr/bin/env python3
"""Small Windows launcher helper for P2000 Monitor.

Used by the .bat launchers so startup does not depend on PowerShell for
HTTP health checks or replacing an older P2000 backend on port 8765.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8765/api/runtime"
PORT = "8765"


def runtime(timeout: float = 0.8) -> dict | None:
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "P2000-Launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", "replace"))
    except Exception:
        return None


def is_current(expected: str) -> bool:
    obj = runtime()
    return bool(obj and obj.get("app") == "P2000 Monitor" and str(obj.get("version")) == expected)


def listener_pids() -> set[int]:
    """Return Windows PIDs that have local TCP port 8765 open.

    Parsing does not depend on the localized LISTENING state label. We only
    inspect the local-address column and numeric PID at the end of each row.
    """
    try:
        cp = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return set()
    result: set[int] = set()
    for raw in cp.stdout.splitlines():
        parts = raw.split()
        if len(parts) < 4 or parts[0].upper() != "TCP":
            continue
        local = parts[1]
        pid_text = parts[-1]
        if not (local.endswith(":" + PORT) and pid_text.isdigit()):
            continue
        pid = int(pid_text)
        if pid > 0:
            result.add(pid)
    return result


def kill_stale(expected: str) -> bool:
    obj = runtime()
    if not obj or obj.get("app") != "P2000 Monitor":
        return True
    if str(obj.get("version")) == expected:
        return True
    pids = listener_pids()
    if not pids:
        print(f"Oud P2000-proces gevonden ({obj.get('version')}), maar PID op poort 8765 kon niet worden bepaald.")
        return False
    ok = True
    for pid in sorted(pids):
        try:
            cp = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ok = ok and cp.returncode == 0
        except Exception:
            ok = False
    time.sleep(0.4)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--wait", type=float, default=0.0)
    ap.add_argument("--kill-stale", action="store_true")
    args = ap.parse_args()

    if args.kill_stale and not kill_stale(args.version):
        return 3
    if args.wait > 0:
        end = time.monotonic() + args.wait
        while time.monotonic() < end:
            if is_current(args.version):
                return 0
            time.sleep(0.30)
        return 1
    return 0 if is_current(args.version) else 1


if __name__ == "__main__":
    raise SystemExit(main())
