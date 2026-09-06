#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path

REQUIRED_FRONTEND = ("frontend/index.html", "frontend/app.js", "frontend/control.js")


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def evaluate_installation_health(root: Path, *, expected_version: str | None=None, runtime_payload: dict | None=None) -> dict:
    root=Path(root).resolve(); critical=[]; degraded=[]
    version=''
    try: version=(root/'VERSION').read_text(encoding='utf-8').strip()
    except Exception as exc: critical.append(f'VERSION onleesbaar: {exc}')
    if expected_version and version != expected_version:
        critical.append(f'versie {version or "?"} != {expected_version}')
    cfg=root/'config'/'config.json'
    if cfg.exists():
        try:
            parsed=json.loads(cfg.read_text(encoding='utf-8'))
            if not isinstance(parsed,dict): critical.append('config/config.json is geen object')
        except Exception as exc: critical.append(f'config/config.json ongeldig: {exc}')
    for rel in REQUIRED_FRONTEND:
        p=root/rel
        if not p.is_file() or p.stat().st_size < 10: critical.append(f'vereist frontendbestand ontbreekt/leeg: {rel}')
    db=root/'data'/'p2000.sqlite3'
    if db.exists():
        try:
            con=sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=2)
            try:
                row=con.execute('PRAGMA quick_check(1)').fetchone()
                if not row or str(row[0]).lower()!='ok': critical.append(f'SQLite quick_check: {row}')
                con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            finally: con.close()
        except Exception as exc: critical.append(f'SQLite niet bruikbaar: {exc}')
    if runtime_payload is not None:
        if runtime_payload.get('app') != 'P2000 Monitor': critical.append('runtime-identiteit ongeldig')
        if expected_version and str(runtime_payload.get('version') or '') != expected_version: critical.append('runtimeversie ongeldig')
    return {'ok':not critical,'critical_failures':critical,'degraded':degraded,'version':version}


def verify_release_manifest(root: Path, expected_version: str | None=None) -> dict:
    root=Path(root).resolve(); manifest_path=root/'release-manifest.json'
    if not manifest_path.is_file(): raise RuntimeError('release-manifest.json ontbreekt')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest,dict): raise RuntimeError('release manifest ongeldig')
    version=str(manifest.get('version') or '')
    if expected_version and version != str(expected_version): raise RuntimeError(f'manifestversie {version!r} != {expected_version!r}')
    files=manifest.get('files')
    if not isinstance(files,dict) or not files: raise RuntimeError('release manifest bevat geen hashes')
    for rel,want in files.items():
        relp=Path(str(rel))
        if relp.is_absolute() or '..' in relp.parts: raise RuntimeError(f'onveilig manifestpad: {rel}')
        p=root/relp
        if not p.is_file(): raise RuntimeError(f'manifestbestand ontbreekt: {rel}')
        got=sha256_file(p)
        if got.lower()!=str(want).lower(): raise RuntimeError(f'SHA-256 mismatch: {rel}')
    return {'ok':True,'version':version,'files':len(files)}
