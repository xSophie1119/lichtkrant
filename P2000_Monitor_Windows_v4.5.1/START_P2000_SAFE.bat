@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title P2000 Monitor - VEILIGE MODUS
if not exist "%~dp0backend\server.py" goto :bad
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :bad
set "P2000_SAFE_MODE=1"
echo P2000 Monitor VEILIGE MODUS
 echo - geen feedpoller
 echo - geen automatische GitHub-update
 echo - geen TTS
 echo - geen kiosk; beheer opent normaal
start "P2000 Safe Backend" /min "%P2000_PYTHON%" "%~dp0backend\server.py" --safe-mode
powershell.exe -NoProfile -Command "for($i=0;$i -lt 40;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/api/runtime -TimeoutSec 1|Out-Null;exit 0}catch{Start-Sleep -Milliseconds 250}};exit 1" >nul 2>&1
start "" "http://127.0.0.1:8765/control.html"
exit /b 0
:bad
echo Veilige modus kon niet starten.
pause
exit /b 1
