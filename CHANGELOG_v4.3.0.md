# P2000 Monitor v4.3.0 — MultiPlatform

## Platform
- Eén release voor Windows 10/11 en Linux.
- Windows-bootstrap en bestaande BAT/PowerShell-routes behouden.
- Linux launchers voor starten, backend, Chrome/Chromium, Edge, stoppen, instellingen, wizard, handleiding, diagnose, autostart en rollback.
- Linux Python-detectie voor Python 3.10+ zonder verplichte pip-installatie.

## Schermen en kiosk
- Native Windows-monitorenumeratie behouden.
- Linux-monitorenumeratie via XRandR of `wlr-randr`, met veilige fallback.
- Kioskpositie en -formaat worden platformonafhankelijk uit `/api/display/info` gehaald.
- Scherm aan/uit: Windows `SC_MONITORPOWER`, Linux X11 `xset`, wlroots Wayland `wlr-randr`.
- Niet-ondersteunde Wayland-compositors geven een gecontroleerde melding in plaats van een crash.

## Audio / omroep
- Windows: lokale Nederlandse SAPI-WAV blijft primair.
- Linux: lokale Nederlandse eSpeak/eSpeak NG-WAV toegevoegd.
- gTTS blijft fallback op beide platformen.
- Aandachtstoon wordt bij lokale WAV correct gecombineerd zodat hij niet dubbel wordt afgespeeld.
- Browseraudio blijft leidend; globale systeemvolume wordt niet ongevraagd gewijzigd.

## Updates en herstel
- GitHub Release-selectie geeft voorrang aan `MultiPlatform`-assets en daarna aan het actieve OS.
- Unix execute-bits van shelllaunchers worden na self-update hersteld.
- Rollbacktool werkt nu op Windows én Linux en kan backendprocessen op beide platformen stoppen.
- Branch/SHA-updategedrag en centrale GitHub-instellingensync behouden.

## Betrouwbaarheid
- Cross-platform `runtime_probe.py` voor stale backendprocessen.
- `ENSURE_PYTHON.sh` werkt zowel direct als via `source` zonder de bovenliggende launcher voortijdig af te sluiten.
- Nieuwe geïsoleerde regressietestrunner: `RUN_TESTS.bat` / `RUN_TESTS.sh`.
- Nieuwe multiplatform regressies voor platformdetectie, monitors, TTS-status, release-selectie, launchers en rollback.

## Validatie
- 10/10 testscripts geslaagd.
- Parsercorpus: 168/168.
- Voertuigdatabase: 27/27.
- Windows-bootstrap: 13/13.
- Nieuwe multiplatformchecks: 15/15.
- Linux end-to-end start/stop, kioskargumenten en lokale eSpeak-WAV daadwerkelijk getest.
