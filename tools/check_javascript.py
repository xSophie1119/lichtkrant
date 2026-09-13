import subprocess
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for path in (root/'frontend').glob('*.js'):
    subprocess.run(['node', '--check', str(path)], check=True)
print('Alle frontend-JavaScript syntactisch geldig')
