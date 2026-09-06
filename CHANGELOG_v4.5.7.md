# P2000 Monitor v4.5.7

Security-, recovery- en lifecycle-hardening bovenop de SHA-gecontroleerde v4.5.6-chain.

- Backend bindt standaard alleen aan `127.0.0.1`; LAN-exposure is niet langer de default.
- Muterende API-calls vanaf niet-loopback vereisen `X-P2000-Admin-Token`; het random installatietoken staat owner-only in `data/secrets/admin-token.txt`.
- Wildcard-CORS is verwijderd voor de beheer-API.
- Handmatige executable ZIP-upload via `/api/update/upload` is uitgeschakeld; updates lopen via de vertrouwde GitHub-bron.
- Iedere staged release moet vóór preflight slagen voor `release-manifest.json` + SHA-256-controle.
- Eén centrale semantische health-gate valideert versie, config, frontendassets en SQLite; feed/internetstoringen zijn geen critical failure.
- Pending update-recovery draait vóór de kandidaatbackend en een failuremarker verdwijnt nooit door leeftijd of een mislukte rollback.
- Update/rollback gebruikt mirror + transaction journal zodat een crash bij de volgende start herstelbaar is en obsolete bestanden verdwijnen.
- Volledige startuptransactie draait onder één per-install startupmutex.
- Linux kioskownership gebruikt commandline + dedicated profile + P2000 URL en ondersteunt native Chromium/Chrome plus Snap/Flatpak handoff.
- Chromium profile locks worden nooit opgeschoond terwijl het profiel aantoonbaar in gebruik is.
- STOP eindigt met een harde restprocescontrole en retourneert non-zero bij achterblijvers.
- Nieuwe runtime/lifecycle-suite bevat echte concurrency-, recovery-, manifest-, SQLite-, mirror- en browserhandofftests.

## Updatevertrouwen

De v4.5.7-laag wordt pas toegepast nadat de bestaande v4.5.6 compatibility-chain succesvol is opgebouwd. `release-manifest.json` is een inhoudsmanifest voor de officiële repositoryrelease; het vervangt geen TLS/GitHub-accountbeveiliging als trust root.
