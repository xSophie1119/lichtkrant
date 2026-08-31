@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Detect the common Windows Explorer mistake: running a single BAT directly
rem from a compressed ZIP instead of extracting the complete application.
if not exist "%~dp0backend\server.py" goto :fatal_extract
if not exist "%~dp0frontend\index.html" goto :fatal_extract
if not exist "%~dp0ENSURE_PYTHON.bat" goto :fatal_extract
title P2000 Monitor - starten
set "P2000_VERSION=4.1.1"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1

echo [1/4] P2000 Python-runtime controleren...
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 goto :fatal_python

echo [2/4] Lokale backend controleren...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --kill-stale >>"%P2000_LOGDIR%\startup.log" 2>&1
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" >nul 2>&1
if errorlevel 1 (
  echo [P2000] Backend starten...
  >"%P2000_LOGDIR%\backend.log" echo ==== P2000 backend gestart %date% %time% ====
  start "P2000 Monitor Backend" /min "%~dp0RUN_BACKEND.bat"
)

echo [3/4] Wachten op http://127.0.0.1:8765/ ...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --version "%P2000_VERSION%" --wait 15 >nul 2>&1
if errorlevel 1 goto :fatal_backend

echo [4/4] Lichtkrant openen...
set "P2000_WINDOW_POSITION=0,0"
set "P2000_WINDOW_SIZE=1920,1080"
set "P2000_DISPLAY_DEVICE=primary"
set "P2000_DISPLAY_ENV=%TEMP%\p2000-display-%RANDOM%-%RANDOM%.bat"
"%P2000_PYTHON%" "%~dp0tools\kiosk_display.py" > "%P2000_DISPLAY_ENV%" 2>>"%P2000_LOGDIR%\startup.log"
if exist "%P2000_DISPLAY_ENV%" call "%P2000_DISPLAY_ENV%"
if exist "%P2000_DISPLAY_ENV%" del /q "%P2000_DISPLAY_ENV%" >nul 2>&1
echo [P2000] Doelscherm: %P2000_DISPLAY_DEVICE%  positie %P2000_WINDOW_POSITION%  formaat %P2000_WINDOW_SIZE%
set "EDGE_X86=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set "EDGE_X64=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
set "CHROME_X64=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "CHROME_X86=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if /I "%P2000_BROWSER%"=="chrome" (
  call :close_other_kiosks "BrowserProfile-Chrome"
  goto :launch_chrome
)
if /I "%P2000_BROWSER%"=="edge" (
  call :close_other_kiosks "BrowserProfile-Edge"
  goto :launch_edge
)

call :any_kiosk_running
if not errorlevel 1 (
  echo [P2000] Er draait al een P2000 lichtkrant-kiosk.
  timeout /t 2 /nobreak >nul
  exit /b 0
)

if exist "%EDGE_X86%" goto :launch_edge
if exist "%EDGE_X64%" goto :launch_edge
if exist "%CHROME_X64%" goto :launch_chrome
if exist "%CHROME_X86%" goto :launch_chrome

echo [P2000] Geen Edge/Chrome gevonden. Standaardbrowser openen.
echo [LET OP] Bij autoplay-blokkade verschijnt 'OMROEP INSCHAKELEN'.
start "" "http://127.0.0.1:8765/"
timeout /t 2 /nobreak >nul
exit /b 0

:launch_edge
set "P2000_BROWSER_PROFILE=%LOCALAPPDATA%\P2000-Monitor\BrowserProfile-Edge"
if not exist "%P2000_BROWSER_PROFILE%" mkdir "%P2000_BROWSER_PROFILE%" >nul 2>&1
call :kiosk_running "%P2000_BROWSER_PROFILE%"
if not errorlevel 1 (
  echo [P2000] Edge lichtkrant-kiosk draait al.
  timeout /t 2 /nobreak >nul
  exit /b 0
)
if exist "%EDGE_X86%" set "P2000_BROWSER_EXE=%EDGE_X86%"
if exist "%EDGE_X64%" set "P2000_BROWSER_EXE=%EDGE_X64%"
if not defined P2000_BROWSER_EXE goto :launch_chrome
echo [P2000] Edge fullscreen openen...
start "" "%P2000_BROWSER_EXE%" --window-position=%P2000_WINDOW_POSITION% --window-size=%P2000_WINDOW_SIZE% --kiosk "http://127.0.0.1:8765/" --edge-kiosk-type=fullscreen --no-first-run --no-default-browser-check --noerrdialogs --disable-session-crashed-bubble --user-data-dir="%P2000_BROWSER_PROFILE%" --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows
timeout /t 2 /nobreak >nul
exit /b 0

:launch_chrome
set "P2000_BROWSER_PROFILE=%LOCALAPPDATA%\P2000-Monitor\BrowserProfile-Chrome"
if not exist "%P2000_BROWSER_PROFILE%" mkdir "%P2000_BROWSER_PROFILE%" >nul 2>&1
call :kiosk_running "%P2000_BROWSER_PROFILE%"
if not errorlevel 1 (
  echo [P2000] Chrome lichtkrant-kiosk draait al.
  timeout /t 2 /nobreak >nul
  exit /b 0
)
if exist "%CHROME_X64%" set "P2000_BROWSER_EXE=%CHROME_X64%"
if exist "%CHROME_X86%" set "P2000_BROWSER_EXE=%CHROME_X86%"
if not defined P2000_BROWSER_EXE goto :fatal_browser
echo [P2000] Chrome fullscreen openen...
start "" "%P2000_BROWSER_EXE%" --window-position=%P2000_WINDOW_POSITION% --window-size=%P2000_WINDOW_SIZE% --kiosk "http://127.0.0.1:8765/" --no-first-run --no-default-browser-check --noerrdialogs --disable-session-crashed-bubble --user-data-dir="%P2000_BROWSER_PROFILE%" --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows
timeout /t 2 /nobreak >nul
exit /b 0

:any_kiosk_running
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine -like '*P2000-Monitor\BrowserProfile*' -and $_.CommandLine -like '*127.0.0.1:8765*' }; if($p){exit 0}else{exit 1}" >nul 2>&1
exit /b %errorlevel%

:close_other_kiosks
set "P2000_WANTED_PROFILE=%~1"
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$wanted='%P2000_WANTED_PROFILE%'; $p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine -like '*P2000-Monitor\BrowserProfile*' -and $_.CommandLine -like '*127.0.0.1:8765*' -and $_.CommandLine -notlike ('*'+$wanted+'*') }; foreach($x in $p){try{Invoke-CimMethod -InputObject $x -MethodName Terminate -ErrorAction SilentlyContinue ^| Out-Null}catch{}}" >nul 2>&1
exit /b 0

:kiosk_running
set "P2000_CHECK_PROFILE=%~1"
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$profile=[IO.Path]::GetFullPath('%P2000_CHECK_PROFILE%'); $p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine -like ('*'+$profile+'*') -and $_.CommandLine -like '*127.0.0.1:8765*' }; if($p){exit 0}else{exit 1}" >nul 2>&1
exit /b %errorlevel%

:fatal_python
echo.
echo ================================================================
echo [FOUT] Python-runtime kon niet worden gestart.
echo ================================================================
echo Logbestand:
echo   %LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log
echo.
echo Dit venster blijft open zodat de fout niet meer na 2 seconden verdwijnt.
pause
exit /b 1

:fatal_backend
echo.
echo ================================================================
echo [FOUT] De P2000-backend start niet of reageert niet.
echo ================================================================
echo Backendlog:
echo   %P2000_LOGDIR%\backend.log
echo.
if exist "%P2000_LOGDIR%\backend.log" type "%P2000_LOGDIR%\backend.log"
echo.
pause
exit /b 1

:fatal_browser
echo.
echo [FOUT] Chrome is niet gevonden en Edge kon niet worden gebruikt.
echo Open handmatig: http://127.0.0.1:8765/
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
