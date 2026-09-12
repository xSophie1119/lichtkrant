# Lichtkrant bedienen vanaf je telefoon

Vanaf v4.6.0 heeft de lichtkrant een apart mobiel bedienpaneel.

1. Start de nieuwe lichtkrant op je Windows- of Linux-pc.
2. Open op **diezelfde pc** de instellingen en kies **Telefoonbediening & QR-code**. Je kunt ook `http://127.0.0.1:8765/remote` openen.
3. Klik op **Telefoontoegang aanzetten**. De backend herstart kort.
4. Verbind je telefoon met hetzelfde wifi-netwerk en scan de QR-code. Je telefoon wordt gekoppeld en opent het bedienpaneel.
5. Voeg de pagina eventueel toe aan het beginscherm via het menu van je telefoonbrowser.

In het paneel kun je het volume aanpassen, normale/prioriteitsomroep of stilte kiezen, de laatste melding herhalen, spraak stoppen, het scherm aan/uit zetten, de kaart en nachtmodus aanpassen, meldingen bekijken en de omroep testen. Via **Alle instellingen** zijn ook tonen, achtergrondfoto, voertuigcorrecties, updates en overige opties bereikbaar. **Regio’s & disciplines** opent de volledige configuratiewizard.

De omroep en schermacties vinden plaats op de lichtkrant-pc. Voor testgeluid moet het lichtkrantscherm geopend zijn. Bij een geluidstest verschijnt pas een geslaagd-resultaat nadat het scherm het afspelen bevestigt.

## Verbinding lukt niet

- Beide apparaten moeten op hetzelfde lokale netwerk zitten. Een gastnetwerk kan communicatie tussen apparaten blokkeren.
- Sta Python zo nodig toe op het **privénetwerk** in Windows Firewall. Het programma past firewallregels niet automatisch aan.
- De pc moet aan staan en de backend moet draaien.
- Gebruik op je telefoon het netwerkadres dat het paneel toont. `localhost` op je telefoon verwijst naar je telefoon zelf.
- Als de pc meerdere netwerkadapters heeft, kan het getoonde adres bij een andere adapter horen. `/api/remote/info` toont lokaal de gevonden adressen; gebruik zo nodig het wifi-/ethernetadres van de pc met poort 8765.
- Scherm uitschakelen hangt af van ondersteuning door Windows/Linux, de desktopsessie en de monitor. Een mislukte systeemactie verschijnt als fout.

## Toegang

De QR-code bevat de koppelcode. Deel hem alleen met mensen die je lichtkrant mogen beheren. De code wordt via een URL-fragment overgedragen en daarna uit de adresbalk verwijderd. De browser gebruikt vervolgens een HttpOnly-cookie, die maximaal 30 dagen wordt bewaard.

De standaardinstelling blijft alleen toegang vanaf de pc zelf. Met **Telefoontoegang uitzetten** op de pc sluit je de toegang vanaf andere apparaten weer. **Telefoon afmelden** verwijdert de sessie op die telefoon.

Het paneel is bedoeld voor een vertrouwd lokaal netwerk en gebruikt daar HTTP. Zet poort 8765 niet rechtstreeks open naar internet. Bediening via mobiel internet is geen onderdeel van deze versie.

## Update vanuit een defecte v4.5.7-installatie

Als de oude versie al niet meer start met `bridge basishash klopt niet: START_P2000.bat`, kan de ingebouwde updater niet draaien. Stop de oude lichtkrant, download de nieuwe versie, pak die uit in een nieuwe map en kopieer desgewenst je bestaande mappen `data` en `config` naar de nieuwe map. Start vervolgens `START_P2000.bat` of `START_P2000.sh`. Bewaar de oude map als terugvaloptie.
