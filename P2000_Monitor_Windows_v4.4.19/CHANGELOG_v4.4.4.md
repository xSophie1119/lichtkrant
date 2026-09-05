# P2000 Monitor MultiPlatform v4.4.4

## Hotfix — GitHub updater

- Opgelost: GitHub-update kon stoppen met `got multiple values for keyword argument 'target_version'`.
- Update-statusvelden worden bij de staged-status nu eerst samengevoegd, zodat `target_version` exact één keer aan `_write_update_status()` wordt doorgegeven.
- Extra regressietest toegevoegd die de volledige GitHub-installatiestatusroute simuleert tot en met `staged`.

## Hotfix — scherm wisselen vanuit backend

- Schermkeuze is nu een expliciete backendactie: exact herkennen → stabiele fingerprint opslaan → displaycache legen → kiosk direct opnieuw plaatsen.
- De backend start de supervisor automatisch wanneer een schermwissel wordt aangevraagd en die nog niet actief is.
- `/api/display/select` toegevoegd voor directe schermwissels vanuit het portaal of andere clients.
- Ook een gewone `/api/settings`-save met een gewijzigde `kioskMonitor` vraagt nu direct een kiosk-restart aan.
- Opgelost: race tussen `/api/settings` en `/api/display/info` kon de opgeslagen tweede monitor terugzetten naar `primary`.
- Opgelost: tijdelijk losgekoppeld scherm verloor zijn opgeslagen fingerprint bij het opslaan van een andere instelling.
- Linux `wlr-randr` ondersteunt nu zowel JSON-uitvoer als de gewone tekstuitvoer van distroversies zonder `--json`.
- Het schermpaneel heeft nu **Nu toepassen** en een keuzewijziging wordt meteen toegepast.
- Extra regressietest met twee gesimuleerde monitoren en een echte HTTP-call naar `/api/display/select`.
