#!/usr/bin/env python3
"""Cross-platform P2000 supervisor/watchdog.

Keeps the backend and kiosk alive, consumes control-page restart commands, detects
monitor reconnects and performs automatic rollback when a freshly installed build
never becomes healthy.
"""
from __future__ import annotations

import argparse, json, os, signal, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; UPDATES=DATA/'updates'
STATUS=DATA/'supervisor-status.json'; COMMAND=DATA/'supervisor-command.json'; PIDFILE=DATA/'supervisor.pid'
PENDING=UPDATES/'pending-health.json'; VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip() if (ROOT/'VERSION').exists() else '4.4.2'
LOG=DATA/'supervisor.log'
_runtime_base=Path(os.environ.get('XDG_RUNTIME_DIR') or '/tmp')
if not _runtime_base.exists() or not os.access(_runtime_base, os.W_OK | os.X_OK): _runtime_base=Path('/tmp')
RUNDIR=_runtime_base/f"p2000-monitor-{getattr(os, 'getuid', lambda: 0)()}"
STARTED=time.monotonic()

def now_iso(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def log(msg):
    line=f"[{now_iso()}] {msg}"
    print(line,flush=True)
    try:
        DATA.mkdir(parents=True,exist_ok=True)
        with LOG.open('a',encoding='utf-8') as f:f.write(line+'\n')
        if LOG.stat().st_size>2_000_000:
            tail=LOG.read_text(encoding='utf-8',errors='replace')[-700_000:];LOG.write_text(tail,encoding='utf-8')
    except Exception:pass

def read_json(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return {} if default is None else default

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)

def pid_alive(pid):
    try:
        if pid<=0:return False
        if os.name=='nt':
            cp=subprocess.run(['tasklist','/FI',f'PID eq {pid}'],capture_output=True,text=True,timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));return str(pid) in cp.stdout
        os.kill(pid,0);return True
    except Exception:return False

def existing_supervisor():
    try:pid=int(PIDFILE.read_text().strip())
    except Exception:return 0
    return pid if pid!=os.getpid() and pid_alive(pid) else 0

def api(path,timeout=2.0):
    try:
        req=urllib.request.Request(f'http://127.0.0.1:8765{path}',headers={'User-Agent':'P2000-Supervisor/4.4'})
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8','replace'))
    except Exception:return None

def iso_age(value):
    if not value:return 10**9
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return max(0,(datetime.now(timezone.utc)-d.astimezone(timezone.utc)).total_seconds())
    except Exception:return 10**9

def terminate_backend():
    subprocess.run([sys.executable,str(ROOT/'tools'/'runtime_probe.py'),'--stop'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)

def start_backend():
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
    with open(LOG,'a',encoding='utf-8') as out:
        subprocess.Popen([sys.executable,str(ROOT/'backend'/'server.py')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,creationflags=flags,start_new_session=(os.name!='nt'))
    end=time.monotonic()+18
    while time.monotonic()<end:
        r=api('/api/runtime',1)
        if r and r.get('app')=='P2000 Monitor':return True
        time.sleep(.5)
    return False

def kill_kiosk():
    if os.name=='nt':
        ps=("$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
            "$_.CommandLine -and $_.CommandLine -like '*127.0.0.1:8765*' -and "
            "($_.CommandLine -like '*P2000-Monitor\\BrowserProfile*' -or $_.CommandLine -like '*p2000-monitor*browser-profile*') }; "
            "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',ps],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    else:
        helper=ROOT/'tools'/'linux_desktop.py'
        if helper.exists():
            try:
                subprocess.run([sys.executable,str(helper),'stop-kiosk','--rundir',str(RUNDIR)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
                return
            except Exception:
                pass
        # Conservative fallback for very old installs without linux_desktop.py.
        for pf in [RUNDIR/'browser.pid']:
            try:
                pid=int(pf.read_text().strip());os.kill(pid,signal.SIGTERM);pf.unlink(missing_ok=True)
            except Exception:pass

def start_kiosk():
    env=os.environ.copy();env['P2000_SUPERVISED']='1'
    if os.name=='nt':
        cmd=['cmd.exe','/c',str(ROOT/'START_P2000.bat')];flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    else:
        cmd=['bash',str(ROOT/'START_P2000.sh')];flags=0
    with open(LOG,'a',encoding='utf-8') as out:
        subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,creationflags=flags,start_new_session=(os.name!='nt'))
    return True

def rollback_if_pending():
    if not PENDING.exists():return False
    meta=read_json(PENDING,{})
    age=iso_age(meta.get('started_at') or meta.get('created_at'))
    # Only consider a pending marker rollback-worthy during the first 15 minutes.
    if age>900:
        try:PENDING.unlink()
        except Exception:pass
        return False
    log(f"Nieuwe build bleef ongezond; automatische rollback ({meta.get('target_version','?')}).")
    try:
        cp=subprocess.run([sys.executable,str(ROOT/'tools'/'rollback_latest.py')],cwd=ROOT,capture_output=True,text=True,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        log((cp.stdout or cp.stderr or '').strip()[-1000:])
        try:PENDING.unlink()
        except Exception:pass
        return cp.returncode==0
    except Exception as e:log(f'Rollback fout: {e}');return False

def selected_fingerprint(display):
    try:return str((display or {}).get('display',{}).get('selected_monitor',{}).get('fingerprint') or '')
    except Exception:return ''

def consume_command():
    if not COMMAND.exists():return ''
    obj=read_json(COMMAND,{})
    try:COMMAND.unlink()
    except Exception:pass
    return str(obj.get('action') or obj.get('command') or '').strip().lower()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--status',action='store_true');ap.add_argument('--once',action='store_true');ap.add_argument('--no-kiosk',action='store_true')
    a=ap.parse_args()
    old=existing_supervisor()
    if a.status:return 0 if old else 1
    if old:
        print(f'P2000 supervisor draait al (PID {old}).');return 0
    DATA.mkdir(parents=True,exist_ok=True);PIDFILE.write_text(str(os.getpid()),encoding='utf-8')
    counters={'backend_restarts':0,'kiosk_restarts':0,'rollbacks':0};state='starting';last_action='';last_error='';backend_failures=0;kiosk_stale_hits=0;last_fp='';last_kiosk_restart=0.0;setup_was_incomplete=False;setup_completed_grace_until=0.0
    log(f'P2000 supervisor v{VERSION} gestart (PID {os.getpid()}).')
    try:
        while True:
            cmd=consume_command()
            if cmd=='restart-backend':
                last_action='Backend handmatig herstart';log(last_action);terminate_backend();time.sleep(.4);start_backend();counters['backend_restarts']+=1;backend_failures=0
            elif cmd=='restart-kiosk' and not a.no_kiosk:
                last_action='Kiosk handmatig herstart';log(last_action);kill_kiosk();time.sleep(.4);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic()

            runtime=api('/api/runtime',1.2);health=api('/api/health',1.8) if runtime else None
            backend_ok=bool(runtime and runtime.get('app')=='P2000 Monitor' and health and health.get('ok'))
            if backend_ok:backend_failures=0;state='healthy';last_error=''
            else:
                backend_failures+=1;state='backend-unhealthy';last_error=f'Backend healthcheck mislukt ({backend_failures}/3)'
            if backend_failures>=3:
                rolled=rollback_if_pending()
                if rolled:counters['rollbacks']+=1
                terminate_backend();time.sleep(.5)
                ok=start_backend();counters['backend_restarts']+=1
                last_action='Rollback + backend herstart' if rolled else 'Backend automatisch herstart'
                log(f'{last_action}: {"OK" if ok else "MISLUKT"}')
                backend_failures=0;backend_ok=ok

            kiosk_age=10**9;fp=''
            if backend_ok:
                setup_row=api('/api/setup',1.5) or {}
                setup_complete=bool((setup_row.get('setup') or {}).get('setup_complete'))
                if not setup_complete:
                    # The setup wizard intentionally does not send the lightkrant
                    # heartbeat. Never restart the user's browser while they are
                    # still filling in the wizard, even if that takes hours.
                    setup_was_incomplete=True
                    kiosk_stale_hits=0
                    state='setup-required'
                else:
                    if setup_was_incomplete:
                        setup_was_incomplete=False
                        setup_completed_grace_until=time.monotonic()+90
                        kiosk_stale_hits=0
                        last_action='Configuratiewizard afgerond; kiosk krijgt 90s opstartgrace'
                        log(last_action)
                    h=(health or {}).get('health') or {}
                    kiosk_age=iso_age((h.get('display_client') or {}).get('reported_at'))
                    disp=api('/api/display/info',2);fp=selected_fingerprint(disp)
                    if fp and last_fp and fp!=last_fp and not a.no_kiosk and time.monotonic()-last_kiosk_restart>30:
                        last_action='Monitor gewijzigd/herverbonden; kiosk opnieuw geplaatst';log(last_action);kill_kiosk();time.sleep(.3);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic()
                    if fp:last_fp=fp
                    # Give browser 90s boot grace and another 90s after setup.
                    grace=max(STARTED+90,setup_completed_grace_until)
                    stale=kiosk_age>75 and time.monotonic()>grace
                    kiosk_stale_hits=(kiosk_stale_hits+1) if stale else 0
                    if kiosk_stale_hits>=2 and not a.no_kiosk and time.monotonic()-last_kiosk_restart>60:
                        last_action='Kiosk-heartbeat verlopen; browser automatisch herstart';log(last_action);kill_kiosk();time.sleep(.3);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic();kiosk_stale_hits=0

            write_json(STATUS,{
                'version':VERSION,'pid':os.getpid(),'heartbeat_at':now_iso(),'state':state,'backend_ok':backend_ok,
                'kiosk_heartbeat_age_seconds':None if kiosk_age>=10**8 else round(kiosk_age,1),'display_fingerprint':fp or last_fp,
                **counters,'last_action':last_action,'last_error':last_error,
            })
            if a.once:return 0 if backend_ok else 2
            time.sleep(5)
    except KeyboardInterrupt:return 0
    finally:
        try:
            if PIDFILE.exists() and PIDFILE.read_text().strip()==str(os.getpid()):PIDFILE.unlink()
        except Exception:pass

if __name__=='__main__':raise SystemExit(main())
