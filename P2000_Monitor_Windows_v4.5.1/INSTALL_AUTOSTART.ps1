$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'START_P2000.bat'
$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'P2000 Monitor.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($link)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 7
$shortcut.Description = 'P2000 Monitor monitor'
$shortcut.Save()
Write-Host "Autostart geinstalleerd: $link" -ForegroundColor Green
Write-Host 'De monitor start voortaan na aanmelden bij Windows.'
Read-Host 'Druk op Enter om te sluiten'
