$ErrorActionPreference = 'Stop'
Write-Host "P2000 Monitor - Nederlandse TTS-stem" -ForegroundColor Cyan

function Get-DutchSpeechVoices {
    try {
        Add-Type -AssemblyName System.Speech
        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        try {
            return @($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'nl-*' } | ForEach-Object { $_.VoiceInfo })
        } finally { $s.Dispose() }
    } catch { return @() }
}

$voices = @(Get-DutchSpeechVoices)
if ($voices.Count -gt 0) {
    Write-Host "Nederlandse Windows-stem is al aanwezig:" -ForegroundColor Green
    $voices | ForEach-Object { Write-Host ("  - {0} ({1})" -f $_.Name, $_.Culture.Name) }
    Write-Host "`nJe hoeft niets te installeren. Herstart P2000 Monitor." -ForegroundColor Green
    exit 0
}

Write-Host "Geen Nederlandse System.Speech-stem gevonden." -ForegroundColor Yellow
Write-Host "Ik probeer Windows Text-to-Speech voor nl-NL te installeren..." -ForegroundColor Yellow

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Administratorrechten zijn nodig; Windows vraagt nu om toestemming." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'))
    exit 0
}

try {
    Add-WindowsCapability -Online -Name 'Language.TextToSpeech~~~nl-NL~0.0.1.0' | Out-Host
} catch {
    Write-Host ("Installatie via Windows Capability mislukte: " + $_.Exception.Message) -ForegroundColor Red
}

Start-Sleep -Seconds 2
$voices = @(Get-DutchSpeechVoices)
if ($voices.Count -gt 0) {
    Write-Host "`nNederlandse stem beschikbaar:" -ForegroundColor Green
    $voices | ForEach-Object { Write-Host ("  - {0} ({1})" -f $_.Name, $_.Culture.Name) }
    Write-Host "Herstart nu P2000 Monitor." -ForegroundColor Green
    exit 0
}

Write-Host "`nWindows heeft nog geen Nederlandse System.Speech-stem zichtbaar gemaakt." -ForegroundColor Yellow
Write-Host "De monitor gebruikt daarom Nederlandse online TTS en zal NOOIT een Engelse stem gebruiken." -ForegroundColor Yellow
Write-Host "Je kunt ook via Instellingen > Tijd en taal > Taal en regio > Nederlands > Taalopties de Spraak/Text-to-speech component installeren." -ForegroundColor Yellow
exit 2
