# P2000 Monitor v4.4.1 — Linux start hotfix

## Opgelost

- Linux-launcher controleert nu of de kioskbrowser **echt blijft draaien** voordat de start als geslaagd wordt gemeld.
- Ubuntu Chromium Snap krijgt automatisch een toegestaan profiel onder `~/snap/chromium/common/p2000-monitor-profile` in plaats van een door Snap geweigerd verborgen XDG-pad.
- Chromium/Chrome/Brave/Edge worden achter elkaar geprobeerd; een defecte eerste browser blokkeert de rest niet meer.
- Wayland start automatisch en valt bij problemen terug op expliciete Wayland- of X11-modus.
- Firefox en daarna de standaardbrowser blijven als fallback beschikbaar.
- Bij een startfout verschijnt nu een zichtbare melding en blijft een handmatig geopend terminalvenster staan zodat de echte fout leesbaar is.
- `START_P2000_DEBUG.sh` toegevoegd voor één-klik diagnose die het venster bewust openhoudt.
- `LINUX_CHECK.sh` toont nu ook browserverpakking (Snap/native) en de laatste startup/backend/browser/supervisor-logs.
- De handmatige Linux desktopstarter gebruikt een terminal zodat een fout niet meer stil verdwijnt; autostart blijft zonder terminal werken.
