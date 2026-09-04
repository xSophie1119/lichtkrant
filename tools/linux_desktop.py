#!/usr/bin/env python3
"""Linux desktop/browser integration for P2000 Monitor.

One implementation is shared by the kiosk launcher, configuratiewizard and
settings launcher. It understands native .deb/rpm browsers, Ubuntu Snap
wrappers and common Flatpak browsers, uses confinement-safe profile paths and
only reports success after a browser process actually survives startup.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

IS_LINUX = sys.platform.startswith("linux")
HOME = Path.home()
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
XDG_STATE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local" / "state")
LOG_DIR = XDG_STATE / "p2000-monitor" / "logs"
LOG_FILE = LOG_DIR / "browser.log"

CHROMIUM_NATIVE = [
    "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
    "brave-browser", "microsoft-edge-stable", "microsoft-edge",
    "microsoft-edge-beta", "microsoft-edge-dev",
]
FIREFOX_NATIVE = ["firefox", "firefox-esr"]
FLATPAKS = [
    ("com.google.Chrome", "chromium", "Google Chrome (Flatpak)"),
    ("org.chromium.Chromium", "chromium", "Chromium (Flatpak)"),
    ("com.brave.Browser", "chromium", "Brave (Flatpak)"),
    ("com.microsoft.Edge", "chromium", "Microsoft Edge (Flatpak)"),
    ("org.mozilla.firefox", "firefox", "Firefox (Flatpak)"),
]

@dataclass
class Candidate:
    ident: str
    family: str
    label: str
    command: list[str]
    packaging: str = "native"
    snap_package: str = ""
    flatpak_id: str = ""


def _run(argv: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, check=False, text=True)
    except Exception:
        return None


def _snap_package_for(path: str) -> str:
    base = Path(path).name
    mapping = {
        "chromium": "chromium", "chromium-browser": "chromium",
        "firefox": "firefox", "brave-browser": "brave",
        "google-chrome": "google-chrome", "google-chrome-stable": "google-chrome",
        "microsoft-edge": "microsoft-edge", "microsoft-edge-stable": "microsoft-edge",
    }
    pkg = mapping.get(base, "")
    if path.startswith("/snap/bin/"):
        return pkg or base
    # Ubuntu's /usr/bin/chromium is commonly a tiny wrapper delegating to snap.
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")[:12000]
        if "snap run chromium" in text or "/snap/bin/chromium" in text:
            return "chromium"
        if "snap run firefox" in text or "/snap/bin/firefox" in text:
            return "firefox"
    except Exception:
        pass
    if pkg and shutil.which("snap"):
        cp = _run(["snap", "list", pkg], 3)
        if cp and cp.returncode == 0:
            return pkg
    return ""


def _family_for_name(name: str) -> str:
    return "firefox" if "firefox" in name.lower() else "chromium"


def discover() -> list[Candidate]:
    rows: list[Candidate] = []
    seen: set[str] = set()
    wanted = (os.environ.get("P2000_BROWSER") or "auto").strip()
    names: list[str] = []
    if wanted and wanted.lower() != "auto":
        names.append(wanted)
    names.extend(CHROMIUM_NATIVE + FIREFOX_NATIVE)
    for name in names:
        path = shutil.which(name) if os.sep not in name else (name if os.access(name, os.X_OK) else None)
        if not path:
            continue
        real = str(Path(path).resolve()) if Path(path).exists() else path
        key = f"native:{real}"
        if key in seen:
            continue
        seen.add(key)
        snap_pkg = _snap_package_for(path)
        rows.append(Candidate(
            ident=path,
            family=_family_for_name(Path(path).name),
            label=Path(path).name + (" (Snap)" if snap_pkg else ""),
            command=[path],
            packaging="snap" if snap_pkg else "native",
            snap_package=snap_pkg,
        ))
        if wanted and wanted.lower() != "auto":
            # An explicit browser is tried first, but keep fallbacks as well.
            wanted = "auto"
    flatpak = shutil.which("flatpak")
    if flatpak:
        for appid, family, label in FLATPAKS:
            cp = _run([flatpak, "info", appid], 3)
            if not cp or cp.returncode != 0:
                continue
            key = f"flatpak:{appid}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(Candidate(appid, family, label, [flatpak, "run", appid], "flatpak", flatpak_id=appid))
    return rows


def runtime_dir(explicit: str = "") -> Path:
    if explicit:
        base = Path(explicit)
        # Caller may pass the already-final p2000 directory.
        if base.name.startswith("p2000-monitor-"):
            target = base
        else:
            target = base / f"p2000-monitor-{os.getuid()}"
    else:
        base_env = os.environ.get("XDG_RUNTIME_DIR")
        base = Path(base_env) if base_env else Path("/tmp")
        if not base.exists() or not os.access(base, os.W_OK | os.X_OK):
            base = Path("/tmp")
        target = base / f"p2000-monitor-{os.getuid()}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def profile_path(c: Candidate, purpose: str) -> Path:
    safe = purpose.replace("/", "-")
    if c.packaging == "snap" and c.snap_package:
        return HOME / "snap" / c.snap_package / "common" / f"p2000-monitor-{safe}"
    if c.packaging == "flatpak" and c.flatpak_id:
        return HOME / ".var" / "app" / c.flatpak_id / "config" / f"p2000-monitor-{safe}"
    clean = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in Path(c.ident).name)
    return XDG_CONFIG / "p2000-monitor" / f"browser-{clean}-{safe}"


def gui_available() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _proc_cmdlines():
    proc = Path("/proc")
    if proc.is_dir():
        for p in proc.iterdir():
            if not p.name.isdigit() or int(p.name) == os.getpid():
                continue
            try:
                raw = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            except Exception:
                continue
            if raw:
                yield int(p.name), raw
    else:
        cp = _run(["ps", "-eo", "pid=,args="], 4)
        if cp:
            for line in cp.stdout.splitlines():
                try:
                    pid_s, cmd = line.strip().split(None, 1)
                    yield int(pid_s), cmd
                except Exception:
                    pass


def _is_p2000_browser_cmd(cmd: str) -> bool:
    low = cmd.lower()
    # Require an actual browser-profile argument. Merely seeing the URL and the
    # words p2000-monitor is unsafe because a parent shell/diagnostic command can
    # contain those strings too.
    profile_marker = (
        ("--user-data-dir=" in low and "p2000-monitor" in low) or
        (("--profile " in low or "-profile " in low) and "p2000-monitor" in low)
    )
    if not profile_marker:
        return False
    return not any(x in low for x in ("linux_desktop.py", "supervisor.py", "runtime_probe.py"))

def matching_pids(profile: Path | None = None, url: str = "") -> list[int]:
    profile_s = str(profile) if profile else ""
    out = []
    for pid, cmd in _proc_cmdlines():
        if not _is_p2000_browser_cmd(cmd):
            continue
        if profile_s and profile_s not in cmd:
            continue
        # Chromium renderer processes usually no longer carry the page URL. The
        # profile marker is sufficient when a specific profile is requested.
        if url and not profile_s and url not in cmd and "127.0.0.1:8765" not in cmd:
            continue
        out.append(pid)
    return out


def _clean_profile_locks(profile: Path) -> None:
    if matching_pids(profile):
        return
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie", ".parentlock", "lock"):
        p = profile / name
        try:
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir() and name.startswith("Singleton"):
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


def _platform_modes(position: str) -> list[str]:
    forced = (os.environ.get("P2000_BROWSER_PLATFORM") or "auto").strip().lower()
    if forced in {"x11", "wayland"}:
        return [forced, "auto"]
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    non_primary = position not in {"", "0,0", "+0+0"}
    # On GNOME/KDE Wayland, XWayland usually respects explicit kiosk geometry
    # better than native Wayland, where the compositor owns placement.
    if wayland and x11 and non_primary:
        return ["x11", "wayland", "auto"]
    modes = ["auto"]
    if wayland:
        modes.append("wayland")
    if x11:
        modes.append("x11")
    return modes


def _browser_argv(c: Candidate, profile: Path, url: str, kiosk: bool,
                  position: str, size: str, platform_mode: str = "auto") -> list[str]:
    argv = list(c.command)
    if c.family == "firefox":
        argv += ["--no-remote", "--profile", str(profile)]
        if kiosk:
            argv += ["--kiosk", url]
        else:
            argv += ["--new-window", url]
        return argv
    argv += [
        f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        "--noerrdialogs", "--disable-session-crashed-bubble",
        "--autoplay-policy=no-user-gesture-required",
    ]
    if kiosk:
        argv += [f"--window-position={position}", f"--window-size={size}", "--kiosk", url,
                 "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                 "--disable-backgrounding-occluded-windows"]
    else:
        argv += ["--new-window", url]
    if platform_mode == "wayland":
        argv.append("--ozone-platform=wayland")
    elif platform_mode == "x11":
        argv.append("--ozone-platform=x11")
    return argv


def _launch(c: Candidate, profile: Path, url: str, kiosk: bool, position: str,
            size: str, probe_seconds: float, rundir: Path, log_path: Path) -> tuple[bool, str]:
    profile.mkdir(parents=True, exist_ok=True)
    _clean_profile_locks(profile)
    if c.family == "firefox":
        try:
            (profile / "user.js").write_text(
                'user_pref("media.autoplay.default", 0);\n'
                'user_pref("media.autoplay.blocking_policy", 0);\n'
                'user_pref("browser.sessionstore.resume_from_crash", false);\n'
                'user_pref("browser.shell.checkDefaultBrowser", false);\n',
                encoding="utf-8",
            )
        except Exception:
            pass
    modes = _platform_modes(position) if c.family == "chromium" else ["auto"]
    for mode in modes:
        if mode == "wayland" and not os.environ.get("WAYLAND_DISPLAY"):
            continue
        if mode == "x11" and not os.environ.get("DISPLAY"):
            continue
        argv = _browser_argv(c, profile, url, kiosk, position, size, mode)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] browser={c.label} package={c.packaging} mode={mode} profile={profile}\n")
            log.write("argv=" + shlex.join(argv) + "\n")
            log.flush()
            try:
                proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                        start_new_session=True, env=os.environ.copy())
            except Exception as exc:
                log.write(f"startfout={type(exc).__name__}: {exc}\n")
                continue
        (rundir / ("browser.pid" if kiosk else "control-browser.pid")).write_text(str(proc.pid), encoding="utf-8")
        end = time.monotonic() + max(0.6, probe_seconds)
        while time.monotonic() < end:
            if proc.poll() is None or matching_pids(profile, url):
                time.sleep(0.15)
                if proc.poll() is None or matching_pids(profile, url):
                    return True, f"{c.label} ({mode})"
            time.sleep(0.15)
        if matching_pids(profile, url):
            return True, f"{c.label} ({mode})"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"browser stopte direct, exit={proc.poll()}\n")
        _clean_profile_locks(profile)
    return False, c.label


def open_browser(url: str, kiosk: bool, position: str, size: str,
                 probe_seconds: float, rundir_path: str = "") -> tuple[bool, str]:
    if not IS_LINUX:
        return False, "linux_desktop.py werkt alleen op Linux"
    if not gui_available():
        return False, "Geen grafische Linux-sessie gevonden (DISPLAY/WAYLAND_DISPLAY ontbreken)"
    rd = runtime_dir(rundir_path)
    purpose = "kiosk" if kiosk else "control"
    candidates = discover()
    for c in candidates:
        profile = profile_path(c, purpose)
        if kiosk and matching_pids(profile, "127.0.0.1:8765"):
            pids = matching_pids(profile, "127.0.0.1:8765")
            if pids:
                (rd / "browser.pid").write_text(str(pids[-1]), encoding="utf-8")
            return True, f"{c.label} draait al"
        ok, detail = _launch(c, profile, url, kiosk, position, size, probe_seconds, rd, LOG_FILE)
        if ok:
            return True, detail
    # For normal control/wizard pages, a standards-compliant desktop opener is a
    # useful last fallback. Do not claim kiosk success through xdg-open.
    if not kiosk:
        for argv in (["xdg-open", url], ["gio", "open", url]):
            if not shutil.which(argv[0]):
                continue
            cp = _run(argv, 8)
            if cp and cp.returncode == 0:
                return True, f"{argv[0]} fallback"
    return False, "Geen ondersteunde browser kon worden gestart"


def stop_kiosk(rundir_path: str = "") -> int:
    rd = runtime_dir(rundir_path)
    pids: set[int] = set()
    pf = rd / "browser.pid"
    try:
        pids.add(int(pf.read_text().strip()))
    except Exception:
        pass
    for pid, cmd in _proc_cmdlines():
        if _is_p2000_browser_cmd(cmd) and "127.0.0.1:8765" in cmd:
            pids.add(pid)
    stopped = 0
    for pid in sorted(pids):
        if pid <= 1 or pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            stopped += 1
        except ProcessLookupError:
            pass
        except Exception:
            pass
    time.sleep(0.35)
    for pid in sorted(pids):
        try:
            os.kill(pid, 0)
        except Exception:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    try:
        pf.unlink()
    except Exception:
        pass
    return stopped


def probe() -> dict:
    candidates = discover() if IS_LINUX else []
    return {
        "linux": IS_LINUX,
        "gui": gui_available(),
        "display": os.environ.get("DISPLAY", ""),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "candidates": [asdict(c) | {"profile_kiosk": str(profile_path(c, "kiosk")), "profile_control": str(profile_path(c, "control"))} for c in candidates],
        "xdg_open": bool(shutil.which("xdg-open")),
        "gio": bool(shutil.which("gio")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("kiosk")
    p.add_argument("--url", default="http://127.0.0.1:8765/")
    p.add_argument("--position", default=os.environ.get("P2000_WINDOW_POSITION", "0,0"))
    p.add_argument("--size", default=os.environ.get("P2000_WINDOW_SIZE", "1920,1080"))
    p.add_argument("--probe-seconds", type=float, default=float(os.environ.get("P2000_BROWSER_PROBE_SECONDS", "3")))
    p.add_argument("--rundir", default="")
    p = sub.add_parser("open")
    p.add_argument("--url", required=True)
    p.add_argument("--probe-seconds", type=float, default=1.8)
    p.add_argument("--rundir", default="")
    p = sub.add_parser("stop-kiosk")
    p.add_argument("--rundir", default="")
    sub.add_parser("probe")
    a = ap.parse_args()
    if a.cmd == "probe":
        print(json.dumps(probe(), ensure_ascii=False, indent=2)); return 0
    if a.cmd == "stop-kiosk":
        print(stop_kiosk(a.rundir)); return 0
    if a.cmd == "kiosk":
        ok, detail = open_browser(a.url, True, a.position, a.size, a.probe_seconds, a.rundir)
    else:
        ok, detail = open_browser(a.url, False, "0,0", "1280,900", a.probe_seconds, a.rundir)
    print(detail)
    return 0 if ok else 5

if __name__ == "__main__":
    raise SystemExit(main())
