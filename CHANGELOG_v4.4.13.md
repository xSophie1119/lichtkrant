# v4.4.13 — alleen-live meldingen, kaart/route en geluidsherstel

- Opstarten bouwt alleen een historische baseline op; geen oude melding of omroep wordt automatisch herhaald.
- Een reconnect haalt het korte gat tussen baseline en SSE-verbinding in, met `ingested_at` als harde opstartgrens.
- De watchdog gebruikt ruimere time-outs, een eenmalige stale-heartbeatherstart en een herstartbudget tegen Linux-restartlussen.
- De Linux-browserhelper kan de eigen kiosk afzonderlijk detecteren zonder beheer- of wizardvensters mee te tellen.
- Meldingsregels verwijderen technische ritnummers, capcodes, postcodes, URL's en RSS-resttekst uit de grote weergave.
- De kaart toont zowel incident als ingestelde standplaats, inclusief afstandsindicatie en externe autoroute.
- Mastervolume `0` blijft nul in TTS, aandachtstonen en wachtrijen; nachtvolume kan stilte niet meer overschrijven.
- Directe volumeknoppen zijn toegevoegd aan het meldingsscherm en beide volumeschuiven in beheer blijven synchroon.
