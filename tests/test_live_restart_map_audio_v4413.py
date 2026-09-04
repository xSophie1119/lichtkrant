#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
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


version = tuple(int(x) for x in (ROOT / "VERSION").read_text(encoding="utf-8").strip().split("."))
check(version >= (4, 4, 13), "version is 4.4.13+")

app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
map_view = (ROOT / "frontend" / "map-view.html").read_text(encoding="utf-8")
control = (ROOT / "frontend" / "control.js").read_text(encoding="utf-8")
supervisor_text = (ROOT / "tools" / "supervisor.py").read_text(encoding="utf-8")

# Startup history is baseline-only. A stream reconnect always closes the tiny
# refresh/SSE race, while ingested_at remains the hard page-start boundary.
check("considerLatestAtStartup" not in app, "startup no longer activates database history")
check("finishStartupBaseline()" in app and "!isNewSinceMonitorStart(m)" in app, "startup baseline and ingested-at gate are wired")
check("es.onopen=()=>{watchMonitorRuntime();if(state.started)refresh()}" in app, "SSE open closes the baseline connection gap")

# Exercise the real small JS functions without booting the full canvas UI.
node_script = r'''
const fs=require('fs'),s=fs.readFileSync('frontend/app.js','utf8');
function source(name,next){const a=s.indexOf('function '+name+'('),b=s.indexOf('function '+next+'(',a+1);if(a<0||b<0)throw new Error(name+' missing');return s.slice(a,b)}
function chunk(start,end){const a=s.indexOf(start),b=s.indexOf(end,a+1);if(a<0||b<0)throw new Error(start+' missing');return s.slice(a,b)}
let state={bootAt:Date.parse('2026-09-04T12:00:00Z'),settings:{masterVolume:0}};
function ingestedMs(m){return Date.parse(m.ingested_at)||0}
eval(source('isNewSinceMonitorStart','finishStartupBaseline'));
if(isNewSinceMonitorStart({ingested_at:'2026-09-04T11:59:59Z'}))process.exit(2);
if(!isNewSinceMonitorStart({ingested_at:'2026-09-04T12:00:01Z'}))process.exit(3);
function nightSpeechExempt(){return false} function nightSpeechFactor(){return .65}
eval(source('speechVolumeForTime','speechDeviceVolumeForTime'));
if(speechVolumeForTime({},72,new Date())!==0)process.exit(4);
state.settings.masterVolume=50;if(speechVolumeForTime({},72,new Date())!==24)process.exit(5);
function rawDisplayText(v){return String(v||'').replace(/\s+/g,' ').trim()}
function originalMessage(m){return m.title||''} function stripCallsignsForSpeech(v){return v} function cleanedCore(){return 'fallback'}
eval(chunk('function displayMessageText(', '\n// De meegeleverde JSON'));
const out=displayMessageText({title:'P 1 BR woning Hoofdstraat 12 1234 AB Tilburg RIT: 998877 1220803 https://example.invalid/rss'});
if(!out.includes('Hoofdstraat 12')||!out.includes('Tilburg')||/1234 AB|998877|1220803|https?:|RIT/i.test(out)){console.error(out);process.exit(6)}
'''
cp = subprocess.run(["node", "-e", node_script], cwd=ROOT, capture_output=True, text=True)
check(cp.returncode == 0, f"startup/audio/display JS behavior works: {cp.stdout}{cp.stderr}")

# Zero must remain zero through every audio layer; master is applied once.
check("Number(volume)||100" not in app and "Number(volume)||72" not in app, "zero volume has no truthy-default leaks")
check("if(master<=0)return 0" in app and "masterVolume??100)<=0" in app, "zero master volume is actually silent")
check("function dispatchTuneVolume" in app and "const master=" not in app[app.index("function dispatchTuneVolume"):app.index("function stopCurrentTune")], "dispatch tune does not multiply master twice")
check(all(x in index for x in ('id="volumeDownBtn"', 'id="monitorMuteBtn"', 'id="volumeUpBtn"', 'id="monitorVolumeLabel"')), "monitor has direct volume controls")
check("scheduleQuickVolume" in control and "syncVolumeControls" in control, "control sliders stay synchronized and save promptly")

# Route context is based on the configured standplaats, never a hardcoded home.
check("state.setupProfile?.standplaats" in app and "routeHomeQuery" in app and "google.com/maps/dir" in app, "route uses configured standplaats")
check(all(x in index for x in ('id="incidentMapCity"', 'id="incidentMapRoute"', 'id="incidentMapRouteDistance"', 'id="incidentMapRouteLink"')), "map card exposes structured route context")
check(all(x in map_view for x in ('id="originMarker"', 'id="routeGuide"', 'viewForSize', 'screenPoint')), "map renders and frames origin plus incident")

# Watchdog restart budgets and Linux kiosk identity are directly testable.
supervisor = load("p2000_supervisor_v4413", ROOT / "tools" / "supervisor.py")
history = [0.0, 100.0, 200.0]
check(not supervisor.restart_budget_available(history, 300.0, 3, 900), "restart budget blocks a fourth rapid restart")
check(supervisor.restart_budget_available(history, 1200.0, 3, 900), "restart budget recovers after cooldown")
check("backend_failures>=5" in supervisor_text and "loop_now-backend_unhealthy_since>=20" in supervisor_text and "runtime=api('/api/runtime',2.0)" in supervisor_text, "backend requires sustained failure")
check("kiosk_stale_episode_restarted" in supervisor_text and "kiosk_age>150" in supervisor_text, "stale kiosk heartbeat restarts once after long grace")

desktop = load("p2000_linux_desktop_v4413", ROOT / "tools" / "linux_desktop.py")
kiosk_cmd = "chromium --user-data-dir=/home/u/.config/p2000-monitor/browser-chromium-kiosk --kiosk http://127.0.0.1:8765/"
control_cmd = "chromium --user-data-dir=/home/u/.config/p2000-monitor/browser-chromium-control --new-window http://127.0.0.1:8765/control"
with tempfile.TemporaryDirectory() as td:
    old_runtime_dir, old_rows = desktop.runtime_dir, desktop._proc_cmdlines
    try:
        desktop.runtime_dir = lambda explicit="": Path(td)
        desktop._proc_cmdlines = lambda: iter(((101, control_cmd), (202, kiosk_cmd)))
        status = desktop.kiosk_status(td)
        check(status == {"running": True, "pids": [202]}, "Linux kiosk status excludes control windows")
    finally:
        desktop.runtime_dir, desktop._proc_cmdlines = old_runtime_dir, old_rows

print(f"v4.4.13 live/restart/map/audio tests: {len(checks)}/{len(checks)} OK")
