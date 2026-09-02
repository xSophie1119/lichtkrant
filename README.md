# P2000 Monitor — Windows v4.2.5

## v4.2.5 – Brandbase en exacte GitHub-pushes

- Brandbase is de primaire bron voor actuele roepnummers en voertuiggegevens van de geselecteerde brandweerregio's.
- Alleen gekozen regio's worden op de achtergrond opgehaald, maximaal dagelijks en met de door Brandbase gevraagde wachttijd tussen verzoeken.
- De bestaande regionale bron en Tomzulu10 blijven als fallback beschikbaar; de laatst goede cache blijft bruikbaar bij een tijdelijke bronstoring.
- Handmatige roepnummercorrecties blijven altijd de hoogste prioriteit houden.
- Gewone GitHub-pushes worden nu herkend aan de exacte commit-SHA, ook wanneer `VERSION` niet is verhoogd.
- De geïnstalleerde commit wordt lokaal vastgelegd, zodat dezelfde push niet na iedere controle opnieuw wordt geïnstalleerd.

## v4.2.4 – snellere GitHub-updatecontrole

- Controleert circa 10 seconden na het starten en daarna standaard iedere 5 minuten.
- De instellingenpagina en configuratiewizard gebruiken nu minuten in plaats van uren.
- Bestaande installaties met het oude urenveld migreren automatisch naar 5 minuten.

## v4.2.3 – audiotests en handmatige roepnummers

- **Test omroep** en **Test gekozen deuntje** negeren tijdens de test bewust de aan/uit-hoofdschakelaar, wachten op een echte afspeelbevestiging van de lichtkrant en tonen een duidelijke fout als de monitor niet verbonden is of audio niet start.
- De omroeptest speelt alleen spraak; hij start niet meer ongemerkt ook het ingestelde deuntje.
- Handmatige roepnummercorrecties kunnen in Instellingen worden toegevoegd, aangepast en verwijderd. Ze hebben altijd voorrang op de regionale cache en blijven in `data/vehicles/overrides.json` behouden bij updates.
- De online voertuigcache wordt voortaan dagelijks in plaats van wekelijks gecontroleerd. Vanaf v4.2.5 is Brandbase primair; Hulpdienstvoertuigen.nl en Tomzulu10 blijven fallbacks.

Een configureerbare P2000-lichtkrant voor **Windows 10/11**. De monitor is niet meer aan één plaats of veiligheidsregio gekoppeld: bij de eerste start stel je zelf de standplaats, gebruiker/organisatie, regio's en disciplines in.

## v4.2.1 – GitHub pushes en centrale instellingen

- Automatische updates volgen nu zowel GitHub Releases als gewone pushes met een hogere versie in `VERSION`.
- De GitHub API-header is hersteld; updatecontroles geven niet langer door die header HTTP 400.
- `p2000-settings.json` kan optioneel iedere 1–60 minuten automatisch op alle monitoren worden toegepast.
- De instellingenpagina heeft weer complete kaart-, kolom-, status- en mobiele styling.
- Opslaan geeft een zichtbare melding bovenin en de instellingenknop op de lichtkrant opent betrouwbaar via `/control.html` of sneltoets `I`.
- Alle deuntjes en eigen MP3/WAV/OGG-functionaliteit uit v4.2.0 blijven behouden.

## v4.2.0 – automatische GitHub Releases-updater

- Nieuwe **GitHub Releases-updater**: controleert optioneel automatisch bij opstart en daarna periodiek op een nieuwere versie.
- Werkt met een openbaar repository in de vorm `xSophie1119/lichtkrant` of een volledige `https://github.com/xSophie1119/lichtkrant` URL.
- Een nieuwe versie wordt alleen geïnstalleerd uit een complete `.zip` **Release asset**; losse source-code ZIPs/tags worden niet blind toegepast.
- De updater controleert versie, ZIP-structuur en – wanneer GitHub die meestuurt – de SHA-256 `digest` van de release asset.
- Voor installatie wordt automatisch een programmabackup gemaakt; `config/config.json` en de volledige `data/` map (database, achtergrondfoto, TTS-cache, voertuigcaches) blijven staan.
- Instellingen bevat **Controleer nu**, **Update installeren** en **Vorige versie herstellen**.
- Voor een backend die na een slechte release helemaal niet meer start is er `HERSTEL_VORIGE_VERSIE.bat`, onafhankelijk van de webinterface.
- De eerste-startwizard kan het GitHub repository en automatisch installeren meteen instellen.

- `START_P2000.bat` zet bij de eerste start automatisch een eigen **Python 3.13.15 embedded runtime** klaar als die nog ontbreekt.
- De runtime staat per gebruiker onder `%LOCALAPPDATA%\P2000-Monitor\Runtime\Python313` en wijzigt Windows `PATH`, registry en bestaande Python-installaties niet.
- De normale route downloadt alleen het officiële embedded ZIP-pakket van `python.org` en controleert het tegen de vaste officiële SHA-256 voordat het wordt uitgepakt.
- Er draait dus geen Python-installer en er zijn geen administratorrechten nodig. PowerShell is alleen nog een noodfallback wanneer Windows `curl.exe` of `tar.exe` ontbreekt.
- `START_BACKEND.bat`, `OPEN_INSTELLINGEN.bat` en `CONFIGURATIE_WIZARD.bat` gebruiken dezelfde vaste runtime.
- Een standplaats mag nu ook een volledig adres zijn; voor parsing wordt de BAG/PDOK-woonplaats apart gebruikt.
- Testmeldingen krijgen daardoor niet meer per ongeluk het volledige standplaatsadres als plaatsnaam.
- Straatmeldingen zonder huisnummer kiezen bij geocoding een straat/weg-resultaat in plaats van een willekeurig BAG-huisnummer.
- De voertuigdatabase synchroniseert nu primair via de gepagineerde regionale tabellen van Hulpdienstvoertuigen.nl; de oude Google/Tomzulu-route is alleen nog fallback.
- Handmatig **Nu bijwerken** kan niet meer verloren gaan als de automatische startsync nog draait: een geforceerde tweede pass wordt gequeued.
- Instellingen toont nu de echte bron, aantallen, pagina's en concrete foutmelding per regio in plaats van alleen `0/1 regio’s`.
- De knop wacht tot 60 seconden op de achtergrondtaak en meldt niet meer onterecht `Bijgewerkt ✓` terwijl de sync nog loopt.
- Nummerplan-fallbacks tonen geen onbevestigde `post XX` meer als exacte standplaats.
- De Tilburg-regressiemelding `209432 209452 209031 209092` heeft een kleine geverifieerde offline seed gekregen.


## Wat is nieuw in 4.2.0

- Eerste-start **configuratiewizard**.
- Profielkeuze **Particulier** of **Bedrijf / organisatie**.
- Bij particulier: naam. Bij bedrijf: bedrijfs-/organisatienaam, optioneel afdeling/vestiging en contactpersoon.
- Vrije **standplaats / hoofdplaats** voor kaart, testmeldingen en monitornaam.
- Selectie per regio én discipline voor alle 25 veiligheidsregio's plus Achterhoek, Bollenstreek en Hoeksche Waard.
- Disciplines: **Brandweer, Ambulance, Politie, KNRM en Lifeliner/traumaheli**.
- RSS-URL's worden automatisch opgebouwd; je hoeft nooit zelf feeds te kopiëren.
- Als een discipline voor alle 25 veiligheidsregio's is gekozen, gebruikt de monitor automatisch de landelijke disciplinefeed om onnodige dubbele requests te voorkomen.
- Een subregiofeed wordt niet dubbel gepolld wanneer de bovenliggende veiligheidsregio voor dezelfde discipline al geselecteerd is.
- Profielwissel wist de RSS-cache en verwijdert opgeslagen meldingen die niet meer binnen de gekozen regio-/disciplinematrix vallen.
- Landelijke parser getest tegen **168 echte politie- en brandweerregels** uit verspreide regio's: 168/168 regressietests groen.
- Parser ondersteunt onder meer P1/P2/P3/P4/P5, `Prio 1`, regionale codes, ICnum, OMS, BR-typen, Ass. Ambu/Pol, wegvervoer, Noord-Nederlandse slashnotatie, 6- en 7-cijferige brandweerroepnummers, GRIP en brand/HV/IBGS-opschalingen.
- Landelijke brandweervoertuigendatabase: alleen de **geselecteerde veiligheidsregio’s** worden als regionale cache geladen en periodiek op de achtergrond bijgewerkt.
- Exacte voertuiglookup is een directe dictionary-lookup (O(1)); RSS/SSE en de lichtkrant wachten nooit op een voertuigdownload.
- Onbekende landelijke brandweerroepnummers blijven direct leesbaar via het landelijke nummerplan, ook vóór of zonder een databasesync.
- Nederlandse WAV-omroep blijft browseronafhankelijk: Chrome en Edge spelen hetzelfde lokaal gerenderde audiobestand af.
- Kaart gebruikt PDOK als primaire locatiebron met lokale straatcache/BGT-fallback.
- Alleen Windows-start-, stop-, check- en autostartscripts worden meegeleverd.

## Installeren

1. Pak de volledige ZIP uit, bijvoorbeeld naar `C:\P2000-Monitor`. Zorg dat de pc bij de allereerste start internet heeft.
2. Start `START_P2000.bat`. Bij de eerste start downloadt de monitor automatisch het officiële Python 3.13 embedded pakket vanaf python.org, controleert de SHA-256 en pakt het alleen voor P2000 uit in je lokale AppData.
3. Wacht tot de automatische runtime-installatie klaar is; daarna start de backend vanzelf door.
4. De eerste start opent automatisch de installatiewizard.
5. Kies gebruiker, standplaats, regio's en disciplines en sla op.
6. De lichtkrant start daarna met de nieuwe selectie.

De wizard kan later opnieuw worden geopend via `CONFIGURATIE_WIZARD.bat` of via **Instellingen → Configuratiewizard**. `CONFIGURATIE_WIZARD.bat` en `OPEN_INSTELLINGEN.bat` starten de backend zelf als die nog niet draait.

## Regio's en RSS

Alarmeringen.nl biedt feeds per regio/discipline en landelijke feeds per discipline. De monitor beheert deze links zelf. In de wizard kun je per regio afzonderlijk aanvinken wat je wilt ontvangen.

Voorbeeld:

- Utrecht: Brandweer + Politie + Lifeliner
- Gooi en Vechtstreek: Brandweer
- Flevoland: Politie

De backend accepteert daarna alleen meldingen die bij de opgeslagen matrix horen. Oude data uit een vorige selectie wordt bij wijziging opgeruimd.

### Heel Nederland

Voor heel Nederland kun je de snelknoppen in de wizard gebruiken, bijvoorbeeld:

- `Heel NL: BRW + POL`
- `Heel NL: alleen BRW`
- `Heel NL: alleen POL`

Als alle 25 veiligheidsregio's voor één regionale discipline geselecteerd zijn, gebruikt de monitor automatisch één landelijke feed voor die discipline. De filtering blijft op berichtniveau actief.

## Landelijke parser

P2000-regels verschillen sterk per regio. Daarom bevat v4.2.0 een regressiecorpus met 168 echte regels uit onder andere Amsterdam-Amstelland, Rotterdam-Rijnmond, Haaglanden, Kennemerland, Twente, Groningen, Flevoland, Utrecht, Brabant, Limburg, Gelderland, IJsselland en Zaanstreek-Waterland.

De parser probeert steeds deze structuur te maken:

**incidenttype → locatie/object → plaats → voertuigen → opschaling**

Voorbeelden van ondersteunde varianten:

- `P 1 BAD-01 BR woning ...`
- `P 1 BNN-01 OMS handmelder ... 01-18-849`
- `ongeval/wegvervoer/letsel prio 1 ...`
- `P 4 373209 Demonstratie ...`
- `Ongeval wegvervoer (Met brand)`
- `Middel HV`, `Kleine IBGS`, `Zeer gr. BR`, `GRIP 1`

Politie-incidentnummers worden bewust niet als brandweervoertuig behandeld.

## Landelijke brandweervoertuigen

De voertuiglaag is bewust gesplitst om de lichtkrant snel te houden. `frontend/vehicles.json` bevat alleen een kleine **offline seed**. Na het instellen van het profiel synchroniseert de backend op de achtergrond de actuele brandweer-/veiligheidsregiovoertuigen voor uitsluitend de gekozen veiligheidsregio’s. Primair worden de gepagineerde regionale tabellen van **Hulpdienstvoertuigen.nl** gebruikt; de oudere Tomzulu10/Google-publicatie blijft alleen als noodfallback bestaan. De regionale shards worden compact opgeslagen onder `data\vehicles\<regiocode>.json` en dagelijks automatisch gecontroleerd. Eigen correcties staan apart in `data\vehicles\overrides.json` en winnen altijd van beide online bronnen.

Bij **Heel Nederland: Brandweer** mogen alle 25 shards lokaal bestaan, maar in geheugen worden ze samengevoegd tot één dictionary. Het opzoeken van een roepnummer blijft daardoor een directe O(1)-lookup; er wordt niet bij iedere melding door duizenden voertuigen geloopt en er vindt tijdens het renderen geen netwerkrequest plaats. De downloads draaien bovendien in maximaal vier achtergrondworkers.

De lichtkrant ondersteunt normale zes-cijferige roepnummers zoals `21-3831` en de gesegmenteerde zeven-cijferige varianten die in sommige noordelijke regio’s voorkomen, zoals `01-18-849`. De oude beperking tot `09/14/25` is verwijderd.

Als de online bron niet bereikbaar is, gebruikt de monitor de laatst opgeslagen regionale cache. Is een voertuig echt nieuw of nog nooit gesynchroniseerd, dan wordt het **direct** generiek herkend via het landelijke brandweer-nummerplan (regio en veilige materieelgroep-afleiding; een onbekende standplaats wordt nooit als exact gepresenteerd). Daardoor blokkeert of verdwijnt een P2000-melding nooit omdat de voertuigdatabase achterloopt. Onbekende exacte roepnummers worden daarnaast onder Diagnose verzameld.

In **Instellingen → Roepnummerdatabase** zie je hoeveel exacte voertuigen geladen zijn en hoeveel geselecteerde regio’s een cache hebben. Met **Nu bijwerken** kun je een geforceerde achtergrondrefresh starten.

## Kaart

De kaart zoekt locaties in deze volgorde:

1. lokale geocode-/straatcache;
2. PDOK Location API;
3. klassieke PDOK Locatieserver;
4. officiële BGT openbare-ruimte-index;
5. OpenStreetMap/Nominatim als laatste fallback.

De standplaats is alleen een herkenningspunt. De kaart kan meldingen uit alle ingestelde Nederlandse regio's geocoderen.

## Omroep

De meest betrouwbare route is:

**P2000 → backend bouwt Nederlandse tekst → Windows rendert lokaal WAV → lichtkrant-tab speelt WAV af.**

Chrome en Edge gebruiken dus dezelfde HTML5-audioroute. De browser hoeft zelf geen TTS-stem te genereren.

- Gebruik `INSTALL_NEDERLANDSE_STEM.bat` als Windows nog geen Nederlandse TTS-stem heeft.
- `START_EDGE.bat` en `START_CHROME.bat` gebruiken ieder een eigen kioskprofiel met autoplay-instellingen.
- Als een handmatig geopend browsertabblad geluid blokkeert, verschijnt `OMROEP INSCHAKELEN`; één klik ontgrendelt audio voor dat tabblad.

### Deuntjes vóór de omroep (v4.2.0)

Onder **Instellingen → Deuntjes** kan vóór de gesproken melding een apart alarmeringsdeuntje worden gekozen. Er zijn aparte keuzes voor standaard, brandweer, ambulance, politie, Lifeliner/MMT, KNRM/waterhulp en urgente meldingen. Beschikbaar zijn ingebouwde attentietonen, een YouTube-stream of één eigen MP3/WAV/OGG-bestand tot 12 MB.

De meegeleverde standaard-YouTube-URL is `https://www.youtube.com/watch?v=VleijwaD_-U`. De video wordt niet gedownload of in het pakket gekopieerd; het geselecteerde fragment wordt via de YouTube-embed afgespeeld. De afspeelduur en het deuntjevolume zijn instelbaar. Een eigen bestand wordt lokaal bewaard onder `data/tunes/` en blijft behouden bij software-updates. Als een deuntje succesvol wordt afgespeeld vervangt het de oude korte attentiepiep, waarna de normale Nederlandse omroep start.

## Automatische updates via GitHub

De updater gebruikt **GitHub Releases**. Publiceer dus niet alleen een commit/tag, maar maak een Release en voeg de complete Windows-ZIP toe, bijvoorbeeld:

```text
Tag: v4.2.0
Asset: P2000_Monitor_Windows_v4.2.0.zip
```

Stel daarna op de monitor onder **Instellingen → Updates** het repository in als `xSophie1119/lichtkrant`. Je kunt kiezen tussen alleen automatisch controleren of nieuwe releases ook meteen automatisch installeren. Standaard gebruikt de monitor xSophie1119/lichtkrant en staan automatisch controleren en installeren aan. Zet die schakelaars uit als je dat niet wilt. De controle loopt bij backendstart na een korte wachttijd en daarna minimaal eens per ingesteld interval (1–168 uur), zodat de publieke GitHub API niet onnodig wordt belast.

Bij een installatie blijven `config/config.json` en `data/` onaangeroerd. Voor de programmabestanden wordt eerst een backup gemaakt onder `data\updates\backups`. Maximaal drie backups worden bewaard. Als de webinterface nog werkt kan **Vorige versie herstellen** worden gebruikt; start de backend helemaal niet meer, voer dan `HERSTEL_VORIGE_VERSIE.bat` uit.

GitHub Releases is bewust gekozen boven `git pull`: de ontvangende Windows-pc heeft daardoor geen Git-installatie nodig en lokale instellingen kunnen niet in een merge/conflict terechtkomen.

## Handige bestanden

| Bestand | Functie |
|---|---|
| `START_P2000.bat` | Zet zo nodig automatisch de eigen embedded Python-runtime klaar, start backend en kiest Edge/Chrome |
| `START_EDGE.bat` | Start expliciet in Edge kiosk |
| `START_CHROME.bat` | Start expliciet in Chrome kiosk |
| `STOP_P2000.bat` | Sluit kiosk en backend |
| `CONFIGURATIE_WIZARD.bat` | Wijzig profiel, standplaats, regio's en disciplines |
| `OPEN_INSTELLINGEN.bat` | Open beheerpagina |
| `WINDOWS_CHECK.bat` | Controleert de eigen Python-runtime, browsers, Nederlandse TTS, profiel en ingestelde RSS-feeds |
| `INSTALL_NEDERLANDSE_STEM.bat` | Controleert/installeert Nederlandse Windows TTS |
| `INSTALL_AUTOSTART.bat` | Start monitor na Windows-aanmelding |
| `REMOVE_AUTOSTART.bat` | Verwijdert autostart |
| `OPEN_HANDLEIDING.bat` | Opent de uitgebreide HTML-handleiding |
| `HERSTEL_VORIGE_VERSIE.bat` | Herstelt de nieuwste lokale programmabackup als een update fout ging |

## Python-runtime

De monitor gebruikt bewust **niet** de globale `python`, de Microsoft Store-alias of een `py`-launcher. De vaste interpreter is `%LOCALAPPDATA%\P2000-Monitor\Runtime\Python313\python.exe`. Ontbreekt of beschadigt die runtime, dan downloadt en herstelt `START_P2000.bat` hem automatisch als lokaal embedded pakket. Hierdoor werkt de monitor op een schone 64-bit Windows-pc zonder handmatige Python-installatie, PATH-configuratie of administratorrechten. De projectafhankelijkheden voor de normale monitorroute zijn meegeleverd; er hoeft geen `pip install` uitgevoerd te worden.

## Testen

Parsercorpus:

```text
python tests\test_parser_corpus.py
```

Verwacht resultaat in deze build:

```json
{"total":168,"failures":0,"passed":168}
```

De regio-/RSS-matrix heeft daarnaast 12 regressietests (`python tests\test_setup_matrix.py`) en de landelijke voertuiglaag heeft een aparte regressieset (`python tests\test_vehicle_db.py`). Gebruik `WINDOWS_CHECK.bat` op de uiteindelijke Windows-pc voor browser-, stem-, RSS- en voertuigcachecontrole.

## Opmerking

Deze monitor is een informatieve weergave van openbare P2000-data. Hij is **geen officieel alarmeringsmiddel** en mag niet worden gebruikt als vervanging voor pager/pieper, C2000, meldkamercommunicatie of andere operationele voorzieningen.

Python-check configuratiewizard: CONFIGURATIE_WIZARD.bat controleert en herstelt altijd eerst de eigen P2000 Python 3.13-runtime, ook wanneer de backend al actief is.


## Startproblemen en logs (v4.2.0)

Als een start mislukt sluit het venster niet meer direct. De concrete fout blijft in beeld. De twee belangrijkste logbestanden zijn:

- `%LOCALAPPDATA%\P2000-Monitor\Logs\python-bootstrap.log` – download, architectuur, SHA-256 en uitpakken van de eigen Python-runtime.
- `%LOCALAPPDATA%\P2000-Monitor\Logs\backend.log` – foutoutput van de P2000-backend.

Gebruik `START_BACKEND.bat` als extra diagnose; dit venster blijft ook na een crash open. De normale Python-bootstrap heeft PowerShell niet nodig.


Start de BAT-bestanden nooit rechtstreeks vanuit de ZIP; pak de volledige ZIP eerst uit. Vanaf v4.2.0 wordt dit automatisch herkend en blijft het foutvenster open.


## Nieuwe persoonlijke weergave (v4.2.0)
- **Omroepplaatsen:** Instellingen → *Alleen deze steden uitspreken*. Komma, puntkomma of nieuwe regel. Leeg = alles dat zichtbaar binnenkomt mag gesproken worden.
- **Achtergrond:** zwart, nachtblauw, antraciet, donkergroen, donkerrood of een eigen kleur.
- **Doelscherm:** Instellingen → *Windows scherm*. Kies een gedetecteerd scherm en herstart de lichtkrant. Chrome/Edge krijgt automatisch de juiste Windows-positie en resolutie.


## Achtergrondfoto (v4.2.0)
Onder **Instellingen → Weergave → Achtergrond → Foto** kan een lokale JPG, PNG of WebP tot 15 MB worden gekozen. De afbeelding wordt opgeslagen onder `data/background/` en blijft daardoor behouden bij software-updates. Met **Donkere laag** (0–90%) blijft tekst leesbaar; **Scherm vullen** snijdt zo nodig bij, **Hele foto tonen** behoudt de volledige afbeelding. De foto wordt alleen lokaal vanaf de monitor-pc geserveerd en veroorzaakt geen externe netwerkrequests.
