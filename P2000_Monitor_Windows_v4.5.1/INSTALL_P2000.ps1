param([switch]$NoStart)
$ErrorActionPreference='Stop'
$Source=(Resolve-Path $PSScriptRoot).Path
$Dest=Join-Path $env:LOCALAPPDATA 'P2000-Monitor\App'
$version=(Get-Content (Join-Path $Source 'VERSION') -Raw).Trim()
Write-Host "P2000 Monitor v$version installeren naar $Dest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$save=Join-Path $env:TEMP ('p2000-install-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Force $save|Out-Null
try {
  if(Test-Path (Join-Path $Dest 'config\config.json')){New-Item -ItemType Directory -Force (Join-Path $save 'config')|Out-Null;Copy-Item (Join-Path $Dest 'config\config.json') (Join-Path $save 'config\config.json') -Force}
  if(Test-Path (Join-Path $Dest 'data')){Copy-Item (Join-Path $Dest 'data') (Join-Path $save 'data') -Recurse -Force}
  if($Source -ne $Dest){
    Get-ChildItem $Dest -Force | Where-Object {$_.Name -notin @('data','config')} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $Source -Force | Where-Object {$_.Name -notin @('data','config')} | Copy-Item -Destination $Dest -Recurse -Force
    New-Item -ItemType Directory -Force (Join-Path $Dest 'config')|Out-Null
    if(Test-Path (Join-Path $Source 'config\config.json')){Copy-Item (Join-Path $Source 'config\config.json') (Join-Path $Dest 'config\config.json') -Force}
    if(Test-Path (Join-Path $save 'config\config.json')){Copy-Item (Join-Path $save 'config\config.json') (Join-Path $Dest 'config\config.json') -Force}
    if(Test-Path (Join-Path $save 'data')){Remove-Item (Join-Path $Dest 'data') -Recurse -Force -ErrorAction SilentlyContinue;Copy-Item (Join-Path $save 'data') (Join-Path $Dest 'data') -Recurse -Force}
  }
  & (Join-Path $Dest 'ENSURE_PYTHON.bat') /nopause
  & (Join-Path $Dest 'INSTALL_AUTOSTART.bat')
  $ws=New-Object -ComObject WScript.Shell
  $programs=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs';$lnk=$ws.CreateShortcut((Join-Path $programs 'P2000 Monitor.lnk'));$lnk.TargetPath=(Join-Path $Dest 'START_P2000.bat');$lnk.WorkingDirectory=$Dest;$lnk.IconLocation="$env:SystemRoot\System32\shell32.dll,167";$lnk.Save()
  $desktop=[Environment]::GetFolderPath('Desktop');$dlnk=$ws.CreateShortcut((Join-Path $desktop 'P2000 Monitor.lnk'));$dlnk.TargetPath=(Join-Path $Dest 'START_P2000.bat');$dlnk.WorkingDirectory=$Dest;$dlnk.IconLocation="$env:SystemRoot\System32\shell32.dll,167";$dlnk.Save()
  Write-Host '[OK] Geïnstalleerd. Bestaande config en data zijn behouden.' -ForegroundColor Green
  if(-not $NoStart){Start-Process (Join-Path $Dest 'START_P2000.bat')}
} finally {Remove-Item $save -Recurse -Force -ErrorAction SilentlyContinue}
