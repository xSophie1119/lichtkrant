# Lichtkrant bedienen vanaf je telefoon — v4.7.0

1. Start de nieuwe lichtkrant op de Windows- of Linux-pc.
2. Open op **diezelfde pc** `http://127.0.0.1:8765/remote`.
3. Kies **Telefoontoegang aanzetten**. De backend herstart kort.
4. Vul een apparaatnaam in en kies **Bedienen** of **Alleen kijken**.
5. Klik op **Nieuwe koppelcode maken**. Verbind de telefoon met hetzelfde wifi-netwerk en scan de QR-code. Elke code werkt één keer en verloopt na vijf minuten.
6. Voeg de pagina eventueel toe aan het beginscherm via je telefoonbrowser.

Na een update vanaf v4.6.0 moet je telefoons opnieuw koppelen: de oude gedeelde code wordt niet meer geaccepteerd. Een apparaatsessie blijft maximaal dertig dagen geldig. **Telefoon afmelden** trekt die sessie ook op de server in. Op de pc kun je onder **Wie heeft toegang?** ieder apparaat apart verwijderen.

## Meekijken en opdrachten

**Live meekijken** toont een verkleinde kopie van het echte tekstcanvas, de huidige melding, de leeftijd van het beeld en de opdrachtbevestigingen per scherm. Gebruik de keuzelijst om een scherm te selecteren. Nieuwe beelden komen ongeveer elke tien seconden binnen, alleen zolang een bedienpaneel actief meekijkt. De afzonderlijke kaartlaag en fysieke aan/uitstand van de monitor zitten niet in de canvasafbeelding. De kaartstatus wordt apart vermeld. Een externe achtergrondfoto kan een canvasvoorvertoning blokkeren; de hartslag blijft dan beschikbaar.

Opdrachten onderscheiden **ontvangen**, **getoond**, **afgerond** en **mislukt**. Een ontbrekende bevestiging wordt nooit als succes getoond. Afspeelbevestigingen komen van de browser of de lokale audiospeler; zij kunnen niet meten of een fysieke luidspreker hoorbaar is. De Windows-route wacht op het audioproces en gebruikt geen geschatte duur als afspeelbewijs.

## Profielen

| Profiel | Gedrag |
| --- | --- |
| Normaal | Herstelt het normale volume en de weergave die actief waren vóór de profielwissel. |
| Nacht | Volume 25%, prioriteitsomroep en de bestaande nacht-/dimregeling. De ingestelde nachttijden blijven gelden. |
| Oefening | Volume 50%, scherm wakker; live meldingen blijven in het archief. Alleen handmatige tests/archiefacties worden getoond. |
| Alleen urgent | Alleen P1/A0/A1, MMT en opgeschaalde meldingen tonen en omroepen, binnen je bestaande plaats- en dienstenfilters. |

Je plaats-, diensten- en zoekwoordfilters worden niet gewist. Normaal herstellen brengt je eerdere volume terug, ook als je tussendoor meerdere andere profielen gebruikt.

## Archief en herstelpunten

Zoek op tekst, plaats, dienst, prioriteit en datum. De einddatum is inclusief, volgens de lokale dag van je telefoon. **Meer meldingen** haalt de volgende vijftig op. Open een incident op de kaart, laat het opnieuw omroepen of zet het maximaal vijf minuten vast op het gekozen scherm. Urgente live meldingen mogen een vastgezette archiefmelding onderbreken. **Losmaken op scherm** beëindigt de vastgezette melding. Archiefmeldingen krijgen een herkenbare archiefaanduiding op de lichtkrant.

Belangrijke wijzigingen van lichtkrantinstellingen krijgen vooraf automatisch een herstelpunt. Je kunt ook zelf een beschrijving opgeven. Bekijk eerst de verschillen en zet vervolgens de instellingen terug. Als iemand tussendoor instellingen wijzigt, moet je de verschillen opnieuw bekijken. De veertig recentste herstelpunten worden bewaard. Volume schuiven maakt niet telkens een extra herstelpunt.

Herstelpunten bevatten de lichtkrantinstellingen: volume, filters, tonenkeuze en schermweergave. Ze bevatten geen audio-/fotobestanden, regio-configuratie, API-sleutels of complete programmaversie. De bestaande updateback-ups blijven afzonderlijk beschikbaar.

## Storingen en prestaties

**Werkt alles?** toont de bronstatus, de laatste geslaagde broncontrole, het verbonden scherm en audioterugkoppeling apart. Geen nieuwe meldingen ontvangen is niet hetzelfde als een defecte bron. Heropen het scherm, verbind bronnen opnieuw of stuur een omroeptest vanuit het paneel. Bij geblokkeerde browseraudio kan een tik op het lichtkrantscherm nodig zijn.

Onder **Snelheid en geheugengebruik** staan recente ophaal-, parser-, kaart- en tekentijden. De backend meet CPU en resident geheugen iedere tien seconden en bewaart maximaal één uur in geheugen. CPU 100% betekent één volledig gebruikte processorkern. Browser-JavaScriptgeheugen wordt alleen getoond als de browser die meting ondersteunt. Dit zijn meetwaarden van je eigen installatie, geen garantie over de snelheid van externe feeds.

De telefoon gebruikt een aparte statusverbinding met automatische herverbinding. Als die niet werkt, valt het paneel terug op periodiek ophalen. Verbindingen sluiten wanneer de pagina op de achtergrond staat. Een telefoonpaneel telt nooit als lichtkrantscherm.

## Verbindingsproblemen

- Gebruik hetzelfde wifi-/LAN-netwerk. Dit paneel is bedoeld voor een vertrouwd lokaal netwerk; er wordt geen internettoegang of routerpoort ingesteld.
- Geef Python indien nodig toegang tot het privénetwerk in Windows Firewall.
- Bij meerdere netwerkadapters kan het getoonde adres niet je wifi-/ethernetadres zijn. Gebruik dan het juiste lokale pc-adres met poort 8765 en plak de koppelcode handmatig.
- Een verlopen of gebruikte koppelcode vervang je op de pc door een nieuwe.

## Herstel van de oude v4.5.7-opstartbridge

Als v4.5.7 niet meer start door `bridge basishash klopt niet`, kan die installatie zichzelf niet bijwerken. Pak de nieuwe versie uit in een nieuwe map, sluit de oude lichtkrant en kopieer je eigen `data`- en `config`-mappen naar de nieuwe map. Start daarna `START_P2000.bat` of `START_P2000.sh`. Bewaar de oude map als terugvaloptie.
