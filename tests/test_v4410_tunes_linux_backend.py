#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, tempfile, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
checks={}
server_text=(ROOT/'backend/server.py').read_text('utf-8')
control=(ROOT/'frontend/control.js').read_text('utf-8')
html=(ROOT/'frontend/control.html').read_text('utf-8')
probe=(ROOT/'tools/runtime_probe.py').read_text('utf-8')
start=(ROOT/'START_P2000.sh').read_text('utf-8')
start_backend=(ROOT/'START_BACKEND.sh').read_text('utf-8')
version=(ROOT/'VERSION').read_text().strip()
parts=tuple(int(x) for x in version.split('.')[:3])
checks['version_4410']=parts >= (4,4,10) and f'APP_VERSION = "{version}"' in server_text
checks['dedicated_tune_store']='TUNE_SETTINGS_PATH = TUNE_DIR / "settings.json"' in server_text
checks['tune_api_get_post']=server_text.count('parsed.path == "/api/tune/settings"')>=2
checks['settings_merge_safe']='merged = dict(existing)' in server_text and 'merged.update(clean)' in server_text
checks['tune_autosave']='scheduleTuneSave' in control and '/api/tune/settings' in control
checks['tune_save_button']='saveTuneSettingsBtn' in control and 'Toontjes nu opslaan' in html
checks['linux_hung_backend_detection']='Vastgelopen P2000 backend' in probe and '_is_this_p2000_backend' in probe
checks['linux_port_diagnostics']='--describe-port' in start and '--describe-port' in probe
checks['linux_write_permission_check']='.write-test-' in start and 'kan niet schrijven' in start
checks['linux_retry']='automatische herstelpoging' in start and 'start_backend_once' in start
checks['start_backend_preflight']='--kill-stale' in start_backend and '.write-test-' in start_backend

spec=importlib.util.spec_from_file_location('p2000_server_v4410',ROOT/'backend/server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    mod.DB_PATH=td/'p2000.sqlite3';mod.TUNE_DIR=td/'tunes';mod.TUNE_SETTINGS_PATH=mod.TUNE_DIR/'settings.json'
    st=mod.AppState({});st.init_db()
    saved=st.save_display_settings({
        'dispatchTuneEnabled':True,'dispatchTuneDefault':'builtin:double','dispatchTuneBrandweer':'builtin:urgent',
        'dispatchTuneAmbulance':'builtin:rising','dispatchTunePolitie':'none','dispatchTuneLifeliner':'youtube',
        'dispatchTuneKnrm':'custom','dispatchTuneUrgent':'builtin:classic','dispatchTuneVolume':65,
        'dispatchTuneYoutubeSeconds':7,'dispatchTuneYoutubeUrl':'https://www.youtube.com/watch?v=VleijwaD_-U'
    })
    st.save_display_settings({'masterVolume':42})
    after=st.get_display_settings()
    st2=mod.AppState({});st2.init_db();after_restart=st2.get_display_settings()
    tune_file=mod.TUNE_SETTINGS_PATH
    checks['functional_tune_persistence']=(saved.get('dispatchTuneDefault')=='builtin:double' and after.get('dispatchTuneBrandweer')=='builtin:urgent' and after.get('masterVolume')==42 and after_restart.get('dispatchTuneKnrm')=='custom' and after_restart.get('dispatchTuneVolume')==65 and tune_file.exists())
    if os.name!='nt':checks['tune_file_private']=(tune_file.stat().st_mode & 0o777)==0o600

failed=[k for k,v in checks.items() if not v]
print(json.dumps(checks,ensure_ascii=False,indent=2))
if failed:raise SystemExit('FAIL: '+', '.join(failed))
print(f'OK: {len(checks)}/{len(checks)} v4.4.10+ deuntjes/Linux backend checks')
