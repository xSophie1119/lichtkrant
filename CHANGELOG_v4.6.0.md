# v4.6.0 — mobiel bedienpaneel, betrouwbare start en minder achtergrondwerk

## Telefoonbediening

- Nieuw compact `/remote`-paneel met volume, omroepmodus, herhalen/stoppen, schermacties, kaart/nachtmodus, meldingen en tests.
- Lokale inschakelknop en QR-koppeling; dezelfde sessie werkt op het paneel, alle instellingen en de wizard.
- Standaard localhost; externe API-verzoeken vereisen het installatietoken of een HttpOnly/SameSite-cookie. Host- en origincontrole beschermen lokale beheeracties.
- Eén compacte statusaanvraag per vijf seconden; geen polling vanuit verborgen telefoontabs. Het bedienpaneel telt niet als lichtkrantscherm.

## Concrete reparaties

- Schone v4.5.7-downloads konden niet starten doordat de oude bridge `START_P2000.bat` en `tools/supervisor.py` afkeurde. De runtime is uit exact gecontroleerde historische baselines opgebouwd en wordt nu als gewone Python/JS-bron geleverd. Starten herschrijft geen programmabestanden meer.
- De nationale parser en coremodules zijn nu leesbare broncode. Verpakte bridge-payloads zijn verwijderd.
- Supervisor verwerkt herstartopdrachten daadwerkelijk. Unieke opdrachtbestanden voorkomen overschrijven; trage browserstarts blokkeren de heartbeat niet.
- Supervisor neemt een nieuwe programmaversie over en voert niet langer een extra SQLite-integriteitscontrole uit bij elke heartbeat.
- De ontbrekende `_atomic_json_write` voor updatejournalen is toegevoegd; corrupte herstelmarkers mogen niet de installatie over zichzelf terugzetten.
- Staged-updatecontrole gebruikt veilige modus; `--no-poll` start ook geen update-/databasesynchronisatie op de achtergrond.
- Snelle volume- en omroepacties slaan alleen de gewijzigde velden op. De instellingenpagina bewaart plaats-/trefwoordfilters en een opgeslagen monitor, ook voordat schermdetectie klaar is.
- Instellingenpagina schrijft alleen gewijzigde velden en serialiseert schrijfacties. Volume veranderen wist een nog niet opgeslagen tekstwijziging niet meer.
- Een herhaalopdracht wordt bij tijdelijk ontbrekende SSE-verbinding correct als gequeueerd teruggegeven; de pollingfallback kan hem afhandelen.
- Een RSS-bron in fout-backoff telt niet langer als online, zodat reservebronnen bij uitval daadwerkelijk worden geactiveerd.
- Windows/Linux-instellingen en wizard gebruiken dezelfde geserialiseerde startup-guard. De ontbrekende Linux `open`- en `probe`-commando’s zijn hersteld.
- Netwerkadresdetectie sluit de socket ook als detectie mislukt.
- Verdwenen SSE-clients worden afgemeld en gesloten.

## Prestaties

- Gedeelde instellingen worden kort gecachet en bij opslaan bijgewerkt; ongewijzigde saves schrijven niet opnieuw naar disk.
- De dure health-gate wordt maximaal eens per acht seconden uitgevoerd; een geforceerde controle blijft mogelijk.
- Kaartcontext zoekt een melding rechtstreeks via de database-primary-key in plaats van de laatste 500 meldingen te laden en te parsen. Oudere meldingen blijven vindbaar.
- Bij gezonde SSE-push hoeft het scherm de commandofallback niet meer elke 1,5 seconde op te vragen; de snellere fallback blijft beschikbaar bij verbindingsverlies.
- De volledige instellingenpagina pauzeert achtergrondpolling in verborgen tabs en voorkomt overlappende aanvragen per taak.

## Validatie en grenzen

- Bestaande 12 controles, 24 runtime-/HTTP-regressietests en 7 DOM-tests slagen.
- Schone backendstart in veilige modus: ongeveer 0,2–0,3 seconde in de Linux-testomgeving. Dit is geen meting van jouw pc of van RSS-bronvertraging.
- Getest: auth/cookies/origin/host, blijvende en gelijktijdige saves, commandowachtrij, pollingtest, parserbeleid, cachegedrag, ID-lookup en start zonder bronwijzigingen.
- Een compleet ZIP-pakket is uitgepakt, op alle manifesthashes gecontroleerd en geïsoleerd gestart via de echte updater-preflight.
- Python-compilatie, JavaScript-syntax en shell-syntax gecontroleerd.
- Visuele browsercontrole was geblokkeerd doordat de beschikbare browser geen lokale testserver kon bereiken. DOM-gedrag is automatisch getest; echte iPhone/Android-, Windows-kiosk-, audio- en monitorhardwaretests blijven nodig.
