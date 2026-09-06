#!/usr/bin/env python3
"""Restore the newest P2000 self-update backup on Windows or Linux."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "data" / "updates" / "backups"


def stop_runtime() -> bool:
    """Stop watchdogs before backends so rollback cannot race a respawn."""
    probe = ROOT / "tools" / "runtime_probe.py"
    try:
        cp = subprocess.run(
            [sys.executable, str(probe), "--stop-all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        print(f"[FOUT] Actieve P2000-processen konden niet veilig worden gestopt: {exc}")
        return False
    if cp.returncode != 0:
        detail = (cp.stdout or cp.stderr or "").strip()
        print("[FOUT] Actieve P2000-processen konden niet veilig worden gestopt.")
        if detail:
            print(detail[-1200:])
        return False
    return True


def restore_unix_modes() -> None:
    if os.name == "nt":
        return
    paths = list(ROOT.glob("*.sh")) + [
        ROOT / "tools" / "run_tests.py",
        ROOT / "tools" / "runtime_probe.py",
        ROOT / "tools" / "kiosk_display.py",
        ROOT / "tools" / "linux_desktop.py",
        ROOT / "tools" / "windows_desktop.py",
        ROOT / "tools" / "rollback_latest.py",
        ROOT / "tools" / "supervisor.py",
    ]
    for path in paths:
        try:
            if path.is_file():
                path.chmod(path.stat().st_mode | 0o111)
        except OSError:
            pass


def main() -> int:
    if not BACKUPS.exists():
        print("[FOUT] Er zijn nog geen updatebackups.")
        return 2
    rows = sorted(
        [path for path in BACKUPS.iterdir() if path.is_dir() and (path / "backend" / "server.py").is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not rows:
        print("[FOUT] Geen bruikbare vorige versie gevonden.")
        return 2
    backup = rows[0]
    version = "onbekend"
    try:
        version = str(json.loads((backup / "backup.json").read_text(encoding="utf-8")).get("version") or version)
    except Exception:
        pass
    print(f"[P2000] Vorige programmaversie herstellen: {version}")
    if not stop_runtime():
        return 3

    for src in backup.iterdir():
        if src.name == "backup.json":
            continue
        dst = ROOT / src.name
        if src.is_dir():
            if dst.exists() and dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    restore_unix_modes()
    print(f"[OK] P2000 Monitor {version} is teruggezet. Config en data zijn behouden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
