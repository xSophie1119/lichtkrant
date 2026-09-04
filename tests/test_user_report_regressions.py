import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_user_regressions',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
class DummyState:
    def get_display_settings(self):return {}
state=DummyState();cases=json.loads((Path(__file__).with_name('regressions_user_reports.json')).read_text(encoding='utf-8'))
fail=[]
for case in cases:
    r=mod.parse_raw_p2000_line(state,case['line'],case.get('categories') or [])
    def contains(field,key):return str(case.get(key,'')).lower() in str(r.get(field,'')).lower()
    if r.get('service')!=case.get('service'):fail.append((case['name'],'service',r));continue
    if mod.normalize_city_token(r.get('city',''))!=mod.normalize_city_token(case.get('city','')):fail.append((case['name'],'city',r))
    if case.get('type_contains') and not contains('incident_type','type_contains'):fail.append((case['name'],'type',r))
    if case.get('location_contains') and not contains('location','location_contains'):fail.append((case['name'],'location',r))
    if case.get('scale_contains') and not contains('scale','scale_contains'):fail.append((case['name'],'scale',r))
    units=' '.join(r.get('units') or [])
    for want in case.get('units_contains') or []:
        if want not in units:fail.append((case['name'],f'unit {want}',r))
print(json.dumps({'total':len(cases),'failures':len(fail),'passed':len(cases)-len({x[0] for x in fail})},ensure_ascii=False))
for name,kind,r in fail:print('FAIL',name,kind,json.dumps(r,ensure_ascii=False))
if fail:raise SystemExit(1)
