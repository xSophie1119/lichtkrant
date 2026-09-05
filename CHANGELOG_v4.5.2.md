# P2000 Monitor v4.5.2

## Omroep sneller en betrouwbaarder

- Windows-kiosk gebruikt lokale SAPI/SoundPlayer nu direct als primaire TTS-route; Chromium-audio is fallback.
- Een deuntje mag de omroep maximaal circa 0,9 seconde ophouden. Als YouTube traag start, gaat de omroep direct door met de ingebouwde aandachtstoon.
- Browseraudio geeft na circa 1,2 seconde op in plaats van 4 seconden te blijven hangen.
- TTS-render timeout verlaagd van 16 naar 8 seconden.
- Browserstemdetectie en audio-retries zijn korter gemaakt.
- Een mislukte omroep wordt na circa 250 ms opnieuw geprobeerd in plaats van na 1,5 seconde.
- De bestaande v4.5.1 compatibility- en SW-roepnummerfixes blijven behouden.
