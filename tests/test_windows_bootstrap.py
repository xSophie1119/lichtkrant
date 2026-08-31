from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
ensure = (root / 'ENSURE_PYTHON.bat').read_text('utf-8')
start = (root / 'START_P2000.bat').read_text('utf-8')
wizard = (root / 'CONFIGURATIE_WIZARD.bat').read_text('utf-8')
probe = (root / 'tools' / 'runtime_probe.py').read_text('utf-8')

checks = {
    'python_version': '3.13.15' in ensure,
    'amd64_embed_url': 'python-%PYVER%-embed-!PKGARCH!.zip' in ensure,
    'amd64_hash': 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf' in ensure,
    'arm64_hash': 'cd992cbfb33be433ff20f150691595efb2862e56f4f1bec684c6077d4775af8e' in ensure,
    'curl_primary': 'curl.exe --fail' in ensure,
    'sha256_check': 'certutil.exe -hashfile' in ensure,
    'powershell_fallback_only': 'no python installer' in ensure.lower() and 'ENSURE_PYTHON.ps1' in ensure,
    'start_pauses_on_python_error': ':fatal_python' in start and 'pause' in start.split(':fatal_python',1)[1],
    'wizard_pauses_on_python_error': ':fatal_python' in wizard and 'pause' in wizard.split(':fatal_python',1)[1],
    'backend_log': 'backend.log' in start,
    'python_bootstrap_log': 'python-bootstrap.log' in start,
    'runtime_probe_no_powershell': 'urllib.request' in probe and 'netstat' in probe and 'taskkill' in probe,
    'zip_extract_guard': 'niet volledig uitgepakt' in start and 'backend\\server.py' in start,
}
failed = [k for k,v in checks.items() if not v]
print({'tests': len(checks), 'passed': len(checks)-len(failed), 'failures': len(failed), 'failed': failed})
raise SystemExit(1 if failed else 0)
