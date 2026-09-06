@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 exit /b 1
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1
set "P2000_BACKEND_LOG=%P2000_LOGDIR%\backend.log"
if exist "%P2000_BACKEND_LOG%" for %%F in ("%P2000_BACKEND_LOG%") do if %%~zF GTR 5242880 (
  if exist "%P2000_BACKEND_LOG%.1" del /q "%P2000_BACKEND_LOG%.1" >nul 2>&1
  move /Y "%P2000_BACKEND_LOG%" "%P2000_BACKEND_LOG%.1" >nul 2>&1
)
>>"%P2000_BACKEND_LOG%" echo.
>>"%P2000_BACKEND_LOG%" echo ==== P2000 backend gestart %date% %time% ====
>>"%P2000_BACKEND_LOG%" echo Python: %P2000_PYTHON%
>>"%P2000_BACKEND_LOG%" echo Server: %~dp0backend\server.py
"%P2000_PYTHON%" -u -X faulthandler "%~dp0backend\server.py" >>"%P2000_BACKEND_LOG%" 2>&1
set "P2000_BACKEND_RC=%errorlevel%"
>>"%P2000_BACKEND_LOG%" echo ==== Backend exitcode %P2000_BACKEND_RC% op %date% %time% ====
exit /b %P2000_BACKEND_RC%
