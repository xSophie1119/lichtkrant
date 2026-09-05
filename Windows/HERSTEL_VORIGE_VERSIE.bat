@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title P2000 Monitor - vorige versie herstellen
if not exist "%~dp0tools\rollback_latest.py" goto :missing
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :python
"%P2000_PYTHON%" "%~dp0tools\rollback_latest.py"
if errorlevel 1 goto :failed
echo.
echo Vorige versie hersteld. P2000 Monitor opnieuw starten...
call "%~dp0START_P2000.bat"
exit /b 0
:missing
echo [FOUT] rollback-tool ontbreekt.
pause
exit /b 2
:python
echo [FOUT] P2000 Python-runtime is niet beschikbaar.
pause
exit /b 3
:failed
echo.
echo [FOUT] Vorige versie herstellen is mislukt.
echo Kijk in data\updates\backups of een backup aanwezig is.
pause
exit /b 4
