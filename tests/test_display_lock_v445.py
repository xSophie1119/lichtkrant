#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util, sys, os
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_server_v445',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
checks={}
# Two physically identical Wayland displays without serials must never collide.
a={'id':'DP-1','device':'DP-1','label':'A','x':-1920,'y':0,'width':1920,'height':1080,'primary':True,'make':'ACME','model':'SamePanel','serial':''}
b={'id':'HDMI-A-1','device':'HDMI-A-1','label':'B','x':0,'y':0,'width':1920,'height':1080,'primary':False,'make':'ACME','model':'SamePanel','serial':''}
a['fingerprint']=mod.monitor_fingerprint(a);b['fingerprint']=mod.monitor_fingerprint(b)
checks['identical_model_fingerprints_unique']=a['fingerprint']!=b['fingerprint']
checks['linux_selector_is_connector_lock']=mod.monitor_selector(b)=='linux-output:HDMI-A-1'
row,exact=mod.resolve_monitor('linux-output:HDMI-A-1',[a,b])
checks['connector_lock_resolves_exact_output']=exact and row['device']=='HDMI-A-1'
# 0,0 does not mean primary: XWayland should still be preferred for a fixed second output.
old_way=os.environ.get('WAYLAND_DISPLAY');old_disp=os.environ.get('DISPLAY')
try:
 os.environ['WAYLAND_DISPLAY']='wayland-0';os.environ['DISPLAY']=':0'
 import importlib.util as iu
 sp=iu.spec_from_file_location('linuxdesktop_v445',ROOT/'tools'/'linux_desktop.py');desk=iu.module_from_spec(sp);sys.modules[sp.name]=desk;sp.loader.exec_module(desk)
 checks['nonprimary_zero_zero_prefers_x11']=desk._platform_modes('0,0',True)[0]=='x11'
finally:
 if old_way is None:os.environ.pop('WAYLAND_DISPLAY',None)
 else:os.environ['WAYLAND_DISPLAY']=old_way
 if old_disp is None:os.environ.pop('DISPLAY',None)
 else:os.environ['DISPLAY']=old_disp
# Once selected, one bad monitor enumeration must preserve last-known geometry and never fall back primary.
orig_enum=mod.enumerate_monitors;orig_db=mod.DB_PATH;orig_data=mod.DATA_DIR
try:
 with TemporaryDirectory() as td:
  td=Path(td);mod.DATA_DIR=td;mod.DB_PATH=td/'db.sqlite3'
  current=[dict(a),dict(b)]
  for r in current:r['selector']=mod.monitor_selector(r)
  mod.enumerate_monitors=lambda:list(current)
  state=mod.AppState({'vehicle_cache_regions':[]});state.init_db()
  selected=state.select_display('HDMI-A-1')
  checks['saved_connector_lock']=state.get_display_settings().get('kioskMonitor')=='linux-output:HDMI-A-1'
  # transient dropout: only primary is seen
  current[:]=[dict(a,selector=mod.monitor_selector(a))]
  info=state.display_info(force=True)
  m=info.get('selected_monitor') or {}
  checks['dropout_does_not_fallback_primary']=info.get('selection_connected') is False and m.get('device')=='HDMI-A-1' and m.get('x')==0
  checks['dropout_keeps_selector']=info.get('selected_monitor_id')=='linux-output:HDMI-A-1'
  # reconnect with focus/primary ordering changed; exact connector still wins
  aa=dict(a,primary=False,selector=mod.monitor_selector(a));bb=dict(b,primary=True,selector=mod.monitor_selector(b))
  current[:]=[bb,aa]
  info2=state.display_info(force=True);m2=info2.get('selected_monitor') or {}
  checks['focus_order_change_stays_on_selected']=info2.get('selection_connected') is True and m2.get('device')=='HDMI-A-1'
finally:
 mod.enumerate_monitors=orig_enum;mod.DB_PATH=orig_db;mod.DATA_DIR=orig_data
sup=(ROOT/'tools'/'supervisor.py').read_text('utf-8')
checks['supervisor_no_fingerprint_pingpong']='fp!=last_fp' not in sup and 'selected_fingerprint' not in sup
checks['supervisor_reconnect_is_diagnostic_only']='Display enumeration is diagnostic only' in sup and 'Geselecteerd scherm opnieuw aangesloten; kiosk teruggeplaatst' not in sup
launcher=(ROOT/'START_P2000.sh').read_text('utf-8')
checks['launcher_passes_nonprimary_intent']='P2000_DISPLAY_PRIMARY' in launcher and '--prefer-x11' in launcher
failed=[k for k,v in checks.items() if not v]
print(f'Linux display lock v4.4.5: {len(checks)-len(failed)}/{len(checks)}')
for k,v in checks.items():print(('OK ' if v else 'FAIL ')+k)
if failed:raise SystemExit(1)
