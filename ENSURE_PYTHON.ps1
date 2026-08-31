$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Compatibility fallback only. Normal installs use curl.exe/tar.exe/certutil.exe
# from ENSURE_PYTHON.bat and never need PowerShell.
$PythonVersion = '3.13.15'
$RuntimeRoot = Join-Path $env:LOCALAPPDATA 'P2000-Monitor\Runtime'
$PythonDir = Join-Path $RuntimeRoot 'Python313'
$PythonExe = Join-Path $PythonDir 'python.exe'

try {
    $arch = $env:PROCESSOR_ARCHITEW6432
    if ([string]::IsNullOrWhiteSpace($arch)) { $arch = $env:PROCESSOR_ARCHITECTURE }
    switch -Regex ($arch) {
        '^AMD64$' {
            $suffix = 'amd64'
            $expected = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
        }
        '^ARM64$' {
            $suffix = 'arm64'
            $expected = 'cd992cbfb33be433ff20f150691595efb2862e56f4f1bec684c6077d4775af8e'
        }
        default { throw "Niet-ondersteunde Windows-architectuur: $arch" }
    }

    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    $zip = Join-Path $env:TEMP "p2000-python-$PythonVersion-embed-$suffix.zip"
    $url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-$suffix.zip"
    Write-Host "[P2000] Noodfallback: embedded Python downloaden..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.ServicePointManager]::SecurityProtocol
    } catch {}
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip -TimeoutSec 180 -Headers @{ 'User-Agent' = 'P2000-Monitor-Windows/4.1.1' }

    $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "SHA256-controle mislukt. Verwacht $expected, ontvangen $actual" }

    if (Test-Path -LiteralPath $PythonDir) { Remove-Item -LiteralPath $PythonDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $PythonDir -Force
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue

    if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'python.exe ontbreekt na uitpakken.' }
    & $PythonExe -c "import sys,sqlite3,urllib.request; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'De uitgepakte Python-runtime start niet correct.' }
    Write-Host '[P2000] Embedded Python-runtime is klaar.' -ForegroundColor Green
    exit 0
}
catch {
    Write-Error ("P2000 Python bootstrap: " + $_.Exception.Message)
    exit 1
}
