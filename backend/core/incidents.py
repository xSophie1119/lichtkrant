from __future__ import annotations
from datetime import datetime, timezone
import math, re

def _norm(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9à-ÿ]+", " ", value)
    return " ".join(value.split())

def _tokens(value: str) -> set[str]:
    return {x for x in _norm(value).split() if len(x) > 2}

def _jaccard(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb: return 0.0
    return len(aa & bb) / max(1, len(aa | bb))

def _seconds(a: str, b: str) -> float:
    try:
        da=datetime.fromisoformat(str(a).replace("Z","+00:00")); db=datetime.fromisoformat(str(b).replace("Z","+00:00"))
        if da.tzinfo is None: da=da.replace(tzinfo=timezone.utc)
        if db.tzinfo is None: db=db.replace(tzinfo=timezone.utc)
        return abs((da-db).total_seconds())
    except Exception:
        return 10**9

def _distance_m(a: dict, b: dict) -> float | None:
    try:
        lat1,lon1=float(a.get("lat")),float(a.get("lon")); lat2,lon2=float(b.get("lat")),float(b.get("lon"))
    except (TypeError,ValueError): return None
    r=6371000.0; p1=math.radians(lat1);p2=math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(min(1.0, math.sqrt(h)))

def incident_similarity(a: dict, b: dict) -> dict:
    """Explainable 0..100 score for two messages belonging to one incident."""
    score=0; reasons=[]
    ac,bc=_norm(a.get("city","")),_norm(b.get("city",""))
    al,bl=_norm(a.get("location","")),_norm(b.get("location",""))
    if ac and ac==bc: score+=24; reasons.append("zelfde plaats")
    elif ac and bc: score-=35; reasons.append("andere plaats")
    if al and al==bl: score+=38; reasons.append("zelfde locatie")
    else:
        j=_jaccard(al,bl)
        if j>=.75: score+=32; reasons.append("bijna gelijke locatie")
        elif j>=.45: score+=20; reasons.append("vergelijkbare locatie")
    at=_norm(a.get("incident_type",a.get("classification","")));bt=_norm(b.get("incident_type",b.get("classification","")))
    if at and at==bt: score+=12; reasons.append("zelfde incidenttype")
    elif _jaccard(at,bt)>=.5: score+=7; reasons.append("vergelijkbaar incidenttype")
    dt=_seconds(a.get("published",a.get("last_seen","")),b.get("published",b.get("last_seen","")))
    if dt<=300: score+=16; reasons.append("binnen 5 minuten")
    elif dt<=900: score+=12; reasons.append("binnen 15 minuten")
    elif dt<=1800: score+=6; reasons.append("binnen 30 minuten")
    elif dt>3600: score-=25; reasons.append("meer dan een uur verschil")
    ua={str(x) for x in a.get("units",[]) if x};ub={str(x) for x in b.get("units",[]) if x}
    if ua and ub and ua&ub: score+=8;reasons.append("zelfde eenheid")
    dist=_distance_m(a,b)
    if dist is not None:
        if dist<=150: score+=18;reasons.append("zelfde coördinaten")
        elif dist<=500: score+=10;reasons.append("locaties dichtbij")
        elif dist>5000: score-=20;reasons.append("locaties ver uit elkaar")
    score=max(0,min(100,score))
    return {"score":score,"match":score>=62,"strong":score>=78,"reasons":reasons}
