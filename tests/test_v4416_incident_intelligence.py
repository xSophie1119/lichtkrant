#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_v4416',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
class DummyState:
    def get_display_settings(self): return {}
state=DummyState(); checks={}

pol=mod.parse_raw_p2000_line(state,'P 1 386198 Letsel Beethovenlaan Tilburg')
checks['police_bundle_not_vehicle']=pol['service']=='politie' and pol['units']==[] and pol['location']=='Beethovenlaan' and any(x.get('token')=='386198' and 'geen voertuig' in x.get('reason','') for x in pol.get('removed',[]))

a1=mod.parse_raw_p2000_line(state,'A1 20-9432 Letsel Beethovenlaan Tilburg')
checks['a1_fire_block']=a1['service']=='ambulance' and a1['priority']=='A1' and a1['units']==[] and a1['location']=='Beethovenlaan' and 'geblokkeerd' in a1['unit_policy']
checks['a1_builder']=a1['screen_text'].startswith('A1 • Ongeval met letsel') and 'Beethovenlaan' in a1['speech_text'] and any('brandweerroepnummer genegeerd' in x.get('reason','') for x in a1.get('removed',[]))

baarle=mod.parse_raw_p2000_line(state,'A1 20-9432 Letsel Singel Baarle-Nassau')
checks['baarle_exception']=baarle['city']=='Baarle-Nassau' and baarle['location']=='Singel' and baarle['unit_policy']=='Brandweereenheden toegestaan'

# The backend discipline filter must also reject enriched fire tokens on A1.
checks['backend_unit_firewall']=mod.enforce_unit_discipline('ambulance','A1','Tilburg','A1 letsel Tilburg','',['TS 20-9432','20-9432','AMB 12345'])==['AMB 12345']
checks['backend_baarle_allows']=mod.enforce_unit_discipline('ambulance','A1','Baarle-Nassau','A1 letsel Baarle-Nassau','',['TS 20-9432'])==['TS 20-9432']

now=datetime.now(timezone.utc)
def msg(mid,minutes,title,priority='P1',service='brandweer',scale='',scale_score=0,units=None):
    published=(now+timedelta(minutes=minutes)).isoformat().replace('+00:00','Z')
    return {'id':mid,'published':published,'updated':published,'title':title,'summary':'','url':'','service':service,'priority':priority,'city':'Tilburg','location':'Beethovenlaan','units':units or [],'scale':scale,'scale_score':scale_score,'incident_key':'same','parser_confidence':90}
rows=[msg('1',-4,'P 1 BR woning Beethovenlaan Tilburg'),msg('2',-2,'P 1 Grote brand Beethovenlaan Tilburg',scale='Grote brand',scale_score=3,units=['HVT-KR 20-9471']),msg('3',-1,'P 1 Grote brand Beethovenlaan Tilburg MMT 17992',scale='Grote brand',scale_score=3,units=['17992 - Lifeliner 2'])]
inc=mod.build_incidents(rows,limit=10)
checks['incident_merge']=len(inc)==1 and inc[0]['message_count']==3 and len(inc[0]['timeline'])==3
checks['incident_priority_reasons']=all(x in inc[0]['urgency_reasons'] for x in ['opschaling','grote brand','MMT-inzet','3 gekoppelde meldingen']) and inc[0]['urgency_score']>0

# Route provider result gets normalized/cached; no real network required.
old_http=mod.pooled_http_bytes
try:
    mod._ROUTE_CACHE.clear()
    payload={'routes':[{'distance':12345.0,'duration':901.0,'geometry':'abc123'}]}
    mod.pooled_http_bytes=lambda *a,**k:(200,{},json.dumps(payload).encode())
    route=mod.route_between_coords(51.55,5.08,51.56,5.09)
    cached=mod.route_between_coords(51.55,5.08,51.56,5.09)
    checks['route_metrics']=route['distance_m']==12345.0 and route['duration_s']==901.0 and route['geometry']=='abc123' and cached['cached'] is True
finally:
    mod.pooled_http_bytes=old_http

app=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
control=(ROOT/'frontend'/'control.js').read_text(encoding='utf-8')
map_html=(ROOT/'frontend'/'map-view.html').read_text(encoding='utf-8')
checks['frontend_discipline_firewall']='vehicleAllowedForMessage' in app and 'fireVehicleAllowedForMessage' in app and '386198' in app
checks['frontend_smart_priority']='linkedIncidentCount' in app and 'specialVehicleForPriority' in app and 'GROTE BRAND' in app
checks['admin_builder_and_incidents']='builderOriginal' in control and "api('/api/incidents?limit=16&scan=700')" in control
checks['route_polyline']='routePolyline' in map_html and 'decodePolyline' in map_html and 'routePath' in map_html
checks['version_4416']=tuple(map(int,(ROOT/'VERSION').read_text().strip().split('.'))) >= (4,4,16)

failed=[k for k,v in checks.items() if not v]
print(f"v4.4.16 incident-intelligence tests: {len(checks)-len(failed)}/{len(checks)} OK")
for k,v in checks.items(): print(('OK ' if v else 'FAIL ')+k)
if failed: raise SystemExit(1)
