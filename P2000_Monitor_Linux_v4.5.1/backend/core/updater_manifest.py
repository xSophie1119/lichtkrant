from __future__ import annotations
import hashlib, json, os, re, sys
from urllib.parse import urlparse

MANIFEST_VERSION=1

def platform_key() -> str:
    if os.name=="nt": return "windows"
    if sys.platform.startswith("linux"): return "linux"
    return sys.platform.lower()

def version_key(v: str) -> tuple[int,...]:
    nums=[int(x) for x in re.findall(r"\d+",str(v or ""))[:4]]
    return tuple(nums+[0]*(4-len(nums)))

def parse_manifest(body: bytes, current_version: str) -> dict:
    doc=json.loads(body.decode("utf-8","replace"))
    if not isinstance(doc,dict): raise ValueError("update-manifest is geen JSON-object")
    if int(doc.get("manifest_version") or 0)!=MANIFEST_VERSION: raise ValueError("onbekende manifestversie")
    version=str(doc.get("version") or "").lstrip("vV").strip()
    if not version or not re.search(r"\d",version): raise ValueError("manifest bevat geen geldige versie")
    raw_platforms=doc.get("platforms") or {}
    if not isinstance(raw_platforms,dict): raise ValueError("manifest platforms is ongeldig")
    platforms={}
    for key,row in raw_platforms.items():
        if not isinstance(row,dict): continue
        url=str(row.get("url") or "").strip(); sha=str(row.get("sha256") or "").strip().lower()
        if urlparse(url).scheme!="https": raise ValueError(f"update-URL voor {key} moet HTTPS zijn")
        if not re.fullmatch(r"[0-9a-f]{64}",sha): raise ValueError(f"manifest mist geldige SHA-256 voor {key}")
        platforms[str(key).lower()]={"name":str(row.get("name") or f"P2000_Monitor_{key}_{version}.zip")[:240],
                                     "url":url,"sha256":sha,"size":int(row.get("size") or 0)}
    key=platform_key()
    if key not in platforms: raise ValueError(f"manifest bevat geen pakket voor {key}")
    min_version=str(doc.get("min_supported_version") or "").lstrip("vV").strip()
    return {"version":version,"platform":key,"platforms":platforms,
            "required":bool(doc.get("required")),"min_supported_version":min_version,
            "published_at":doc.get("published_at"),"notes":str(doc.get("notes") or "")[:4000],
            "compatible":not min_version or version_key(current_version)>=version_key(min_version),"source_kind":"manifest"}

def verify_file(path, expected_sha256: str) -> bool:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest().lower()==expected_sha256.lower()
