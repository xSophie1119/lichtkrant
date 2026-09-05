#!/usr/bin/env python3
"""Run the repository's script-style regression tests in isolated processes."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEST_DIR=ROOT/'tests'

def main() -> int:
    tests=sorted(TEST_DIR.glob('test_*.py'))
    if not tests:
        print('Geen tests gevonden.', file=sys.stderr)
        return 2
    env=os.environ.copy()
    env.setdefault('PYTHONUNBUFFERED','1')
    passed=[]; failed=[]
    started=time.monotonic()
    print(f'P2000 Monitor regressietests: {len(tests)} scripts')
    print(f'Python: {sys.executable}')
    print('-'*72)
    for test in tests:
        t0=time.monotonic()
        proc=subprocess.run([sys.executable,str(test)],cwd=str(ROOT),env=env,text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        elapsed=time.monotonic()-t0
        status='OK' if proc.returncode==0 else 'FAIL'
        print(f'[{status:4}] {test.name} ({elapsed:.2f}s)')
        output=(proc.stdout or '').strip()
        if output:
            for line in output.splitlines():
                print(f'       {line}')
        (passed if proc.returncode==0 else failed).append(test.name)
    print('-'*72)
    print(f'Klaar in {time.monotonic()-started:.2f}s: {len(passed)} geslaagd, {len(failed)} mislukt.')
    if failed:
        print('Mislukt: '+', '.join(failed), file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
