import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SERVER=ROOT/'backend'/'server.py'
spec=importlib.util.spec_from_file_location('p2000_server_under_test',SERVER)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class DummyState:
    def get_display_settings(self): return {}
state=DummyState()
corpus=json.loads((Path(__file__).with_name('parser_corpus.json')).read_text(encoding='utf-8'))
fail=[]
for i,e in enumerate(corpus,1):
    categories=[e['service'],e['city']]
    r=mod.parse_raw_p2000_line(state,e['line'],categories)
    if r['service'] != e['service']:
        fail.append((i,'service',e,r))
        continue
    if mod.normalize_city_token(r['city']) != mod.normalize_city_token(e['city']):
        fail.append((i,'city',e,r))
    is_control=bool(re.search(r'contact|vrijhouden|testmelding|herbevoorrading',e['line'],re.I))
    if not is_control:
        if not r['location'] or mod.normalize_city_token(r['location']) == mod.normalize_city_token(r['city']):
            fail.append((i,'location-empty',e,r))
        if re.search(r'(?:\b\d{6}\b|\b\d{2}-\d{4}\b|\b\d{2}-\d{2}-\d{3}\b)\s*$',r['location'] or ''):
            fail.append((i,'location-has-unit',e,r))
        if r['incident_type']=='P2000-melding':
            fail.append((i,'type-default',e,r))
    if e['service']=='politie':
        # Police incident/bundle IDs must never be exposed as fire vehicles.
        m=re.match(r'^\s*P\s*[1-5]\s+(\d{4,7})\b',e['line'],re.I)
        if m and any(m.group(1) in re.sub(r'\D','',u) for u in r['units']):
            fail.append((i,'police-bundle-as-unit',e,r))

print(json.dumps({'total':len(corpus),'failures':len(fail),'passed':len(corpus)-len({x[0] for x in fail})},ensure_ascii=False))
for row in fail[:80]:
    i,kind,e,r=row
    print(f"FAIL {i:03d} {kind}: {e['line']}")
    print(' expected',e['service'],e['city'])
    print(' got',r['service'],r['city'],'|',r['location'],'|',r['incident_type'],'|',r['units'])
if fail:
    raise SystemExit(1)
