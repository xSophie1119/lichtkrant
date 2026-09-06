#!/usr/bin/env python3
"""P2000 v4.5.6 release/lifecycle test runner with per-test hard timeouts."""
from __future__ import annotations

import argparse
import importlib.util
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_TIMEOUT = 15


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"kan module niet laden: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case_python_compile() -> None:
    files = [
        ROOT / "tools" / "runtime_probe.py",
        ROOT / "tools" / "supervisor.py",
        ROOT / "tools" / "rollback_latest.py",
        ROOT / "tools" / "windows_desktop.py",
        ROOT / "tools" / "linux_desktop.py",
        ROOT / "tools" / "run_tests.py",
        ROOT / "backend" / "compat455.py",
        ROOT / "backend" / "compat456.py",
        ROOT / "backend" / "server.py",
    ]
    for path in files:
        require(path.is_file(), f"ontbreekt: {path.relative_to(ROOT)}")
        py_compile.compile(str(path), doraise=True)


def case_runtime_paths() -> None:
    mod = load_module("p2000_runtime_probe_test", ROOT / "tools" / "runtime_probe.py")
    samples = [
        (r'"C:\Program Files\Python313\python.exe" "C:\P2000 Monitor v4.5.6\backend\server.py"', "backend/server.py", r"C:\P2000 Monitor v4.5.6\backend\server.py"),
        (r'python3 "/home/test/P2000 Monitor/backend/server.py"', "backend/server.py", "/home/test/P2000 Monitor/backend/server.py"),
        (r'python3 "/home/test/P2000 Monitor/tools/supervisor.py"', "tools/supervisor.py", "/home/test/P2000 Monitor/tools/supervisor.py"),
    ]
    for cmd, suffix, expected in samples:
        tokens = mod._script_path_tokens(cmd, suffix)
        require(expected in tokens, f"pad met spaties niet herkend: {cmd!r} -> {tokens!r}")


def case_windows_profile_args() -> None:
    mod = load_module("p2000_windows_desktop_test", ROOT / "tools" / "windows_desktop.py")
    target = r"C:\Users\Sophie\AppData\Local\P2000-Monitor\BrowserProfile-Edge"
    cases = [
        rf'--user-data-dir="{target}" --kiosk http://127.0.0.1:8765/',
        rf'"--user-data-dir={target}" --kiosk http://127.0.0.1:8765/',
        rf'--foo bar --user-data-dir={target.replace(" ", "_")} --kiosk http://127.0.0.1:8765/',
    ]
    require(mod.parse_user_data_dir(cases[0]) == target, "quoted value-vorm niet herkend")
    require(mod.parse_user_data_dir(cases[1]) == target, "geheel gequote Windows-argument niet herkend")
    require(mod.parse_user_data_dir(cases[2]) == target.replace(" ", "_"), "bare vorm niet herkend")
    require("-v" not in mod.stable_profile("edge").name.casefold(), "browserprofiel is nog versiegebonden")


def case_lifecycle_static() -> None:
    text = (ROOT / "tools" / "runtime_probe.py").read_text(encoding="utf-8")
    require("taskkill python.exe" not in text.casefold(), "breed taskkill python.exe gevonden")
    kill = text.index("def kill_stale")
    reconcile = text.index("reconcile_supervisors", kill)
    current = text.index("current_ok = is_current", kill)
    require(reconcile < current, "multi-instance supervisorreconciliatie gebeurt te laat")
    stop_all = text[text.index("def stop_all_p2000"):text.index("def kill_stale")]
    require(stop_all.index("stop_supervisors") < stop_all.index("stop_backends_all"), "STOP-volgorde is niet supervisor -> backend")
    require("p2000_processes(\"backend\")" in text, "orphan backend process scan ontbreekt")

    sup = load_module("p2000_supervisor_test", ROOT / "tools" / "supervisor.py")
    recent = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(timespec="seconds")
    require(sup.status_is_fresh({"version": sup.VERSION, "heartbeat_at": recent}), "verse same-folder supervisor wordt niet behouden")
    require(not sup.status_is_fresh({"version": sup.VERSION, "heartbeat_at": old}), "stale same-folder supervisor wordt als gezond gezien")
    require(not sup.status_is_fresh({"version": "0.0.0", "heartbeat_at": recent}), "oude supervisorversie wordt als gezond gezien")


def case_release_static() -> None:
    require((ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.5.6", "VERSION is niet 4.5.6")
    server = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
    compat = (ROOT / "backend" / "compat456.py").read_text(encoding="utf-8")
    require("compat456.py" in server, "server wrapper gebruikt v4.5.6-laag niet")
    require("V455_SERVER_SHA" in compat and "_apply_v455()" in compat, "v4.5.6 bouwt niet aantoonbaar op v4.5.5")
    require("version-badge\">v4.5.6" in compat, "setup.html v4.5.6 patch ontbreekt")
    require("st.version||'4.5.6'" in compat, "control.js v4.5.6 fallbackpatch ontbreekt")
    require("POST_V455_ARTIFACTS" in compat and "bridge eindcontrole" in compat, "exacte post-v4.5.5 bridge-allowlist ontbreekt")
    start = (ROOT / "START_P2000.bat").read_text(encoding="utf-8")
    require("windows_desktop.py" in start, "Windows kiosk is niet gecentraliseerd")
    require("BrowserProfile-Edge-v" not in start and "BrowserProfile-Chrome-v" not in start, "versiegebonden browserprofiel staat nog in START")
    backend = (ROOT / "RUN_BACKEND.bat").read_text(encoding="utf-8")
    require("-u -X faulthandler" in backend, "Windows backenddiagnostiek mist -u -X faulthandler")
    debug = (ROOT / "START_P2000_DEBUG.bat").read_text(encoding="utf-8")
    require("v4.2.0" not in debug and "browser.log" in debug and "startup.log" in debug, "debuglauncher is nog verouderd")
    rollback = (ROOT / "tools" / "rollback_latest.py").read_text(encoding="utf-8")
    require('"--stop-all"' in rollback, "rollback stopt lifecycle niet atomair")
    bootstrap = ROOT / "ENSURE_PYTHON.bat"
    if bootstrap.is_file():
        boot = bootstrap.read_text(encoding="utf-8")
        require("PYVER=3.13.15" in boot, "embedded Python is niet 3.13.15")
        require("d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf" in boot, "AMD64 Python SHA wijkt af")
        require("cd992cbfb33be433ff20f150691595efb2862e56f4f1bec684c6077d4775af8e" in boot, "ARM64 Python SHA wijkt af")


def case_shell_syntax() -> None:
    bash = shutil.which("bash")
    if not bash:
        return
    scripts = sorted(ROOT.glob("*.sh"))
    require(bool(scripts), "geen Linux shelllaunchers gevonden")
    cp = subprocess.run([bash, "-n", *map(str, scripts)], capture_output=True, text=True, timeout=10)
    require(cp.returncode == 0, cp.stderr or "bash -n mislukt")


def case_timeout_contract() -> None:
    source = (ROOT / "tools" / "run_tests.py").read_text(encoding="utf-8")
    require("timeout=CASE_TIMEOUT" in source, "per-test hard timeout ontbreekt")
    require(CASE_TIMEOUT <= 20, "testtimeout is onnodig hoog")


CASES = {
    "python-compile": case_python_compile,
    "runtime-paths": case_runtime_paths,
    "windows-profile-args": case_windows_profile_args,
    "lifecycle-static": case_lifecycle_static,
    "release-static": case_release_static,
    "shell-syntax": case_shell_syntax,
    "timeout-contract": case_timeout_contract,
}


def run_case(name: str) -> int:
    started = time.monotonic()
    CASES[name]()
    print(f"[OK] {name} ({time.monotonic() - started:.2f}s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=sorted(CASES))
    a = ap.parse_args()
    if a.case:
        return run_case(a.case)

    failed = 0
    for name in CASES:
        try:
            cp = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--case", name],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=CASE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"[FOUT] {name}: harde timeout na {CASE_TIMEOUT}s")
            failed += 1
            continue
        output = (cp.stdout or "").strip()
        error = (cp.stderr or "").strip()
        if output:
            print(output)
        if cp.returncode != 0:
            print(f"[FOUT] {name}: {error or f'exitcode {cp.returncode}'}")
            failed += 1
    if failed:
        print(f"\n{failed} test(s) mislukt.")
        return 1
    print(f"\nAlle {len(CASES)} release-/lifecycletests geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
