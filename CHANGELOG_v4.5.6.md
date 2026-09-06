# P2000 Monitor v4.5.6

Lifecycle-, update- en kiosk-hardening bovenop de bewezen v4.5.5 compatibility-chain.

## Belangrijkste fixes

- v4.5.6 wordt deterministisch pas toegepast nadat de SHA-gecontroleerde v4.5.5 runtime is opgebouwd.
- Post-v4.5.5 launcherbestanden mogen de legacy bridge alleen passeren wanneer hun volledige SHA-256 exact op de v4.5.6 allowlist staat.
- Oude supervisors uit andere uitgepakte P2000-mappen worden altijd vóór backendcontrole beëindigd.
- Een verse supervisor uit dezelfde map en dezelfde versie blijft draaien; stale/oude supervisors worden verwijderd.
- Ook P2000 `backend/server.py`-processen die nog niet aan poort 8765 gebonden zijn worden veilig als orphan herkend.
- Geen brede `taskkill python.exe`: procesbeëindiging vereist een herkenbare P2000-projectroot met `VERSION`, `backend/server.py` en `frontend/index.html`.
- STOP en rollback gebruiken supervisor → backend → tweede backendcontrole → kiosk, zodat de watchdog niets opnieuw kan starten tijdens afsluiten/herstellen.
- Windows kioskbeheer is gecentraliseerd in `tools/windows_desktop.py`, met stabiele profielen, veilige lock-cleanup, Edge/Chrome/Chromium-detectie en kiosk → app/fullscreen → standaardbrowser fallback.
- Windows profielherkenning ondersteunt zowel `--user-data-dir="..."` als een door Windows geheel gequote `"--user-data-dir=..."` argument.
- Linux heeft weer complete start/stop/backend/configuratie-launchers en `tools/linux_desktop.py`.
- Backendlogging gebruikt `-u -X faulthandler`, logt Python/serverpad en exitcode en roteert logs zonder ze bij elke start te wissen.
- `START_P2000_DEBUG.bat` leest de echte `VERSION` en toont de staart van startup-, backend-, browser- en Python-bootstraplogs.
- Wizard-/control-versiefallbacks worden na de bewezen v4.5.5-laag naar 4.5.6 gebracht.
- Nieuwe `RUN_TESTS.bat`/`RUN_TESTS.sh` voeren echte release- en lifecycletests uit; iedere testcase draait in een eigen subprocess met harde timeout.

## Compatibiliteit

Windows en Linux gebruiken dezelfde lifecycle-regels. Gewone Edge/Chrome-processen buiten het dedicated P2000-profiel worden niet beheerd of beëindigd.
