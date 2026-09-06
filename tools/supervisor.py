#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, signal, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from health_gate import evaluate_installation_health
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';PID=DATA/'supervisor.pid';LOCK=DATA/'supervisor.lock';STATUS=DATA/'supervisor-status.json';VERSION=(ROOT/'VERSION').read_text().strip();INSTALL_ID=hashlib.sha256(os.path.realpath(str(ROOT)).encode()).hexdigest()[:16]

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def writej(p,o):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(o,indent=2));os.replace(t,p)
def cmdline(pid):
    try:
        if os.name=='nt':
            ps=f'$p=Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" -ErrorAction SilentlyContinue; if($p.CommandLine){{$p.CommandLine}}'
            return subprocess.run(['powershell.exe','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=5).stdout.strip()
        return (Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ').decode()
    except Exception:return ''
def mine(pid):return str((ROOT/'tools'/'supervisor.py').resolve()).replace('\\','/').casefold() in cmdline(pid).replace('\\','/').casefold()
def api(path,t=1.2):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:8765{path}',timeout=t) as r:return json.loads(r.read().decode())
    except Exception:return None
def health_ok():
    rt=api('/api/runtime');h=api('/api/health')
    if not rt or rt.get('app')!='P2000 Monitor' or str(rt.get('version'))!=VERSION or str(rt.get('install_id') or '')!=INSTALL_ID:return False
    loc=evaluate_installation_health(ROOT,expected_version=VERSION,runtime_payload=rt)
    return bool(loc['ok'] and isinstance(h,dict) and h.get('ok') is True and not h.get('critical_failures'))
def claim():
    DATA.mkdir(parents=True,exist_ok=True);f=LOCK.open('a+b');
    if f.seek(0,2)==0:f.write(b'0');f.flush()
    try:
        f.seek(0)
        if os.name=='nt':import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except Exception:f.close();return None
    PID.write_text(str(os.getpid()));return f
def stop():
    try:p=int(PID.read_text().strip())
    except Exception:return True
    if p<=1 or not mine(p):PID.unlink(missing_ok=True);return True
    try:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(p),'/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        else:os.kill(p,signal.SIGTERM)
    except Exception:pass
    end=time.monotonic()+4
    while time.monotonic()<end and mine(p):time.sleep(.1)
    ok=not mine(p)
    if ok:PID.unlink(missing_ok=True)
    return ok
def start_backend():
    env=os.environ.copy();env['P2000_SUPERVISED']='1';cmd=['cmd.exe','/c',str(ROOT/'RUN_BACKEND.bat')] if os.name=='nt' else ['bash',str(ROOT/'RUN_BACKEND.sh')]
    subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--status',action='store_true');ap.add_argument('--stop',action='store_true');ap.add_argument('--once',action='store_true');a=ap.parse_args()
    if a.status:
        try:p=int(PID.read_text().strip())
        except Exception:return 1
        return 0 if mine(p) else 1
    if a.stop:return 0 if stop() else 2
    f=claim()
    if not f:return 0
    failures=0
    try:
        while True:
            ok=health_ok();state='healthy' if ok else 'unhealthy'
            if ok:failures=0
            else:
                failures+=1
                if failures>=3:
                    subprocess.run([sys.executable,str(ROOT/'tools'/'runtime_probe.py'),'--stop'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    start_backend();end=time.monotonic()+20
                    while time.monotonic()<end and not health_ok():time.sleep(.5)
                    ok=health_ok();state='healthy' if ok else 'backend-restart-failed';failures=0
            writej(STATUS,{'version':VERSION,'pid':os.getpid(),'heartbeat_at':now(),'state':state,'backend_ok':ok})
            if a.once:return 0 if ok else 2
            time.sleep(2)
    finally:
        try:
            if PID.exists() and PID.read_text().strip()==str(os.getpid()):PID.unlink()
        except Exception:pass
        f.close()
if __name__=='__main__':raise SystemExit(main())
