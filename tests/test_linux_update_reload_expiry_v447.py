import importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
server_path=ROOT/'backend'/'server.py'
spec=importlib.util.spec_from_file_location('p2000_v447',server_path)
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
app=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
start=(ROOT/'START_P2000.sh').read_text(encoding='utf-8')
index=(ROOT/'frontend'/'index.html').read_text(encoding='utf-8')

checks={}
checks['version_447']=tuple(map(int,mod.APP_VERSION.split('.'))) >= (4,4,7) and tuple(map(int,(ROOT/'VERSION').read_text().strip().split('.'))) >= (4,4,7)
checks['update_forces_kiosk_restart']='def _restart_kiosk_after_healthy_update' in server_path.read_text(encoding='utf-8') and 'queue_supervisor_command("restart-kiosk")' in server_path.read_text(encoding='utf-8')
checks['linux_start_is_idempotent']='ordinary/autostart invocation' in start and 'linux_desktop.py" stop-kiosk' not in start
asset_js=re.search(r'/app\.js\?v=(\d+)',index); asset_css=re.search(r'/lightkrant\.css\?v=(\d+)',index)
checks['fresh_asset_buster']=bool(asset_js and asset_css and asset_js.group(1)==asset_css.group(1) and int(asset_js.group(1))>=4470)
checks['expiry_uses_ingest_and_firstseen']='function localFirstSeenMs' in app and 'ingestedMs(m)' in app and '__monitorFirstSeenAt' in app
checks['render_enforces_expiry']='return !!state.activeMessage&&isLiveMessageActive(state.activeMessage,Date.now())' in app

# Exercise the backend helper without touching a real supervisor.
calls=[]
old_ensure,old_queue=mod.ensure_supervisor_running,mod.queue_supervisor_command
try:
    mod.ensure_supervisor_running=lambda timeout=0:{'running':True,'pid':123}
    mod.queue_supervisor_command=lambda action:(calls.append(action) or {'action':action,'token':'test'})
    row=mod._restart_kiosk_after_healthy_update()
    checks['helper_runtime']=row.get('ok') is True and calls==['restart-kiosk']
finally:
    mod.ensure_supervisor_running,mod.queue_supervisor_command=old_ensure,old_queue

# Evaluate the exact expiry functions from app.js in Node with a tiny harness.
def extract_function(src,name):
    marker=f'function {name}('
    start=src.index(marker)
    brace=src.index('{',start)
    depth=0
    i=brace
    while i<len(src):
        if src[i]=='{': depth+=1
        elif src[i]=='}':
            depth-=1
            if depth==0:return src[start:i+1]
        i+=1
    raise ValueError(name)

funcs='\n'.join(extract_function(app,n) for n in ['localFirstSeenMs','liveMessageStartedAt','liveMessageExpiresAt','isLiveMessageActive','activeVisible'])
js=f'''
const FIXED=1700000000000; Date.now=()=>FIXED;
function publishedMs(m){{const ms=new Date(m?.published||0).getTime();return Number.isFinite(ms)?ms:0}}
function ingestedMs(m){{const ms=new Date(m?.ingested_at||0).getTime();return Number.isFinite(ms)?ms:0}}
function visibleMs(){{return 180000}}
const state={{activeMessages:[],activeMessage:null,activeUntil:0}};
{funcs}
function iso(ms){{return new Date(ms).toISOString()}}
const future={{published:iso(FIXED+10*60*1000),ingested_at:iso(FIXED)}};
const old={{published:iso(FIXED-181000),ingested_at:iso(FIXED)}};
const noIngestFuture={{published:iso(FIXED+10*60*1000)}};
const r={{
 futureExpires:liveMessageExpiresAt(future),
 futureActive:isLiveMessageActive(future,FIXED+179999),
 futureExpired:isLiveMessageActive(future,FIXED+180001),
 oldActive:isLiveMessageActive(old,FIXED),
 noIngestExpires:liveMessageExpiresAt(noIngestFuture)
}};
state.activeMessages=[old];state.activeMessage=old;state.activeUntil=FIXED+9999999;r.activeVisibleOld=activeVisible();
console.log(JSON.stringify(r));
'''
with tempfile.NamedTemporaryFile('w',suffix='.js',delete=False,encoding='utf-8') as fh:
    fh.write(js); js_path=Path(fh.name)
try:
    cp=subprocess.run(['node',str(js_path)],capture_output=True,text=True,timeout=8)
    if cp.returncode==0:
        r=json.loads(cp.stdout.strip())
        checks['expiry_future_clock_skew']=r['futureExpires']==1700000180000 and r['futureActive'] is True and r['futureExpired'] is False
        checks['expiry_old_message']=r['oldActive'] is False and r['activeVisibleOld'] is False
        checks['expiry_future_without_ingest']=r['noIngestExpires']==1700000180000
    else:
        checks['expiry_future_clock_skew']=checks['expiry_old_message']=checks['expiry_future_without_ingest']=False
        print(cp.stdout,cp.stderr)
finally:
    js_path.unlink(missing_ok=True)

print(json.dumps(checks,ensure_ascii=False,indent=2))
failed=[k for k,v in checks.items() if not v]
if failed:
    print('FAIL:',', '.join(failed));raise SystemExit(1)
