# P2000 Monitor lokale API — Windows v4.2.0

De backend luistert standaard op `http://127.0.0.1:8765` en dient ook de lichtkrant, beheerpagina en configuratiewizard uit.

## Installatieprofiel

- `GET /api/setup` — huidig profiel, standplaats, regio-/disciplinematrix en opgebouwde RSS-feeds.
- `POST /api/setup` — sla de configuratiewizard op. Wijzigingen bouwen de RSS-set opnieuw op, legen de feedcache en verwijderen meldingen die buiten de nieuwe selectie vallen.
- `GET /api/feed-catalog` — beschikbare regio's, disciplines, landelijke feeds en subregio-relaties.

## Monitor

- `GET /api/runtime` — appnaam, versie en serverinstantie.
- `GET /api/status` — feed- en monitorstatus.
- `GET /api/health` — watchdog/clientstatus, inclusief audio-status van het lichtkrant-tabblad.
- `GET /api/messages?limit=100` — opgeslagen meldingen binnen de huidige selectie.
- `GET /api/stream` — Server-Sent Events voor nieuwe meldingen, status, instellingen en testopdrachten.
- `GET /api/settings` / `POST /api/settings` — lichtkrantinstellingen; wijzigingen worden atomisch en permanent onder de gebruikersconfiguratiemap opgeslagen, met SQLite als compatibiliteitskopie.
- `GET /api/feed-config` — door de wizard opgebouwde RSS-bronnen.
- `POST /api/feeds/reconnect` — feedcache legen en opnieuw verbinden.

## Parser / kaart / omroep

- `POST /api/parser/debug` met `{"raw":"..."}` — test één ruwe P2000-regel met de landelijke parser.
- `GET /api/geocode?city=...&location=...` — PDOK/BGT-geocoding voor de kaart.
- `POST /api/test-message` — stuur een testmelding, omroeptest of stop-opdracht naar het lichtkrant-tabblad.
- `POST /api/tts` met tekst/service/snelheid — render Nederlandse omroepaudio; geeft WAV terug wanneer lokale Windows-TTS beschikbaar is en gebruikt de ingebouwde Nederlandse fallbackroute waar nodig.
- `GET /api/tts/status` — status van Nederlandse TTS-rendering en gebruikte stem/engine.

## Voertuigen

- `GET /vehicles.json` — kleine meegeleverde offline seed; niet de volledige runtimecatalogus.
- `GET /api/vehicles` — samengevoegde O(1)-runtimecatalogus voor alleen de geselecteerde brandweerregio’s, inclusief metadata per regionale cache.
- `GET /api/vehicles/status` — status, geselecteerde regiocodes, aantallen, laatste refresh en eventuele bronfout.
- `POST /api/vehicles/sync` met `{"force":true}` — start een geforceerde **achtergrond**sync. De HTTP-call wacht niet op alle regio-downloads.
- `GET /api/unknown-vehicles` — nog niet exact bekende landelijke brandweerroepnummers die tijdens gebruik zijn gezien.

Regionale caches staan onder `data/vehicles/<regiocode>.json` en worden standaard maximaal eens per 7 dagen ververst. Een netwerk- of bronfout laat de RSS/SSE-verwerking ongemoeid: de laatst bekende cache blijft bruikbaar en onbekende voertuigen worden onmiddellijk via het landelijke nummerplan weergegeven.


## Achtergrondfoto
- `GET /api/background/info` – status van de lokaal opgeslagen achtergrondfoto.
- `GET /api/background/image?v=<versie>` – geeft de lokale JPG/PNG/WebP terug.
- `POST /api/background/upload` – raw image body, maximaal 15 MB; alleen JPG/PNG/WebP.
- `POST /api/background/remove` – verwijdert de lokale achtergrondfoto.

## GitHub Releases updates (v4.2.0)

- `GET /api/update/github/settings` — huidige GitHub update-instellingen.
- `POST /api/update/github/settings` — `{github_repo, github_auto_check, github_auto_install, github_check_hours}`.
- `GET /api/update/status` — huidige/laatste update-status, beschikbare versie en release-informatie.
- `POST /api/update/github/check` — `{install:false}` controleert; `{install:true}` downloadt, valideert, back-upt en installeert de nieuwste release.
- `POST /api/update/rollback` — herstelt de nieuwste lokale programmabackup en herstart de backend.
- `POST /api/update/upload` — bestaande handmatige ZIP-update blijft beschikbaar voor lokale beheerclients.

GitHub-updates ondersteunen openbare repositories en gebruiken de nieuwste gepubliceerde GitHub Release. De release moet een complete `.zip` asset bevatten. Config/data worden niet overschreven.
