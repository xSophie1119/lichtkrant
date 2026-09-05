$ErrorActionPreference='SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host '=== P2000 Monitor Windows-check ===' -ForegroundColor Cyan

$runtimePython = Join-Path $env:LOCALAPPDATA 'P2000-Monitor\Runtime\Python313\python.exe'
if (Test-Path -LiteralPath $runtimePython) {
  try {
    $pv = (& $runtimePython --version 2>&1).ToString().Trim()
    Write-Host ('P2000 Python-runtime: OK - ' + $pv) -ForegroundColor Green
    Write-Host ('  ' + $runtimePython) -ForegroundColor DarkGray
  } catch { Write-Host 'P2000 Python-runtime: beschadigd; START_P2000.bat herstelt hem automatisch.' -ForegroundColor Red }
} else {
  Write-Host 'P2000 Python-runtime: nog niet aanwezig; START_P2000.bat zet Python 3.13 embedded automatisch klaar.' -ForegroundColor Yellow
}

$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe","${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($edge) { Write-Host ('Edge kiosk: OK - ' + $edge) -ForegroundColor Green } else { Write-Host 'Edge kiosk: niet gevonden.' -ForegroundColor Yellow }
$chrome = @("${env:ProgramFiles}\Google\Chrome\Application\chrome.exe","${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($chrome) { Write-Host ('Chrome kiosk: OK - ' + $chrome) -ForegroundColor Green } else { Write-Host 'Chrome kiosk: niet gevonden (optioneel).' -ForegroundColor Yellow }

try {
  Add-Type -AssemblyName System.Speech
  $synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
  $voices=@($synth.GetInstalledVoices() | Where-Object { $_.Enabled })
  $nl=@($voices | Where-Object { $_.VoiceInfo.Culture.Name -like 'nl-*' })
  if($nl.Count -gt 0){ Write-Host ('Nederlandse lokale TTS: OK - ' + $nl[0].VoiceInfo.Name) -ForegroundColor Green }
  elseif($voices.Count -gt 0){ Write-Host 'Nederlandse lokale TTS: GEEN NL-STEM. Start INSTALL_NEDERLANDSE_STEM.bat.' -ForegroundColor Yellow }
  else { Write-Host 'Lokale TTS: geen Windows-spraakstem gevonden' -ForegroundColor Red }
  $synth.Dispose()
} catch { Write-Host ('Lokale TTS: FOUT - ' + $_.Exception.Message) -ForegroundColor Red }

$configPath = Join-Path $root 'config\config.json'
$config = $null
try { if(Test-Path $configPath){ $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json } } catch {}
if($config -and $config.setup_complete){
  Write-Host ('Installatieprofiel: OK - ' + $config.display_name + ' / ' + $config.standplaats) -ForegroundColor Green
} else {
  Write-Host 'Installatieprofiel: nog niet afgerond; eerste start opent de wizard.' -ForegroundColor Yellow
}

$backendOnline=$false
try {
  $r=Invoke-RestMethod -TimeoutSec 2 'http://127.0.0.1:8765/api/runtime'
  $backendOnline=$true
  Write-Host ('Backend: ONLINE v' + $r.version) -ForegroundColor Green
} catch { Write-Host 'Backend: offline (start START_P2000.bat of START_BACKEND.bat)' -ForegroundColor Yellow }

if($backendOnline){
  try {
    $vs=Invoke-RestMethod -TimeoutSec 2 'http://127.0.0.1:8765/api/vehicles/status'
    $st=$vs.status
    $regions=@($st.selected_regions)
    if($regions.Count -eq 0){
      Write-Host 'Voertuigcache: geen brandweerregio geselecteerd.' -ForegroundColor Yellow
    } elseif($st.running){
      Write-Host ('Voertuigcache: achtergrondupdate actief voor ' + $regions.Count + ' regio(s).') -ForegroundColor Cyan
    } else {
      Write-Host ('Voertuigcache: ' + $st.count + ' exacte roepnummers geladen voor ' + $regions.Count + ' regio(s).') -ForegroundColor Green
      if($st.last_error){ Write-Host ('  Laatste bronfout: ' + $st.last_error) -ForegroundColor Yellow }
    }
  } catch { Write-Host 'Voertuigcache: status niet leesbaar; nummerplan-fallback blijft beschikbaar.' -ForegroundColor Yellow }
}

$urls=@()
if($config -and $config.feed_urls){ $urls=@($config.feed_urls) }
if($urls.Count -eq 0){
  $urls=@('https://alarmeringen.nl/feeds/discipline/brandweer.rss')
  Write-Host 'RSS internettest: configuratie heeft nog geen feeds; landelijke brandweerfeed wordt als verbindingstest gebruikt.'
} else {
  Write-Host ('RSS internettest: maximaal 5 van ' + $urls.Count + ' ingestelde bron(nen).')
  $urls=@($urls | Select-Object -First 5)
}
foreach($u in $urls){
  try{
    $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Headers @{'User-Agent'='P2000-Monitor-WindowsCheck'} $u
    Write-Host ('  OK   ' + $u) -ForegroundColor Green
  }catch{
    Write-Host ('  FOUT ' + $u + ' - ' + $_.Exception.Message) -ForegroundColor Red
  }
}

Read-Host 'Druk op Enter om te sluiten'
