#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from health_gate import evaluate_installation_health
from recovery_bootstrap import recover_pending
ROOT=Path(__file__).resolve().parents[1]
VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
INSTALL_ID=hashlib.sha256(os.path.realpath(str(ROOT)).encode()).hexdigest()[:16]
LOCK=ROOT/'data'/'startup.lock'

def api(path,timeout=1.2):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:8765{path}',timeout=timeout) as r:return json.loads(r.read().decode())
    except Exception:return None

def semantic_ok():
    rt=api('/api/runtime'); h=api('/api/health')
    if not rt or rt.get('app')!='P2000 Monitor' or str(rt.get('version'))!=VERSION or str(rt.get('install_id') or '')!=INSTALL_ID:return False
    local=evaluate_installation_health(ROOT,expected_version=VERSION,runtime_payload=rt)
    return bool(local['ok'] and isinstance(h,dict) and h.get('ok') is True and not h.get('critical_failures'))

def lock_handle(timeout=35):
    LOCK.parent.mkdir(parents=True,exist_ok=True);f=LOCK.open('a+b')
    if f.seek(0,2)==0:f.write(b'0');f.flush()
    end=time.monotonic()+timeout
    while True:
        try:
            f.seek(0)
            if os.name=='nt':
                import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            return f
        except OSError:
            if semantic_ok(): f.close();return None
            if time.monotonic()>=end:f.close();raise TimeoutError('startup-lock bleef bezet')
            time.sleep(.25)

def unlock(f):
    if not f:return
    try:
        f.seek(0)
        if os.name=='nt':
            import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    finally:f.close()

def run_probe(*args,timeout=20):
    return subprocess.run([sys.executable,str(ROOT/'tools'/'runtime_probe.py'),*args],cwd=ROOT,timeout=timeout).returncode

def spawn_backend():
    env=os.environ.copy();env['P2000_SUPERVISED']='1'
    cmd=['cmd.exe','/c',str(ROOT/'RUN_BACKEND.bat')] if os.name=='nt' else ['bash',str(ROOT/'RUN_BACKEND.sh')]
    subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')

def ensure_supervisor():
    cp=subprocess.run([sys.executable,str(ROOT/'tools'/'supervisor.py'),'--status'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if cp.returncode==0:return
    subprocess.run([sys.executable,str(ROOT/'tools'/'supervisor.py'),'--stop'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.Popen([sys.executable,str(ROOT/'tools'/'supervisor.py')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')

def startup():
    f=lock_handle()
    if f is None:return 0
    try:
        global VERSION
        rec=recover_pending()
        if not rec.get('ok'): print('[FOUT] recovery:',rec.get('error'),file=sys.stderr);return 3
        # Recovery may have restored an older VERSION. The stable guard keeps running
        # from memory, but all probes/health gates must follow the restored release.
        VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
        if run_probe('--version',VERSION,'--kill-stale')!=0:return 4
        if not semantic_ok():
            spawn_backend(); end=time.monotonic()+20
            while time.monotonic()<end and not semantic_ok():time.sleep(.5)
        if not semantic_ok():
            run_probe('--version',VERSION,'--kill-stale');spawn_backend();end=time.monotonic()+20
            while time.monotonic()<end and not semantic_ok():time.sleep(.5)
        if not semantic_ok():return 5
        ensure_supervisor();return 0
    finally:unlock(f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',action='store_true');a=ap.parse_args()
    if a.probe:return 0 if semantic_ok() else 2
    return startup()
if __name__=='__main__':raise SystemExit(main())
