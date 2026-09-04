#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util, os, sys, json, threading, urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_server_display_hotfix',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)

monitors=[
    {'id':'DP-1','device':'DP-1','label':'Scherm 1','x':0,'y':0,'width':1920,'height':1080,'primary':True,'fingerprint':'fp:primary111'},
    {'id':'HDMI-A-1','device':'HDMI-A-1','label':'Scherm 2','x':1920,'y':0,'width':2560,'height':1440,'primary':False,'fingerprint':'fp:second222'},
]
checks={}
row,exact=mod.resolve_monitor('fp:second222',monitors)
checks['resolve_fingerprint_exact']=exact and row['device']=='HDMI-A-1'
row,exact=mod.resolve_monitor('HDMI-A-1',monitors)
checks['resolve_device_exact']=exact and row['x']==1920
row,exact=mod.resolve_monitor('missing-monitor',monitors)
checks['unknown_selector_reports_nonmatch']=(not exact) and row['primary']

orig_enum=mod.enumerate_monitors;orig_db=mod.DB_PATH;orig_data=mod.DATA_DIR
try:
    with TemporaryDirectory() as td:
        td=Path(td);mod.DATA_DIR=td;mod.DB_PATH=td/'test.sqlite3';mod.enumerate_monitors=lambda:list(monitors)
        state=mod.AppState({'vehicle_cache_regions':[]});state.init_db()
        state.display_info_cache={'stale':True};state.display_info_monotonic=999999
        result=state.select_display('HDMI-A-1')
        saved=state.get_display_settings()
        checks['selection_saved_as_exact_linux_output']=saved.get('kioskMonitor')=='linux-output:HDMI-A-1'
        checks['selection_returns_geometry']=result.get('selected_monitor',{}).get('x')==1920 and result.get('selected_monitor',{}).get('width')==2560
        checks['display_cache_refreshed']=state.display_info_cache is not None and state.display_info_cache.get('selected_monitor',{}).get('device')=='HDMI-A-1'
        try:
            state.select_display('not-connected')
            checks['invalid_selection_rejected']=False
        except ValueError:
            checks['invalid_selection_rejected']=True
finally:
    mod.enumerate_monitors=orig_enum;mod.DB_PATH=orig_db;mod.DATA_DIR=orig_data

# wlr-randr plain-text fallback: many distro builds do not implement --json.
class CP:
    def __init__(self,code,out): self.returncode=code;self.stdout=out.encode();self.stderr=b''
orig_which=mod.shutil.which;orig_run=mod._run_quiet;old_wayland=os.environ.get('WAYLAND_DISPLAY')
try:
    os.environ['WAYLAND_DISPLAY']='wayland-0'
    mod.shutil.which=lambda name:'/usr/bin/wlr-randr' if name=='wlr-randr' else orig_which(name)
    sample='''DP-1 "Dell U2419H"\n  Make: Dell Inc.\n  Model: U2419H\n  Serial: ABC123\n  Enabled: yes\n  Modes:\n    1920x1080 px, 60.000000 Hz (preferred, current)\n  Position: 0,0\nHDMI-A-1 "Samsung TV"\n  Make: Samsung\n  Model: TV\n  Serial: XYZ987\n  Enabled: yes\n  Modes:\n    3840x2160 px, 60.000000 Hz (current)\n  Position: 1920,0\n'''
    def fake_run(argv,timeout=3):
        return CP(1,'unknown option --json') if '--json' in argv else CP(0,sample)
    mod._run_quiet=fake_run
    rows=mod._linux_wlr_monitors()
    checks['wlr_text_fallback_two_outputs']=len(rows)==2
    second=next((r for r in rows if r.get('device')=='HDMI-A-1'),{})
    checks['wlr_text_geometry']=second.get('x')==1920 and second.get('width')==3840 and second.get('height')==2160
finally:
    mod.shutil.which=orig_which;mod._run_quiet=orig_run
    if old_wayland is None: os.environ.pop('WAYLAND_DISPLAY',None)
    else: os.environ['WAYLAND_DISPLAY']=old_wayland


# HTTP integration: exercise the same POST endpoint used by /control.
orig_enum=mod.enumerate_monitors;orig_db=mod.DB_PATH;orig_data=mod.DATA_DIR
orig_sup=mod.ensure_supervisor_running;orig_queue=mod.queue_supervisor_command
try:
    with TemporaryDirectory() as td:
        td=Path(td);mod.DATA_DIR=td;mod.DB_PATH=td/'api.sqlite3';mod.enumerate_monitors=lambda:list(monitors)
        mod.ensure_supervisor_running=lambda timeout=3.5:{'running':True,'state':'healthy'}
        mod.queue_supervisor_command=lambda action:{'action':action,'token':'test'}
        state=mod.AppState({'vehicle_cache_regions':[]});state.init_db();mod.Handler.state=state
        httpd=mod.QuietThreadingHTTPServer(('127.0.0.1',0),mod.Handler);port=httpd.server_address[1]
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/display/select',data=json.dumps({'selector':'HDMI-A-1'}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=4) as r: payload=json.load(r)
        checks['api_switch_ok']=payload.get('ok') is True and payload.get('reposition_requested') is True
        checks['api_switch_geometry']=payload.get('selected_monitor',{}).get('device')=='HDMI-A-1' and payload.get('selected_monitor',{}).get('x')==1920
        checks['api_switch_queues_kiosk_restart']=payload.get('command',{}).get('action')=='restart-kiosk'
        httpd.shutdown();httpd.server_close()
finally:
    mod.enumerate_monitors=orig_enum;mod.DB_PATH=orig_db;mod.DATA_DIR=orig_data
    mod.ensure_supervisor_running=orig_sup;mod.queue_supervisor_command=orig_queue

control=(ROOT/'frontend'/'control.js').read_text('utf-8')
html=(ROOT/'frontend'/'control.html').read_text('utf-8')
backend=(ROOT/'backend'/'server.py').read_text('utf-8')
checks['frontend_backend_source_of_truth']="x.selected_monitor_id||settings.kioskMonitor" in control
checks['frontend_direct_apply_endpoint']="/api/display/select" in control and 'applyDisplaySelection' in control
checks['frontend_preserves_disconnected_selector']='Opgeslagen scherm • momenteel niet aangesloten' in control
checks['apply_button_present']='applyDisplayBtn' in html and 'Nu toepassen' in html
checks['backend_settings_change_restarts_kiosk']='display_reposition_requested' in backend and 'queue_supervisor_command("restart-kiosk")' in backend
checks['backend_can_start_supervisor']='def ensure_supervisor_running' in backend

failed=[k for k,v in checks.items() if not v]
print(f'Display switch hotfix: {len(checks)-len(failed)}/{len(checks)}')
for k,v in checks.items(): print(('OK ' if v else 'FAIL ')+k)
if failed: raise SystemExit(1)
