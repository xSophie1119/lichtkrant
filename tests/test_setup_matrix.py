import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SERVER=ROOT/'backend'/'server.py'
spec=importlib.util.spec_from_file_location('p2000_setup_under_test',SERVER)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

fails=[]

def check(cond,msg):
    if not cond: fails.append(msg)

# v4.4.8: all five 112-nu discipline feeds are always the primary transport
# layer; region/discipline scope is applied after parsing.
expected_primary=[mod.NU112_DISCIPLINE_URLS[d] for d in ('brandweer','ambulance','politie','lifeliner','knrm')]
m={'utrecht':['brandweer','ambulance','politie','knrm','lifeliner']}
u=mod.build_feed_urls(m)
check(u==expected_primary,f'fixed 112-nu primary set mismatch: {u}')
check(mod.NU112_DISCIPLINE_URLS['brandweer'] in u,'112-nu brandweer missing')
check(mod.NU112_DISCIPLINE_URLS['lifeliner'] in u,'112-nu traumahelikopter missing')

# Changing the selected regions may change filtering/fallback, never the five primary feeds.
m={'hollands-midden':['brandweer'],'bollenstreek':['brandweer']}
u=mod.build_feed_urls(m)
check(u==expected_primary,f'primary feed set changed with region selection: {u}')

m={slug:['brandweer','politie'] for slug in mod.SAFETY_REGION_SLUGS}
u=mod.build_feed_urls(m)
check(u==expected_primary,f'primary feed set changed for national selection: {u}')

# Scope filter: same article allowed for selected discipline/region, rejected elsewhere.
def msg(region,service='brandweer',url=''):
    meta=mod.REGION_CATALOG[region]
    return mod.Message(id='x',published=mod.utcnow_iso(),updated=mod.utcnow_iso(),title='P 1 BR woning Hoofdstraat Teststad 123431',summary='',url=url,service=service,priority='P1',city='Teststad',location='Hoofdstraat',units=['12-3431'],categories=[service,f"Regio {meta['label']}"],scale='',scale_score=0,incident_key='x')
config={'region_disciplines':{'utrecht':['brandweer'],'flevoland':['politie']}}
check(mod.config_allows_message(config,msg('utrecht','brandweer')),'selected Utrecht brandweer rejected')
check(not mod.config_allows_message(config,msg('utrecht','politie')),'unselected Utrecht politie accepted')
check(mod.config_allows_message(config,msg('flevoland','politie')),'selected Flevoland politie rejected')
check(not mod.config_allows_message(config,msg('flevoland','brandweer')),'unselected Flevoland brandweer accepted')

# Subregion articles may be accepted by a selected parent safety region.
config={'region_disciplines':{'hollands-midden':['brandweer']}}
check(mod.config_allows_message(config,msg('bollenstreek','brandweer')),'subregion article not accepted through parent')


# Regionless national-feed items are accepted only for a truly nationwide selection.
regionless=mod.Message(id='r',published=mod.utcnow_iso(),updated=mod.utcnow_iso(),title='P 2 BR buiten onbekende locatie',summary='',url='',service='brandweer',priority='P2',city='',location='',units=[],categories=['brandweer'],scale='',scale_score=0,incident_key='r')
all_brw={'region_disciplines':{slug:['brandweer'] for slug in mod.SAFETY_REGION_SLUGS}}
check(mod.config_allows_message(all_brw,regionless),'regionless national item rejected for all-NL selection')
check(not mod.config_allows_message({'region_disciplines':{'utrecht':['brandweer']}},regionless),'regionless item accepted for narrow profile')

print({'tests':12,'failures':len(fails),'passed':12-len(fails)})
for f in fails: print('FAIL',f)
if fails: raise SystemExit(1)
