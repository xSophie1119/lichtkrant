# P2000 Monitor — MultiPlatform v4.4.10

Configureerbare P2000-lichtkrant voor **Windows 10/11** en **Linux**. Dezelfde backend, frontend, database, parser, voertuiglaag en GitHub-updater worden op beide platformen gebruikt; alleen de OS-specifieke start-, scherm- en TTS-laag wisselt automatisch.

> Informatieve monitor. Niet bedoeld als officieel of primair alarmeringsmiddel.

## Nieuw in v4.4.10 — toontjes + Linux backendherstel

- Deuntje-instellingen hebben een eigen persistente opslag en worden automatisch opgeslagen.
- Gedeeltelijke instellingenwrites kunnen andere velden niet meer wissen.
- Nieuwe knop **Toontjes nu opslaan** en aparte `/api/tune/settings`-route.
- Linux herkent en beëindigt een oude/vastgelopen P2000-backend op poort 8765, ook als `/api/runtime` niet meer antwoordt.
- Linux controleert schrijfrechten op `data/` en geeft concrete PID/poort/rechten-diagnose.
- Backendstart krijgt één automatische herstelpoging voordat de launcher opgeeft.

## Nieuw in v4.4.6 — SW Mediaproducties Roepnummer API

- Primaire roepnummerbron: `https://swmediaproducties.nl/roepnummers-api/v1`.
- Backend-authenticatie via `X-API-Key`; de key wordt nooit naar de lichtkrantfrontend of GitHub-settings teruggestuurd.
- Volledige `/units?page=N&limit=500` synchronisatie direct bij opstarten en daarna iedere 5 minuten.
- Lokale cache in `data/vehicles/swmediaproducties.json`; bij storing blijft de laatst geldige cache actief.
- Onbekende roepnummers worden asynchroon opgezocht via `/resolve?callsign=...&source=lichtkrant`.
- `lookup_key` wordt genormaliseerd zodat `209471` en `20-9471` dezelfde eenheid vinden.
- Beheer toont API online, geldigheid van de key, aantal SW-eenheden en laatste synchronisatie.
- Handmatige overrides blijven winnen; Brandbase/Hulpdienst/seed blijven als fallback aanwezig.


## Hotfix v4.4.5 — updater + schermwissel

- Fix voor dubbele `target_version` in de update-status bij het klaarzetten van een GitHub-release.
- Schermkeuze wordt nu direct backend-side toegepast: valideren, stabiele monitor-ID opslaan en kiosk opnieuw plaatsen.
- De backend start de supervisor automatisch als die voor een schermwissel nog niet draait.
- Een tijdelijk losgekoppelde monitor blijft als keuze bewaard in plaats van terug te springen naar `primary`.
- Linux `wlr-randr` werkt nu ook met distroversies zonder `--json`.
- Updatepad en schermwissel opnieuw regressiegetest.

## Nieuw in v4.4.3 — 112-nu + landelijke parser + eigen rustscherm

- **112-nu.nl is de vaste hoofdbron** via vijf landelijke disciplinefeeds: Brandweer, Ambulance, Politie, Traumahelikopter en KNRM. Ze worden iedere pollcyclus parallel opgehaald; Alarmeringen blijft alleen een onafhankelijke race/fallback. Exact dezelfde ruwe P2000-regel wordt bron-onafhankelijk gededupliceerd.
- De lichtkrant toont standaard de **originele P2000-regel groot**. De samengevatte incidentweergave blijft als optie beschikbaar.
- Regionale brandweerkanaalcodes zoals `BZB-01`, `BNH-01`, `BGM-01`, `Sxx-..` en `KAZ-..` worden als kanaalmetadata herkend en niet uitgesproken als locatie.
- Rijkswegspraak begrijpt o.a. `Li` = links, `Re` = rechts, `Kp` = knooppunt en `St.` = Sint. De originele tekst op het scherm blijft ongewijzigd.
- Het rustscherm heeft een eigen builder met gecentreerd, links, split of minimaal ontwerp, eigen kop/onderregel, klokgrootte en schakelaars voor datum/seconden/status.
- Brandweerregio kan landelijk uit het eerste twee-cijferige roepnummer worden afgeleid wanneer een nationale RSS-feed geen regio meestuurt.



### v4.4.9 performance & stabiliteit

- Hergebruik van TCP/TLS-verbindingen voor de vijf 112-nu hoofdfeeds en de SW Roepnummer API.
- Recente melding-ID's worden in RAM gededupliceerd voordat SQLite wordt aangesproken.
- Database-retentie draait maximaal eenmaal per uur in plaats van in de feed-hot-path.
- Scope-cleanup gebruikt een profielhandtekening en scant de database alleen wanneer de regio-/disciplinematrix verandert.
- Feedfouten krijgen per bron een beperkte backoff; een defecte fallbackfeed zet de hoofdstatus niet meer onterecht op fout.
- Supervisor controleert backend snel maar zware health/display-detectie veel minder vaak.
- Statische frontendbestanden worden in het backendproces op mtime gecachet.
- Getunede defaults: 8 s polling, 6 s netwerktimeout en 10 parallelle feedworkers.

### v4.4.8 landelijker en leesbaarder

- Vijf 112-nu disciplinefeeds zijn altijd de primaire transportlaag.
- Plaats uit een 112-nu artikel-URL is leidend; een verkeerde/generieke RSS-category kan de melding dus niet meer naar de ingestelde hoofdplaats trekken.
- De backend houdt een landelijke woonplaatsenindex bij uit PDOK/BAG en bewaart die lokaal voor offline/fail-safe parsing.
- SW Mediaproducties Roepnummer API-voertuigen worden als normale tekst getoond, bijvoorbeeld `Hulpverleningsvoertuig met kraan (HVT-KR) — Tilburg Centrum`.
- Roepnummers worden landelijk uit de omroeptekst verwijderd; de originele P2000-regel op het scherm blijft ongewijzigd.

## Linux-start hotfix v4.4.2

Op Ubuntu wordt Chromium vaak als streng geïsoleerde Snap geleverd. De launcher gebruikt daarom automatisch een Snap-veilige profielmap, controleert of de browser na het starten daadwerkelijk blijft draaien en probeert bij problemen alternatieve browser-/Wayland-/X11-routes. Voor diagnose: `./START_P2000_DEBUG.sh`.

## Nieuw in v4.4.2

- Windows- en Linux-installer met behoud van config/data.
- Externe watchdog voor backend, kiosk, monitor-reconnects en update-rollback.
- Parallelle feed-race voor lagere P2000-latency en bron-wins/latencydiagnose.
- Omroepmodi Normaal / Alleen prioriteit / STIL en mastervolume.
- Betere voertuigoverrides, onbekende-roepnummersuggesties en wijzigingshistorie.
- Staged update-preflight plus automatische rollback als de nieuwe build niet gezond wordt.
- Monitor-fingerprints, mobiele snelbediening en live parserpreview.
- Extra regressietests gebaseerd op echte probleemmeldingen.

## Snel starten

### Windows

**Aanbevolen:** pak de ZIP volledig uit en start `INSTALL_P2000.bat`. De installer zet het programma onder `%LOCALAPPDATA%\P2000-Monitor\App`, behoudt bestaande instellingen/data bij upgrades, maakt snelkoppelingen en schakelt autostart in.

Portable gebruiken kan ook: start rechtstreeks `START_P2000.bat` vanuit de uitgepakte map. De eerste start zet automatisch een eigen Python 3.13-runtime onder `%LOCALAPPDATA%\P2000-Monitor\Runtime` klaar. De configuratiewizard opent wanneer het profiel nog niet is afgerond.

Handig:

- `START_EDGE.bat` / `START_CHROME.bat`
- `OPEN_INSTELLINGEN.bat`
- `CONFIGURATIE_WIZARD.bat`
- `WINDOWS_CHECK.bat`
- `OPEN_HANDLEIDING.bat`
- `RUN_TESTS.bat`
- `INSTALL_AUTOSTART.bat`
- `STOP_P2000.bat`
- `HERSTEL_VORIGE_VERSIE.bat`

#

## Linux

**Aanbevolen:** pak de ZIP volledig uit, geef zo nodig execute-rechten met `chmod +x *.sh tools/*.py` en start als je **normale desktopgebruiker** `./INSTALL_P2000.sh`. Gebruik hiervoor **geen `sudo`**: Chromium/Chrome weigert onder root vaak te starten zonder onveilige sandbox-flags en de desktop-/autostartbestanden horen bij je eigen gebruikersaccount. De installer gebruikt standaard `~/.local/share/p2000-monitor`, behoudt instellingen/data en maakt appmenu-items voor Monitor, Instellingen, Configuratiewizard, Linux Diagnose en Stoppen.

Portable gebruiken kan ook: start rechtstreeks `./START_P2000.sh` vanuit de uitgepakte map. Op een eerste installatie kun je `./CONFIGURATIE_WIZARD.sh` apart openen. De wizard start de backend indien nodig en controleert of de browser daadwerkelijk openblijft.

De Linux-build gebruikt **Python 3.10 of nieuwer**. Er is geen `pip install` nodig: de normale dependencies zijn meegeleverd of onderdeel van de standaardbibliotheek. De installer kan op ondersteunde distributies aanbieden om ontbrekende Python via de pakketbeheerder te installeren.

Handig:

- `./START_P2000.sh` — normale monitorstart
- `./START_P2000_DEBUG.sh` — start met zichtbare diagnose
- `./OPEN_INSTELLINGEN.sh` — beheerpagina
- `./CONFIGURATIE_WIZARD.sh` — eerste configuratie of opnieuw instellen
- `./LINUX_CHECK.sh` — complete Linux-controle
- `./LINUX_REPAIR.sh` — execute-rechten, shortcuts en autostart herstellen
- `./INSTALL_NEDERLANDSE_STEM.sh` — lokale TTS controleren/installeren
- `./OPEN_HANDLEIDING.sh`
- `./RUN_TESTS.sh`
- `./INSTALL_AUTOSTART.sh`
- `./STOP_P2000.sh`
- `./HERSTEL_VORIGE_VERSIE.sh`

De browserlaag ondersteunt native Chrome/Chromium/Brave/Edge/Firefox, Ubuntu **Snap** en veelgebruikte **Flatpak**-varianten. Snap krijgt automatisch een profiel onder `~/snap/<pakket>/common/`; kiosk en wizard/instellingen hebben aparte profielen. Onder Wayland wordt automatisch tussen Wayland/XWayland/X11-routes gewisseld. Als een compositor een tweede scherm niet goed positioneert kun je voor diagnose `P2000_BROWSER_PLATFORM=x11 ./START_P2000_DEBUG.sh` gebruiken.

Wanneer de wizard of monitor toch niet opent, voer eerst `./LINUX_CHECK.sh` uit. `./LINUX_REPAIR.sh` herstelt de meest voorkomende problemen na uitpakken/updaten (execute-rechten, appmenu en autostart).



## Linux: aanbevolen pakketten

Alleen Python is noodzakelijk voor de backend. Voor de beste kioskervaring zijn onderstaande pakketten handig:

- Chrome/Chromium voor de kiosk.
- `espeak-ng` voor volledig lokale Nederlandse TTS.
- X11: `xrandr` voor schermdetectie en `xset` voor DPMS aan/uit.
- wlroots-Wayland: `wlr-randr` voor schermdetectie en output aan/uit.

Op GNOME Wayland bestaat geen universele veilige CLI om één fysiek scherm uit te schakelen. De monitor blijft daar gewoon werken; alleen de knop **Scherm uit/aan** kan als niet beschikbaar worden gemeld. Nachtmodus/true-black blijft onafhankelijk daarvan werken.

## Architectuur

- `backend/server.py` — RSS, parser, SQLite, voertuigdatabase, geocoding, TTS, updates en API.
- `frontend/` — lichtkrant, instellingen, configuratiewizard en kaart.
- `data/` — runtimegegevens zoals SQLite, caches, achtergronden, deuntjes en updatebackups.
- `config/config.json` — installatieprofiel en feedconfiguratie.
- `tools/runtime_probe.py` — backenddetectie en stale-process cleanup.
- `tools/kiosk_display.py` — vertaalt het gekozen scherm naar browserpositie/-formaat.
- `tools/supervisor.py` — externe watchdog voor backend, kiosk, monitorreconnects en mislukte updates.

## P2000-bronnen

De vijf landelijke 112-nu disciplinefeeds (Brandweer, Ambulance, Politie, Traumahelikopter en KNRM) zijn vanaf v4.4.8 altijd de primaire transportlaag. De gekozen regio-/disciplinematrix filtert de berichten pas na parsing. Passende landelijke Alarmeringen-feeds worden parallel als race/fallback opgehaald; de eerste kopie van dezelfde originele P2000-regel wint en SQLite dedupliceert de rest. Het portaal toont per feed fetch-tijd, geschatte ingest-latency en feed-wins. Extra compatibele feeds kunnen als supplemental/fallback worden toegevoegd. De frontend ontvangt nieuwe meldingen via SSE zonder pagina-refresh.

De parser bevat regressies voor onder andere brandweer, politie, lifeliner/MMT, opschalingen, GRIP, BZB/Contact MKB en uiteenlopende adres-/roepnummerformaten.

## Voertuigdatabase

De voertuiglaag gebruikt per geselecteerde brandweerregio een compacte lokale shard. De volgorde is:

1. **Brandbase** als primaire actuele bron;
2. Hulpdienstvoertuigen.nl als eerste fallback;
3. Tomzulu10 als tweede fallback;
4. lokale laatst-goede cache;
5. landelijk nummerplan als generieke herkenning.

Handmatige correcties in `data/vehicles/overrides.json` hebben altijd voorrang en blijven bij software-updates behouden.

## Omroep en audio

De browser speelt altijd één gewone same-origin audiofile af.

**Windows:** P2000 → Nederlandse tekst → lokale Windows SAPI → WAV → lichtkrant-tab.

**Linux:** P2000 → Nederlandse tekst → lokale `espeak-ng`/`espeak` → WAV → lichtkrant-tab. Als lokale TTS ontbreekt of faalt wordt dezelfde Nederlandse gTTS-route gebruikt.

De browserstem is alleen de laatste noodfallback. Een lokaal WAV-bestand bevat de attentietoon al; daardoor wordt de toon niet dubbel afgespeeld.

Als autoplay bij een handmatig geopend tabblad wordt geblokkeerd verschijnt **OMROEP INSCHAKELEN**. De kiosklaunchers gebruiken autoplay-flags om dit normaal te voorkomen.

## Schermen

In **Instellingen → Scherm & slaapstand** kies je op welk scherm de kiosk moet staan. Een andere keuze wordt **direct toegepast**: de backend slaat de stabiele monitor-ID op en laat de kiosk opnieuw op de juiste coördinaten starten.

- Windows: native monitorcoördinaten en resoluties.
- Linux/X11: `xrandr`.
- Linux/wlroots-Wayland: `wlr-randr`, met JSON- én tekstparser.
- Een tijdelijk losgekoppeld gekozen scherm blijft opgeslagen en wordt weer gebruikt zodra het terugkomt.
- Geen ondersteunde detectietool: veilige primaire 1920×1080 fallback; de monitor blijft bruikbaar.

De monitor verandert geen desktopresolutie en herschrijft geen permanente displayconfiguratie.

## Automatische GitHub-updates

Standaardrepository: `xSophie1119/lichtkrant`.

- controle circa 10 seconden na backendstart;
- daarna standaard elke 5 minuten;
- Release-versies én gewone branchpushes kunnen worden gevolgd;
- branchpushes worden op exacte commit-SHA herkend, ook wanneer `VERSION` gelijk blijft;
- een nieuwe build wordt eerst in staging gestart en krijgt een runtime/health-preflight;
- pas daarna wordt een backup gemaakt en de build geactiveerd;
- `config/config.json` en de volledige `data/` map worden niet overschreven;
- de externe supervisor bewaakt de eerste gezonde start en rolt bij een mislukte verse update automatisch terug;
- maximaal drie programmabackups worden bewaard.

Voor Releases is een complete distributie-ZIP aanbevolen, bijvoorbeeld:

```text
P2000_Monitor_MultiPlatform_v4.4.10.zip
```

Een source-code ZIP zonder complete monitorstructuur wordt geweigerd.

## Centrale instellingen vanuit GitHub

Optioneel kan `p2000-settings.json` op de ingestelde branch automatisch worden opgehaald. Alleen bekende veilige display-/filter-/omroepinstellingen worden toegepast; lokale database, achtergrond, deuntjes en voertuigcaches blijven lokaal.

## Data en updates

Updatecode bewaart lokale runtimegegevens bewust:

- `config/config.json`
- `data/p2000.sqlite3`
- `data/vehicles/`
- `data/background/`
- `data/tunes/`
- `data/tts-cache/`
- `data/updates/backups/`

## Testen

Alle meegeleverde regressiescripts:

```bash
for f in tests/test_*.py; do python3 "$f" || exit 1; done
```

Belangrijkste sets:

- parsercorpus: 168 cases;
- probleemmelding-regressies: 8 expliciete cases uit eerder fout verwerkte meldingen;
- v4.4 reliability-contracten voor watchdog, feed-race, updater, display, audio en control UI;
- setup/feedmatrix;
- voertuigdatabase + Brandbase/fallbacks;
- GitHub updater + SHA-updates;
- centrale GitHub-instellingen;
- UI-contracten;
- Windows Python-bootstrap.

Platformdiagnose:

- Windows: `WINDOWS_CHECK.bat`
- Linux: `./LINUX_CHECK.sh`

## Logbestanden

Windows:

```text
%LOCALAPPDATA%\P2000-Monitor\Logs
```

Linux:

```text
${XDG_STATE_HOME:-~/.local/state}/p2000-monitor/logs
```

De backenddatabase en instellingen blijven bewust naast de applicatie staan zodat bestaande installaties en de ingebouwde updater hun data kunnen behouden.
