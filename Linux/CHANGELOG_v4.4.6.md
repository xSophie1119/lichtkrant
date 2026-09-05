# P2000 Monitor MultiPlatform v4.4.6

## SW Mediaproducties Roepnummer API

- SW Mediaproducties Roepnummer API is de primaire exacte voertuigbron.
- Volledige paginering (`limit=500`) bij opstarten en iedere vijf minuten.
- `X-API-Key` blijft backend-only; Windows gebruikt DPAPI, Linux een owner-only 0600-bestand.
- Lokale SW-cache blijft actief bij timeout, storing of HTTP-fout.
- Onbekende roepnummers gebruiken `/resolve?callsign=...&source=lichtkrant` zonder de P2000-ingest te blokkeren.
- `lookup_key` herkent zowel kale als gestreepte roepnummers.
- Beheer toont API-status, key-status, aantal eenheden en laatste synchronisatie.
- Voertuigweergave toont roepnummer, functiecode, functienaam en post.
- Handmatige overrides blijven hoogste prioriteit; oude regionale/hardcoded data blijft fallback.
