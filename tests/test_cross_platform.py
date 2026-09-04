from __future__ import annotations
import importlib.util, os, stat, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_server_cross_platform',ROOT/'backend'/'server.py')
server=importlib.util.module_from_spec(spec); sys.modules[spec.name]=server; spec.loader.exec_module(server)

checks={}
checks['version_430']=server.APP_VERSION=='4.4.4'
checks['runtime_platform']=server.runtime_platform() in {'windows','linux','macos'}
monitors=server.enumerate_monitors()
checks['monitor_enumeration']=isinstance(monitors,list) and len(monitors)>=1
checks['monitor_shape']=all(isinstance(x,dict) and 'id' in x and 'width' in x and 'height' in x for x in monitors)
checks['monitor_selection']=isinstance(server.choose_monitor('primary',monitors),dict)
status=server.tts_runtime_status()
checks['tts_platform']=status.get('platform')==server.runtime_platform()
checks['tts_local_flag']='local_wav_available' in status
rel={'assets':[
 {'name':'P2000_Monitor_Windows_v4.4.1.zip','browser_download_url':'https://github.com/o/r/releases/download/v4.4.1/windows.zip'},
 {'name':'P2000_Monitor_Linux_v4.4.1.zip','browser_download_url':'https://github.com/o/r/releases/download/v4.4.1/linux.zip'},
 {'name':'P2000_Monitor_MultiPlatform_v4.4.1.zip','browser_download_url':'https://github.com/o/r/releases/download/v4.4.1/multi.zip'},
]}
checks['multiplatform_asset_preferred']=server._select_github_release_asset(rel)['name']=='P2000_Monitor_MultiPlatform_v4.4.1.zip'
required_sh=['START_P2000.sh','START_BACKEND.sh','START_CHROME.sh','START_EDGE.sh','STOP_P2000.sh',
             'OPEN_INSTELLINGEN.sh','CONFIGURATIE_WIZARD.sh','OPEN_HANDLEIDING.sh','INSTALL_AUTOSTART.sh',
             'REMOVE_AUTOSTART.sh','LINUX_CHECK.sh','ENSURE_PYTHON.sh','RUN_TESTS.sh']
checks['linux_launchers_exist']=all((ROOT/x).is_file() for x in required_sh)
if os.name!='nt':
    checks['linux_launchers_executable']=all(bool((ROOT/x).stat().st_mode & stat.S_IXUSR) for x in required_sh)
else:
    checks['linux_launchers_executable']=True
checks['windows_launchers_exist']=all((ROOT/x).is_file() for x in ['START_P2000.bat','START_BACKEND.bat','START_CHROME.bat','START_EDGE.bat','STOP_P2000.bat','RUN_TESTS.bat'])
probe=(ROOT/'tools'/'runtime_probe.py').read_text('utf-8')
checks['probe_cross_platform']='SIGTERM' in probe and 'taskkill' in probe and 'fuser' in probe
rollback=(ROOT/'tools'/'rollback_latest.py').read_text('utf-8')
checks['rollback_cross_platform']='SIGTERM' in rollback and 'taskkill' in rollback and 'restore_unix_modes' in rollback
kiosk=(ROOT/'tools'/'kiosk_display.py').read_text('utf-8')
checks['kiosk_cross_platform']='--shell' in kiosk and '"cmd"' in kiosk and '"sh"' in kiosk
readme=(ROOT/'README.md').read_text('utf-8')
checks['readme_multiplatform']='MultiPlatform v4.4.4' in readme and './START_P2000.sh' in readme and 'START_P2000.bat' in readme
failed=[k for k,v in checks.items() if not v]
print({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed})
raise SystemExit(1 if failed else 0)
