#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shlex,urllib.request

def info():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/display/info",timeout=2) as r:
            d=json.load(r);x=d.get("display") or {};return x.get("selected_monitor") or {}
    except Exception:return {}

def defaults():return {"device":"primary","x":0,"y":0,"width":1920,"height":1080,"primary":True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shell",choices=("cmd","sh","json"),default=("cmd" if os.name=="nt" else "sh"));a=ap.parse_args()
    r=defaults();r.update({k:v for k,v in info().items() if v is not None})
    vals={"P2000_WINDOW_POSITION":f"{int(r.get('x',0))},{int(r.get('y',0))}","P2000_WINDOW_SIZE":f"{max(320,int(r.get('width',1920)))},{max(240,int(r.get('height',1080)))}","P2000_DISPLAY_DEVICE":str(r.get('device') or r.get('id') or 'primary'),"P2000_DISPLAY_PRIMARY":"1" if bool(r.get('primary')) else "0","P2000_DISPLAY_SELECTOR":str(r.get('selector') or '')}
    if a.shell=="json":print(json.dumps(vals,ensure_ascii=False));return
    for k,v in vals.items():
        if a.shell=="cmd":print(f'set "{k}={v}"')
        else:print(f'export {k}={shlex.quote(v)}')
if __name__=="__main__":main()
