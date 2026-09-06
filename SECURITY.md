# Security model

P2000 Monitor is standaard een localhost-applicatie. Poort 8765 bindt standaard aan `127.0.0.1`.

## LAN-beheer

Wie bewust een andere bind-address configureert, moet voor muterende API-calls het installatietoken meesturen als `X-P2000-Admin-Token`. Het token wordt lokaal aangemaakt in `data/secrets/admin-token.txt` en is op Unix owner-only.

## Updates

Executable ZIP-upload via de beheer-API is uitgeschakeld. Staged officiële updates moeten een `release-manifest.json` bevatten waarvan alle opgenomen SHA-256 hashes overeenkomen voordat de staged backend wordt gestart.

## Recovery

`pending-health.json` en `transaction.json` zijn recoverybewijs. Ze worden niet op leeftijd weggegooid. Na een mislukte rollback blijft de foutstatus met attempt-count staan. Een update wordt pas committed nadat de semantische health-gate groen is.
