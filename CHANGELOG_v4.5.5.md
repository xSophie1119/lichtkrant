# P2000 Monitor v4.5.5

## Landelijke parser 2.0

- Nieuwe landelijke grammatica-/fallbackparser: metadata, incidenttype, qualifiers, locatie, plaats en roepnummers worden los geparseerd.
- Brede actuele steekproef op Nederlandse P2000-formaten uit alle windstreken en disciplines.
- Ondersteuning voor o.a. BNN/BON/BMD/BNH/BAD/BDH/BRT/BZB/BOB/BLB/SNH/KAZ en BNH-inci-201.
- Betere ambulanceformaten: DIA, AMBU, BON, RIT, VWS, plaatscodes, MMT en kale Amsterdam/Limburg-regels.
- Extra live-formaten van 5 september 2026 afgevangen: `DIA: BA`, compacte `: rit-id MMT2`, `posten ... svp/ajb`, provinciecode `GE` en plaatscodes zoals `KRIMLK`, `REEUWK`, `SCHIDM` en `HENDIA`.
- Betere politie/RWS-formaten: P-bundels, ICnum, slash-taxonomie, GMS/OC en Prio 4 verkeersmanagement.
- Nieuwe incidenttypes: onderwijs, bijeenkomst, scheepvaart, spoorvervoer, luchtvaart, agrarisch, afgevallen lading, contact meldkamer, enz.
- Onbekende qualifiers breken de parser niet meer; bruikbare resttekst blijft als object/locatie behouden.
- Brandweervoertuigen uit 01-25 + 26/28 landelijk ondersteund; dubbele schrijfwijzen worden gededupliceerd.
- A0/A1/A2/B1/B2 disciplinefirewall blijft actief, met Baarle-Nassau/Hertog als expliciete uitzondering.
- Nieuwe regressiesuite met ruim 100 nationale parserchecks; politie-/incident-ID's zoals 386198 blijven geen voertuig.
- v4.5.4 landelijke SW voertuigkennis, v4.5.3 reload-fix en v4.5.2 snelle omroep blijven behouden.
