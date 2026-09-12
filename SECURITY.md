# Toegang en updates

P2000 Monitor bindt standaard aan `127.0.0.1:8765`. De eigenaar kan op de lichtkrant-pc via `/remote` bewust LAN-bediening aanzetten. Dat slaat de bindinstelling op en herstart de backend.

Alle API-verzoeken vanaf andere apparaten vereisen het installatietoken als `X-P2000-Admin-Token` of een geldige HttpOnly/SameSite=Strict-cookie. De QR-koppeling zet die cookie; de code verdwijnt uit de URL. Alleen de pc zelf kan de koppelcode opvragen of LAN-toegang wijzigen. Requests met een vreemde Host/Origin of cross-site browsercontext worden geweigerd. Lokale scripts zonder Origin blijven werken.

Het token staat in `data/secrets/admin-token.txt`, op Unix met owner-only rechten. Deze map hoort nooit in Git. De sessiecookie verloopt na 30 dagen; afmelden verwijdert hem op dat apparaat. Voor het intrekken van alle bestaande koppelingen: stop het programma, verwijder uitsluitend `data/secrets/admin-token.txt`, en start opnieuw om een nieuw token te genereren.

LAN-bediening gebruikt HTTP en is bestemd voor een vertrouwd lokaal netwerk. Publiceer deze poort niet rechtstreeks op internet. Er worden geen firewallregels, routerinstellingen of externe tunnels aangemaakt.

Executable ZIP-upload via de beheer-API blijft uitgeschakeld. GitHub-updates moeten door manifestcontrole en een geïsoleerde backend-healthcheck komen voordat bestanden worden vervangen. SHA-256 controleert volledigheid en integriteit; het is geen cryptografische uitgevershandtekening. De ingestelde GitHub-repository blijft de vertrouwensbron.

Recovery gebruikt `pending-health.json` en `transaction.json`. Mislukte herstelpogingen behouden hun foutbewijs; een update wordt pas bevestigd na een geslaagde health-gate. Ongeldige backupverwijzingen mogen de installatie niet over zichzelf terugzetten.
