# v4.4.16 — slimmere incidenten, correcte discipline en echte route

- Blokkeert foutieve brandweermatches op politie-/ambulancemeldingen, waaronder `P 1 386198 Letsel Beethovenlaan Tilburg`.
- Behandelt A0/A1/A2/B1/B2 als ambulanceprioriteit en staat brandweereenheden alleen toe bij Baarle-Nassau/Hertog.
- Gebruikt dezelfde discipline-firewall in live feed, raw parser, testmelding en voertuigfrontend.
- Sorteert actieve meldingen slimmer op GRIP, schiet-/steekincident, zeer/grote/middelbrand, MMT, bijzondere eenheden, gekoppelde meldingen en basisprioriteit.
- Bundelt vervolgmeldingen per incident en toont in beheer een korte tijdlijn, score en redenen voor de prioriteit.
- Breidt de live parserpreview uit met originele regel, opgeschoonde schermtekst, definitieve omroeptekst en uitleg van verwijderde tokens.
- Berekent echte snelste autoroute, rijafstand en reistijd vanaf de standplaats en tekent de route op de lokale kaart.
- Houdt een hemelsbrede kaartfallback actief wanneer een routeprovider tijdelijk niet bereikbaar is.
