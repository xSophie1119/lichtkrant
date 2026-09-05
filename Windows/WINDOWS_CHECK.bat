@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title P2000 Monitor - Windows-check

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo ================================================================
  echo [LET OP] Windows PowerShell is niet beschikbaar.
  echo De normale P2000-start kan vanaf v4.1.0 alsnog werken.
  echo Gebruik START_P2000_DEBUG.bat voor een startdiagnose.
  echo ================================================================
  echo.
  if exist "%LOCALAPPDATA%\P2000-Monitor\Runtime\Python313\python.exe" (
    echo Python-runtime: aanwezig
  ) else (
    echo Python-runtime: nog niet aanwezig
  )
  pause
  exit /b 0
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0WINDOWS_CHECK.ps1"
if errorlevel 1 (
  echo.
  echo [LET OP] De uitgebreide PowerShell-diagnose gaf een fout.
  echo Dit betekent vanaf v4.1.0 NIET automatisch dat START_P2000.bat stuk is.
  echo Probeer START_P2000_DEBUG.bat voor de normale startroute.
  pause
)
