@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ENSURE_PYTHON.bat" /nopause
if errorlevel 1 exit /b 1
"%P2000_PYTHON%" -u "%~dp0tools\run_tests.py"
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" pause
exit /b %RC%
