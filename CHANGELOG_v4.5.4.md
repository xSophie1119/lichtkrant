# P2000 Monitor v4.5.4

## Landelijke voertuigkennis

- SW Mediaproducties Roepnummer API is nu altijd landelijk actief, onafhankelijk van de gekozen meldingsregio.
- Bijstand uit andere veiligheidsregio's wordt daardoor gewoon herkend, getoond en uitgesproken.
- De live SW-resolver accepteert bij brandweermeldingen alle Nederlandse regio-prefixen 01-25 plus 26/28.
- Geselecteerde regio's bepalen alleen welke meldingen worden getoond en welke tragere regionale fallbackshards worden bijgewerkt.
- Voorbeeld: met alleen Midden- en West-Brabant geselecteerd blijven 19-xxxx, 21-xxxx, 22-xxxx en andere landelijke brandweereenheden herkenbaar.
- Politie- en ambulancegetallen blijven uitgesloten van de brandweer-resolver; de eerdere bescherming tegen nummers zoals 386198 blijft actief.
