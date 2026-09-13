# Toegang en updates

P2000 Monitor bindt standaard aan `127.0.0.1:8765`. De eigenaar kan op de lichtkrant-pc via `/remote` LAN-bediening aanzetten. Alleen loopback kan telefoontoegang wijzigen, koppelcodes maken of toegang van andere apparaten intrekken.

Vanaf v4.7.0 krijgt ieder apparaat een eigen willekeurige sessie. Koppelcodes bevatten 256 bits willekeur, werken één keer en verlopen na vijf minuten. Ze staan uitsluitend in geheugen; een herstart maakt openstaande codes ongeldig. De QR-code gebruikt een URL-fragment, dat vóór verdere aanvragen uit de geschiedenis wordt verwijderd. Het inwisselen gebruikt `X-P2000-Admin-Token`; daarna gebruikt de browser een HttpOnly/SameSite=Strict-cookie.

Sessies verlopen na dertig dagen. Serveropslag in `data/secrets/devices.json` bevat uitsluitend SHA-256-hashes van de sessiesleutels. Intrekken en afmelden maken een sessie ook server-side ongeldig; open statusstreams controleren de toegang opnieuw. De oude v4.6.0-code uit `admin-token.txt` wordt niet meer geaccepteerd. Alle apparaten moeten eenmalig opnieuw worden gekoppeld. Om alle koppelingen te herstellen: stop het programma, bewaar desgewenst een privéback-up van `devices.json`, verwijder dat bestand en start opnieuw.

Kijkers mogen alleen de expliciet toegestane dashboard-, archief- en kaartaanvragen doen, plus hun eigen sessie beëindigen. De server weigert overige API-toegang en alle bedieningsacties. Alleen knoppen verbergen is niet de toegangscontrole. Bedieningsapparaten mogen de lichtkrantinstellingen en bestaande beheerfuncties gebruiken; apparaatbeheer blijft op de pc.

Verzoeken met een onbekende Host/Origin of cross-site browsercontext worden geweigerd. Lokale scripts zonder Origin blijven werken. LAN-bediening gebruikt HTTP en is bestemd voor een vertrouwd lokaal netwerk. Publiceer deze poort niet rechtstreeks op internet. Er worden geen firewallregels, routerinstellingen of externe tunnels aangemaakt.

Schermbeelden, opdrachtbevestigingen en prestatiegeschiedenis hebben begrensde buffers. Schermbeelden zijn verkleinde JPEG's en worden niet op schijf opgeslagen. Herstelpunten bevatten uitsluitend lichtkrantinstellingen en staan in `data/remote/restore-points.json`. Runtimegegevens en geheimen horen nooit in Git.

Executable ZIP-upload via de beheer-API blijft uitgeschakeld. GitHub-updates doorlopen manifestcontrole en een geïsoleerde backend-healthcheck voordat bestanden worden vervangen. SHA-256 controleert volledigheid en integriteit; het is geen cryptografische uitgevershandtekening. De ingestelde GitHub-repository blijft de vertrouwensbron. CI gebruikt alleen leestoegang tot de repository en vastgepinde versies van GitHub Actions.

Recovery gebruikt `pending-health.json` en `transaction.json`. Mislukte herstelpogingen behouden hun foutbewijs; een update wordt pas bevestigd na een geslaagde health-gate. Ongeldige backupverwijzingen mogen de installatie niet over zichzelf terugzetten.
