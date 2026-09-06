#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, os, py_compile, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TIMEOUT=20

def req(x,m):
    if not x:raise AssertionError(m)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def compile_case():
    for rel in ['backend/compat457.py','backend/server.py','tools/health_gate.py','tools/recovery_bootstrap.py','tools/startup_guard.py','tools/supervisor.py','tools/linux_desktop.py','tools/rollback_latest.py','tools/stop_verify.py','tools/run_tests.py']:
        py_compile.compile(str(ROOT/rel),doraise=True)
def shell_case():
    b=shutil.which('bash');
    if b:req(subprocess.run([b,'-n',str(ROOT/'START_P2000.sh'),str(ROOT/'STOP_P2000.sh')]).returncode==0,'bash -n')
def health_case():
    h=load('hg',ROOT/'tools/health_gate.py')
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);(r/'frontend').mkdir();(r/'config').mkdir();(r/'data').mkdir();(r/'VERSION').write_text('4.5.7');
        for n in ['index.html','app.js','control.js']:(r/'frontend'/n).write_text('x'*20)
        (r/'config'/'config.json').write_text('{}')
        import sqlite3;c=sqlite3.connect(r/'data'/'p2000.sqlite3');c.execute('create table x(a)');c.commit();c.close()
        req(h.evaluate_installation_health(r,expected_version='4.5.7')['ok'],'healthy install rejected')
        (r/'config'/'config.json').write_text('{')
        req(not h.evaluate_installation_health(r,expected_version='4.5.7')['ok'],'broken config accepted')
def manifest_case():
    h=load('hgm',ROOT/'tools/health_gate.py')
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);(r/'VERSION').write_text('4.5.7\n');f=r/'x.txt';f.write_text('abc');sha=hashlib.sha256(b'abc').hexdigest();(r/'release-manifest.json').write_text(json.dumps({'version':'4.5.7','files':{'x.txt':sha}}));req(h.verify_release_manifest(r,'4.5.7')['ok'],'manifest rejected');f.write_text('evil')
        try:h.verify_release_manifest(r,'4.5.7');raise AssertionError('tamper accepted')
        except RuntimeError:pass
def recovery_marker_case():
    m=load('rb',ROOT/'tools/recovery_bootstrap.py')
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);b=r/'backup';b.mkdir();(b/'VERSION').write_text('old');p=r/'pending.json';j=r/'journal.json';p.write_text(json.dumps({'backup':str(r/'missing')}));m.ROOT=r;m.PENDING=p;m.JOURNAL=j;out=m.recover_pending();req(not out['ok'] and p.exists(),'failed rollback destroyed marker');meta=json.loads(p.read_text());req(meta['attempt_count']==1 and meta['last_error'],'failure state missing')
def mirror_case():
    m=load('rb2',ROOT/'tools/recovery_bootstrap.py')
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);b=r/'backup';d=r/'dst';b.mkdir();d.mkdir();(b/'VERSION').write_text('old');(b/'keep.txt').write_text('yes');(d/'obsolete.txt').write_text('no');(d/'VERSION').write_text('new');m.mirror_restore(b,d,preserve=());req((d/'VERSION').read_text()=='old' and not (d/'obsolete.txt').exists(),'mirror rollback not exact')
def startup_static_case():
    for p in [ROOT/'START_P2000.sh',ROOT/'START_P2000.bat']:
        t=p.read_text();req('startup_guard.py' in t and '--kill-stale' not in t,'launcher still owns lifecycle transaction')
    g=(ROOT/'tools/startup_guard.py').read_text()
    req('return startup()' in g,'startup guard swallows non-zero startup return codes')
    block=g[g.index('def startup():'):]
    req("VERSION=(ROOT/'VERSION').read_text" in block,'recovery does not reload restored VERSION')
def stop_static_case():
    for p in [ROOT/'STOP_P2000.sh',ROOT/'STOP_P2000.bat']:
        req('stop_verify.py' in p.read_text(),'STOP has no verification')
def security_static_case():
    t=(ROOT/'backend/compat457.py').read_text();req('127.0.0.1' in t and 'Handmatige executable ZIP-updates zijn uitgeschakeld' in t,'security patch absent');req('X-P2000-Admin-Token' in t and 'Vary\", \"Origin' in t,'admin auth/CORS absent')
def linux_handoff_case():
    m=load('ld',ROOT/'tools/linux_desktop.py');profile=m._profile('chromium');m._all=lambda:[(123,f'/usr/lib/chromium --user-data-dir={profile} --kiosk http://127.0.0.1:8765/')];req(m._owned(profile),'handoff child not recognized');req(m._profile_in_use(profile),'active profile not protected')
def browser_sources_case():
    t=(ROOT/'tools/linux_desktop.py').read_text();req("snap,'run','chromium'" in t and "flat,'run','org.chromium.Chromium'" in t,'snap/flatpak missing')
def concurrency_case():
    guard=ROOT/'tools/startup_guard.py'
    with tempfile.TemporaryDirectory() as td:
        lock=Path(td)/'l';out=Path(td)/'o';code=f'''import importlib.util,sys,time\nfrom pathlib import Path\ns=importlib.util.spec_from_file_location("g",r"{guard}");m=importlib.util.module_from_spec(s);sys.path.insert(0,r"{ROOT/'tools'}");s.loader.exec_module(m);m.LOCK=Path(r"{lock}");m.semantic_ok=lambda:False\nf=m.lock_handle(timeout=5);open(r"{out}","a").write(f"{{time.time()}}\\n");time.sleep(.7);m.unlock(f)'''
        a=subprocess.Popen([sys.executable,'-c',code]);b=subprocess.Popen([sys.executable,'-c',code]);a.wait(8);b.wait(8);req(a.returncode==0 and b.returncode==0,'concurrent workers failed');rows=[float(x) for x in out.read_text().splitlines()];req(len(rows)==2 and abs(rows[1]-rows[0])>.55,'startup mutex did not serialize')
CASES=[compile_case,shell_case,health_case,manifest_case,recovery_marker_case,mirror_case,startup_static_case,stop_static_case,security_static_case,linux_handoff_case,browser_sources_case,concurrency_case]
def main():
    fail=0
    for fn in CASES:
        st=time.monotonic()
        try:
            # self-process cases are bounded by suite-level simplicity; external calls have own timeouts.
            fn();print(f'[OK] {fn.__name__} ({time.monotonic()-st:.2f}s)')
        except Exception as e:fail+=1;print(f'[FOUT] {fn.__name__}: {e}')
    print(f'\n{len(CASES)-fail}/{len(CASES)} tests geslaagd.');return 1 if fail else 0
if __name__=='__main__':raise SystemExit(main())
