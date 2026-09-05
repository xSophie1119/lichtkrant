@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title P2000 Monitor - debug start

echo ================================================================
echo P2000 Monitor v4.2.0 - DEBUG START
echo Dit venster blijft altijd open.
echo ================================================================
echo.
call "%~dp0START_P2000.bat"
set "RC=%errorlevel%"
echo.
echo START_P2000.bat eindigde met exitcode %RC%.
echo Pythonlog: %LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log
echo Backendlog: %LOCALAPPDATA%\P2000-Monitor\Logs\backend.log
echo.
pause
exit /b %RC%
