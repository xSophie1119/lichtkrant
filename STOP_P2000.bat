@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo P2000 Monitor stoppen...

echo [P2000] Lichtkrant-kiosk sluiten...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$procs=Get-CimInstance Win32_Process ^| Where-Object { $_.CommandLine -and $_.CommandLine -like '*P2000-Monitor\BrowserProfile*' -and $_.CommandLine -like '*127.0.0.1:8765*' }; foreach($p in $procs){ try { Invoke-CimMethod -InputObject $p -MethodName Terminate ^| Out-Null } catch {} }" >nul 2>&1

echo [P2000] Backend stoppen...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$root=[IO.Path]::GetFullPath('%~dp0'); Get-CimInstance Win32_Process ^| Where-Object { $_.CommandLine -and $_.CommandLine -match 'backend[\\/]server\.py' -and $_.CommandLine -like ('*'+$root+'*') } ^| ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate ^| Out-Null }" >nul 2>&1

echo Klaar.
timeout /t 2 /nobreak >nul
