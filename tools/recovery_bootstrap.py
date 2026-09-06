#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PENDING=ROOT/'data'/'updates'/'pending-health.json'
JOURNAL=ROOT/'data'/'updates'/'transaction.json'

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def readj(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}
def writej(p,o):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(t,p)

def mirror_restore(src:Path,dst:Path,preserve=('data','config')):
    src=src.resolve(); dst=dst.resolve(); preserve=set(preserve)
    wanted={p.name for p in src.iterdir() if p.name!='backup.json'}
    for child in list(dst.iterdir()):
        if child.name in preserve or child.name.startswith('.git'): continue
        if child.name not in wanted:
            if child.is_dir(): shutil.rmtree(child)
            else: child.unlink(missing_ok=True)
    for s in src.iterdir():
        if s.name=='backup.json' or s.name in preserve: continue
        d=dst/s.name; tmp=dst/(s.name+'.restore-tmp')
        if tmp.exists(): shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink()
        if s.is_dir(): shutil.copytree(s,tmp)
        else: shutil.copy2(s,tmp)
        if d.exists(): shutil.rmtree(d) if d.is_dir() else d.unlink()
        os.replace(tmp,d)

def recover_pending() -> dict:
    if JOURNAL.exists():
        meta=readj(JOURNAL); backup=Path(str(meta.get('backup') or ''))
        if str(meta.get('state') or '') in {'applying','rollback-failed'} and backup.is_dir():
            mirror_restore(backup,ROOT); meta.update(state='recovered',recovered_at=now());writej(JOURNAL,meta)
    if not PENDING.exists(): return {'ok':True,'action':'none'}
    meta=readj(PENDING); backup=Path(str(meta.get('backup') or ''))
    attempts=int(meta.get('attempt_count') or 0)+1
    meta.update(attempt_count=attempts,last_attempt_at=now())
    if not backup.is_dir():
        meta['last_error']='backup ontbreekt';writej(PENDING,meta);return {'ok':False,'error':'backup ontbreekt'}
    try:
        mirror_restore(backup,ROOT)
        meta.update(state='rolled-back',rollback_completed_at=now(),last_error='');writej(PENDING,meta)
        return {'ok':True,'action':'rollback','backup':str(backup)}
    except Exception as exc:
        meta.update(state='rollback-failed',last_error=f'{type(exc).__name__}: {exc}');writej(PENDING,meta)
        return {'ok':False,'error':meta['last_error']}

def main():
    r=recover_pending();print(json.dumps(r,ensure_ascii=False));return 0 if r.get('ok') else 3
if __name__=='__main__': raise SystemExit(main())
