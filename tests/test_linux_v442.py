from __future__ import annotations
import importlib.util, os, subprocess, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'tools'/'linux_desktop.py'

def load_helper():
    spec=importlib.util.spec_from_file_location('linux_desktop_v442',HELPER)
    mod=importlib.util.module_from_spec(spec);import sys;sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod

mod=load_helper()
checks={}
with tempfile.TemporaryDirectory() as td:
    t=Path(td); home=t/'home';config=t/'config';state=t/'state';runtime=t/'runtime'
    for p in (home,config,state,runtime):p.mkdir(parents=True,exist_ok=True)
    fake=t/'fake-chromium';args=t/'args.log'
    fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$P2000_FAKE_ARGS"\nsleep 4\n',encoding='utf-8');fake.chmod(0o755)
    env=os.environ.copy();env.update({'HOME':str(home),'XDG_CONFIG_HOME':str(config),'XDG_STATE_HOME':str(state),'XDG_RUNTIME_DIR':str(runtime),'DISPLAY':':99','P2000_BROWSER':str(fake),'P2000_FAKE_ARGS':str(args)})
    cp=subprocess.run([os.environ.get('P2000_PYTHON',os.sys.executable),str(HELPER),'open','--url','http://127.0.0.1:8765/setup.html?edit=1','--probe-seconds','.4'],env=env,capture_output=True,text=True,timeout=8)
    checks['wizard_browser_launch']=cp.returncode==0 and args.exists() and '--new-window http://127.0.0.1:8765/setup.html?edit=1' in args.read_text()
    cp2=subprocess.run([os.environ.get('P2000_PYTHON',os.sys.executable),str(HELPER),'kiosk','--url','http://127.0.0.1:8765/','--position','1920,0','--size','1920,1080','--probe-seconds','.4'],env=env,capture_output=True,text=True,timeout=8)
    txt=args.read_text() if args.exists() else ''
    checks['kiosk_geometry']=cp2.returncode==0 and '--window-position=1920,0' in txt and '--kiosk http://127.0.0.1:8765/' in txt
    # Stop must never kill this test process/parent shell; it may kill only browser-profile processes.
    cp3=subprocess.run([os.environ.get('P2000_PYTHON',os.sys.executable),str(HELPER),'stop-kiosk'],env=env,capture_output=True,text=True,timeout=8)
    checks['safe_stop']=cp3.returncode==0
    # Confinement-safe Snap location is deterministic without requiring snap itself.
    c=mod.Candidate('/snap/bin/chromium','chromium','Chromium (Snap)',['/snap/bin/chromium'],'snap','chromium','')
    old_home=mod.HOME; mod.HOME=home
    try: checks['snap_profile']=str(mod.profile_path(c,'kiosk')).endswith('/snap/chromium/common/p2000-monitor-kiosk')
    finally: mod.HOME=old_home
checks['wizard_script_shared']=(ROOT/'CONFIGURATIE_WIZARD.sh').read_text().find('LINUX_OPEN_PAGE.sh')>=0
checks['autostart_retry']='for attempt in 1 2 3' in (ROOT/'START_P2000_AUTOSTART.sh').read_text()
checks['proc_port_fallback']='def _proc_listener_pids' in (ROOT/'tools'/'runtime_probe.py').read_text()

checks['root_guard']='P2000_ALLOW_ROOT_RUN' in (ROOT/'START_P2000.sh').read_text()
checks['firefox_autoplay']='media.autoplay.default' in HELPER.read_text()
checks['wayland_dpms_safe']='real_x11' in (ROOT/'backend'/'server.py').read_text()
failed=[k for k,v in checks.items() if not v]
print({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed})
if failed: raise SystemExit(1)
