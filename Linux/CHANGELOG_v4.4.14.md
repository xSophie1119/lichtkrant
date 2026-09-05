# v4.4.14 — GitHub 403-herstel

- GitHub branchupdates vallen bij REST-API HTTP 403/429 automatisch terug op publieke GitHub-endpoints.
- `VERSION` wordt in de fallback rechtstreeks uit de gekozen branch of commit gelezen.
- De exacte commit-SHA wordt eerst via `git ls-remote` en daarna via de publieke commitfeed geprobeerd.
- Wanneer geen SHA beschikbaar is, kan alleen een hogere versie worden geïnstalleerd; gelijke versies veroorzaken geen herhaalupdate.
- De gewone branchcontrole gebruikt nog maar één REST-call plus één publieke bestandsopvraag.
- Optionele authenticatie via `P2000_GITHUB_TOKEN` of `GITHUB_TOKEN`, zonder opslag of uitlekken via de UI.
- Duidelijkere fouttekst voor rate limiting, resetmomenten en tijdelijke GitHub 403-weigeringen.
