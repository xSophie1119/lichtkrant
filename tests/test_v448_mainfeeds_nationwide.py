from __future__ import annotations
import importlib.util, json, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_v448',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
checks={}

matrix={slug:list(mod.ALL_DISCIPLINES) for slug in mod.SAFETY_REGION_SLUGS}
primary=mod.build_feed_urls(matrix)
checks['five_112nu_primary']=primary==[
    'https://112-nu.nl/brandweer/rss',
    'https://112-nu.nl/ambulance/rss',
    'https://112-nu.nl/politie/rss',
    'https://112-nu.nl/trauma-helikopter/rss',
    'https://112-nu.nl/knrm/rss',
]
class State:
    def __init__(self):
        self.config={'region_disciplines':matrix,'feed_race_enabled':True,'feed_urls':primary,'feed_112nu_enabled':True}
    def get_display_settings(self):return {}
state=State()
race=mod.AppState.race_feed_urls(state)
checks['alarmeringen_secondary']=all(mod.NATIONAL_DISCIPLINE_URLS[d] in race for d in mod.ALL_DISCIPLINES)
checks['no_legacy_112nu_aggregate']=mod.NU112_ALL_RSS not in primary and mod.NU112_ALL_RSS not in race

# 112-nu URL locality must win over a misleading generic/category locality.
raw='P 1 BLB-02 BR gebouw Munsterplein Roermond 235131'
xml=f'''<rss><channel><item><title>Brandweer - Munsterplein Roermond</title><description>Originele Melding: {raw}</description><link>https://112-nu.nl/melding/17848054/roermond/munsterplein/brandweer-met-grote-spoed.html</link><category>Brandweer</category><category>Tilburg</category><pubDate>Fri, 04 Sep 2026 16:17:39 GMT</pubDate></item></channel></rss>'''.encode()
msg=mod.FeedPoller(state).parse_feed(xml,mod.NU112_DISCIPLINE_URLS['brandweer'])[0]
checks['112nu_url_city_beats_wrong_category']=msg.city=='Roermond'
checks['112nu_service_from_feed']=msg.service=='brandweer'
checks['112nu_channel_removed_from_location']=msg.location=='Munsterplein'
checks['112nu_region_from_callsign']='Regio Limburg-Noord' in msg.categories

# Representative rows across the country.
examples={
 'Haren Gn':'P 1 BNN-01 Ongeval op water Hoornseplas Haren Gn 011810 011871 038131',
 'Zaandijk':'P 1 BNH-01 BR industrie Ofi (Olam) Cocoa (Kza) Bijenkorfstraat Zaandijk 118531',
 'Ugchelen':'P 1 BON-06 Ass. Ambu (afhijsen, tilassistentie) Hoog Buurloseweg Ugchelen 069851',
 'Eindhoven':'P 1 BOB-01 Reanimatie Veldmaarschalk Montgomerylaan Eindhoven 222331',
 'Nijmegen':'P 1 BON-05 Ongeval wegvervoer Beukstraat Nijmegen 089191 082131',
 'Dalfsen':'P 1 BON-01 BR wegvervoer Koelmansstraat Dalfsen 041630',
 'Leeuwarden':'P 1 BNN-02 OMS beheerssysteem Makro Hidalgoweg Leeuwarden 026131',
}
for city,rawline in examples.items():
    got=mod.parse_raw_p2000_line(state,rawline)
    checks[f'city_{city}']=got['city']==city
    checks[f'location_not_city_{city}']=got['location'] and got['location']!=city

# Prove the PDOK gazetteer is not limited to the bundled seed: mock two pages,
# add a fictitious BAG locality and verify the generic raw parser learns it.
class H(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def do_GET(self):
        page2='cursor=2' in self.path
        features=[{'properties':{'woonplaats':'Testdorp-Noord' if page2 else 'Voorbeelddam','status':'Woonplaats aangewezen'}}]
        links=[] if page2 else [{'rel':'next','href':f'http://127.0.0.1:{self.server.server_port}/items?cursor=2'}]
        raw=json.dumps({'type':'FeatureCollection','features':features,'links':links}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
srv=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=srv.serve_forever,daemon=True).start()
old_url,old_path,old_dir=mod.PDOK_BAG_WOONPLAATS_URL,mod.NL_PLACES_CACHE_PATH,mod.PLACE_CACHE_DIR
try:
  with TemporaryDirectory() as td:
    td=Path(td);mod.PLACE_CACHE_DIR=td;mod.NL_PLACES_CACHE_PATH=td/'places.json';mod.PDOK_BAG_WOONPLAATS_URL=f'http://127.0.0.1:{srv.server_port}/items'
    app=mod.AppState({'region_disciplines':matrix});w=mod.NLPlaceGazetteerWorker(app);w._sync()
    checks['pdok_gazetteer_online']=app.place_gazetteer_status.get('online') is True
    checks['pdok_pagination']=app.place_gazetteer_status.get('pages')==2
    checks['pdok_arbitrary_place']=mod.infer_city_from_nl_gazetteer('P 1 BOB-01 BR woning Hoofdstraat Testdorp-Noord 223131')=='Testdorp-Noord'
finally:
  mod.PDOK_BAG_WOONPLAATS_URL,mod.NL_PLACES_CACHE_PATH,mod.PLACE_CACHE_DIR=old_url,old_path,old_dir
  srv.shutdown();srv.server_close()


# SW API rows are presentation data regardless of discipline; exact 5-digit
# ambulance/police-style units should not be discarded as 'not brandweer'.
_, amb=mod.canonical_sw_unit({'lookup_key':'12345','callsign':'12-345','discipline':'ambulance','function_code':'AMB','function_name':'Ambulance','station_name':'Utrecht'})
ambcat=mod.sw_units_to_vehicle_catalog({'12345':amb})
checks['sw_cross_discipline_unit']=ambcat.get('12345',{}).get('function_name')=='Ambulance' and ambcat['12345'].get('api_primary') is True

appjs=(ROOT/'frontend'/'app.js').read_text('utf-8')
# Execute the exact UI helpers with minimal stubs.
def extract(src,name):
    start=src.index(f'function {name}('); brace=src.index('{',start); depth=0
    for i in range(brace,len(src)):
        if src[i]=='{': depth+=1
        elif src[i]=='}':
            depth-=1
            if depth==0:return src[start:i+1]
    raise ValueError(name)
js='''
%s
%s
function vehicleDetails(m){return [{key:'209471'},{key:'12345'}]}
const v={api_primary:true,source:'SW Mediaproducties Roepnummer API',function_code:'HVT-KR',function_name:'Hulpverleningsvoertuig met kraan',station_name:'Tilburg Centrum'};
const natural=vehicleDisplayLabel(v),header=vehicleHeaderFor(v,'20-9471');
const stripped=stripCallsignsForSpeech('A58 Li - Kp St.Annabosch Bavel 205332 20-3171 01-18-849 12-345',{service:'brandweer'});
console.log(JSON.stringify({natural,header,stripped}));
'''%(extract(appjs,'vehicleDisplayLabel')+'\n'+extract(appjs,'vehicleHeaderFor'),extract(appjs,'stripCallsignsForSpeech'))
cp=subprocess.run(['node','-e',js],cwd=ROOT,capture_output=True,text=True)
if cp.returncode==0:
    r=json.loads(cp.stdout.strip())
    checks['sw_vehicle_natural_text']=r['natural']=='Hulpverleningsvoertuig met kraan (HVT-KR) — Tilburg Centrum' and r['header']==r['natural'] and '20-9471' not in r['header']
    checks['speech_all_callsigns_removed']=all(x not in r['stripped'] for x in ('205332','20-3171','01-18-849','12-345'))
else:
    checks['sw_vehicle_natural_text']=checks['speech_all_callsigns_removed']=False
    print(cp.stdout,cp.stderr)

failed=[k for k,v in checks.items() if not v]
print(json.dumps({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed},ensure_ascii=False))
if failed: raise SystemExit(1)
