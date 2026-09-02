import importlib.util, json, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_vehicle_under_test',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
fails=[]
def check(c,m):
    if not c:fails.append(m)

csv1='Standplaats,Roepnummer,Voertuig\nGroningen Hoofdpost,01-1831,Tankautospuit\nGroningen Vinkhuizen,01-1851,Hoogwerker\n'
v=mod.parse_vehicle_csv(csv1,'01')
check(v.get('011831',{}).get('type')=='TS',f'011831 type {v.get("011831")}')
check(v.get('011831',{}).get('station')=='Groningen Hoofdpost',f'011831 station {v.get("011831")}')
check(v.get('011851',{}).get('type')=='HW',f'011851 type {v.get("011851")}')

csv2='Eemnes\n09-1631,Tankautospuit\n09-1668,Motorspuitaanhanger\n'
v2=mod.parse_vehicle_csv(csv2,'09')
check(v2.get('091631',{}).get('station')=='Eemnes',f'merged heading {v2.get("091631")}')
check(mod.fire_vehicle_type('', '213831')[0]=='TS','number plan TS failed')
check(mod.fire_vehicle_type('', '213851')[0]=='RV','number plan redmaterieel failed')
check(mod.normalize_vehicle_digits('01-18-849')=='0118849','extended normalization failed')
check(mod.selected_fire_region_codes({'region_disciplines':{'bollenstreek':['brandweer']}})==['16'],'subregion->parent region failed')
check(mod.selected_fire_region_codes({'region_disciplines':{'utrecht':['politie'],'flevoland':['brandweer']}})==['25'],'discipline filtering failed')

# Regional sharding: a Groningen profile must not load Utrecht cache/seed entries.
with tempfile.TemporaryDirectory() as td:
    td=Path(td); cache=td/'vehicles'; cache.mkdir()
    seed=td/'vehicles.json'
    seed.write_text(json.dumps({'vehicles':{
        '011831':{'callsign':'01-1831','type':'TS','station':'Seed Groningen'},
        '091631':{'callsign':'09-1631','type':'TS','station':'Seed Eemnes'},
    }}),encoding='utf-8')
    (cache/'01.json').write_text(json.dumps({'meta':{'region':'01'},'vehicles':{
        '011831':{'callsign':'01-1831','type':'TS','station':'Exact Groningen'},
        '011851':{'callsign':'01-1851','type':'HW','station':'Exact Groningen'},
    }}),encoding='utf-8')
    (cache/'09.json').write_text(json.dumps({'meta':{'region':'09'},'vehicles':{
        '091631':{'callsign':'09-1631','type':'TS','station':'Exact Eemnes'},
    }}),encoding='utf-8')
    old_seed,old_cache=mod.VEHICLE_DB_PATH,mod.VEHICLE_CACHE_DIR
    mod.VEHICLE_DB_PATH,mod.VEHICLE_CACHE_DIR=seed,cache
    try:
        cat,meta=mod.load_vehicle_catalog({'region_disciplines':{'groningen':['brandweer']}})
        check(set(cat)=={'011831','011851'},f'sharding loaded wrong keys: {sorted(cat)}')
        check(cat['011831']['station']=='Exact Groningen','regional cache did not override seed')
        check(set(meta)=={'01'},f'wrong region meta: {meta}')
    finally:
        mod.VEHICLE_DB_PATH,mod.VEHICLE_CACHE_DIR=old_seed,old_cache

# Manual overrides are sanitized, persisted and applied after every cache/seed.
with tempfile.TemporaryDirectory() as td:
    td=Path(td); old_seed,old_cache,old_overrides=mod.VEHICLE_DB_PATH,mod.VEHICLE_CACHE_DIR,mod.VEHICLE_OVERRIDES_PATH
    mod.VEHICLE_CACHE_DIR=td/'vehicles';mod.VEHICLE_OVERRIDES_PATH=mod.VEHICLE_CACHE_DIR/'overrides.json';mod.VEHICLE_DB_PATH=td/'seed.json'
    mod.VEHICLE_DB_PATH.write_text(json.dumps({'vehicles':{'203161':{'callsign':'20-3161','type':'WT','station':'Fout'}}}),encoding='utf-8')
    try:
        digits,item=mod.sanitize_vehicle_override({'callsign':'20-3161','type':'WTW-M','station':'Breda','display':'Watertankwagen met monitor Breda'})
        check(digits=='203161' and item['manual'] and item['callsign']=='20-3161',f'override sanitize failed: {digits} {item}')
        mod.write_vehicle_overrides({digits:item})
        cat,_=mod.load_vehicle_catalog({'region_disciplines':{'midden-en-west-brabant':['brandweer']}})
        check(cat['203161']['display']=='Watertankwagen met monitor Breda' and cat['203161']['source']=='handmatige override',f'override priority failed: {cat.get("203161")}')
    finally:
        mod.VEHICLE_DB_PATH,mod.VEHICLE_CACHE_DIR,mod.VEHICLE_OVERRIDES_PATH=old_seed,old_cache,old_overrides

# Primary HTML source: pagination, discipline filter and exact station/type.
html1='''<html><body><table><tr><th>ID</th><th>Discipline</th><th>Type</th><th>Omschrijving</th><th>Kazerne</th></tr>
<tr><td>20-9432</td><td>Brandweer</td><td>Tankautospuit (TS)</td><td>1e Tankautospuit</td><td>Tilburg-Vossenberg</td></tr>
<tr><td>20-101</td><td>Ambulance</td><td>Ambulance</td><td>Ambulance</td><td>Tilburg</td></tr></table><p>Pagina 1 van 2</p></body></html>'''
hv,pages=mod.parse_hulpdienst_vehicle_html(html1,'20')
check(pages==2,f'html pagination failed: {pages}')
check(set(hv)=={'209432'},f'html discipline filtering failed: {hv}')
check(hv['209432']['type']=='TS' and hv['209432']['station']=='Tilburg-Vossenberg',f'html exact vehicle failed: {hv.get("209432")}')

# End-to-end regional sync uses Hulpdienstvoertuigen first and follows pages.
with tempfile.TemporaryDirectory() as td:
    td=Path(td); old_cache=mod.VEHICLE_CACHE_DIR; mod.VEHICLE_CACHE_DIR=td
    old_urlopen=mod.urllib.request.urlopen
    calls=[]
    class Headers:
        def get_content_charset(self): return 'utf-8'
    class Resp:
        headers=Headers()
        def __init__(self,body): self.body=body
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,n=-1): return self.body[:n] if n and n>0 else self.body
    page1=html1.encode()
    page2=b'''<html><body><table><tr><th>ID</th><th>Discipline</th><th>Type</th><th>Omschrijving</th><th>Kazerne</th></tr><tr><td>20-9451</td><td>Brandweer</td><td>Redmaterieel</td><td>Hoogwerker</td><td>Tilburg-Vossenberg</td></tr></table><p>Pagina 2 van 2</p></body></html>'''
    def fake_urlopen(req,timeout=0):
        calls.append((req.full_url,timeout))
        return Resp(page2 if 'pagina=2' in req.full_url else page1)
    mod.urllib.request.urlopen=fake_urlopen
    try:
        state=object.__new__(mod.AppState)
        result=state._sync_vehicle_region('20',True)
        cache,_=mod.load_cached_vehicle_region('20')
        check(result.get('ok') and result.get('source')=='Hulpdienstvoertuigen.nl' and result.get('pages')==2,f'primary sync failed: {result}')
        check(set(cache)=={'209432','209451'},f'pagination cache failed: {cache}')
    finally:
        mod.urllib.request.urlopen=old_urlopen; mod.VEHICLE_CACHE_DIR=old_cache

# If the primary site is unavailable, the legacy Google source remains a fallback.
with tempfile.TemporaryDirectory() as td:
    td=Path(td); old_cache=mod.VEHICLE_CACHE_DIR; mod.VEHICLE_CACHE_DIR=td
    old_urlopen=mod.urllib.request.urlopen
    calls=[]
    class Headers:
        def get_content_charset(self): return 'utf-8'
    class Resp:
        headers=Headers()
        def __init__(self,body): self.body=body
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,n=-1): return self.body[:n] if n and n>0 else self.body
    def fake_urlopen(req,timeout=0):
        calls.append((req.full_url,timeout))
        if 'hulpdienstvoertuigen.nl' in req.full_url: raise OSError('simulated primary failure')
        if 'gviz' in req.full_url: raise OSError('simulated gviz failure')
        return Resp(b'Standplaats,Roepnummer,Voertuig\nGroningen,01-1831,Tankautospuit\n')
    mod.urllib.request.urlopen=fake_urlopen
    try:
        state=object.__new__(mod.AppState)
        result=state._sync_vehicle_region('01',True)
        check(result.get('ok') and result.get('source')=='Tomzulu10' and result.get('endpoint')=='published-csv',f'fallback failed: {result}')
        check(len(calls)==3,f'wrong fallback attempts: {calls}')
    finally:
        mod.urllib.request.urlopen=old_urlopen; mod.VEHICLE_CACHE_DIR=old_cache

TOTAL=22
print({'tests':TOTAL,'failures':len(fails),'passed':TOTAL-len(fails)})
for f in fails:print('FAIL',f)
if fails:raise SystemExit(1)
