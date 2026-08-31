@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ---------------------------------------------------------------------------
rem P2000 Monitor v4.1.1 - Python bootstrap
rem Primary path uses only Windows curl.exe + tar.exe + certutil.exe.
rem No Python installer, registry changes, PATH changes or administrator rights.
rem PowerShell is only a last-resort fallback on older Windows installations.
rem ---------------------------------------------------------------------------

set "P2000_RUNTIME=%LOCALAPPDATA%\P2000-Monitor\Runtime"
set "P2000_LOGDIR=%LOCALAPPDATA%\P2000-Monitor\Logs"
set "P2000_PYDIR=%P2000_RUNTIME%\Python313"
set "P2000_PY=%P2000_PYDIR%\python.exe"
set "P2000_BOOTLOG=%P2000_LOGDIR%\python-bootstrap.log"
set "PYVER=3.13.15"

if not exist "%P2000_LOGDIR%" mkdir "%P2000_LOGDIR%" >nul 2>&1
if not exist "%P2000_RUNTIME%" mkdir "%P2000_RUNTIME%" >nul 2>&1

call :check_python
if not errorlevel 1 goto :ready

>"%P2000_BOOTLOG%" echo ==== P2000 Python bootstrap %date% %time% ====
>>"%P2000_BOOTLOG%" echo Runtime: %P2000_PYDIR%
>>"%P2000_BOOTLOG%" echo PROCESSOR_ARCHITECTURE=%PROCESSOR_ARCHITECTURE%
>>"%P2000_BOOTLOG%" echo PROCESSOR_ARCHITEW6432=%PROCESSOR_ARCHITEW6432%

echo [P2000] Eigen Python-runtime ontbreekt. Eerste installatie starten...
echo [P2000] Dit wijzigt GEEN Windows PATH en vereist GEEN administrator.

call :install_embedded >>"%P2000_BOOTLOG%" 2>&1
if not errorlevel 1 goto :verify_after_install

rem Last-resort compatibility fallback. The error remains logged and visible.
echo [P2000] Standaard Windows downloadroute niet beschikbaar; noodfallback proberen...
>>"%P2000_BOOTLOG%" echo Primary bootstrap failed with errorlevel !errorlevel!; trying PowerShell fallback.
where powershell.exe >nul 2>&1
if errorlevel 1 goto :failed
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0ENSURE_PYTHON.ps1" >>"%P2000_BOOTLOG%" 2>&1
if errorlevel 1 goto :failed

:verify_after_install
call :check_python
if errorlevel 1 goto :failed

:ready
endlocal & set "P2000_PYTHON=%P2000_PY%" & set "P2000_BOOTSTRAP_LOG=%P2000_BOOTLOG%"
exit /b 0

:check_python
if not exist "%P2000_PY%" exit /b 1
"%P2000_PY%" -c "import sys,sqlite3,urllib.request; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
exit /b %errorlevel%

:install_embedded
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "ARCH=%PROCESSOR_ARCHITEW6432%"

if /I "!ARCH!"=="AMD64" (
  set "PKGARCH=amd64"
  set "EXPECTED_SHA=d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
) else if /I "!ARCH!"=="ARM64" (
  set "PKGARCH=arm64"
  set "EXPECTED_SHA=cd992cbfb33be433ff20f150691595efb2862e56f4f1bec684c6077d4775af8e"
) else (
  echo Unsupported Windows architecture: !ARCH!
  exit /b 40
)

set "PYZIP=%TEMP%\p2000-python-%PYVER%-embed-!PKGARCH!.zip"
set "PYPART=!PYZIP!.part"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-!PKGARCH!.zip"

echo Download URL: !PYURL!
where curl.exe >nul 2>&1
if errorlevel 1 (
  echo curl.exe not found.
  exit /b 41
)
where tar.exe >nul 2>&1
if errorlevel 1 (
  echo tar.exe not found.
  exit /b 42
)
where certutil.exe >nul 2>&1
if errorlevel 1 (
  echo certutil.exe not found.
  exit /b 43
)

if exist "!PYPART!" del /q "!PYPART!" >nul 2>&1
if exist "!PYZIP!" del /q "!PYZIP!" >nul 2>&1

curl.exe --fail --location --silent --show-error --retry 3 --retry-delay 2 --connect-timeout 15 --max-time 180 -o "!PYPART!" "!PYURL!"
if errorlevel 1 (
  echo curl download failed.
  exit /b 44
)
move /y "!PYPART!" "!PYZIP!" >nul
if errorlevel 1 exit /b 45

for %%F in ("!PYZIP!") do set "PYBYTES=%%~zF"
echo Downloaded !PYBYTES! bytes.
if !PYBYTES! LSS 8000000 (
  echo Download is too small/incomplete.
  exit /b 46
)

set "ACTUAL_SHA="
for /f "skip=1 tokens=* delims=" %%H in ('certutil.exe -hashfile "!PYZIP!" SHA256 2^>nul') do if not defined ACTUAL_SHA set "ACTUAL_SHA=%%H"
set "ACTUAL_SHA=!ACTUAL_SHA: =!"
echo Expected SHA256: !EXPECTED_SHA!
echo Actual   SHA256: !ACTUAL_SHA!
if /I not "!ACTUAL_SHA!"=="!EXPECTED_SHA!" (
  echo SHA256 mismatch; refusing runtime.
  del /q "!PYZIP!" >nul 2>&1
  exit /b 47
)

if exist "%P2000_PYDIR%" rmdir /s /q "%P2000_PYDIR%" >nul 2>&1
mkdir "%P2000_PYDIR%" >nul 2>&1
if errorlevel 1 exit /b 48

tar.exe -xf "!PYZIP!" -C "%P2000_PYDIR%"
set "TAR_RC=!errorlevel!"
del /q "!PYZIP!" >nul 2>&1
if not "!TAR_RC!"=="0" (
  echo tar extraction failed with !TAR_RC!.
  exit /b 49
)
if not exist "%P2000_PY%" (
  echo Extracted runtime has no python.exe.
  exit /b 50
)

rem Keep the official embedded isolation model. The backend adds its own vendor
rem directory explicitly, so pip/site installation is not needed.
"%P2000_PY%" -c "import sys,sqlite3,urllib.request; print(sys.version)"
if errorlevel 1 exit /b 51

echo Embedded Python runtime ready.
exit /b 0

:failed
echo.
echo ================================================================
echo [FOUT] De P2000 Python-runtime kon niet worden klaargezet.
echo ================================================================
echo.
echo Er is niets aan PATH of andere Python-installaties gewijzigd.
echo Het volledige log staat hier:
echo   %P2000_BOOTLOG%
echo.
echo Laat dit bestand zien als je hulp nodig hebt.
if /I not "%~1"=="/nopause" pause
endlocal
exit /b 1
