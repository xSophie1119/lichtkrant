# P2000 Monitor v4.4.0 — Reliability & Control

## Nieuw
- Eénklik-installatie voor Windows (`INSTALL_P2000.bat`) en Linux (`INSTALL_P2000.sh`), met behoud van bestaande config/data.
- Externe supervisor/watchdog voor backend, kiosk en monitor-reconnects.
- Parallelle P2000 feed-race: regionale feeds, landelijke disciplinefeeds en optionele extra feeds worden gelijktijdig opgehaald; de eerste unieke melding wint.
- Feed-cyclustijden en bron-wins in de health/statusdiagnose.
- Omroepmodi **Normaal**, **Alleen prioriteit** en **STIL**, plus mastervolume.
- Slimmere TTS-wachtrij: een nieuwere/hogere opschaling kan een oudere nog-wachtende omroep van hetzelfde incident vervangen.
- Voertuigdatabase met auditgeschiedenis; handmatige overrides blijven altijd boven online bronnen staan.
- Onbekende roepnummers krijgen suggesties voor type/regio en zijn met één tik voor te vullen.
- Nieuwe regressiecorpus met echte probleemmeldingen zoals Contact MKB, BR buiten, zichtschermen, BR Natuur, Ongeval Wegvervoer en Lifeliner.
- Veilige updater: staged preflight op een aparte lokale poort + pending-health marker + automatische rollback door de supervisor.
- Monitor-fingerprints (waar OS/driver dit levert), zodat schermkeuze beter blijft werken na HDMI/DP reconnect of connectornaamwijziging.
- Mobiele snelbediening: omroepmodus, volume, stop, laatste melding herhalen en kiosk herstarten.
- Live parserpreview in het bedieningsportaal.

## Compatibiliteit
Windows 10/11 en Linux (X11/Wayland waar desktopfunctionaliteit beschikbaar is). De P2000 backend blijft ook headless bruikbaar.
