# GitHub-updates — v4.4.5

De monitor kan zowel Releases als gewone pushes op de ingestelde branch volgen. Branchupdates worden op exacte commit-SHA herkend, ook wanneer `VERSION` gelijk blijft.

Aanbevolen Release-asset:

```text
P2000_Monitor_MultiPlatform_v4.4.5.zip
```

De assetselectie geeft voorrang aan `multiplatform`/`multi-platform`. Als er meerdere OS-assets bestaan kiest Windows liever een Windows-ZIP en Linux liever een Linux-ZIP.

De validator accepteert alleen een complete monitorstructuur met onder andere:

- `backend/server.py`
- `frontend/index.html`
- `frontend/control.html`

Symlinks, path traversal, te grote archives en ongeldige structuren worden geweigerd. Bij Release-assets wordt een door GitHub opgegeven SHA-256 digest gecontroleerd.

Bij installatie blijven `config/config.json` en `data/` behouden. Eerst wordt een programmabackup gemaakt onder `data/updates/backups/`; maximaal drie backups blijven staan.

Linux-launchers krijgen na een update opnieuw execute-rechten wanneer de ZIP Unix-modebits bevat of wanneer het om een bekende `.sh` launcher gaat.
