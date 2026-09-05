# P2000 Monitor v4.5.1

## Omroep / SW Mediaproducties
- SW API-objecten voor `function` en `station` worden nu als object uitgelezen in plaats van als Python-dictionary naar tekst geconverteerd.
- `function.name`, `function.code`, `station.name`, `station.city` en detailvelden worden expliciet genormaliseerd.
- Oude cachewaarden die al als `{"code": ...}` / `{'code': ...}`-tekst waren opgeslagen worden bij laden automatisch hersteld.
- De uiteindelijke voertuigomroep heeft een extra veiligheidsfilter zodat object-/lijst-representaties nooit worden uitgesproken.
- Voorbeeld: `20-9432` wordt `Tankautospuit Tilburg Vossenberg`.

## Windows updater
- Legacy v4.4.17 -> v4.5.x preflight gebruikt geen `os.execv` meer voor de backend-handoff.
- Paden met spaties, waaronder `Telegram Desktop`, worden via een argumentlijst veilig doorgegeven.
