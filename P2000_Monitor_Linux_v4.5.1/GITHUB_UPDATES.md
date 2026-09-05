# GitHub-updates — v4.5.1

Vanaf v4.5.0 gebruikt de monitor primair `update-manifest.json` op de ingestelde GitHub-branch. Het manifest verwijst per platform naar één ZIP en bevat de verwachte SHA-256. Daardoor hoeft de updater niet meer te gokken op assetnamen of de repository-indeling.

## Volgorde
1. `update-manifest.json` (voorkeur)
2. GitHub Release (compatibiliteitsfallback)
3. branch-ZIP (alleen voor oudere installaties/legacy fallback)

## Platformpakketten
- `P2000_Monitor_Windows_v4.5.1.zip`
- `P2000_Monitor_Linux_v4.5.1.zip`

Elke ZIP bevat precies één complete P2000 Monitor-map. Windows pakt nooit Linux-bestanden uit en Linux nooit Windows-bestanden. De stagingmap staat vanaf v4.5.0 kort onder de systeem-tempmap (`p2u-*`) om de klassieke Windows MAX_PATH-problemen te vermijden.

## Manifest
Het manifest bevat minimaal:

```json
{
  "manifest_version": 1,
  "version": "4.5.1",
  "platforms": {
    "windows": {"name": "...zip", "url": "https://...", "sha256": "..."},
    "linux": {"name": "...zip", "url": "https://...", "sha256": "..."}
  }
}
```

De SHA-256 wordt tijdens het downloaden gecontroleerd. Bij een mismatch wordt de update geweigerd voordat de live installatie wordt aangeraakt.

## Oude v4.4.x installaties
De root van `main` blijft bewust een vlakke, complete compatibiliteitsbuild met `VERSION`, `backend/` en `frontend/`. Daardoor kan de oude branch-updater eerst naar v4.5.0 komen zonder de eerdere `Windows/` + `Linux/`-nesting en zonder het 260-tekenpad. Vanaf v4.5.0 neemt het manifest het over.

Bij installatie blijven `config/config.json` en `data/` behouden. Vóór installatie worden zowel een codebackup als een leesbare instellingenback-up gemaakt; bij een mislukte healthcheck blijft rollback beschikbaar.
