#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_server_sw_api',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
checks={}
requests=[]

class H(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def do_GET(self):
        from urllib.parse import urlparse,parse_qs
        u=urlparse(self.path);q=parse_qs(u.query);requests.append((u.path,q,self.headers.get('X-API-Key')))
        if self.headers.get('X-API-Key')!='secret-test-key':
            self.send_response(401);self.end_headers();return
        if u.path.endswith('/units'):
            page=int(q.get('page',['1'])[0]);limit=int(q.get('limit',['0'])[0])
            if limit!=500:self.send_response(400);self.end_headers();return
            if page==1:
                payload={'data':[{'callsign':'20-9471','lookup_key':'209471','region_code':'20','station_name':'Tilburg Centrum','function_code':'HVT-KR','function_name':'Hulpverleningsvoertuig met kraan','discipline':'brandweer','verified':True},{'callsign':'21-3131','lookup_key':'213131','region_code':'21','station_name':'Den Bosch','function_code':'TS','function_name':'Tankautospuit','discipline':'brandweer'}], 'pagination':{'has_more':True,'next_page':2}}
            else:
                payload={'units':[{'callsign':'20-3161','lookup_key':'20-3161','region_code':'20','station_name':'Breda','function_code':'WTW-M','function_name':'Watertankwagen met monitor','discipline':'brandweer'}], 'meta':{'has_more':False}}
        elif u.path.endswith('/resolve'):
            if q.get('source')!=['lichtkrant']:
                self.send_response(400);self.end_headers();return
            payload={'unit':{'callsign':q.get('callsign',[''])[0],'lookup_key':q.get('callsign',[''])[0],'region_code':'20','station_name':'Testpost','function_code':'TS','function_name':'Tankautospuit','discipline':'brandweer'}}
        else:
            self.send_response(404);self.end_headers();return
        raw=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

srv=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=srv.serve_forever,daemon=True).start()
old={k:getattr(mod,k) for k in ('DB_PATH','VEHICLE_CACHE_DIR','VEHICLE_OVERRIDES_PATH','VEHICLE_HISTORY_PATH','SW_VEHICLE_CACHE_PATH','SECRETS_DIR','SW_API_SECRET_PATH','SW_ROEPNUMMER_API_BASE')}
try:
    with TemporaryDirectory() as td:
        td=Path(td);veh=td/'vehicles';sec=td/'secrets'
        mod.DB_PATH=td/'test.sqlite3';mod.VEHICLE_CACHE_DIR=veh;mod.VEHICLE_OVERRIDES_PATH=veh/'overrides.json';mod.VEHICLE_HISTORY_PATH=veh/'history.jsonl';mod.SW_VEHICLE_CACHE_PATH=veh/'swmediaproducties.json';mod.SECRETS_DIR=sec;mod.SW_API_SECRET_PATH=sec/'sw-roepnummer-api.json';mod.SW_ROEPNUMMER_API_BASE=f'http://127.0.0.1:{srv.server_port}/v1'
        mod.write_sw_api_key('secret-test-key')
        checks['secret_readback']=mod.read_sw_api_key()=='secret-test-key'
        checks['secret_not_in_config']=not (ROOT/'config'/'config.json').read_text('utf-8').find('secret-test-key')>=0
        if os.name!='nt':checks['linux_secret_mode_0600']=(mod.SW_API_SECRET_PATH.stat().st_mode & 0o777)==0o600
        state=mod.AppState({'region_disciplines':{'midden-en-west-brabant':['brandweer']}});state.init_db()
        status=state.sync_sw_vehicle_api(force=True)
        units,meta=mod.load_sw_vehicle_cache()
        checks['all_pages_downloaded']=status.get('key_valid') is True and len(units)==3 and status.get('pages')==2
        checks['lookup_key_normalized']=mod.normalize_sw_lookup_key('20-9471')=='209471' and '209471' in units
        checks['primary_catalog_mapping']='209471' in state.vehicle_catalog and state.vehicle_catalog['209471'].get('function_code')=='HVT-KR' and state.vehicle_catalog['209471'].get('station_name')=='Tilburg Centrum'
        checks['other_region_cached_not_loaded']='213131' in units and '213131' not in state.vehicle_catalog
        cfg=state.sw_api_config_view(); checks['key_never_returned']='api_key' not in cfg and 'secret-test-key' not in json.dumps(state.sw_api_status_view())
        checks['auth_header_used']=all(x[2]=='secret-test-key' for x in requests if x[0].endswith('/units'))
        # Resolve one cache miss and ensure source=lichtkrant is sent.
        v=state.resolve_sw_vehicle('20-3999');units2,_=mod.load_sw_vehicle_cache()
        checks['resolve_miss_cached']='203999' in units2 and v and v.get('station')=='Testpost'
        checks['resolve_source_parameter']=any(path.endswith('/resolve') and q.get('source')==['lichtkrant'] for path,q,_ in requests)
        # A broken remote must not destroy the previous cache/catalog.
        mod.SW_ROEPNUMMER_API_BASE='http://127.0.0.1:1/v1'
        before=mod.SW_VEHICLE_CACHE_PATH.read_bytes();st2=state.sync_sw_vehicle_api(force=True);after=mod.SW_VEHICLE_CACHE_PATH.read_bytes()
        checks['outage_keeps_cache']=before==after and st2.get('unit_count')==4
        checks['outage_keeps_catalog']='209471' in state.vehicle_catalog
finally:
    srv.shutdown();srv.server_close()
    for k,v in old.items():setattr(mod,k,v)

html=(ROOT/'frontend'/'control.html').read_text('utf-8');js=(ROOT/'frontend'/'control.js').read_text('utf-8');app=(ROOT/'frontend'/'app.js').read_text('utf-8')
checks['control_has_api_status']=all(x in html for x in ('swApiOnline','swApiKeyStatus','swApiUnitCount','swApiLastSync','swApiKeyInput'))
checks['control_never_prefills_key']='value="secret' not in html and 'type="password"' in html
checks['vehicle_sse_rerenders']="loadVehicleDb().then(()=>render())" in app
checks['api_fields_visible_in_vehicle_header']='function_code||v.type' in app and 'function_name||v.label' in app and 'station_name||v.station' in app

failed=[k for k,v in checks.items() if not v]
print(f'SW Mediaproducties Roepnummer API: {len(checks)-len(failed)}/{len(checks)}')
for k,v in checks.items():print(('OK ' if v else 'FAIL ')+k)
if failed:raise SystemExit(1)
