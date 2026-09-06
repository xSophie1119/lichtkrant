@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0backend\server.py" goto :fatal_extract
if not exist "%~dp0frontend\index.html" goto :fatal_extract
if not exist "%~dp0ENSURE_PYTHON.bat" goto :fatal_extract
if not exist "%~dp0tools\runtime_probe.py" goto :fatal_extract
if not exist "%~dp0tools\windows_desktop.py" goto :fatal_extract

title P2000 Monitor - starten
set "P2000_VERSION=4.5.6"
if exist "%~dp0VERSION" set /p P2000_VERSION=<"%~dp0VERSION"
set "P2000_KIOSK_URL=http://127.0.0.1:8765/?v=%P2000_VERSION%"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1
>>"%P2000_LOGDIR%\startup.log" echo.
>>"%P2000_LOGDIR%\startup.log" echo ==== P2000 start v%P2000_VERSION% %date% %time% ====

echo [1/4] P2000 Python-runtime controleren...
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :fatal_python

echo [2/4] Oude instanties opruimen en backend controleren...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --kill-stale >>"%P2000_LOGDIR%\startup.log" 2>&1
if errorlevel 1 (
  "%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --describe-port >>"%P2000_LOGDIR%\startup.log" 2>&1
  goto :fatal_backend
)

"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" >nul 2>&1
if errorlevel 1 (
  call :start_backend_once
  "%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --wait 18 >nul 2>&1
  if errorlevel 1 (
    echo [HERSTEL] Eerste backendstart niet gezond; gecontroleerde herstart.>>"%P2000_LOGDIR%\startup.log"
    "%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --kill-stale >>"%P2000_LOGDIR%\startup.log" 2>&1
    if errorlevel 1 goto :fatal_backend
    call :start_backend_once
    "%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --wait 20 >nul 2>&1
    if errorlevel 1 goto :fatal_backend
  )
)
echo [3/4] Backend is bereikbaar op http://127.0.0.1:8765/

if /I not "%P2000_SUPERVISED%"=="1" (
  "%P2000_PYTHON%" "%~dp0tools\supervisor.py" --status >nul 2>&1
  if errorlevel 1 (
    "%P2000_PYTHON%" "%~dp0tools\supervisor.py" --stop >nul 2>&1
    start "P2000 Supervisor" /min "%P2000_PYTHON%" "%~dp0tools\supervisor.py"
  )
)

echo [4/4] Lichtkrant openen...
set "P2000_WINDOW_POSITION=0,0"
set "P2000_WINDOW_SIZE=1920,1080"
set "P2000_DISPLAY_DEVICE=primary"
set "P2000_DISPLAY_ENV=%TEMP%\p2000-display-%RANDOM%-%RANDOM%.bat"
"%P2000_PYTHON%" "%~dp0tools\kiosk_display.py" > "%P2000_DISPLAY_ENV%" 2>>"%P2000_LOGDIR%\startup.log"
if exist "%P2000_DISPLAY_ENV%" call "%P2000_DISPLAY_ENV%"
if exist "%P2000_DISPLAY_ENV%" del /q "%P2000_DISPLAY_ENV%" >nul 2>&1

echo [P2000] Doelscherm: %P2000_DISPLAY_DEVICE%  positie %P2000_WINDOW_POSITION%  formaat %P2000_WINDOW_SIZE%
"%P2000_PYTHON%" "%~dp0tools\windows_desktop.py" launch --url "%P2000_KIOSK_URL%" --position "%P2000_WINDOW_POSITION%" --size "%P2000_WINDOW_SIZE%" --browser "%P2000_BROWSER%" >>"%P2000_LOGDIR%\startup.log" 2>&1
if errorlevel 1 (
  echo [WAARSCHUWING] Dedicated kiosk kon niet worden bevestigd. Zie browser.log.
  echo [WAARSCHUWING] Dedicated kiosk kon niet worden bevestigd.>>"%P2000_LOGDIR%\startup.log"
)
exit /b 0

:start_backend_once
echo [P2000] Backend starten...
start "P2000 Monitor Backend" /min "%~dp0RUN_BACKEND.bat"
exit /b 0

:fatal_python
echo.
echo ================================================================
echo [FOUT] Python-runtime kon niet worden gestart.
echo ================================================================
echo Logbestand:
echo   %LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log
echo.
echo Dit venster blijft open zodat de fout zichtbaar blijft.
pause
exit /b 1

:fatal_backend
echo.
echo ================================================================
echo [FOUT] De P2000-backend start niet of reageert niet.
echo ================================================================
echo Backendlog:
echo   %P2000_LOGDIR%\backend.log
echo Startup-log:
echo   %P2000_LOGDIR%\startup.log
echo.
if exist "%P2000_LOGDIR%\backend.log" powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath $env:P2000_LOGDIR'\backend.log' -Tail 80" 2>nul
echo.
pause
exit /b 1

:fatal_extract
echo.
echo ================================================================
echo [FOUT] De P2000 Monitor is niet volledig uitgepakt.
echo ================================================================
echo Start de BAT-bestanden NIET rechtstreeks vanuit de ZIP.
echo Kies in Verkenner eerst: Alles uitpakken / Extract all.
echo Start daarna START_P2000.bat vanuit de uitgepakte map.
echo.
pause
exit /b 1
