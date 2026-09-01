# GitHub-updates publiceren

1. Zet de P2000 Monitor in een **openbaar GitHub repository**.
2. Maak voor iedere uitgave een GitHub **Release**, bijvoorbeeld tag `v4.2.0`.
3. Upload de complete distributie-ZIP als Release asset, bij voorkeur `P2000_Monitor_Windows_v4.2.0.zip`.
4. Open op iedere monitor **Instellingen → Updates** en vul `xSophie1119/lichtkrant` in.
5. Zet **Automatisch controleren** aan. Zet desgewenst ook **Nieuwe versie automatisch installeren** aan.

De monitor vraagt `releases/latest` op en kiest een `.zip`-asset waarbij `P2000`, `Monitor` en `Windows` in de bestandsnaam voorrang krijgen. Een source-code ZIP zonder complete monitorstructuur wordt door de validator geweigerd.

## Wat blijft behouden bij updates?

- `config/config.json`
- `data/p2000.sqlite3`
- achtergrondfoto
- voertuigcaches
- TTS-cache
- straat/geocodecache

Voor de overige programmabestanden wordt eerst een lokale backup gemaakt in `data/updates/backups`.

## Noodherstel

Als een verkeerde release de backend niet meer laat starten: dubbelklik `HERSTEL_VORIGE_VERSIE.bat`. Dit herstelt de nieuwste programmabackup zonder config/data te verwijderen.
