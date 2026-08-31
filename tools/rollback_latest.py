#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKUPS=ROOT/'data'/'updates'/'backups'

def listener_pids(port='8765'):
    try:
        cp=subprocess.run(['netstat','-ano','-p','tcp'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception:return set()
    out=set()
    for line in cp.stdout.splitlines():
        parts=line.split()
        if len(parts)>=4 and parts[0].upper()=='TCP' and parts[1].endswith(':'+port) and parts[-1].isdigit():out.add(int(parts[-1]))
    return out

def main():
    if not BACKUPS.exists():
        print('[FOUT] Er zijn nog geen updatebackups.');return 2
    rows=sorted([p for p in BACKUPS.iterdir() if p.is_dir() and (p/'backend'/'server.py').is_file()],key=lambda p:p.stat().st_mtime,reverse=True)
    if not rows:
        print('[FOUT] Geen bruikbare vorige versie gevonden.');return 2
    backup=rows[0];version='onbekend'
    try:version=str(json.loads((backup/'backup.json').read_text(encoding='utf-8')).get('version') or version)
    except Exception:pass
    print(f'[P2000] Vorige programmaversie herstellen: {version}')
    for pid in sorted(listener_pids()):
        try:subprocess.run(['taskkill','/PID',str(pid),'/F'],capture_output=True,timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:pass
    time.sleep(.5)
    for src in backup.iterdir():
        if src.name=='backup.json':continue
        dst=ROOT/src.name
        if src.is_dir():
            if dst.exists() and dst.is_dir():shutil.rmtree(dst,ignore_errors=True)
            shutil.copytree(src,dst)
        else:
            shutil.copy2(src,dst)
    print(f'[OK] P2000 Monitor {version} is teruggezet. Config en data zijn behouden.')
    return 0

if __name__=='__main__':raise SystemExit(main())
