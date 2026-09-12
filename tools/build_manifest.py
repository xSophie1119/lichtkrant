#!/usr/bin/env python3
"""Regenerate the complete release integrity manifest from the Git checkout."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    files = {}
    for name in sorted(set(names)):
        if not name or name == 'release-manifest.json': continue
        path = ROOT / name
        if path.is_file(): files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'version': (ROOT / 'VERSION').read_text().strip(), 'algorithm': 'sha256', 'files': files}
    (ROOT / 'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Manifest v{manifest['version']}: {len(files)} bestanden")


if __name__ == '__main__': main()
