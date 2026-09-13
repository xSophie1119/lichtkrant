"""CI validates the checked-in release manifest, without silently regenerating it."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT/'release-manifest.json').read_text())
names = set(subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')) - {'', 'release-manifest.json'}
assert set(manifest['files']) == names, 'Manifest mist bestanden of bevat onbekende bestanden'
assert manifest['version'] == (ROOT/'VERSION').read_text().strip(), 'Manifestversie wijkt af'
for name, digest in manifest['files'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, f'Hash wijkt af: {name}'
print(f'Manifest gecontroleerd: {len(names)} bestanden')
