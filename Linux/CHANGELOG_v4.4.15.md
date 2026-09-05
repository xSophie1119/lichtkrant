# v4.4.15 — stabiele kiosk op Windows en Linux

- Verwijdert de onvoorwaardelijke kioskstop uit de gewone Linux- en Windows-startprocedure.
- Herhaalde handmatige, autostart- of service-aanroepen hergebruiken een gezonde kiosk.
- Herstartt niet langer uitsluitend vanwege een verlopen client-healthbericht.
- Telt alleen nieuwe browserprocesmetingen mee; één gecachte fout kan niet meer als meerdere mislukkingen gelden.
- Vereist drie onafhankelijke ontbrekende-procesmetingen én geen recente heartbeat/SSE voordat automatisch herstel is toegestaan.
- Monitorreconnects, geometrie-, DPI- en focuswijzigingen veroorzaken geen automatische kioskstop meer.
- Detecteert en vervangt supervisors die nog code van een vorige programmaversie draaien.
- Vindt Chromium, Firefox en Brave via `snap list`, ook zonder `/snap/bin` in `PATH`.
- Verlengt de startgrace voor Snap/Flatpak-handoffs en verbetert de Linux-browserfoutmelding.
