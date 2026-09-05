@echo off
setlocal
cd /d "%~dp0"
title P2000 Monitor Installer
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_P2000.ps1"
if errorlevel 1 (
 echo.
 echo [FOUT] Installatie mislukt. Zie de melding hierboven.
 pause
 exit /b 1
)
echo.
echo Installatie gereed.
timeout /t 3 /nobreak >nul
