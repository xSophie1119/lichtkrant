# GitHub-updates — v4.4.16

De monitor kan zowel Releases als gewone pushes op de ingestelde branch volgen. Branchupdates worden op exacte commit-SHA herkend, ook wanneer `VERSION` gelijk blijft.

Bij HTTP 403 of 429 op de GitHub REST-API schakelt de branchcontrole automatisch over op publieke GitHub-adressen (`raw.githubusercontent.com`, de publieke commitfeed en codeload). Daardoor blijft een openbaar repository zonder token updatebaar. Als een exacte SHA tijdens de fallback niet gevonden kan worden, wordt alleen een hogere `VERSION` aangeboden; een gelijke versie wordt nooit opnieuw geïnstalleerd.

Een token is niet verplicht. Wie op een gedeeld netwerk toch ruimere GitHub API-limieten wil, kan vóór het starten `P2000_GITHUB_TOKEN` instellen (of de algemene `GITHUB_TOKEN`). Het token wordt niet in `config.json`, de webinterface of de status-API opgeslagen.

Aanbevolen Release-asset:

```text
P2000_Monitor_MultiPlatform_v4.4.16.zip
```

De assetselectie geeft voorrang aan `multiplatform`/`multi-platform`. Als er meerdere OS-assets bestaan kiest Windows liever een Windows-ZIP en Linux liever een Linux-ZIP.

De validator accepteert alleen een complete monitorstructuur met onder andere:

- `backend/server.py`
- `frontend/index.html`
- `frontend/control.html`

Symlinks, path traversal, te grote archives en ongeldige structuren worden geweigerd. Bij Release-assets wordt een door GitHub opgegeven SHA-256 digest gecontroleerd.

Bij installatie blijven `config/config.json` en `data/` behouden. Eerst wordt een programmabackup gemaakt onder `data/updates/backups/`; maximaal drie backups blijven staan.

Linux-launchers krijgen na een update opnieuw execute-rechten wanneer de ZIP Unix-modebits bevat of wanneer het om een bekende `.sh` launcher gaat.
