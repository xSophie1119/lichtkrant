#!/usr/bin/env python3
from __future__ import annotations
import ctypes,json,os,urllib.request
from ctypes import wintypes

def get_monitors():
    if os.name != "nt": return [{"device":"primary","x":0,"y":0,"width":1920,"height":1080,"primary":True}]
    user32=ctypes.windll.user32
    class RECT(ctypes.Structure): _fields_=[("left",wintypes.LONG),("top",wintypes.LONG),("right",wintypes.LONG),("bottom",wintypes.LONG)]
    class MI(ctypes.Structure): _fields_=[("cbSize",wintypes.DWORD),("rcMonitor",RECT),("rcWork",RECT),("dwFlags",wintypes.DWORD),("szDevice",wintypes.WCHAR*32)]
    rows=[];CB=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(RECT),wintypes.LPARAM)
    def collect(h,dc,r,l):
        i=MI();i.cbSize=ctypes.sizeof(i)
        if user32.GetMonitorInfoW(h,ctypes.byref(i)):
            q=i.rcMonitor;rows.append({"device":str(i.szDevice),"x":int(q.left),"y":int(q.top),"width":int(q.right-q.left),"height":int(q.bottom-q.top),"primary":bool(i.dwFlags&1)})
        return True
    cb=CB(collect);user32.EnumDisplayMonitors(0,0,cb,0);rows.sort(key=lambda r:(not r["primary"],r["x"],r["y"],r["device"]));return rows

def wanted_monitor():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/settings",timeout=2) as r:return str(json.load(r).get("settings",{}).get("kioskMonitor","primary") or "primary")
    except Exception:return "primary"

def choose(rows,wanted):
    if wanted.lower() not in {"primary","primair","auto"}:
        for r in rows:
            if r["device"].lower()==wanted.lower():return r
        if wanted.isdigit() and 0<int(wanted)<=len(rows):return rows[int(wanted)-1]
    return next((r for r in rows if r["primary"]),rows[0] if rows else {"device":"primary","x":0,"y":0,"width":1920,"height":1080,"primary":True})

r=choose(get_monitors(),wanted_monitor())
print(f'set "P2000_WINDOW_POSITION={r["x"]},{r["y"]}"')
print(f'set "P2000_WINDOW_SIZE={max(320,r["width"])},{max(240,r["height"])}"')
print(f'set "P2000_DISPLAY_DEVICE={r["device"]}"')
