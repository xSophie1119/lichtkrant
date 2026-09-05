@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo P2000 Monitor stoppen...

echo [P2000] Supervisor stoppen...
set "P2000_ROOT=%~dp0"
call "%~dp0ENSURE_PYTHON.bat" /nopause >nul 2>&1
if defined P2000_PYTHON (
  "%P2000_PYTHON%" "%~dp0tools\supervisor.py" --stop >nul 2>&1
  if errorlevel 1 call :fallback_stop_supervisor
) else (
  call :fallback_stop_supervisor
)

echo [P2000] Lichtkrant-kiosk sluiten...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$procs=Get-CimInstance Win32_Process ^| Where-Object { $_.CommandLine -and $_.CommandLine -like '*P2000-Monitor\BrowserProfile*' -and $_.CommandLine -like '*127.0.0.1:8765*' }; foreach($p in $procs){ try { Invoke-CimMethod -InputObject $p -MethodName Terminate ^| Out-Null } catch {} }" >nul 2>&1

echo [P2000] Backend stoppen...
if defined P2000_PYTHON (
  "%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop >nul 2>&1
  if errorlevel 1 call :fallback_stop_backend
) else (
  call :fallback_stop_backend
)

echo Klaar.
timeout /t 2 /nobreak >nul
exit /b 0

:fallback_stop_supervisor
where powershell.exe >nul 2>&1 || exit /b 1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$root=[IO.Path]::GetFullPath($env:P2000_ROOT); Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine -like ('*'+$root+'tools\supervisor.py*') } ^| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b %errorlevel%

:fallback_stop_backend
where powershell.exe >nul 2>&1 || exit /b 1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$root=[IO.Path]::GetFullPath($env:P2000_ROOT); Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine -match 'backend[\\/]server\.py' -and $_.CommandLine -like ('*'+$root+'*') } ^| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b %errorlevel%
