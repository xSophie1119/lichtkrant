#!/usr/bin/env python3
"""v4.5.7 security/recovery layer, applied only after the exact v4.5.6 chain."""
from __future__ import annotations
import importlib.util, os, secrets, shutil, threading, time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('p2000_compat456',HERE/'compat456.py')
if spec is None or spec.loader is None: raise RuntimeError('v4.5.6 compatibility bridge kon niet worden geladen')
compat456=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat456)
compat=compat456.compat;_apply_v456=compat.apply_v451_hotfix

def repl(text,old,new,label,required=True):
    if new in text and old not in text:return text
    n=text.count(old)
    if n==1:return text.replace(old,new,1)
    if required:raise RuntimeError(f'v4.5.7 patch {label}: verwacht 1 match, vond {n}')
    return text

INSTALL_BLOCK=r'''# v4.5.7: fail-closed health/security/update hardening.
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.health_gate import evaluate_installation_health as _v457_eval_health, verify_release_manifest as _v457_verify_manifest
_V457_ADMIN_TOKEN_PATH = DATA_DIR / "secrets" / "admin-token.txt"
def _v457_admin_token():
    try:
        if _V457_ADMIN_TOKEN_PATH.is_file():
            value=_V457_ADMIN_TOKEN_PATH.read_text(encoding="utf-8").strip()
            if len(value)>=32:return value
    except Exception:pass
    _V457_ADMIN_TOKEN_PATH.parent.mkdir(parents=True,exist_ok=True)
    value=secrets.token_urlsafe(32)
    tmp=_V457_ADMIN_TOKEN_PATH.with_suffix(".tmp");tmp.write_text(value+"\n",encoding="utf-8")
    try:os.chmod(tmp,0o600)
    except OSError:pass
    os.replace(tmp,_V457_ADMIN_TOKEN_PATH)
    return value
_V457_ADMIN_TOKEN=_v457_admin_token()
def _v457_client_loopback(ip):
    try:return ipaddress.ip_address((ip or "").split("%",1)[0]).is_loopback
    except Exception:return False
def _v457_mutation_allowed(handler):
    if _v457_client_loopback(handler.client_address[0] if handler.client_address else ""):return True
    supplied=normalize_space(handler.headers.get("X-P2000-Admin-Token") or "")
    return bool(supplied and secrets.compare_digest(supplied,_V457_ADMIN_TOKEN))
_original_health_snapshot=AppState.health_snapshot
def _v457_health_snapshot(self,force=False):
    base=_original_health_snapshot(self,force)
    gate=_v457_eval_health(ROOT,expected_version=APP_VERSION)
    base["ok"]=bool(gate["ok"])
    base["critical_failures"]=list(gate["critical_failures"])
    base["degraded"]=list(gate["degraded"])
    return base
AppState.health_snapshot=_v457_health_snapshot

def _v457_preflight(package_root,target_version):
    _v457_verify_manifest(Path(package_root),str(target_version))
    return _v457_original_preflight(package_root,target_version)
_v457_original_preflight=_preflight_staged_update
_preflight_staged_update=_v457_preflight

def _v457_copy_update_into_place(package_root):
    package_root=Path(package_root).resolve()
    pending={}
    try:pending=json.loads(UPDATE_PENDING_HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception:pass
    backup=Path(str(pending.get("backup") or ""))
    journal=UPDATE_DIR/"transaction.json"
    _atomic_json_write(journal,{"state":"applying","backup":str(backup),"target":str(package_root),"started_at":utcnow_iso()})
    preserve={"data","config",".git","__pycache__"}
    wanted={p.name for p in package_root.iterdir() if p.name not in preserve}
    for old in list(ROOT.iterdir()):
        if old.name in preserve or old.name.startswith('.p2next-'):continue
        if old.name not in wanted:
            if old.is_dir():shutil.rmtree(old)
            else:old.unlink(missing_ok=True)
    for src in package_root.iterdir():
        if src.name in preserve:continue
        dst=ROOT/src.name;tmp=ROOT/(".p2next-"+src.name)
        if tmp.exists():shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink()
        if src.is_dir():shutil.copytree(src,tmp)
        else:shutil.copy2(src,tmp)
        if dst.exists():shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        os.replace(tmp,dst)
    _atomic_json_write(journal,{"state":"applied","backup":str(backup),"target":str(package_root),"applied_at":utcnow_iso()})
_copy_update_into_place=_v457_copy_update_into_place

def _v457_mark_update_healthy_later(state):
    if not UPDATE_PENDING_HEALTH_PATH.exists():return
    def worker():
        if state.stop_event.wait(8):return
        try:
            snap=state.health_snapshot(force=True)
            if not snap.get("ok") or snap.get("critical_failures"):return
            UPDATE_PENDING_HEALTH_PATH.unlink(missing_ok=True)
            (UPDATE_DIR/"transaction.json").unlink(missing_ok=True)
            _write_update_status(state="ready",message="Update semantisch gezond",installed_version=APP_VERSION,latest_version=APP_VERSION,available=False,error="")
        except Exception:return
    threading.Thread(target=worker,daemon=True,name="update-health-confirm-v457").start()
_mark_update_healthy_later=_v457_mark_update_healthy_later

'''

def apply():
    _apply_v456()
    server=HERE/'server.py';text=server.read_text(encoding='utf-8')
    text=repl(text,'APP_VERSION = "4.5.6"','APP_VERSION = "4.5.7"','backendversie')
    text=repl(text,'import signal\n','import signal\nimport secrets\n','secrets import')
    text=repl(text,'"bind": "0.0.0.0"','"bind": "127.0.0.1"','default bind')
    text=text.replace('default.get("bind") or "0.0.0.0"','default.get("bind") or "127.0.0.1"')
    text=text.replace('else "0.0.0.0"','else "127.0.0.1"')
    text=repl(text,'    if addr.is_loopback or addr.is_private or addr.is_link_local:\n        return True','    if addr.is_loopback:\n        return True','update client scope')
    text=repl(text,'        if parsed.path == "/api/update/upload":\n            try:','        if parsed.path == "/api/update/upload":\n            return self.send_json({"ok":False,"error":"Handmatige executable ZIP-updates zijn uitgeschakeld; gebruik de vertrouwde GitHub-updatebron."},403)\n            try:','manual upload disable')
    text=repl(text,'        self.send_header("Access-Control-Allow-Origin", "*")','        origin=normalize_space(self.headers.get("Origin") or "")\n        if origin and _same_origin_or_nonbrowser(self.headers): self.send_header("Access-Control-Allow-Origin", origin)\n        self.send_header("Vary", "Origin")','cors wildcard')
    text=text.replace('self.send_header("Access-Control-Allow-Headers", "Content-Type")','self.send_header("Access-Control-Allow-Headers", "Content-Type, X-P2000-Admin-Token")')
    text=repl(text,'        parsed = urlparse(self.path)\n        if not parsed.path.startswith("/api/"):', '        parsed = urlparse(self.path)\n        if not _v457_mutation_allowed(self): return self.send_json({"error":"admin authenticatie vereist"},403)\n        if not parsed.path.startswith("/api/"):', 'mutation auth')
    marker='def main():\n';text=repl(text,marker,INSTALL_BLOCK+marker,'hardening install block')
    compat.atomic_write(server,text.encode('utf-8'))
    app=ROOT/'frontend'/'app.js'
    if app.is_file():
        at=app.read_text(encoding='utf-8');at=at.replace("const CLIENT_VERSION='4.5.6';","const CLIENT_VERSION='4.5.7';");compat.atomic_write(app,at.encode())
    setup=ROOT/'frontend'/'setup.html'
    if setup.is_file():compat.atomic_write(setup,setup.read_text(encoding='utf-8').replace('v4.5.6','v4.5.7').encode())
    control=ROOT/'frontend'/'control.js'
    if control.is_file():compat.atomic_write(control,control.read_text(encoding='utf-8').replace("st.version||'4.5.6'","st.version||'4.5.7'").encode())
    compat.atomic_write(ROOT/'VERSION',b'4.5.7\n')
compat.apply_v451_hotfix=apply;compat.TARGET_VERSION='4.5.7'
