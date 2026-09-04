#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


supervisor = load("p2000_supervisor_v4415", ROOT / "tools" / "supervisor.py")
desktop = load("p2000_linux_desktop_v4415", ROOT / "tools" / "linux_desktop.py")
server_text = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
start_linux = (ROOT / "START_P2000.sh").read_text(encoding="utf-8")
start_windows = (ROOT / "START_P2000.bat").read_text(encoding="utf-8")

checks = {}
checks["version_4415"] = tuple(map(int, (ROOT / "VERSION").read_text().strip().split("."))) >= (4, 4, 15)

# One cached false result may be observed by many 2-second loop iterations, but
# it is still only one process probe and can never trigger a restart by itself.
hits, restart = supervisor.kiosk_missing_evidence(0, True, False, 999, 0)
for _ in range(20):
    hits, restart = supervisor.kiosk_missing_evidence(hits, False, False, 999, 0)
checks["cached_false_counts_once"] = hits == 1 and restart is False

# A restart is allowed only after three separately marked process probes.
hits = 0
decisions = []
for _ in range(3):
    hits, restart = supervisor.kiosk_missing_evidence(hits, True, False, 999, 0)
    decisions.append(restart)
checks["three_independent_probes"] = decisions == [False, False, True]

# Either the explicit client heartbeat or an open SSE stream proves the kiosk is
# alive, even when platform process inspection produced a false negative.
checks["heartbeat_vetoes_kill"] = supervisor.kiosk_missing_evidence(2, True, False, 20, 0) == (0, False)
checks["sse_vetoes_kill"] = supervisor.kiosk_missing_evidence(2, True, False, 999, 1) == (0, False)

# Re-running either launcher must leave a healthy kiosk alone.
checks["linux_launcher_no_forced_stop"] = 'linux_desktop.py" stop-kiosk' not in start_linux and "ordinary/autostart invocation" in start_linux
main_windows = start_windows[:start_windows.index(":close_all_kiosks")]
checks["windows_launcher_no_forced_stop"] = "call :close_all_kiosks" not in main_windows and "call :any_kiosk_running" in main_windows
checks["display_probe_is_diagnostic"] = "Display enumeration is diagnostic only" in (ROOT / "tools" / "supervisor.py").read_text(encoding="utf-8")
checks["old_supervisor_replaced"] = 'str(status.get("version") or "") == APP_VERSION' in server_text and 'supervisor.py --stop' in start_linux and 'supervisor.py" --stop' in start_windows

# Linux's browser helper short-circuits before discovery/launch when any known
# P2000 kiosk profile already exists, including a different browser family.
old_linux, old_gui, old_rd = desktop.IS_LINUX, desktop.gui_available, desktop.runtime_dir
old_status, old_discover = desktop.kiosk_status, desktop.discover
try:
    with tempfile.TemporaryDirectory() as td:
        desktop.IS_LINUX = True
        desktop.gui_available = lambda: True
        desktop.runtime_dir = lambda explicit="": Path(td)
        desktop.kiosk_status = lambda explicit="": {"running": True, "pids": [123]}
        desktop.discover = lambda: (_ for _ in ()).throw(AssertionError("browser discovery should not run"))
        ok, detail = desktop.open_browser("http://127.0.0.1:8765/", True, "0,0", "1920,1080", 3.0)
        checks["linux_existing_kiosk_short_circuit"] = ok and "draait al" in detail
finally:
    desktop.IS_LINUX, desktop.gui_available, desktop.runtime_dir = old_linux, old_gui, old_rd
    desktop.kiosk_status, desktop.discover = old_status, old_discover

desktop_text = (ROOT / "tools" / "linux_desktop.py").read_text(encoding="utf-8")
checks["snap_without_snap_bin_path"] = '[snap, "run", pkg]' in desktop_text and '[snap, "list"]' in desktop_text
checks["slow_browser_handoff_grace"] = '10.0 if c.packaging in {"snap", "flatpak"}' in desktop_text and 'P2000_BROWSER_PROBE_SECONDS", "8"' in desktop_text

failed = [name for name, value in checks.items() if not value]
print(f"v4.4.15 kiosk-loop tests: {len(checks)-len(failed)}/{len(checks)} OK")
for name in checks:
    print(("OK " if checks[name] else "FAIL ") + name)
if failed:
    raise SystemExit(1)
