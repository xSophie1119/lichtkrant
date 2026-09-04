#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data'/'vehicles'/'swmediaproducties.json'
DB=ROOT/'data'/'p2000.sqlite3'
checks=[]
def check(cond,msg):
    if not cond: raise AssertionError(msg)
    checks.append(msg)

# Preserve any local dev artifacts, then reproduce a real upgrade: existing SW cache
# is present before backend/server.py is imported.
backup_cache=CACHE.read_bytes() if CACHE.exists() else None
backup_db=DB.read_bytes() if DB.exists() else None
try:
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    CACHE.write_text(json.dumps({
        'version':1,'meta':{'last_sync':'2026-09-04T18:00:00+00:00'},
        'units':{'209471':{
            'callsign':'20-9471','lookup_key':'209471','region_code':'20',
            'station_name':'Tilburg Centrum','function_code':'HVT-KR',
            'function_name':'Hulpverleningsvoertuig met kraan','discipline':'brandweer','verified':True
        }}
    }),encoding='utf-8')
    code='import backend.server as s; assert "209471" in s.KNOWN_FIRE_VEHICLE_KEYS; print(s.APP_VERSION, s.INSTALL_ID)'
    cp=subprocess.run([sys.executable,'-c',code],cwd=ROOT,text=True,capture_output=True,timeout=20)
    check(cp.returncode==0, f'backend import with pre-existing SW cache failed: {cp.stderr[-500:]}')
    check('4.4.11' in cp.stdout,'backend did not report 4.4.11')

    # Load module in this process after the cache exists and exercise the method that
    # used to reference undefined FIRE_TYPE_DIGIT.
    spec=importlib.util.spec_from_file_location('p2000_server_v4411',ROOT/'backend'/'server.py')
    mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)
    cfg=mod.load_config(); state=mod.AppState(cfg); state.init_db()
    with state.connect() as con:
        con.execute('DELETE FROM unknown_vehicles')
        con.execute('''INSERT INTO unknown_vehicles(callsign,digits,first_seen,last_seen,seen_count,last_message_id,last_message,last_city,last_url)
                       VALUES(?,?,?,?,?,?,?,?,?)''',('20-5332','205332',mod.utcnow_iso(),mod.utcnow_iso(),1,'x','test','Bavel',''))
    rows=state.list_unknown_callsigns(20)
    row=next((r for r in rows if r.get('digits')=='205332'),None)
    check(bool(row),'unknown callsign row missing')
    check(row.get('suggested_type')=='Tankautospuit',f"unexpected suggested_type: {row}")
    check(row.get('suggested_function_code')=='TS',f"unexpected suggested code: {row}")

    # Runtime identity must distinguish same-version copies in different folders.
    rid=mod.INSTALL_ID
    check(isinstance(rid,str) and len(rid)==16,'install id missing/invalid')
    import hashlib, os
    other=hashlib.sha256(os.path.realpath(str(ROOT/'different-copy')).encode()).hexdigest()[:16]
    check(rid!=other,'install id is not path-specific')
finally:
    try:
        if backup_cache is None: CACHE.unlink(missing_ok=True)
        else: CACHE.write_bytes(backup_cache)
    except Exception: pass
    try:
        if backup_db is None: DB.unlink(missing_ok=True)
        else: DB.write_bytes(backup_db)
    except Exception: pass

print(f'v4.4.11 startup/cache tests: {len(checks)}/{len(checks)} OK')
