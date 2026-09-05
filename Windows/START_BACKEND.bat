@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Detect the common Windows Explorer mistake: running a single BAT directly
rem from a compressed ZIP instead of extracting the complete application.
if not exist "%~dp0backend\server.py" goto :fatal_extract
if not exist "%~dp0frontend\index.html" goto :fatal_extract
if not exist "%~dp0ENSURE_PYTHON.bat" goto :fatal_extract
title P2000 Monitor Backend - diagnose

echo [P2000] Python-runtime controleren...
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :fatal

echo [P2000] Backend starten met:
echo   %P2000_PYTHON%
echo.
"%P2000_PYTHON%" "%~dp0backend\server.py"
set "P2000_RC=%errorlevel%"
echo.
echo ================================================================
echo Backend is gestopt met exitcode %P2000_RC%.
echo Bekijk eventuele foutmelding hierboven.
echo ================================================================
pause
exit /b %P2000_RC%

:fatal
echo.
echo [FOUT] Python-runtime kon niet worden gestart.
echo Log: %LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log
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
