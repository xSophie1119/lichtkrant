#!/usr/bin/env python3
"""Cross-platform launcher helper for P2000 Monitor."""
from __future__ import annotations
import argparse, hashlib, json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
URL="http://127.0.0.1:8765/api/runtime"; PORT="8765"
INSTALL_ID=hashlib.sha256(os.path.realpath(str(ROOT)).encode("utf-8")).hexdigest()[:16]

def runtime(timeout:float=.8)->dict|None:
    try:
        req=urllib.request.Request(URL,headers={"User-Agent":"P2000-Launcher"})
        with urllib.request.urlopen(req,timeout=timeout) as res:return json.loads(res.read().decode("utf-8","replace"))
    except Exception:return None

def is_current(expected:str)->bool:
    obj=runtime();return bool(obj and obj.get("app")=="P2000 Monitor" and str(obj.get("version"))==expected and str(obj.get("install_id") or "")==INSTALL_ID)

def _run(argv):
    try:return subprocess.run(argv,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=8,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    except Exception:return None

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

def _proc_cmdline(pid:int)->str:
    if os.name=="nt":
        # Query only the requested PID.  netstat can identify the listener, but
        # its command line is required before we may safely terminate it.
        ps=(f'$p=Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" '
            '-ErrorAction SilentlyContinue; if($p.CommandLine){[Console]::Out.Write($p.CommandLine)}')
        cp=_run(["powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-Command",ps])
        if cp and cp.returncode==0 and cp.stdout.strip():return cp.stdout.strip()
        # WMIC is absent on newer Windows builds, but remains a harmless fallback
        # for older/offline machines where PowerShell CIM is unavailable.
        cp=_run(["wmic","process","where",f"processid={int(pid)}","get","CommandLine","/value"])
        if cp and cp.returncode==0:
            for line in cp.stdout.splitlines():
                if line.lower().startswith("commandline="):return line.split("=",1)[1].strip()
        return ""
    try:
        raw=(Path("/proc")/str(pid)/"cmdline").read_bytes().replace(b"\x00",b" ").decode("utf-8","replace").strip()
        return raw
    except Exception:return ""

def _is_this_p2000_backend(pid:int)->bool:
    cmd=_proc_cmdline(pid)
    if not cmd:return False
    normalized=cmd.replace("\\","/")
    expected=str((ROOT/"backend"/"server.py").resolve()).replace("\\","/")
    if os.name=="nt":
        normalized=normalized.casefold();expected=expected.casefold()
    if expected in normalized:return True
    # Symlinked installs may preserve a different textual root in argv. Verify
    # cwd plus the exact backend/server.py suffix before treating it as ours.
    try:
        cwd=os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
        root=os.path.realpath(str(ROOT))
        if cwd==root and re.search(r"(?:^|\s)(?:\S*/)?backend/server\.py(?:\s|$)",cmd):return True
    except Exception:pass
    # Also recognize another extracted/installed P2000 version. This is common
    # during manual Linux upgrades: the old backend may still own 8765 while the
    # user starts the new folder. Only accept a server.py whose project root has
    # the P2000 VERSION + frontend/index.html markers.
    candidates=[]
    for quoted,bare in re.findall(r'(?i)(?:"([^"\r\n]*backend[\\/]server\.py)"|([^\s"\r\n]*backend[\\/]server\.py))',cmd):
        candidates.append(quoted or bare)
    for token in candidates:
        try:
            server=Path(token).resolve();project=server.parent.parent
            if (project/"VERSION").is_file() and (project/"frontend"/"index.html").is_file():return True
        except Exception:pass
    return False

def describe_listener_pids(pids:set[int])->str:
    rows=[]
    for pid in sorted(pids):
        cmd=_proc_cmdline(pid)
        rows.append(f"PID {pid}"+(f": {cmd[:240]}" if cmd else ""))
    return "; ".join(rows) if rows else "geen listener gevonden"

def listener_pids()->set[int]:
    if os.name=="nt":
        cp=_run(["netstat","-ano","-p","tcp"]); result=set()
        if not cp:return result
        for raw in cp.stdout.splitlines():
            parts=raw.split()
            if len(parts)>=4 and parts[0].upper()=="TCP" and parts[1].endswith(":"+PORT) and parts[-1].isdigit():
                pid=int(parts[-1]);
                if pid>0:result.add(pid)
        return result
    result=set()
    cp=_run(["ss","-ltnp"]) if _which("ss") else None
    if cp:
        for line in cp.stdout.splitlines():
            if re.search(rf":{PORT}\b",line):
                result.update(int(x) for x in re.findall(r"pid=(\d+)",line))
    if not result and _which("fuser"):
        cp=_run(["fuser","-n","tcp",PORT])
        if cp: result.update(int(x) for x in re.findall(r"\b\d+\b",cp.stdout+" "+cp.stderr))
    if not result:
        result.update(_proc_listener_pids(PORT))
    return {p for p in result if p>0}

def _which(name):
    import shutil
    return shutil.which(name)

def terminate_pids(pids:set[int])->bool:
    ok=True
    for pid in sorted(pids):
        try:
            if os.name=="nt":
                cp=_run(["taskkill","/PID",str(pid),"/F"])
                ok=ok and bool((cp and cp.returncode==0) or not _proc_cmdline(pid))
            else:
                os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
        except PermissionError:ok=False
        except Exception: ok=False
    if os.name!="nt" and pids:
        end=time.monotonic()+2
        while time.monotonic()<end:
            alive=[]
            for pid in pids:
                try:os.kill(pid,0);alive.append(pid)
                except OSError:pass
            if not alive:break
            time.sleep(.1)
        for pid in alive if 'alive' in locals() else []:
            try:os.kill(pid,signal.SIGKILL)
            except OSError:pass
    time.sleep(.25);return ok

def kill_stale(expected:str)->bool:
    obj=runtime()
    if is_current(expected):
        return True
    pids=listener_pids()
    if obj and obj.get("app")=="P2000 Monitor":
        if not pids:
            print(f"Oud P2000-proces gevonden ({obj.get('version')}), maar PID op poort 8765 kon niet worden bepaald.")
            return False
        print(f"Oude P2000 backend v{obj.get('version')} op poort 8765 stoppen: {describe_listener_pids(pids)}")
        return terminate_pids(pids)
    if not pids:
        return True
    # A hung P2000 backend may own the socket while /api/runtime no longer answers.
    # Recover that exact process on either OS, but never kill another service.
    ours={pid for pid in pids if _is_this_p2000_backend(pid)}
    if ours:
        print(f"Vastgelopen P2000 backend op poort 8765 herstellen: {describe_listener_pids(ours)}")
        if not terminate_pids(ours):return False
        remaining=listener_pids()
        if remaining:
            print(f"Poort 8765 blijft bezet: {describe_listener_pids(remaining)}")
            return False
        return True
    print(f"Poort 8765 is bezet door een ander proces: {describe_listener_pids(pids)}")
    return False

def _other_p2000_supervisor_pids()->set[int]:
    out=set(); me=os.getpid(); rows=[]
    if os.name=="nt":
        ps=("Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object {$_.CommandLine -and $_.CommandLine -match 'tools[\\\\/]supervisor\\.py'} | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
        cp=_run(["powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-Command",ps])
        if cp and cp.returncode==0 and cp.stdout.strip():
            try:
                data=json.loads(cp.stdout);data=data if isinstance(data,list) else [data]
                rows=[(int(x.get("ProcessId") or 0),str(x.get("CommandLine") or "")) for x in data]
            except Exception:rows=[]
    elif os.path.isdir("/proc"):
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():rows.append((int(entry.name),_proc_cmdline(int(entry.name))))
    for pid,cmd in rows:
        if pid<=0 or pid==me: continue
        if not cmd or "tools/supervisor.py" not in cmd.replace("\\","/").casefold(): continue
        # Only touch recognizable P2000 project supervisors owned by this user.
        if os.name!="nt":
            try:
                if (Path("/proc")/str(pid)).stat().st_uid != os.getuid(): continue
            except Exception:continue
        for quoted,bare in re.findall(r'(?i)(?:"([^"\r\n]*tools[\\/]supervisor\.py)"|([^\s"\r\n]*tools[\\/]supervisor\.py))',cmd):
            try:
                project=Path(quoted or bare).resolve().parent.parent
                if (project/"VERSION").is_file() and (project/"frontend"/"index.html").is_file():
                    out.add(pid);break
            except Exception:pass
    return out

def stop_all_p2000()->bool:
    ok=True
    obj=runtime()
    pids=listener_pids()
    if obj and obj.get("app")=="P2000 Monitor":
        if pids:ok=terminate_pids(pids) and ok
    elif pids:
        ours={pid for pid in pids if _is_this_p2000_backend(pid)}
        if ours:ok=terminate_pids(ours) and ok
    supers=_other_p2000_supervisor_pids()
    if supers:
        print(f"Oude P2000 supervisor(s) stoppen: {', '.join(map(str,sorted(supers)))}")
        ok=terminate_pids(supers) and ok
    return ok

def stop_any()->bool:
    obj=runtime()
    pids=listener_pids()
    if obj and obj.get("app")=="P2000 Monitor":return terminate_pids(pids) if pids else False
    # A wedged backend may not answer /api/runtime.  Stop it only after its
    # command line proves that it is a P2000 backend; leave other services alone.
    ours={pid for pid in pids if _is_this_p2000_backend(pid)}
    return terminate_pids(ours) if ours else True

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--version",default="");ap.add_argument("--wait",type=float,default=0);ap.add_argument("--kill-stale",action="store_true");ap.add_argument("--stop",action="store_true");ap.add_argument("--stop-all",action="store_true");ap.add_argument("--describe-port",action="store_true")
    a=ap.parse_args()
    if a.stop_all:return 0 if stop_all_p2000() else 2
    if a.stop:return 0 if stop_any() else 2
    if a.describe_port:
        pids=listener_pids();print(describe_listener_pids(pids));return 0 if not pids else 1
    if not a.version:ap.error("--version is required unless --stop/--describe-port is used")
    if a.kill_stale:
        if not kill_stale(a.version):return 3
        if a.wait<=0:return 0
    if a.wait>0:
        end=time.monotonic()+a.wait
        while time.monotonic()<end:
            if is_current(a.version):return 0
            time.sleep(.3)
        return 1
    return 0 if is_current(a.version) else 1
if __name__=="__main__":raise SystemExit(main())
