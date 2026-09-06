@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo P2000 Monitor stoppen...
call "%~dp0ENSURE_PYTHON.bat" /nopause >nul 2>&1
if not defined P2000_PYTHON goto :no_python

echo [1/4] Supervisor(s) stoppen...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop-supervisors >nul 2>&1

echo [2/4] Backend(s) stoppen...
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop >nul 2>&1

echo [3/4] Tweede backendcontrole...
timeout /t 1 /nobreak >nul
"%P2000_PYTHON%" "%~dp0tools\runtime_probe.py" --stop >nul 2>&1

echo [4/4] Dedicated lichtkrant-kiosk sluiten...
"%P2000_PYTHON%" "%~dp0tools\windows_desktop.py" stop-kiosk >nul 2>&1

echo Klaar.
timeout /t 2 /nobreak >nul
exit /b 0

:no_python
echo [WAARSCHUWING] Python-runtime is niet beschikbaar.
echo Uit veiligheid worden geen willekeurige python.exe-processen gestopt.
where powershell.exe >nul 2>&1 && powershell.exe -NoLogo -NoProfile -Command "Write-Host 'Sluit P2000 na herstel van ENSURE_PYTHON.bat opnieuw af.'" >nul 2>&1
exit /b 2
