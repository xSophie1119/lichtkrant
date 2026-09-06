@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ENSURE_PYTHON.bat" /nopause >nul 2>&1
if not defined P2000_PYTHON exit /b 2
set "RC=0"
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop-supervisors || set "RC=1"
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop || set "RC=1"
timeout /t 1 /nobreak >nul
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop || set "RC=1"
"%P2000_PYTHON%" "%~dp0tools\windows_desktop.py" stop-kiosk || set "RC=1"
"%P2000_PYTHON%" "%~dp0tools\stop_verify.py" || set "RC=1"
if "%RC%"=="0" (echo Klaar.) else (echo [FOUT] Niet alle P2000-processen zijn gestopt.)
exit /b %RC%
