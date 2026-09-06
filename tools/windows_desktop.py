#!/usr/bin/env python3
"""Dedicated Windows kiosk lifecycle for P2000 Monitor.

Only Chromium processes using a profile below LOCALAPPDATA\\P2000-Monitor and the
local P2000 URL are ever inspected/terminated. Normal Edge/Chrome sessions are
left untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
BASE = LOCALAPPDATA / "P2000-Monitor"
LOGDIR = BASE / "Logs"
LOG = LOGDIR / "browser.log"
LOCK_NAMES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK"}
DEFAULT_URL = "http://127.0.0.1:8765/"


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        LOGDIR.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            rotated = LOG.with_suffix(".log.1")
            try:
                rotated.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                LOG.replace(rotated)
            except OSError:
                pass
        with LOG.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        pass


def _run_ps(script: str, timeout: float = 10):
    try:
        return subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None


def parse_user_data_dir(command_line: str) -> str:
    """Read --user-data-dir even when Windows quotes the complete argument."""
    text = str(command_line or "")
    patterns = (
        r'(?i)"--user-data-dir=([^"\r\n]+)"',
        r'(?i)--user-data-dir="([^"\r\n]+)"',
        r'(?i)--user-data-dir=([^\s"\r\n]+)',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _norm(path: str | Path) -> str:
    try:
        return os.path.normcase(os.path.abspath(os.path.expandvars(str(path))))
    except Exception:
        return os.path.normcase(str(path))


def is_dedicated_profile(path: str | Path) -> bool:
    value = _norm(path)
    base = _norm(BASE)
    try:
        common = os.path.commonpath([value, base])
    except Exception:
        return False
    if common != base:
        return False
    name = Path(value).name.casefold()
    return name.startswith("browserprofile-edge") or name.startswith("browserprofile-chrome") or name.startswith("browserprofile-chromium")


def _process_rows() -> list[dict]:
    if os.name != "nt":
        return []
    ps = (
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object {$_.CommandLine -and $_.CommandLine -match '--user-data-dir'} | "
        "Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    )
    cp = _run_ps(ps)
    if not cp or cp.returncode != 0 or not cp.stdout.strip():
        return []
    try:
        data = json.loads(cp.stdout)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def kiosk_processes(profile: str | Path | None = None) -> list[dict]:
    wanted = _norm(profile) if profile else ""
    rows = []
    for row in _process_rows():
        cmd = str(row.get("CommandLine") or "")
        low = cmd.casefold()
        if "127.0.0.1:8765" not in low and "localhost:8765" not in low:
            continue
        profile_dir = parse_user_data_dir(cmd)
        if not profile_dir or not is_dedicated_profile(profile_dir):
            continue
        if wanted and _norm(profile_dir) != wanted:
            continue
        try:
            pid = int(row.get("ProcessId") or 0)
        except Exception:
            pid = 0
        if pid > 0:
            row = dict(row)
            row["profile"] = profile_dir
            row["pid"] = pid
            rows.append(row)
    return rows


def stop_kiosk() -> bool:
    rows = kiosk_processes()
    if not rows:
        return True
    ok = True
    for row in rows:
        pid = int(row["pid"])
        cp = _run_ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue", 6)
        ok = ok and bool(cp is not None and cp.returncode == 0)
        log(f"Dedicated kiosk PID {pid} gestopt ({row.get('profile')}).")
    return ok


def _browser_candidates(preferred: str = "") -> list[tuple[str, Path]]:
    env = os.environ
    program_files = Path(env.get("ProgramFiles") or r"C:\Program Files")
    program_files_x86 = Path(env.get("ProgramFiles(x86)") or r"C:\Program Files (x86)")
    local = Path(env.get("LOCALAPPDATA") or LOCALAPPDATA)
    candidates = [
        ("edge", program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
        ("edge", program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
        ("chrome", program_files / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ("chrome", program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ("chrome", local / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ("chromium", program_files / "Chromium" / "Application" / "chrome.exe"),
        ("chromium", local / "Chromium" / "Application" / "chrome.exe"),
    ]
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(("edge" if name == "msedge" else name, Path(found)))
    unique: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for kind, path in candidates:
        key = _norm(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        unique.append((kind, path))
    pref = str(preferred or "").strip().casefold()
    if pref in {"edge", "chrome", "chromium"}:
        unique.sort(key=lambda row: 0 if row[0] == pref else 1)
    return unique


def stable_profile(kind: str) -> Path:
    canonical = "Edge" if kind == "edge" else "Chrome" if kind == "chrome" else "Chromium"
    return BASE / f"BrowserProfile-{canonical}"


def _legacy_profiles(kind: str) -> list[Path]:
    canonical = "Edge" if kind == "edge" else "Chrome" if kind == "chrome" else "Chromium"
    try:
        return sorted(BASE.glob(f"BrowserProfile-{canonical}-v*"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []


def _profile_in_use(profile: Path) -> bool:
    return bool(kiosk_processes(profile))


def _migrate_profile(kind: str, profile: Path) -> None:
    if profile.exists():
        return
    for old in _legacy_profiles(kind):
        if _profile_in_use(old):
            continue
        try:
            def ignore(_dir, names):
                return [name for name in names if name in LOCK_NAMES]
            shutil.copytree(old, profile, ignore=ignore)
            log(f"Browserprofiel gemigreerd: {old.name} -> {profile.name}")
            return
        except Exception as exc:
            log(f"Profielmigratie {old} mislukt: {exc}")
    profile.mkdir(parents=True, exist_ok=True)


def _prepare_profile(kind: str, profile: Path) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    _migrate_profile(kind, profile)
    if _profile_in_use(profile):
        return
    profile.mkdir(parents=True, exist_ok=True)
    for name in LOCK_NAMES:
        target = profile / name
        try:
            if target.is_symlink() or target.exists():
                target.unlink()
        except OSError:
            pass


def _parse_pair(value: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        left, right = str(value).split(",", 1)
        return int(left.strip()), int(right.strip())
    except Exception:
        return default


def _launch_and_confirm(exe: Path, args: list[str], profile: Path, wait: float = 3.0) -> bool:
    try:
        subprocess.Popen(
            [str(exe), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        log(f"Browserstart mislukt ({exe}): {exc}")
        return False
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if kiosk_processes(profile):
            return True
        time.sleep(.25)
    return bool(kiosk_processes(profile))


def _common_args(url: str, profile: Path, position: tuple[int, int], size: tuple[int, int]) -> list[str]:
    return [
        f"--window-position={position[0]},{position[1]}",
        f"--window-size={size[0]},{size[1]}",
        "--no-first-run",
        "--no-default-browser-check",
        "--noerrdialogs",
        "--disable-session-crashed-bubble",
        f"--user-data-dir={profile}",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
    ]


def launch(url: str, position: str, size: str, preferred: str = "") -> int:
    pos = _parse_pair(position, (0, 0))
    wh = _parse_pair(size, (1920, 1080))
    browsers = _browser_candidates(preferred or os.environ.get("P2000_BROWSER", ""))
    if not browsers:
        log("Geen ondersteunde Chromium-browser gevonden; standaardbrowser wordt gebruikt.")
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return 0
        except Exception:
            return 2

    # Reuse a current dedicated kiosk, otherwise remove only P2000's own kiosk.
    if kiosk_processes():
        log("Bestaande dedicated P2000-kiosk is actief; geen tweede browser gestart.")
        return 0
    stop_kiosk()

    for kind, exe in browsers:
        profile = stable_profile(kind)
        _prepare_profile(kind, profile)
        common = _common_args(url, profile, pos, wh)
        kiosk_args = [*common, "--kiosk", url]
        if kind == "edge":
            kiosk_args.insert(-2, "--edge-kiosk-type=fullscreen")
        log(f"{kind} kiosk starten: exe={exe}, profiel={profile}, positie={pos}, formaat={wh}")
        if _launch_and_confirm(exe, kiosk_args, profile):
            return 0

        # Do not touch live locks: prepare only after the failed launch has proven
        # that no process is using this dedicated profile.
        _prepare_profile(kind, profile)
        app_args = [*common, "--start-fullscreen", f"--app={url}"]
        log(f"{kind} kioskmodus stopte; app/fullscreen-fallback proberen.")
        if _launch_and_confirm(exe, app_args, profile):
            return 0

    log("Alle dedicated kioskstarts mislukten; standaardbrowser wordt geopend.")
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        return 0
    except Exception:
        return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    launch_p = sub.add_parser("launch")
    launch_p.add_argument("--url", default=DEFAULT_URL)
    launch_p.add_argument("--position", default="0,0")
    launch_p.add_argument("--size", default="1920,1080")
    launch_p.add_argument("--browser", default="")
    sub.add_parser("status")
    sub.add_parser("stop-kiosk")
    a = ap.parse_args()

    if a.command == "status":
        rows = kiosk_processes()
        if rows:
            print(json.dumps({"running": True, "pids": [r["pid"] for r in rows], "profiles": [r["profile"] for r in rows]}, ensure_ascii=False))
            return 0
        return 1
    if a.command == "stop-kiosk":
        return 0 if stop_kiosk() else 2
    if a.command == "launch":
        return launch(a.url, a.position, a.size, a.browser)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
