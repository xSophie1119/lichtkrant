# P2000 Monitor v4.4.19

## Voertuigen in de omroep
- Brandweerroepnummers zelf worden niet uitgesproken.
- De volledige voertuigfunctie en standplaats worden uitgesproken.
- Voorbeeld: `20-9432` wordt `Tankautospuit Tilburg Vossenberg`.
- De omroep gebruikt `Gealarmeerde voertuigen:` ook bij één gekoppeld voertuig.
- De echte `function_name`/voertuigomschrijving uit de voertuigdatabase of API krijgt voorrang boven technische afkortingen.

## Incidentkaart
- Nieuwe instelling `Kaartweergave bij melding`.
- `Standplaats + incidentlocatie`: toont beide punten, snelste autoroute, rijafstand en geschatte reistijd.
- `Alleen incidentlocatie`: toont alleen het incident en gebruikt een iets verder uitgezoomd omgevingsoverzicht.
- De keuze wordt permanent in de backendinstellingen opgeslagen.

## Updates / Windows + Linux
- Update-assets zijn vanaf deze versie platform-specifiek.
- `P2000_Monitor_Windows_v4.4.19.zip` bevat precies één Windows-monitor-map.
- `P2000_Monitor_Linux_v4.4.19.zip` bevat precies één Linux-monitor-map.
- Hierdoor zijn de ZIPs ook te installeren met de oudere v4.4.17-updatevalidator, die precies één P2000 Monitor-map vereist.
- Windows- en Linux-bestanden blijven fysiek van elkaar gescheiden.
