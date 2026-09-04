@echo off
setlocal
cd /d "%~dp0"
call "%~dp0ENSURE_PYTHON.bat"
if errorlevel 1 exit /b %errorlevel%
"%P2000_PYTHON%" "%~dp0tools\run_tests.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
