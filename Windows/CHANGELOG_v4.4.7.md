# v4.4.7 — Linux kiosk reload & melding-expiry hotfix

- Na een succesvolle self-update wordt de kiosk via de externe supervisor expliciet herstart.
- Handmatig starten op Linux recyclet het bestaande kioskprofiel zodat oude frontendcode niet blijft draaien.
- Frontend-assets hebben nieuwe cache-busters.
- Live meldingen krijgen een harde absolute vervaldatum op basis van de vroegste betrouwbare tijd (publicatie/ingest/first-seen).
- `activeVisible()` controleert de deadline ook tijdens rendering; een gemiste timer kan een melding niet meer eindeloos laten staan.
- Toekomstige/afwijkende feedtimestamps worden begrensd door backend-ingest en lokale first-seen.
