# Changelog v4.4.18

## Windows
- Oude P2000-kiosks uit vorige versies worden niet meer hergebruikt. Edge/Chrome-profielen zijn versiegebonden en de kiosk-URL bevat een cachebuster.
- Dezelfde-versie kiosk blijft idempotent draaien; alleen aantoonbaar verouderde P2000-kiosks worden afgesloten.
- Nieuwe lokale Windows-TTS fallback via backend + `System.Media.SoundPlayer` wanneer Chromium autoplay/media stil blijft.
- Host-TTS accepteert alleen localhostverzoeken.

## Omroep
- TS wordt expliciet uitgesproken als `T S`, inclusief standplaats wanneer bekend.
- De parser-/beheerpreview toont dezelfde voertuigfunctie in de omroeptekst zonder het roepnummer uit te spreken.

## Distributie
- Releasebundel bevat aparte complete `Windows/` en `Linux/` mappen.
- Updatevalidatie kiest automatisch de juiste platformmap wanneer een gecombineerde release-ZIP beide bevat.

## Testen
- 30/30 regressiescripts geslaagd.
- Nieuwe v4.4.18 Windows/TTS-regressietest: 12/12 checks geslaagd.
