@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0backend\server.py" goto :fatal
if not exist "%~dp0tools\startup_guard.py" goto :fatal
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 exit /b 1
set "P2000_VERSION=4.5.7"
if exist "%~dp0VERSION" set /p P2000_VERSION=<"%~dp0VERSION"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1
echo [1/3] Recovery + geserialiseerde backendstart...
"%P2000_PYTHON%" "%~dp0tools\startup_guard.py" >>"%P2000_LOGDIR%\startup.log" 2>&1
if errorlevel 1 goto :backend_error
echo [2/3] Backend semantisch gezond.
set "P2000_KIOSK_URL=http://127.0.0.1:8765/?v=%P2000_VERSION%"
set "P2000_WINDOW_POSITION=0,0"
set "P2000_WINDOW_SIZE=1920,1080"
set "P2000_DISPLAY_ENV=%TEMP%\p2000-display-%RANDOM%-%RANDOM%.bat"
"%P2000_PYTHON%" "%~dp0tools\kiosk_display.py" > "%P2000_DISPLAY_ENV%" 2>>"%P2000_LOGDIR%\startup.log"
if exist "%P2000_DISPLAY_ENV%" call "%P2000_DISPLAY_ENV%"
if exist "%P2000_DISPLAY_ENV%" del /q "%P2000_DISPLAY_ENV%" >nul 2>&1
echo [3/3] Lichtkrant openen...
"%P2000_PYTHON%" "%~dp0tools\windows_desktop.py" launch --url "%P2000_KIOSK_URL%" --position "%P2000_WINDOW_POSITION%" --size "%P2000_WINDOW_SIZE%" --browser "%P2000_BROWSER%" >>"%P2000_LOGDIR%\startup.log" 2>&1
exit /b %errorlevel%
:backend_error
echo [FOUT] Startup/recovery mislukt. Zie %P2000_LOGDIR%\startup.log
pause
exit /b 1
:fatal
echo [FOUT] P2000 Monitor is niet volledig uitgepakt.
pause
exit /b 1
