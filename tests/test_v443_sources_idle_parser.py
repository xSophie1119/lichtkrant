from __future__ import annotations
import importlib.util, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('server_v443',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)

RAW='P 1 BZB-01 Ongeval wegvervoer (Soort THV: Zware THV) A58 Li - Kp St.Annabosch Bavel 205332 203171 203092 203145'
class State:
    def __init__(self):
        self.config={'region_disciplines':{'midden-en-west-brabant':['brandweer']},'feed_112nu_enabled':True,'feed_race_enabled':True,'feed_urls':[]}
    def get_display_settings(self): return {}

state=State(); parsed=mod.parse_raw_p2000_line(state,RAW)
checks={
    'version_443': mod.APP_VERSION=='4.4.4' and (ROOT/'VERSION').read_text().strip()=='4.4.4',
    'sample_city': parsed['city']=='Bavel',
    'sample_location': parsed['location']=='A58 Li - Kp St.Annabosch',
    'sample_channel': parsed['dispatch_channel']=='BZB-01',
    'sample_region': parsed['region']=='Midden- en West-Brabant',
    'sample_units': parsed['units']==['20-5332','20-3171','20-3092','20-3145'],
}
# Other regional channel families are syntax-based, not BZB-only.
checks['bnh_channel']=mod.dispatch_channel_code('P 1 BNH-02 Nacontrole Baljuw Assendelft 118038')=='BNH-02'
checks['bad_channel']=mod.dispatch_channel_code('P 1 BAD-04 BR buiten industrie Vlothavenweg Amsterdam 134081')=='BAD-04'
checks['bgm_channel']=mod.dispatch_channel_code('P 1 BGM-01 BR woning Dorpsstraat Arnhem 074231')=='BGM-01'

xml=f'''<rss><channel><item><title>Ongeval op de A58 bij Bavel</title><description>Originele Melding: {RAW} Tijdstip: 04-09-2026 15:44</description><link>https://112-nu.nl/melding/123456/bavel/a58/brandweer-met-grote-spoed.html</link><category>Brandweer</category><pubDate>Fri, 04 Sep 2026 13:44:00 GMT</pubDate></item></channel></rss>'''.encode()
msg=mod.FeedPoller(state).parse_feed(xml,mod.NU112_ALL_RSS)[0]
checks.update({
    '112nu_raw_title': msg.title==RAW,
    '112nu_source': msg.source=='112-nu.nl',
    '112nu_city_url': msg.city=='Bavel',
    '112nu_region_callsign': 'Regio Midden- en West-Brabant' in msg.categories,
    '112nu_scope': mod.config_allows_message(state.config,msg),
    '112nu_race': mod.NU112_ALL_RSS in mod.AppState.race_feed_urls(state),
})
# Same original line from another source/day must share the same id for race dedupe.
id_a=mod.canonical_message_id(RAW,'2026-09-04T13:44:00+00:00','https://112-nu.nl/a')
id_b=mod.canonical_message_id(RAW,'2026-09-04T13:44:03+00:00','https://alarmeringen.nl/b')
id_c=mod.canonical_message_id(RAW,'2026-09-05T13:44:00+00:00','https://112-nu.nl/c')
checks['cross_source_dedupe']=id_a==id_b and id_a!=id_c

app=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
control=(ROOT/'frontend'/'control.html').read_text(encoding='utf-8')
index=(ROOT/'frontend'/'index.html').read_text(encoding='utf-8')
checks['raw_display_default']="messageDisplayMode:'raw'" in app and 'ORIGINELE P2000-MELDING' in app
checks['idle_builder']='idleLayoutInput' in control and 'idleBuilderPreview' in control and 'idleClockScaleInput' in control
checks['112nu_control']='feed112nuInput' in control
checks['112nu_attribution']='href="https://112-nu.nl/"' in index and 'sourceAttribution' in index
checks['speech_channel_generic']='(?:B[A-Z]{2}|S[A-Z]{2}|KAZ)-\\d{1,3}' in app

# Execute the actual JS road-abbreviation helper in isolation.
node_script=r'''
const fs=require('fs');const s=fs.readFileSync('frontend/app.js','utf8');
const a=s.indexOf('function naturalRoadSpeechLocation('),b=s.indexOf('function contextualFireType(',a);
eval(s.slice(a,b));
const got=naturalRoadSpeechLocation('A58 li - kp st.annabosch');
if(got!=='A58 links - knooppunt Sint annabosch'){console.error(got);process.exit(2)}
'''
cp=subprocess.run(['node','-e',node_script],cwd=ROOT,capture_output=True,text=True)
checks['road_speech']=cp.returncode==0

failed=[k for k,v in checks.items() if not v]
print({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed})
if cp.returncode: print(cp.stdout,cp.stderr)
if failed: raise SystemExit(1)
