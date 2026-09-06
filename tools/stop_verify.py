#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('probe',ROOT/'tools'/'runtime_probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
    back=m.p2000_processes('backend');sup=m.p2000_processes('supervisor');owned=set(back)|set(sup)
    listeners=m.listener_pids(); bad_listener=bool(set(back)&listeners)
    helper=ROOT/'tools'/('windows_desktop.py' if sys.platform.startswith('win') else 'linux_desktop.py')
    kiosk=False
    if helper.is_file():
        args=[sys.executable,str(helper),'status' if sys.platform.startswith('win') else 'kiosk-status']
        if not sys.platform.startswith('win'):
            import os
            rd=os.environ.get('P2000_RUNTIME_DIR') or str(Path(os.environ.get('XDG_RUNTIME_DIR') or (Path.home()/'.cache'/'p2000-monitor'/'runtime'))/f'p2000-monitor-{getattr(os,"getuid",lambda:0)()}')
            args += ['--rundir',rd]
        kiosk=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if owned or bad_listener or kiosk:
        print('[FOUT] P2000 is niet volledig gestopt.')
        if back: print('Backend:',m.describe_pids(set(back)))
        if sup: print('Supervisor:',m.describe_pids(set(sup)))
        if kiosk: print('Dedicated kiosk leeft nog.')
        return 2
    print('[OK] Geen eigen supervisor/backend/kiosk meer actief.')
    return 0
if __name__=='__main__':raise SystemExit(main())
