# v4.4.9 — Performance & stabiliteit

- Persistent HTTP connection pooling voor RSS en SW Roepnummer API.
- RAM-deduplicatie van recente P2000 IDs vóór SQLite.
- Feedpoller gebruikt een blijvende workerpool en corrigeert het pollritme voor fetchduur.
- Per-feed backoff bij storingen; fallback/racefeed fouten degraderen de primaire 112-nu status niet.
- SQLite-retentie maximaal één keer per uur.
- Scope-cleanup alleen bij gewijzigde regio-/disciplineconfiguratie.
- Health endpoint en supervisorchecks gecachet/ontkoppeld van zware schermdetectie.
- Statische frontendbestanden backend-side gecachet op mtime.
- Oude standaardconfig wordt eenmalig veilig getuned naar 8 s / 6 s / 10 workers.
- Geen wijziging aan handmatig ingestelde performancewaarden.
- Brandbase/geocoder fallback blijven bewust op de bewezen urllib-route voor compatibiliteit.
