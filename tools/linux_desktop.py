#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, shutil, signal, subprocess, time
from pathlib import Path
DEFAULT_URL='http://127.0.0.1:8765/';STATE=Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state')/'p2000-monitor';DATA=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'p2000-monitor';LOG=STATE/'browser.log'
def log(s):
    try:STATE.mkdir(parents=True,exist_ok=True);LOG.open('a').write(f'[{time.strftime("%F %T")}] {s}\n')
    except Exception:pass
def _cmd(pid):
    try:return (Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ').decode('utf-8','replace')
    except Exception:return ''
def _all():
    out=[];proc=Path('/proc')
    if not proc.is_dir():return out
    for p in proc.iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=os.getuid():continue
        except Exception:continue
        c=_cmd(int(p.name))
        if c:out.append((int(p.name),c))
    return out
def _profile(kind):return DATA/f'browser-profile-{kind}'
def _owned(profile:Path,url=DEFAULT_URL):
    key=str(profile.resolve()).replace('\\','/').casefold();host='127.0.0.1:8765'
    return [(pid,c) for pid,c in _all() if key in c.replace('\\','/').casefold() and host in c]
def _profile_in_use(profile):return bool(_owned(profile))
def _browsers(pref=''):
    rows=[];seen=set();cands=[('chrome',['google-chrome-stable','google-chrome']),('chromium',['chromium','chromium-browser'])]
    for kind,names in cands:
        for n in names:
            p=shutil.which(n)
            if p and p not in seen:seen.add(p);rows.append((kind,[p]));break
    snap=shutil.which('snap')
    if snap:
        rows += [('chromium-snap',[snap,'run','chromium']),('chrome-snap',[snap,'run','chromium'])]
    flat=shutil.which('flatpak')
    if flat:
        rows += [('chromium-flatpak',[flat,'run','org.chromium.Chromium']),('chrome-flatpak',[flat,'run','com.google.Chrome'])]
    p=str(pref or '').casefold();rows.sort(key=lambda r:0 if p and p in r[0] else 1);return rows
def _clean(profile):
    if _profile_in_use(profile):return False
    for n in ('SingletonLock','SingletonCookie','SingletonSocket','LOCK'):
        try:(profile/n).unlink(missing_ok=True)
        except OSError:pass
    return True
def status(rundir):
    for kind,_ in _browsers(''):
        if _owned(_profile(kind)):return True
    return False
def stop(rundir):
    victims=[]
    for kind,_ in _browsers(''):victims += _owned(_profile(kind))
    for pid,_ in victims:
        try:os.kill(pid,signal.SIGTERM)
        except OSError:pass
    end=time.monotonic()+4
    while time.monotonic()<end and any(_cmd(pid) for pid,_ in victims):time.sleep(.1)
    for pid,_ in victims:
        if _cmd(pid):
            try:os.kill(pid,signal.SIGKILL)
            except OSError:pass
    return not status(rundir)
def launch(url,position,size,rundir,pref=''):
    rundir.mkdir(parents=True,exist_ok=True)
    if status(rundir):return 0
    try:x,y=map(int,position.split(',',1));w,h=map(int,size.split(',',1))
    except Exception:x=y=0;w=1920;h=1080
    for kind,base in _browsers(pref):
        profile=_profile(kind);profile.mkdir(parents=True,exist_ok=True)
        if not _clean(profile):return 0
        common=[f'--user-data-dir={profile}',f'--window-position={x},{y}',f'--window-size={w},{h}','--no-first-run','--no-default-browser-check','--autoplay-policy=no-user-gesture-required']
        for mode in ('kiosk','app'):
            args=[*base,*common,('--kiosk' if mode=='kiosk' else '--start-fullscreen'),(url if mode=='kiosk' else f'--app={url}')]
            try:subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            except Exception as exc:log(f'{kind}: {exc}');continue
            end=time.monotonic()+8
            while time.monotonic()<end:
                if _owned(profile,url):log(f'{kind} {mode} actief');return 0
                time.sleep(.25)
            if not _profile_in_use(profile):_clean(profile)
    op=shutil.which('xdg-open')
    if op:subprocess.Popen([op,url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);return 0
    return 2
def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='c',required=True);p=sp.add_parser('launch');p.add_argument('--url',default=DEFAULT_URL);p.add_argument('--position',default='0,0');p.add_argument('--size',default='1920,1080');p.add_argument('--browser',default='');p.add_argument('--rundir',required=True)
    for n in ('kiosk-status','stop-kiosk'):q=sp.add_parser(n);q.add_argument('--rundir',required=True)
    a=ap.parse_args();r=Path(a.rundir)
    if a.c=='kiosk-status':return 0 if status(r) else 1
    if a.c=='stop-kiosk':return 0 if stop(r) else 2
    return launch(a.url,a.position,a.size,r,a.browser)
if __name__=='__main__':raise SystemExit(main())
