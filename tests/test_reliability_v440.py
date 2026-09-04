import importlib.util,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_v440',ROOT/'backend'/'server.py');mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
server=(ROOT/'backend'/'server.py').read_text(encoding='utf-8');app=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8');control=(ROOT/'frontend'/'control.js').read_text(encoding='utf-8');html=(ROOT/'frontend'/'control.html').read_text(encoding='utf-8')
checks={
 'version_440':tuple(map(int,mod.APP_VERSION.split('.'))) >= (4,4,0) and tuple(map(int,(ROOT/'VERSION').read_text().strip().split('.'))) >= (4,4,0),
 'supervisor':(ROOT/'tools'/'supervisor.py').is_file() and 'pending-health.json' in (ROOT/'tools'/'supervisor.py').read_text(),
 'installers':all((ROOT/x).is_file() for x in ['INSTALL_P2000.bat','INSTALL_P2000.ps1','INSTALL_P2000.sh','UNINSTALL_P2000.bat','UNINSTALL_P2000.ps1','UNINSTALL_P2000.sh']),
 'feed_race':'ThreadPoolExecutor' in server and 'feed_race_enabled' in server and 'race_feed_urls' in server,
 'update_preflight':'_preflight_staged_update' in server and 'pending-health.json' in server,
 'display_fingerprint':'monitor_fingerprint' in server and 'fingerprint' in control,
 'speech_modes':"speechMode:'normal'" in app and 'priorityModeEligible' in app and 'masterVolume' in app,
 'mobile_quick':'quickRestartKioskBtn' in html and '/api/quick-action' in control,
 'live_preview':'livePreview' in control and '/api/parser/debug' in control,
 'vehicle_history':'/api/vehicle-history' in server and 'vehicleHistoryList' in html,
 'unknown_suggestions':'suggested_type' in server and 'Suggestie gebruiken' in control,
 'regression_corpus':(ROOT/'tests'/'regressions_user_reports.json').is_file(),
}
print(json.dumps(checks,ensure_ascii=False,indent=2))
failed=[k for k,v in checks.items() if not v]
if failed:print('FAIL:',', '.join(failed));raise SystemExit(1)
