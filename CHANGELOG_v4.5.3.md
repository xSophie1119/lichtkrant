# P2000 Monitor v4.5.3

## Reload-loop hotfix

- Opgelost: endless reload op zowel Windows als Linux wanneer een oude `app.js` uit browsercache een nieuwere backend zag.
- De lichtkrant forceert niet langer een paginareload bij tijdelijke runtime-versie- of server-instanceverschillen; SSE/polling vangt backendwissels live op.
- `index.html` geeft `app.js` en de lichtkrant-CSS bij iedere echte paginalaad een unieke cachekey, zodat Chromium/Edge/Chrome nooit eindeloos dezelfde oude frontend blijft hergebruiken.
- Behoudt de v4.5.2 snelle omroepfixes: Windows direct via SAPI/SoundPlayer, maximaal ~0,9 s deuntje-wacht, kortere TTS/browserfallbacks en snellere retries.
- De v4.5.1 SW Mediaproducties roepnummernormalisatie blijft behouden.
