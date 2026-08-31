import importlib.util, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_screenshot_under_test',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
fails=[]
def check(c,m):
    if not c:fails.append(m)

raw='P 1 BR WONING BINGELRADESTRAAT TILBURG 209432 209452 209031 209092'
# The physical setup location may be an address. It must resolve to a city before
# being reused by test-message parsing.
hint=mod.AppState._standplaats_city_hint('Bingelradestraat 12, 5043BS, Tilburg')
check(hint=='Tilburg',f'address-like standplaats city hint wrong: {hint!r}')
check(mod.infer_location(raw,'',hint).upper()=='BINGELRADESTRAAT',f'city leaked into street: {mod.infer_location(raw,"",hint)!r}')

# Verified seed rows from the screenshot should beat generic number-plan labels.
cat,_=mod.load_vehicle_catalog({'region_disciplines':{'midden-en-west-brabant':['brandweer']}})
expected={
 '209432':('TS','Tilburg-Vossenberg'),
 '209452':('HW','Tilburg-Centrum'),
 '209031':('TS-RES','Tilburg-Centrum'),
 '209092':('OVD-B','Tilburg-Centrum'),
}
for key,(typ,station) in expected.items():
    row=cat.get(key,{})
    check(row.get('type')==typ and row.get('station')==station,f'{key} exact seed missing/wrong: {row}')

# Street-only geocoding must not invent an arbitrary house number. Exact address
# queries should still prefer the BAG address result.
class Fake:
    def _fetch_json_url(self,*a,**k):
        return {'features':[
            {'collection':'adres','geometry':{'type':'Point','coordinates':[5.0246,51.5814]},'properties':{'weergavenaam':'Bingelradestraat 12, Tilburg'}},
            {'collection':'wegdeel','geometry':{'type':'Point','coordinates':[5.0247,51.5815]},'properties':{'weergavenaam':'Bingelradestraat, Tilburg'}},
        ]}
fake=Fake()
street=mod.AppState._pdok_location_search(fake,'Tilburg','Bingelradestraat Tilburg')
address=mod.AppState._pdok_location_search(fake,'Tilburg','Bingelradestraat 12 Tilburg')
check(street and '12' not in street.get('display_name',''),f'street query chose arbitrary address: {street}')
check(address and '12' in address.get('display_name',''),f'exact address query did not prefer address: {address}')

TOTAL=2+len(expected)+2
print({'tests':TOTAL,'failures':len(fails),'passed':TOTAL-len(fails)})
for f in fails:print('FAIL',f)
if fails:raise SystemExit(1)
