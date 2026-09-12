# P2000 Monitor v4.5.0

## Architectuur
- Nieuwe centrale core-laag voor incidenten, prioriteiten, spraaktemplates, configmigraties en updates.
- Discipline-first veiligheidsrails: ambulanceprioriteiten kunnen buiten Baarle-Nassau/Hertog geen brandweereenheid meer meekrijgen.
- Incidenten worden op verklaarbare similarity samengevoegd en krijgen Critical/High/Normal/Low naast een sorteerscore.

## Voertuigen & SW Mediaproducties
- SW Mediaproducties Roepnummer API is de primaire voertuigcatalogus voor parser, omroep, kaart en beheerdebug.
- Omroep gebruikt volledige functie + standplaats; numerieke roepnummers worden niet uitgesproken.
- Lokale overrides blijven de hoogste prioriteit houden en worden met historie opgeslagen.

## Omroep
- Template-gebaseerde omroepteksten en een geprioriteerde audioqueue.
- Windows gebruikt lokale/native audio met host-fallback; Linux ondersteunt lokale Piper-rendering met bestaande fallback.
- Urgente incidenten kunnen laag-prioritaire omroep onderbreken zonder audio door elkaar te laten lopen.

## Kaart
- Vier kaartmodi: Automatisch, standplaats + incident, alleen incident, en gealarmeerde posten + incident.
- Routes worden alleen berekend wanneer de gekozen kaartmodus ze nodig heeft en worden gecachet.

## Beheer & diagnose
- Healthdashboard voor backend/feed/SW API/TTS/updater/supervisor.
- Lichtkrantschermen hebben eigen client-id, heartbeat en gerichte testmogelijkheid.
- “Waarom ziet hij dit zo?” toont parserpipeline, verwijderde tokens, voertuigresolutie, incidentkoppeling en omroeptekst.
- Testpresets en golden regressiecategorieën voor bekende probleemmeldingen.
- Handmatige incidentcorrecties en centrale voertuigoverrides.

## Updates & herstel
- Manifest-updater met apart Windows/Linux-pakket en SHA-256-validatie.
- Windows gebruikt een kort stagingpad in de systeem-tempmap en filtert het andere platform vóór extractie.
- Instellingenback-up vóór update, rollback, config-schema-migratie, safe mode en opstart-selftest.
- Compatibiliteitsroute voor oudere branch-updaters zodat de 260-teken/MAX_PATH-fout niet terugkomt.
