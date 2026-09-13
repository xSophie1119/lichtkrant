# v4.7.0 — compleet telefoonpaneel

## Toegevoegd

- Verkorte schermbeelden van het echte tekstcanvas, schermkeuze, actuele melding en leeftijd van het beeld. De kaartlaag en fysieke schermstatus worden niet gefotografeerd.
- Opdrachtbevestigingen per scherm: ontvangen, getoond, afgerond en fout. Ontbrekende of verlopen bevestigingen worden niet als succes voorgesteld.
- Normaal-, Nacht-, Oefening- en Alleen urgent-profielen; normale instellingen blijven herstelbaar en plaats-/dienstenfilters blijven behouden.
- Eenmalige koppelcodes, afzonderlijke apparaten, server-side intrekken en rollen voor kijken of bedienen. Apparaatbeheer blijft lokaal op de pc. Bestaande v4.6.0-koppelingen moeten opnieuw worden gemaakt.
- Bron-, scherm- en audiodiagnose met gerichte herstelacties.
- Veertig automatische/handmatige herstelpunten voor lichtkrantinstellingen, verschillen vooraf en conflictcontrole vóór herstel.
- Een telefoonarchief met filters, stabiele paginering, incidentkaart, omroep en vijf minuten vastzetten. Urgente live meldingen krijgen voorrang boven vastgezette archiefmeldingen.
- Een aparte statusstream voor telefoons met polling als terugval; telefoons tellen nooit mee als scherm. Verborgen pagina's sluiten de stream.
- Begrensde metingen van ophalen, verwerken, geocoding, tekenen, backend-CPU en geheugen. Archiefqueries gebruiken passende indexen.
- Afzonderlijke modules voor dashboardstatus, HTTP-routes, opslag, toegang en afspeelstatus, met regressietests.
- GitHub Actions voor Windows en Linux: manifestintegriteit, backend/HTTP/updatepakket, DOM-/schermprotocoltests en JavaScript-syntaxis.

## Extra reparaties

- Polling verwerkt opdrachten vóór het vooruitzetten van de cursor; asynchrone opdrachten kunnen daardoor niet worden overgeslagen.
- Herhalen accepteert de daadwerkelijke opgeslagen meldingsvelden in plaats van een niet-bestaand verplicht `raw`-veld.
- Windows-hostomroep controleert het einde en de exitcode van de audiospeler. Een geschatte afspeeltijd geldt niet meer als bewijs.
- SoundPlayer-WAV krijgt de gekozen volumeverzwakking in de PCM-data, inclusief echt volume nul. De globale OS-mixer wordt niet aangepast.
- Stoppen beëindigt ook de lokale hostomroep. Vervangen spraakopdrachten krijgen een annulering in plaats van ongemerkt uit de wachtrij te verdwijnen.
- Herstellen verwijdert ook instellingen die ná een herstelpunt werden toegevoegd. Gelijktijdige instellingenwijzigingen blokkeren een verouderde herstelvoorvertoning.
- Een archiefkaart zoekt alleen de incidentlocatie op en wacht niet op alle betrokken posten.

- Broncontroles lezen UTF-8 expliciet, zodat de tests ook op Windows met een andere standaardtekencodering werken.

## Lokale verificatie

- 44 echte backend-/HTTP-regressies en 16 DOM-/schermprotocoltests geslaagd.
- De twaalf bestaande aanvullende controles geslaagd, inclusief procesmutex, broncompilatie en herstelcontroles.
- Het volledige manifestpakket is uitgepakt, gevalideerd en als staged backend gestart.
- Duurproef van 120 seconden met drie gelijktijdige statusstreams en 473 combinaties van schermhartslag + dashboardaanvraag: nul fouten, 357 ontvangen statusupdates.
- In die Linux-testomgeving: 95% van de HTTP-aanvraagparen binnen 5,49 ms; gemiddeld 1,59% van één CPU-kern. Resident geheugen groeide van 57.528.320 naar 57.774.080 bytes tijdens de meetperiode. Dit is een korte synthetische proef, geen bewijs van dagenlange stabiliteit of live-feedlatentie.

Echte Windows-audio, HDMI/Wayland-schermbediening en iPhone-/Android-browserweergave blijven afhankelijk van installatie en hardware. DOM-tests zijn geen visuele browsertests. De voorvertoning fotografeert geen externe kaartlaag. Een softwarematige afspeelbevestiging bewijst niet dat fysieke luidsprekers hoorbaar zijn.
