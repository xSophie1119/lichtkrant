#!/usr/bin/env python3
"""Restore the newest P2000 self-update backup on Windows or Linux."""
from __future__ import annotations
import json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKUPS=ROOT/'data'/'updates'/'backups'
PORT='8765'

def _run(argv):
    try:
        return subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception:
        return None

def _proc_listener_pids(port: str) -> set[int]:
    """Find same-user TCP listener PIDs without ss/netstat/fuser."""
    if os.name == "nt" or not os.path.isdir("/proc"):
        return set()
    try:
        port_hex=f"{int(port):04X}"
    except Exception:
        return set()
    inodes=set()
    for table in ("/proc/net/tcp","/proc/net/tcp6"):
        try:
            for line in Path(table).read_text(encoding="ascii",errors="ignore").splitlines()[1:]:
                parts=line.split()
                if len(parts)<10:
                    continue
                local=parts[1];state=parts[3];inode=parts[9]
                if state=="0A" and local.rsplit(":",1)[-1].upper()==port_hex:
                    inodes.add(inode)
        except Exception:
            pass
    if not inodes:
        return set()
    out=set()
    proc=Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        fd=entry/"fd"
        try:
            for link in fd.iterdir():
                try: target=os.readlink(link)
                except OSError: continue
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    out.add(int(entry.name));break
        except (PermissionError,FileNotFoundError,ProcessLookupError):
            continue
    return out

def listener_pids(port: str=PORT) -> set[int]:
    out:set[int]=set()
    if os.name=='nt':
        cp=_run(['netstat','-ano','-p','tcp'])
        if not cp:return out
        for line in cp.stdout.splitlines():
            parts=line.split()
            if len(parts)>=4 and parts[0].upper()=='TCP' and parts[1].endswith(':'+port) and parts[-1].isdigit():
                pid=int(parts[-1])
                if pid>0:out.add(pid)
        return out
    if shutil.which('ss'):
        cp=_run(['ss','-ltnp'])
        if cp:
            for line in cp.stdout.splitlines():
                if re.search(rf':{re.escape(port)}\b',line):
                    out.update(int(x) for x in re.findall(r'pid=(\d+)',line))
    if not out and shutil.which('fuser'):
        cp=_run(['fuser','-n','tcp',port])
        if cp:out.update(int(x) for x in re.findall(r'\b\d+\b',(cp.stdout or '')+' '+(cp.stderr or '')))
    if not out:
        out.update(_proc_listener_pids(port))
    return {x for x in out if x>0}

def stop_backend() -> None:
    pids=listener_pids()
    for pid in sorted(pids):
        try:
            if os.name=='nt': _run(['taskkill','/PID',str(pid),'/F'])
            else: os.kill(pid,signal.SIGTERM)
        except (OSError,PermissionError):pass
    if os.name!='nt' and pids:
        end=time.monotonic()+2
        while time.monotonic()<end:
            alive=[]
            for pid in pids:
                try:os.kill(pid,0);alive.append(pid)
                except OSError:pass
            if not alive:return
            time.sleep(.1)
        for pid in alive:
            try:os.kill(pid,signal.SIGKILL)
            except OSError:pass

def restore_unix_modes() -> None:
    if os.name=='nt':return
    for path in list(ROOT.glob('*.sh'))+[ROOT/'tools'/'run_tests.py',ROOT/'tools'/'runtime_probe.py',ROOT/'tools'/'kiosk_display.py',ROOT/'tools'/'linux_desktop.py',ROOT/'tools'/'rollback_latest.py',ROOT/'tools'/'supervisor.py']:
        try:path.chmod(path.stat().st_mode | 0o111)
        except OSError:pass

def main() -> int:
    if not BACKUPS.exists():
        print('[FOUT] Er zijn nog geen updatebackups.');return 2
    rows=sorted([p for p in BACKUPS.iterdir() if p.is_dir() and (p/'backend'/'server.py').is_file()],
                key=lambda p:p.stat().st_mtime,reverse=True)
    if not rows:
        print('[FOUT] Geen bruikbare vorige versie gevonden.');return 2
    backup=rows[0];version='onbekend'
    try:version=str(json.loads((backup/'backup.json').read_text(encoding='utf-8')).get('version') or version)
    except Exception:pass
    print(f'[P2000] Vorige programmaversie herstellen: {version}')
    stop_backend();time.sleep(.25)
    for src in backup.iterdir():
        if src.name=='backup.json':continue
        dst=ROOT/src.name
        if src.is_dir():
            if dst.exists() and dst.is_dir():shutil.rmtree(dst,ignore_errors=True)
            shutil.copytree(src,dst)
        else:
            shutil.copy2(src,dst)
    restore_unix_modes()
    print(f'[OK] P2000 Monitor {version} is teruggezet. Config en data zijn behouden.')
    return 0

if __name__=='__main__':raise SystemExit(main())
