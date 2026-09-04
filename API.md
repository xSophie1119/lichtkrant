# P2000 Monitor lokale API — v4.4.14

De API is op Windows en Linux gelijk en luistert standaard op poort `8765`.

Belangrijkste endpoints:

- `GET /api/runtime` — app, versie, backend-instance en platform.
- `GET /api/status` — feed/database/watchdog/status.
- `GET /api/health` — browser/SSE/audio health.
- `GET /api/settings` / `POST /api/settings` — lichtkrantinstellingen.
- `GET /api/setup` / `POST /api/setup` — installatieprofiel.
- `GET /api/display/info` — platform, sessietype, monitoren en gekozen monitor.
- `POST /api/display/power` — `{ "state": "on" | "off", "manual": true }`.
- `GET /api/tts/status` — beschikbare lokale/online TTS-routes.
- `POST /api/tts` — Nederlandse omroepaudio; Windows SAPI-WAV of Linux eSpeak-WAV waar beschikbaar, anders gTTS MP3.
- `GET /api/vehicles/status` / `POST /api/vehicles/sync` — voertuigcache.
- `GET /api/vehicle-overrides` — handmatige correcties.
- `POST /api/test-message` — test naar verbonden lichtkrant.
- `GET /api/test-status?token=...` — bevestiging van afspelen/test.
- `GET /api/update/status` — updaterstatus.
- `POST /api/system/restart` — backend zelf herstarten.

Browsermutaties met gevolgen worden alleen vanaf lokale/private clients en same-origin browserrequests geaccepteerd waar van toepassing.


## SW Mediaproducties Roepnummer API-integratie

De externe API-key is uitsluitend backend-side. De lokale control-API geeft nooit de key zelf terug.

- `GET /api/roepnummer-api/config` — base URL, key ingesteld ja/nee, opslagmethode en synchronisatie-interval.
- `GET /api/roepnummer-api/status` — online-status, geldigheid API-key, aantal geladen eenheden, laatste sync en foutstatus.
- `POST /api/roepnummer-api/config` met `{ "api_key": "..." }` — key veilig opslaan en direct synchroniseren.
- `POST /api/roepnummer-api/config` met `{ "clear_key": true }` — key verwijderen; bestaande voertuigcache blijft behouden.
- `POST /api/roepnummer-api/sync` — handmatige volledige synchronisatie starten.

Extern gebruikt de backend `X-API-Key`, `/units?page=N&limit=500` en voor cache-misses `/resolve?callsign={roepnummer}&source=lichtkrant`.
