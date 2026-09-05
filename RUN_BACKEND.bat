@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 exit /b 1
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1
"%P2000_PYTHON%" "%~dp0backend\server.py" >>"%P2000_LOGDIR%\backend.log" 2>&1
exit /b %errorlevel%
