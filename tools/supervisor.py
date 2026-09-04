#!/usr/bin/env python3
"""Cross-platform P2000 supervisor/watchdog.

Keeps the backend and kiosk alive, consumes control-page restart commands, detects
monitor reconnects and performs automatic rollback when a freshly installed build
never becomes healthy.
"""
from __future__ import annotations

import argparse, hashlib, json, os, signal, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; UPDATES=DATA/'updates'
STATUS=DATA/'supervisor-status.json'; COMMAND=DATA/'supervisor-command.json'; PIDFILE=DATA/'supervisor.pid'; LOCKFILE=DATA/'supervisor.lock'
PENDING=UPDATES/'pending-health.json'; VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip() if (ROOT/'VERSION').exists() else '4.4.13'
LOG=DATA/'supervisor.log'
_explicit_runtime=os.environ.get('P2000_RUNTIME_DIR')
_runtime_env=os.environ.get('XDG_RUNTIME_DIR')
_runtime_base=Path(_runtime_env) if _runtime_env else Path(os.environ.get('XDG_CACHE_HOME') or (Path.home()/'.cache'))/'p2000-monitor'/'runtime'
if _runtime_env and (not _runtime_base.exists() or not os.access(_runtime_base, os.W_OK | os.X_OK)):
    _runtime_base=Path(os.environ.get('XDG_CACHE_HOME') or (Path.home()/'.cache'))/'p2000-monitor'/'runtime'
RUNDIR=Path(_explicit_runtime) if _explicit_runtime else _runtime_base/f"p2000-monitor-{getattr(os, 'getuid', lambda: 0)()}"
STARTED=time.monotonic()
INSTALL_ID=hashlib.sha256(os.path.realpath(str(ROOT)).encode('utf-8')).hexdigest()[:16]

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

def process_cmdline(pid):
    try:
        if pid<=0:return ''
        if os.name=='nt':
            ps=(f'$p=Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" '
                '-ErrorAction SilentlyContinue; if($p.CommandLine){[Console]::Out.Write($p.CommandLine)}')
            cp=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',ps],capture_output=True,text=True,timeout=6,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return cp.stdout.strip() if cp.returncode==0 else ''
        return (Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ').decode('utf-8','replace').strip()
    except Exception:return ''

def pid_is_this_supervisor(pid):
    cmd=process_cmdline(pid)
    if not cmd:return False
    expected=str((ROOT/'tools'/'supervisor.py').resolve()).replace('\\','/')
    normalized=cmd.replace('\\','/')
    if os.name=='nt':expected=expected.casefold();normalized=normalized.casefold()
    return expected in normalized

def existing_supervisor():
    try:pid=int(PIDFILE.read_text().strip())
    except Exception:return 0
    return pid if pid!=os.getpid() and pid_is_this_supervisor(pid) else 0

_SUPERVISOR_LOCK_HANDLE=None

def claim_pidfile():
    """Hold an OS lock for the process lifetime; return the existing owner."""
    global _SUPERVISOR_LOCK_HANDLE
    DATA.mkdir(parents=True,exist_ok=True)
    handle=LOCKFILE.open('a+b')
    if handle.seek(0,os.SEEK_END)==0:
        handle.write(b'\0');handle.flush()
    handle.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,ImportError):
        handle.close()
        return existing_supervisor() or -1
    _SUPERVISOR_LOCK_HANDLE=handle
    tmp=PIDFILE.with_name(f'{PIDFILE.name}.{os.getpid()}.tmp')
    tmp.write_text(str(os.getpid()),encoding='ascii');os.replace(tmp,PIDFILE)
    if os.name!='nt':
        try:os.chmod(PIDFILE,0o600)
        except OSError:pass
    return 0

def release_pidfile():
    global _SUPERVISOR_LOCK_HANDLE
    try:
        if PIDFILE.exists() and PIDFILE.read_text(encoding='ascii').strip()==str(os.getpid()):PIDFILE.unlink()
    except OSError:pass
    handle=_SUPERVISOR_LOCK_HANDLE;_SUPERVISOR_LOCK_HANDLE=None
    if not handle:return
    try:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except (OSError,ImportError):pass
    try:handle.close()
    except OSError:pass

def stop_supervisor():
    try:pid=int(PIDFILE.read_text(encoding='ascii').strip())
    except Exception:return True
    if pid<=1 or pid==os.getpid() or not pid_is_this_supervisor(pid):
        try:PIDFILE.unlink()
        except OSError:pass
        return True
    try:
        if os.name=='nt':
            cp=subprocess.run(['taskkill','/PID',str(pid),'/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            ok=cp.returncode==0
        else:
            os.kill(pid,signal.SIGTERM);ok=True
            end=time.monotonic()+3
            while time.monotonic()<end and process_cmdline(pid):time.sleep(.1)
            if process_cmdline(pid):os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:ok=True
    except Exception:ok=False
    if ok:
        try:PIDFILE.unlink()
        except OSError:pass
    return ok

def api(path,timeout=1.2):
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
        if r and r.get('app')=='P2000 Monitor' and str(r.get('version'))==VERSION and str(r.get('install_id') or '')==INSTALL_ID:return True
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

def kiosk_process_alive():
    """Return True/False when the dedicated kiosk process can be identified."""
    if os.name=='nt':
        ps=("$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
            "$_.CommandLine -and $_.CommandLine -like '*127.0.0.1:8765*' -and "
            "($_.CommandLine -like '*P2000-Monitor\\BrowserProfile*' -or $_.CommandLine -like '*p2000-monitor*browser-profile*') }; "
            "if($p){[Console]::Out.Write('1')}")
        try:
            cp=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',ps],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return cp.returncode==0 and cp.stdout.strip()=='1'
        except Exception:return None
    helper=ROOT/'tools'/'linux_desktop.py'
    if not helper.exists():return None
    try:
        cp=subprocess.run([sys.executable,str(helper),'kiosk-status','--rundir',str(RUNDIR)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        return cp.returncode==0
    except Exception:return None

def restart_budget_available(history,now,limit=3,window_seconds=900):
    history[:]=[x for x in history if now-x<window_seconds]
    return len(history)<limit

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

def selected_display_state(display):
    try:
        d=(display or {}).get('display',{}) or {}
        m=d.get('selected_monitor',{}) or {}
        selector=str(d.get('selected_monitor_id') or m.get('selector') or m.get('device') or '')
        connected=bool(d.get('selection_connected',d.get('connected',False)))
        geometry=(int(m.get('x',0)),int(m.get('y',0)),int(m.get('width',0)),int(m.get('height',0)))
        return selector,connected,geometry
    except Exception:return '',False,(0,0,0,0)

def consume_command():
    if not COMMAND.exists():return ''
    obj=read_json(COMMAND,{})
    try:COMMAND.unlink()
    except Exception:pass
    return str(obj.get('action') or obj.get('command') or '').strip().lower()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--status',action='store_true');ap.add_argument('--stop',action='store_true');ap.add_argument('--once',action='store_true');ap.add_argument('--no-kiosk',action='store_true')
    a=ap.parse_args()
    if a.stop:return 0 if stop_supervisor() else 2
    RUNDIR.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':
        try:os.chmod(RUNDIR,0o700)
        except OSError:pass
    old=existing_supervisor()
    if a.status:return 0 if old else 1
    old=old or claim_pidfile()
    if old:
        print(f'P2000 supervisor draait al'+(f' (PID {old}).' if old>0 else ' of wordt al gestart.'));return 0
    counters={'backend_restarts':0,'kiosk_restarts':0,'rollbacks':0};state='starting';last_action='';last_error='';backend_failures=0;backend_unhealthy_since=0.0;backend_restart_times=[];kiosk_stale_hits=0;kiosk_missing_hits=0;kiosk_stale_episode_restarted=False;last_display_report='';kiosk_restart_times=[];last_selector='';last_connected=None;last_geometry=None;geometry_candidate=None;geometry_hits=0;last_kiosk_restart=0.0;kiosk_grace_until=STARTED+150;setup_was_incomplete=False;setup_completed_grace_until=0.0
    health={};health_checked=0.0;setup_row={};setup_checked=0.0;disp={};display_checked=0.0;kiosk_alive=None;kiosk_checked=0.0
    log(f'P2000 supervisor v{VERSION} gestart (PID {os.getpid()}).')
    try:
        while True:
            cmd=consume_command()
            if cmd=='restart-backend':
                last_action='Backend handmatig herstart';log(last_action);terminate_backend();time.sleep(.4);start_backend();counters['backend_restarts']+=1;backend_failures=0;backend_unhealthy_since=0.0
            elif cmd=='restart-kiosk' and not a.no_kiosk:
                last_action='Kiosk handmatig herstart';log(last_action);kill_kiosk();time.sleep(.4);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic();kiosk_grace_until=last_kiosk_restart+150;kiosk_stale_episode_restarted=False;kiosk_stale_hits=0;kiosk_missing_hits=0

            loop_now=time.monotonic()
            runtime=api('/api/runtime',2.0)
            backend_ok=bool(runtime and runtime.get('app')=='P2000 Monitor' and str(runtime.get('version'))==VERSION and str(runtime.get('install_id') or '')==INSTALL_ID)
            # /api/health scans cache/database/process metrics and used to run every
            # five seconds. Cache it at supervisor level; runtime is the cheap
            # liveness probe and stays frequent for fast crash recovery.
            if backend_ok and (not health or loop_now-health_checked>=10):
                fresh=api('/api/health',1.2)
                if fresh:
                    health=fresh;health_checked=loop_now
            if backend_ok:backend_failures=0;backend_unhealthy_since=0.0;state='healthy';last_error=''
            else:
                backend_failures+=1
                if not backend_unhealthy_since:backend_unhealthy_since=loop_now
                unhealthy_for=max(0,loop_now-backend_unhealthy_since);state='backend-unhealthy';last_error=f'Backend runtimecheck mislukt ({backend_failures}/5, {unhealthy_for:.0f}s)'
            if backend_failures>=5 and loop_now-backend_unhealthy_since>=20:
                if restart_budget_available(backend_restart_times,loop_now,3,600):
                    rolled=rollback_if_pending()
                    if rolled:counters['rollbacks']+=1
                    terminate_backend();time.sleep(.5)
                    ok=start_backend();backend_restart_times.append(time.monotonic());counters['backend_restarts']+=1
                    last_action='Rollback + backend herstart' if rolled else 'Backend automatisch herstart'
                    log(f'{last_action}: {"OK" if ok else "MISLUKT"}')
                    backend_failures=0;backend_unhealthy_since=0.0;backend_ok=ok
                else:
                    state='backend-restart-paused';last_error='Automatische backendherstart gepauzeerd: 3 pogingen in 10 minuten';backend_failures=4

            kiosk_age=10**9;selector='';display_connected=False;geometry=(0,0,0,0)
            if backend_ok:
                if not setup_row or loop_now-setup_checked>=10:
                    setup_row=api('/api/setup',1.0) or setup_row or {}
                    setup_checked=loop_now
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
                        setup_completed_grace_until=time.monotonic()+150
                        kiosk_stale_hits=0
                        last_action='Configuratiewizard afgerond; kiosk krijgt 150s opstartgrace'
                        log(last_action)
                    h=(health or {}).get('health') or {}
                    display_report=str((h.get('display_client') or {}).get('reported_at') or '')
                    kiosk_age=iso_age(display_report)
                    if display_report and display_report!=last_display_report:
                        last_display_report=display_report
                        if kiosk_age<75:kiosk_stale_episode_restarted=False;kiosk_stale_hits=0;kiosk_missing_hits=0
                    # Monitor enumeration can spawn xrandr/wlr-randr/PowerShell.
                    # Fifteen seconds is responsive enough for reconnects without
                    # continuously hammering the desktop stack.
                    if not disp or loop_now-display_checked>=15:
                        disp=api('/api/display/info',1.5) or disp or {}
                        display_checked=loop_now
                    if kiosk_alive is None or loop_now-kiosk_checked>=15:
                        kiosk_alive=kiosk_process_alive();kiosk_checked=loop_now
                    selector,display_connected,geometry=selected_display_state(disp)
                    # Explicit screen changes already enqueue restart-kiosk from
                    # the backend. Never infer a screen change from focus/order/
                    # fingerprint changes: that caused Linux monitor ping-pong.
                    if selector and last_selector and selector==last_selector:
                        if last_connected is False and display_connected and not a.no_kiosk and time.monotonic()-last_kiosk_restart>20:
                            now=time.monotonic()
                            if restart_budget_available(kiosk_restart_times,now):
                                last_action='Geselecteerd scherm opnieuw aangesloten; kiosk teruggeplaatst';log(last_action);kill_kiosk();time.sleep(.3);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic();kiosk_restart_times.append(last_kiosk_restart);kiosk_grace_until=last_kiosk_restart+150;kiosk_alive=None
                        if display_connected and last_geometry and geometry!=last_geometry:
                            if geometry_candidate==geometry: geometry_hits+=1
                            else: geometry_candidate=geometry;geometry_hits=1
                            if geometry_hits>=2 and not a.no_kiosk and time.monotonic()-last_kiosk_restart>30:
                                now=time.monotonic()
                                if restart_budget_available(kiosk_restart_times,now):
                                    last_action='Geometrie van geselecteerd scherm stabiel gewijzigd; kiosk opnieuw geplaatst';log(last_action);kill_kiosk();time.sleep(.3);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic();kiosk_restart_times.append(last_kiosk_restart);kiosk_grace_until=last_kiosk_restart+150;kiosk_alive=None
                                last_geometry=geometry;geometry_candidate=None;geometry_hits=0
                        else:
                            geometry_candidate=None;geometry_hits=0
                    else:
                        geometry_candidate=None;geometry_hits=0
                    if selector:last_selector=selector
                    last_connected=display_connected
                    if display_connected and last_geometry is None:last_geometry=geometry
                    # Give slow Linux/Snap/Flatpak browser starts enough time and
                    # restart at most once per unchanged stale-heartbeat episode.
                    grace=max(kiosk_grace_until,setup_completed_grace_until)
                    # If the locked monitor is unplugged, restarting the browser
                    # cannot help and may make the compositor move it to primary.
                    stale=display_connected and kiosk_age>150 and time.monotonic()>grace
                    kiosk_stale_hits=(kiosk_stale_hits+1) if stale else 0
                    kiosk_missing_hits=(kiosk_missing_hits+1) if stale and kiosk_alive is False else 0
                    should_restart=(kiosk_missing_hits>=2) or (kiosk_stale_hits>=3 and not kiosk_stale_episode_restarted)
                    if should_restart and not a.no_kiosk and time.monotonic()-last_kiosk_restart>90:
                        now=time.monotonic()
                        if restart_budget_available(kiosk_restart_times,now):
                            reason='Kioskproces ontbreekt; browser automatisch herstart' if kiosk_missing_hits>=2 else 'Kiosk-heartbeat verlopen; eenmalige browserherstart'
                            last_action=reason;log(last_action);kill_kiosk();time.sleep(.3);start_kiosk();counters['kiosk_restarts']+=1;last_kiosk_restart=time.monotonic();kiosk_restart_times.append(last_kiosk_restart);kiosk_grace_until=last_kiosk_restart+150;kiosk_stale_episode_restarted=True;kiosk_stale_hits=0;kiosk_missing_hits=0;kiosk_alive=None
                        else:
                            state='kiosk-restart-paused';last_error='Automatische kioskherstart gepauzeerd: 3 pogingen in 15 minuten';kiosk_stale_episode_restarted=True;kiosk_stale_hits=0;kiosk_missing_hits=0

            write_json(STATUS,{
                'version':VERSION,'pid':os.getpid(),'heartbeat_at':now_iso(),'state':state,'backend_ok':backend_ok,
                'kiosk_heartbeat_age_seconds':None if kiosk_age>=10**8 else round(kiosk_age,1),'kiosk_process_alive':kiosk_alive,'display_selector':selector or last_selector,'display_connected':display_connected,
                **counters,'last_action':last_action,'last_error':last_error,
            })
            if a.once:return 0 if backend_ok else 2
            time.sleep(2)
    except KeyboardInterrupt:return 0
    finally:
        release_pidfile()

if __name__=='__main__':raise SystemExit(main())
