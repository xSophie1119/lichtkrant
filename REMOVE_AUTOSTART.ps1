$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'P2000 Monitor.lnk'
if (Test-Path $link) { Remove-Item $link -Force; Write-Host 'Autostart verwijderd.' -ForegroundColor Green } else { Write-Host 'Er was geen P2000 Monitor-autostart ingesteld.' }
Read-Host 'Druk op Enter om te sluiten'
