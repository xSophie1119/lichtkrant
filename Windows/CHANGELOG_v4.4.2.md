# P2000 Monitor MultiPlatform v4.4.2 — Linux Stability Hotfix

Deze release richt zich volledig op Linux-betrouwbaarheid en de configuratiewizard.

## Linux desktop/browser
- Eén gedeelde browserlaag (`tools/linux_desktop.py`) voor kiosk, wizard en instellingen.
- Ondersteuning voor native browsers, Ubuntu Snap en veelgebruikte Flatpak-browsers.
- Snap-veilige browserprofielen onder `~/snap/<pakket>/common/`.
- Aparte profielen voor kiosk en beheerpagina's, zodat ze elkaar niet blokkeren.
- Gecontroleerde browserstart: succes wordt pas gemeld nadat het proces daadwerkelijk blijft draaien.
- Veilige kiosk-stop die alleen P2000-browserprocessen beëindigt en geen shell/diagnoseproces kan raken.
- X11/Wayland fallback; bij een tweede scherm wordt XWayland eerst geprobeerd wanneer dat betrouwbaarder is voor vensterpositie.
- Firefox-fallback krijgt expliciete autoplay-instellingen zodat attentietoon en TTS niet door standaard autoplay-beleid worden geblokkeerd.

## Configuratiewizard
- `CONFIGURATIE_WIZARD.sh` gebruikt dezelfde gecontroleerde browserlaag als de kiosk.
- Backendstart en wizard-HTTP worden gecontroleerd; fouten blijven zichtbaar en worden gelogd.
- Watchdog herstart de kiosk niet meer terwijl de eerste configuratiewizard nog openstaat.
- Na afronden van de wizard geldt 90 seconden extra kiosk-opstartgrace.
- API-calls in de wizard hebben een duidelijke timeout/foutmelding.
- RSS-interval 10 seconden is nu de aanbevolen standaard in de wizard.

## Start / autostart / installatie
- Nieuwe `START_P2000_AUTOSTART.sh` met retries voor login-races.
- Grafische sessievariabelen kunnen uit de systemd-useromgeving worden hersteld.
- Installer maakt appmenu-items voor Monitor, Instellingen, Configuratiewizard, Diagnose en Stoppen.
- Installer waarschuwt tegen `sudo ./INSTALL_P2000.sh` en kan ontbrekende Python automatisch proberen te installeren.
- Nieuwe `LINUX_REPAIR.sh` herstelt execute-rechten, shortcuts en autostart.
- `LINUX_CHECK.sh` controleert nu wizard-API, wizardbestanden, browserdetectie, schrijfrechten, launchers en logs.
- Start/install via root of `sudo` wordt standaard geweigerd met een duidelijke uitleg; desktopbrowsers en gebruikersautostart horen onder het normale Linux-account te draaien.

## Runtime / updater
- `runtime_probe.py` en rollback kunnen op Linux listener-PID's via `/proc` vinden als `ss`/`fuser` ontbreken.
- Updater/rollback herstellen ook execute-rechten van de nieuwe Linux-scripts en browserhelper.
- Runtime-directory valt veilig terug op `/tmp` wanneer `XDG_RUNTIME_DIR` niet bruikbaar is.
- Op Wayland wordt `xset` niet meer ten onrechte als geslaagde fysieke scherm-aan/uit-methode gebruikt; wlroots gebruikt waar mogelijk `wlr-randr`, anders wordt de beperking eerlijk gemeld.

## Tests
- Nieuwe Linux-desktopregressies voor wizardbrowser, kioskgeometry, veilige stop, Snap-profielen, autostart en `/proc`-fallback.
