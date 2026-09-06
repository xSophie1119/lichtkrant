@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "P2000_VERSION=onbekend"
if exist "%~dp0VERSION" set /p P2000_VERSION=<"%~dp0VERSION"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
title P2000 Monitor v%P2000_VERSION% - debug start

echo ================================================================
echo P2000 Monitor v%P2000_VERSION% - DEBUG START
echo Dit venster blijft altijd open.
echo ================================================================
echo.
call "%~dp0START_P2000.bat"
set "RC=%errorlevel%"
echo.
echo START_P2000.bat eindigde met exitcode %RC%.
echo.
for %%L in (startup.log backend.log browser.log python-bootstrap.log) do (
  echo ---------------- %%L ----------------
  if exist "%P2000_LOGDIR%\%%L" (
    powershell.exe -NoLogo -NoProfile -NonInteractive -Command "Get-Content -LiteralPath $env:P2000_LOGDIR'\%%L' -Tail 60" 2>nul
  ) else (
    echo [geen logbestand]
  )
  echo.
)
pause
exit /b %RC%
