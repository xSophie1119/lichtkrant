#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from recovery_bootstrap import mirror_restore
from health_gate import evaluate_installation_health
ROOT=Path(__file__).resolve().parents[1];BACKUPS=ROOT/'data'/'updates'/'backups'
def main():
    rows=sorted([p for p in BACKUPS.iterdir() if p.is_dir()] if BACKUPS.exists() else [],key=lambda p:p.stat().st_mtime,reverse=True)
    if not rows:print('[FOUT] Geen backup.');return 2
    cp=subprocess.run([sys.executable,str(ROOT/'tools'/'runtime_probe.py'),'--stop-all'],cwd=ROOT)
    if cp.returncode:return 3
    backup=rows[0]
    try:mirror_restore(backup,ROOT)
    except Exception as exc:print('[FOUT] rollback:',exc);return 4
    ver=''
    try:ver=json.loads((backup/'backup.json').read_text()).get('version','')
    except Exception:pass
    h=evaluate_installation_health(ROOT,expected_version=ver or None)
    if not h['ok']:print('[FOUT] rollback-health:',h['critical_failures']);return 5
    print(f'[OK] Hersteld naar {ver or "vorige versie"}.');return 0
if __name__=='__main__':raise SystemExit(main())
