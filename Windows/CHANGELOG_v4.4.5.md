# P2000 Monitor MultiPlatform v4.4.5

## Linux display-lock hotfix

- Linux monitorselectie wordt nu hard vastgezet op de exacte outputconnector (`linux-output:HDMI-A-1`, `DP-1`, enz.).
- Identieke monitoren zonder EDID/serienummer krijgen geen botsende selectie-identiteit meer.
- Tijdelijke detectie-uitval valt niet langer terug naar het primaire scherm; de laatst bekende geometrie blijft behouden.
- Supervisor reageert niet meer op focus-/fingerprintwisselingen en veroorzaakt daardoor geen monitor-pingpong.
- Alleen een echte reconnect van de reeds gekozen output kan automatisch een kiosk-herplaatsing triggeren.
- Niet-primaire outputs op positie `0,0` worden correct herkend; XWayland wordt op Wayland expliciet verkozen voor betrouwbare plaatsing.
- Als `wmctrl` of `xdotool` aanwezig is, wordt de X11/XWayland-kiosk na starten nogmaals hard naar de gekozen geometrie verplaatst.
- Schermkeuze bewaart een last-known monitor snapshot zodat een korte hotplug/detectiehapering de target niet verandert.
