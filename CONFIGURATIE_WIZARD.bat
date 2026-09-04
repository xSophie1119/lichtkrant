@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Detect the common Windows Explorer mistake: running a single BAT directly
rem from a compressed ZIP instead of extracting the complete application.
if not exist "%~dp0backend\server.py" goto :fatal_extract
if not exist "%~dp0frontend\index.html" goto :fatal_extract
if not exist "%~dp0ENSURE_PYTHON.bat" goto :fatal_extract
title P2000 Monitor - configuratiewizard
set "P2000_VERSION=4.4.5"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1

echo [1/3] Eigen P2000 Python-runtime controleren...
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :fatal_python

echo [2/3] Backend controleren...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --kill-stale >>"%P2000_LOGDIR%\startup.log" 2>&1
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" >nul 2>&1
if errorlevel 1 (
  >"%P2000_LOGDIR%\backend.log" echo ==== P2000 backend gestart %date% %time% ====
  start "P2000 Monitor Backend" /min "%~dp0RUN_BACKEND.bat"
)
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --wait 15 >nul 2>&1
if errorlevel 1 goto :fatal_backend

echo [3/3] Configuratiewizard openen...
start "" "http://127.0.0.1:8765/setup.html?edit=1"
timeout /t 2 /nobreak >nul
exit /b 0

:fatal_python
echo.
echo [FOUT] De Python-runtime kon niet worden klaargezet.
echo Log: %LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log
pause
exit /b 1

:fatal_backend
echo.
echo [FOUT] De backend kon niet worden gestart.
echo Log: %P2000_LOGDIR%\backend.log
if exist "%P2000_LOGDIR%\backend.log" type "%P2000_LOGDIR%\backend.log"
pause
exit /b 1

:fatal_extract
echo.
echo ================================================================
echo [FOUT] De P2000 Monitor is niet volledig uitgepakt.
echo ================================================================
echo.
echo Start de BAT-bestanden NIET rechtstreeks vanuit de ZIP.
echo Kies in Verkenner eerst: Alles uitpakken / Extract all.
echo Start daarna START_P2000.bat vanuit de uitgepakte map.
echo.
pause
exit /b 1
