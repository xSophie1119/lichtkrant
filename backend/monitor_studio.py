"""Bounded local flight recorder and versioned, validated monitor design settings."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from remote_storage import atomic_json

SERVICES = {'brandweer', 'ambulance', 'politie', 'lifeliner', 'knrm', 'overig'}
FIELDS = {'city', 'location', 'service', 'priority', 'units'}
BLOCKS = {'message', 'map', 'vehicles', 'clock', 'incidents'}


def defaults():
    boxes = [dict(type='message', x=2, y=3, w=62, h=60), dict(type='map', x=66, y=3, w=32, h=70) ,dict(type='vehicles', x=2, y=65, w=62, h=25),dict(type='clock', x=66, y=75, w=32, h=15)]
    return dict(enabled=False, default_action='show', unknown_location='show', zones=[], rules=[],
                speech=dict(enabled=False, template='{incident}{where}. {scale} {units}', cue=True),
                layout=dict(enabled=False, aspect='16:9', min_font=24, scenes={
                    'idle':[dict(type='clock',x=10,y=20,w=80,h=50)], 'single':boxes,
                    'multiple': [dict(type='message',x=2,y=3,w=60,h=55),dict(type='incidents',x=2,y=60,w=60,h=35),dict(type='map',x=64,y=3,w=34,h=70),dict(type='clock',x=64,y=75,w=34,h=20)]}), corrections=[], examples=[])

def text(value, limit=160):
    if not isinstance(value, str) or len(value) > limit: raise ValueError('Tekst ontbreekt of is te lang')
    return value.strip()


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Getal moet tussen {low} en {high} liggen')
    return value


def rows(value, limit):
    if not isinstance(value, list) or len(value) > limit or not all(isinstance(x, dict) for x in value): raise ValueError('Ongeldige lijst of te veel onderdelen')
    return value


def choice(value, allowed):
    if value not in allowed: raise ValueError('Onbekende keuze: '+str(value)[:80])
    return value


def correction(row):
    out = dict(id=text(row.get('id') or uuid.uuid4().hex,80), match=text(row.get('match',''),1200), mode=choice(row.get('mode','exact'), {'exact','contains'}), changes={})
    if len(out['match']) < (8 if out['mode']=='contains' else 1): raise ValueError('Gebruik minstens acht tekens voor een bredere correctie')
    changes=row.get('changes')
    if not isinstance(changes,dict) or not changes or set(changes)-FIELDS: raise ValueError('Kies plaats, locatie, dienst, prioriteit of voertuigen')
    for k,v in changes.items():
        if k=='units':
            if not isinstance(v,list) or len(v)>40 or any(not isinstance(x,str) or not x.replace('-','').isdigit() or len(x)>12 for x in v): raise ValueError('Ongeldige roepnummers')
            out['changes'][k]=list(dict.fromkeys(v))
        else: out['changes'][k]=text(v,240)
    if 'service' in changes: choice(changes['service'],SERVICES)
    if 'priority' in changes: choice(changes['priority'],{'','P1','P2','P3','P4','P5','A0','A1','A2','B1','B2'})
    return out


def validate(doc):
    if not isinstance(doc,dict): raise ValueError('Instellingen moeten een object zijn')
    out=defaults()
    for k in ('enabled',): out[k]=doc.get(k,False) is True
    out['default_action']=choice(doc.get('default_action','show'),{'show','hide'})
    out['unknown_location']=choice(doc.get('unknown_location','show'),{'show','hide'})
    ids=set()
    for z in rows(doc.get('zones',[]),30):
        zid=text(z.get('id',''),80)
        if not zid or zid in ids: raise ValueError('Gebieden moeten unieke namen/codes hebben')
        ids.add(zid); pts=z.get('points')
        if not isinstance(pts,list) or not 3<=len(pts)<=80: raise ValueError('Teken een gebied met 3 tot 80 punten')
        points=[]
        for p in pts:
            if not isinstance(p,list) or len(p)!=2: raise ValueError('Ongeldig kaartpunt')
            points.append([number(p[0],-85,85),number(p[1],-180,180)])
        if len({tuple(p) for p in points})!=len(points): raise ValueError('Een gebied mag geen dubbele hoekpunten hebben')
        def orient(a,b,c): return (b[1]-a[1])*(c[0]-a[0])-(b[0]-a[0])*(c[1]-a[1])
        for i,a in enumerate(points):
            b=points[(i+1)%len(points)]
            for j in range(i+1,len(points)):
                if j==i+1 or i==0 and j==len(points)-1: continue
                c,d=points[j],points[(j+1)%len(points)]
                if orient(a,b,c)*orient(a,b,d)<0 and orient(c,d,a)*orient(c,d,b)<0:
                    raise ValueError('De lijnen van een gebied mogen elkaar niet kruisen')
        area=sum(points[i][1]*points[(i+1)%len(points)][0]-points[(i+1)%len(points)][1]*points[i][0] for i in range(len(points)))
        if abs(area)<1e-9: raise ValueError('Gebied heeft geen oppervlakte')
        out['zones'].append(dict(id=zid,name=text(z.get('name','Gebied'),80),points=points,enabled=z.get('enabled',True) is True,expires=number(z.get('expires',0),0,4102444800000)))
    ruleids=set()
    for r in rows(doc.get('rules',[]),60):
        rid=text(r.get('id',''),80)
        if not rid or rid in ruleids: raise ValueError('Regels moeten unieke codes hebben')
        ruleids.add(rid)
        cond=r.get('when',{})
        if not isinstance(cond,dict) or set(cond)-{'service','priority','city','contains','zone','min_scale','resource'}: raise ValueError('Onbekende regelvoorwaarde')
        when={}
        for k,v in cond.items():
            when[k]=number(v,0,100) if k=='min_scale' else text(v,160)
            if k=='zone' and v not in ids: raise ValueError('Regel verwijst naar een verwijderd gebied')
            if k=='service' and v: choice(v,SERVICES)
            if k=='resource' and v: choice(v,{'mmt','ovdg'})
        out['rules'].append(dict(id=rid,name=text(r.get('name','Regel'),100),enabled=r.get('enabled',True) is True,when=when,action=choice(r.get('action','show'),{'show','hide','silent','urgent'}),cue=choice(r.get('cue','auto'),{'auto','none','brandweer','politie','ambulance','lifeliner'})))
    s=doc.get('speech',{})
    if not isinstance(s,dict): raise ValueError('Ongeldige omroep')
    template=text(s.get('template',out['speech']['template']),1500)
    import re
    if set(re.findall(r'\{([^{}]+)\}',template))-{'incident','where','city','location','scale','units','priority','service'}: raise ValueError('Onbekend omroeponderdeel')
    out['speech']=dict(enabled=s.get('enabled',False) is True,template=template,cue=s.get('cue',True) is True)
    lay=doc.get('layout',out['layout'])
    if not isinstance(lay,dict): raise ValueError('Ongeldige schermindeling')
    out['layout']=dict(enabled=lay.get('enabled',False) is True,aspect=choice(lay.get('aspect','16:9'),{'16:9','16:10','4:3','21:9','9:16'}),min_font=number(lay.get('min_font',24),14,96),scenes={})
    scenes=lay.get('scenes',defaults()['layout']['scenes'])
    if not isinstance(scenes,dict): raise ValueError('Ongeldige scènes')
    for name in ('idle','single','multiple'):
        boxes=[]; types=set()
        for b in rows(scenes.get(name,[]),5):
            kind=choice(b.get('type'),BLOCKS)
            if kind in types: raise ValueError('Een blok mag maar één keer in een scène staan')
            types.add(kind)
            box=dict(type=kind,**{k:number(b.get(k),0 if k in {'x','y'} else 5,100) for k in ('x','y','w','h')})
            if box['x']+box['w']>100.01 or box['y']+box['h']>100.01: raise ValueError('Schermblok valt buiten het scherm')
            boxes.append(box)
        if lay.get('enabled') and not boxes: raise ValueError('Elke scène moet minstens één blok bevatten')
        out['layout']['scenes'][name]=boxes
    out['corrections']=[correction(c) for c in rows(doc.get('corrections',[]),200)]
    if len({c['id'] for c in out['corrections']})!=len(out['corrections']): raise ValueError('Dubbele correctiecode')
    # Test fixtures can only be added by the correction endpoint, never from a design save.
    return out


def apply_corrections(message, corrections):
    result=copy.deepcopy(message); raw=str(message.get('title') or message.get('raw') or '').strip().casefold()
    for c in corrections:
        match=c['match'].casefold()
        if (raw==match if c['mode']=='exact' else match in raw):
            result.update(copy.deepcopy(c['changes']));result['studio_correction']=c['id'];break
    return result


class Studio:
    def __init__(self, root):
        self.root=Path(root)/'studio';self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'design.json';self.db=self.root/'recorder.sqlite3';self.lock=threading.RLock();self.seen=OrderedDict();self.error=''
        self.doc=dict(revision=0,config=defaults())
        if self.path.exists():
            stored=json.loads(self.path.read_text(encoding='utf-8'));conf=validate(stored['config']);conf['examples']=stored['config'].get('examples',[])[:200]
            self.doc=dict(revision=int(stored['revision']),config=conf)
        with self.connect() as con:
            con.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT, mid TEXT UNIQUE, at REAL, payload TEXT, scope INTEGER, design TEXT);
                CREATE TABLE IF NOT EXISTS decisions(seq INTEGER PRIMARY KEY AUTOINCREMENT, mid TEXT, client TEXT, at REAL, payload TEXT);
                CREATE INDEX IF NOT EXISTS decisions_mid ON decisions(mid,seq DESC);
                CREATE TABLE IF NOT EXISTS designs(id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS recordings(id TEXT PRIMARY KEY, name TEXT, at REAL, payload TEXT);
            ''')

    @contextmanager
    def connect(self):
        con=sqlite3.connect(self.db,timeout=5);con.row_factory=sqlite3.Row
        try: yield con;con.commit()
        except Exception: con.rollback();raise
        finally: con.close()

    def snapshot(self):
        with self.lock: return copy.deepcopy(self.doc)

    def save(self,config,expected,example=None):
        clean=validate(config)
        with self.lock:
            if expected!=self.doc['revision']: raise ValueError('Instellingen zijn elders gewijzigd. Laad opnieuw en bekijk je wijzigingen.')
            clean['examples']=copy.deepcopy(self.doc['config'].get('examples',[]))
            if example: clean['examples']=(clean['examples']+[example])[-200:]
            doc=dict(revision=self.doc['revision']+1,config=clean)
            atomic_json(self.path,doc);self.doc=doc
            return copy.deepcopy(doc)

    def corrected(self,message): return apply_corrections(message,self.snapshot()['config']['corrections'])

    def record(self,messages,scope,settings):
        # One short SQLite transaction per batch. Repeated RSS polls stay in RAM.
        with self.lock:
            fresh=[m for m in messages if m.get('id') and m['id'] not in self.seen]
            if not fresh:return
            design=json.dumps(dict(studio=self.doc,settings=settings),ensure_ascii=False)
            design_id=hashlib.sha256(design.encode()).hexdigest()
            try:
                with self.connect() as con:
                    con.execute('INSERT OR IGNORE INTO designs VALUES(?,?)',(design_id,design))
                    for m in fresh:
                        con.execute('INSERT OR IGNORE INTO records(mid,at,payload,scope,design) VALUES(?,?,?,?,?)',(m['id'],time.time(),json.dumps(m,ensure_ascii=False),int(scope(m)),design_id))
                    con.execute('DELETE FROM records WHERE seq NOT IN (SELECT seq FROM records ORDER BY seq DESC LIMIT 2000)')
                    con.execute('DELETE FROM designs WHERE id NOT IN (SELECT DISTINCT design FROM records)')
                for m in fresh:self.seen[m['id']]=True
                while len(self.seen)>5000:self.seen.popitem(last=False)
                self.error=''
            except sqlite3.Error as exc:
                self.error='Opname opslaan mislukt: '+str(exc)[:180]
                # Recorder failure must never stop live reception.

    def list_records(self,before=0,q='',since=0,until=4102444800,limit=100):
        args=[float(since),float(until)];where='at>=? AND at<?'
        if before:where+=' AND seq<?';args.append(int(before))
        if q:where+=' AND payload LIKE ?';args.append('%'+str(q)[:120]+'%')
        with self.connect() as con:
            result=[];design_cache={}
            for r in con.execute('SELECT * FROM records WHERE '+where+' ORDER BY seq DESC LIMIT ?',args+[min(int(limit),500)]):
                d=dict(r);d['message']=json.loads(d.pop('payload'));design_id=d['design']
                if design_id not in design_cache:
                    stored=con.execute('SELECT payload FROM designs WHERE id=?',(design_id,)).fetchone()
                    design_cache[design_id]=json.loads(stored[0] if stored else design_id)
                d['design']=design_cache[design_id];d['design_id']=design_id
                d['decisions']=[json.loads(x[0]) for x in con.execute('SELECT payload FROM decisions WHERE mid=? ORDER BY seq DESC LIMIT 12',(r['mid'],))]
                result.append(d)
            return result

    def decision(self,payload):
        mid=text(payload.get('id',''),240);client=text(payload.get('client_id',''),120)
        d=dict(id=mid,client_id=client,at=time.time(),reason=text(payload.get('reason',''),400),shown=payload.get('shown') is True,revision=number(payload.get('revision',0),0,1e9),rule=text(payload.get('rule',''),100))
        geo=payload.get('geo')
        if isinstance(geo,dict): d['geo']=dict(lat=number(geo.get('lat'),-85,85),lon=number(geo.get('lon'),-180,180),source=text(geo.get('source',''),100))
        with self.connect() as con:
            if not con.execute('SELECT 1 FROM records WHERE mid=?',(mid,)).fetchone():return
            con.execute('INSERT INTO decisions(mid,client,at,payload) VALUES(?,?,?,?)',(mid,client,time.time(),json.dumps(d,ensure_ascii=False)))
            con.execute('DELETE FROM decisions WHERE seq NOT IN (SELECT seq FROM decisions ORDER BY seq DESC LIMIT 10000)')

    def capture(self,name,since,until):
        name=text(name,100)
        if not name:raise ValueError('Geef de opname een naam')
        number(since,0,4102444800);number(until,0,4102444800)
        if float(since)>=float(until):raise ValueError('Eindtijd moet na begintijd liggen')
        records=self.list_records(since=since,until=until,limit=500)
        if not records:raise ValueError('Geen ontvangen meldingen in deze periode')
        designs={}
        for row in records:
            snap=row.pop('design');key=row['design_id']
            designs[key]=snap;row['design_id']=key
        obj=dict(id=uuid.uuid4().hex,name=name,at=time.time(),records=list(reversed(records)),designs=designs)
        with self.connect() as con:
            con.execute('INSERT INTO recordings VALUES(?,?,?,?)',(obj['id'],name,obj['at'],json.dumps(obj,ensure_ascii=False)))
            con.execute('DELETE FROM recordings WHERE id NOT IN (SELECT id FROM recordings ORDER BY at DESC LIMIT 20)')
        return obj

    def recordings(self,key=''):
        with self.connect() as con:
            if key:
                row=con.execute('SELECT payload FROM recordings WHERE id=?',(key,)).fetchone()
                if not row:raise ValueError('Opname niet gevonden')
                return json.loads(row[0])
            return [dict(r) for r in con.execute('SELECT id,name,at FROM recordings ORDER BY at DESC')]
