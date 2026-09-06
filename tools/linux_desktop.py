#!/usr/bin/env python3
"""Conservative Linux kiosk launcher/status helper for P2000 Monitor."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8765/"
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "p2000-monitor"
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "p2000-monitor"
LOG = STATE_HOME / "browser.log"


def log(message: str) -> None:
    try:
        STATE_HOME.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            rotated = LOG.with_suffix(".log.1")
            rotated.unlink(missing_ok=True)
            LOG.replace(rotated)
        with LOG.open("a", encoding="utf-8") as fp:
            fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def _pidfile(rundir: Path) -> Path:
    return rundir / "browser.pid"


def _profilefile(rundir: Path) -> Path:
    return rundir / "browser.profile"


def _cmdline(pid: int) -> str:
    try:
        return (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except Exception:
        return ""


def _read_pid(rundir: Path) -> int:
    try:
        return int(_pidfile(rundir).read_text(encoding="ascii").strip())
    except Exception:
        return 0


def kiosk_status(rundir: Path) -> bool:
    pid = _read_pid(rundir)
    if pid <= 1:
        return False
    cmd = _cmdline(pid)
    if not cmd:
        return False
    normalized = cmd.replace("\\", "/")
    return "127.0.0.1:8765" in normalized and "p2000-monitor/browser-profile-" in normalized.casefold()


def stop_kiosk(rundir: Path) -> bool:
    pid = _read_pid(rundir)
    if pid <= 1:
        _pidfile(rundir).unlink(missing_ok=True)
        _profilefile(rundir).unlink(missing_ok=True)
        return True
    if not kiosk_status(rundir):
        # Never signal an unrelated PID after PID reuse.
        _pidfile(rundir).unlink(missing_ok=True)
        _profilefile(rundir).unlink(missing_ok=True)
        return True
    try:
        os.kill(pid, signal.SIGTERM)
        end = time.monotonic() + 3
        while time.monotonic() < end and _cmdline(pid):
            time.sleep(.1)
        if _cmdline(pid):
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except (PermissionError, OSError):
        return False
    _pidfile(rundir).unlink(missing_ok=True)
    _profilefile(rundir).unlink(missing_ok=True)
    log(f"Dedicated kiosk PID {pid} gestopt.")
    return True


def _browsers(preferred: str = "") -> list[tuple[str, str]]:
    names = [
        ("chrome", "google-chrome-stable"),
        ("chrome", "google-chrome"),
        ("chromium", "chromium"),
        ("chromium", "chromium-browser"),
    ]
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, name in names:
        path = shutil.which(name)
        if not path or path in seen:
            continue
        seen.add(path)
        rows.append((kind, path))
    pref = str(preferred or "").strip().casefold()
    if pref in {"chrome", "chromium"}:
        rows.sort(key=lambda row: 0 if row[0] == pref else 1)
    return rows


def _profile(kind: str) -> Path:
    return DATA_HOME / f"browser-profile-{kind}"


def _clean_locks(profile: Path) -> None:
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK"):
        path = profile / name
        try:
            if path.is_symlink() or path.exists():
                path.unlink()
        except OSError:
            pass


def launch(url: str, position: str, size: str, rundir: Path, preferred: str = "") -> int:
    rundir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(rundir, 0o700)
    except OSError:
        pass
    if kiosk_status(rundir):
        return 0
    stop_kiosk(rundir)
    try:
        x, y = (int(v.strip()) for v in position.split(",", 1))
        w, h = (int(v.strip()) for v in size.split(",", 1))
    except Exception:
        x, y, w, h = 0, 0, 1920, 1080

    for kind, exe in _browsers(preferred or os.environ.get("P2000_BROWSER", "")):
        profile = _profile(kind)
        profile.mkdir(parents=True, exist_ok=True)
        _clean_locks(profile)
        common = [
            f"--user-data-dir={profile}",
            f"--window-position={x},{y}",
            f"--window-size={w},{h}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
        ]
        for mode in ("kiosk", "app"):
            args = [exe, *common]
            if mode == "kiosk":
                args += ["--kiosk", url]
            else:
                args += ["--start-fullscreen", f"--app={url}"]
            try:
                proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except Exception as exc:
                log(f"{kind} start mislukt: {exc}")
                break
            _pidfile(rundir).write_text(str(proc.pid), encoding="ascii")
            _profilefile(rundir).write_text(str(profile), encoding="utf-8")
            end = time.monotonic() + 4
            while time.monotonic() < end:
                if kiosk_status(rundir):
                    log(f"{kind} {mode} gestart, PID {proc.pid}, profiel {profile}.")
                    return 0
                if proc.poll() is not None:
                    break
                time.sleep(.25)
            stop_kiosk(rundir)
            _clean_locks(profile)
            log(f"{kind} {mode} startcontrole mislukt; volgende fallback.")

    opener = shutil.which("xdg-open")
    if opener:
        try:
            subprocess.Popen([opener, url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            log("Geen ondersteunde Chromium-kiosk; xdg-open fallback gebruikt.")
            return 0
        except Exception:
            pass
    log("Geen bruikbare browser gevonden.")
    return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p_launch = sub.add_parser("launch")
    p_launch.add_argument("--url", default=DEFAULT_URL)
    p_launch.add_argument("--position", default="0,0")
    p_launch.add_argument("--size", default="1920,1080")
    p_launch.add_argument("--browser", default="")
    p_launch.add_argument("--rundir", required=True)
    for name in ("kiosk-status", "stop-kiosk"):
        p = sub.add_parser(name)
        p.add_argument("--rundir", required=True)
    a = ap.parse_args()
    rundir = Path(a.rundir)
    if a.command == "kiosk-status":
        return 0 if kiosk_status(rundir) else 1
    if a.command == "stop-kiosk":
        return 0 if stop_kiosk(rundir) else 2
    if a.command == "launch":
        return launch(a.url, a.position, a.size, rundir, a.browser)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
