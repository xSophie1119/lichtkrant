param([switch]$Purge)
$ErrorActionPreference='SilentlyContinue';$Dest=Join-Path $env:LOCALAPPDATA 'P2000-Monitor\App'
if(Test-Path (Join-Path $Dest 'STOP_P2000.bat')){& (Join-Path $Dest 'STOP_P2000.bat')}
if(Test-Path (Join-Path $Dest 'REMOVE_AUTOSTART.bat')){& (Join-Path $Dest 'REMOVE_AUTOSTART.bat')}
Remove-Item (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\P2000 Monitor.lnk') -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'P2000 Monitor.lnk') -Force
if($Purge){Remove-Item $Dest -Recurse -Force;Write-Host 'P2000 Monitor inclusief data verwijderd.';exit}
$backup=Join-Path $env:LOCALAPPDATA ('P2000-Monitor\UserdataBackup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'));New-Item -ItemType Directory -Force $backup|Out-Null
if(Test-Path (Join-Path $Dest 'data')){Copy-Item (Join-Path $Dest 'data') (Join-Path $backup 'data') -Recurse -Force}
if(Test-Path (Join-Path $Dest 'config\config.json')){New-Item -ItemType Directory -Force (Join-Path $backup 'config')|Out-Null;Copy-Item (Join-Path $Dest 'config\config.json') (Join-Path $backup 'config\config.json') -Force}
Remove-Item $Dest -Recurse -Force;Write-Host "Verwijderd. Instellingenbackup: $backup"
