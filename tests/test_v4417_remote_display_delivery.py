#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_v4417',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
checks={}

# AppState's command mailbox works even without an SSE subscriber.
state=mod.AppState(dict(mod.DEFAULT_CONFIG if hasattr(mod,'DEFAULT_CONFIG') else mod.load_config()))
delivered,seq=state.publish_display_command({'type':'test','payload':{'token':'remote-browser-test','mode':'message'}})
batch=state.display_command_batch(after=0,initial=True)
checks['queue_without_sse']=delivered==0 and seq==1 and len(batch['commands'])==1 and batch['commands'][0]['_command_seq']==1
checks['queue_cursor']=state.display_command_batch(after=1,initial=False)['commands']==[]
# Stale commands are not replayed after a long reconnect.
with state.display_command_lock:
    state.display_commands[-1]['_command_created_monotonic']=time.monotonic()-120
checks['stale_not_replayed']=state.display_command_batch(after=0,initial=False)['commands']==[]

state.record_display_client('browser-a',{'reported_at':mod.utcnow_iso()})
state.record_display_client('browser-b',{'reported_at':mod.utcnow_iso()})
checks['multiple_display_clients']=state.active_display_clients()>=2

server=(ROOT/'backend'/'server.py').read_text(encoding='utf-8')
app=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
control=(ROOT/'frontend'/'control.js').read_text(encoding='utf-8')
checks['no_hard_409']='Geen lichtkrant-tabblad verbonden. Start of open eerst de monitor.' not in server
checks['test_uses_mailbox']='publish_display_command({"type": "test", "payload": test_payload})' in server
checks['poll_endpoint']='if parsed.path == "/api/display-commands"' in server
checks['frontend_poll']='setInterval(pollDisplayCommands,1500)' in app and '/api/display-commands?after=' in app
checks['frontend_client_id']='client_id:DISPLAY_CLIENT_ID' in app and 'sessionStorage.getItem(\'p2000DisplayClientId\')' in app
checks['dedupe']='_command_seq' in app and 'seq<=lastDisplayCommandSeq' in app
checks['accurate_timeout']='dezelfde backend/installatie' in control
checks['version_4417']=(ROOT/'VERSION').read_text().strip()=='4.4.17'

failed=[k for k,v in checks.items() if not v]
print(f"v4.4.17 remote-display tests: {len(checks)-len(failed)}/{len(checks)} OK")
for k,v in checks.items(): print(('OK ' if v else 'FAIL ')+k)
if failed: raise SystemExit(1)
