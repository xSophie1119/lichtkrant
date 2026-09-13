# Lichtkrantstudio — v4.8.0

Open **Bedienpaneel → Beheer → Lichtkrantstudio**, of `/studio.html` op de lichtkrant-pc of je gekoppelde telefoon. Bedienrechten zijn nodig. De studio opent met de nieuwe regels, omroepopbouw en schermindeling uitgeschakeld: je bestaande instellingen blijven actief totdat je jouw ontwerp toepast.

## Werkgebieden en regels

Zoek een plaats, teken minimaal drie hoeken en bewaar het gebied. Via **Verplaatsen** sleep je de kaart; plus/min wijzigt de schaal. Een gebied kan een eindtijd hebben. Je kunt de vorm later aanpassen. Kaarttegels gebruiken dezelfde PDOK-laag als de bestaande incidentkaart; tekenen vergt beschikbare kaarttegels. De opgeslagen grens is een lokaal coördinatenpolygoon.

Maak regels van boven naar beneden, bijvoorbeeld:

1. Bijzondere inzet **OvDG** → tonen.
2. Dienst **ambulance** → verbergen.
3. Dienst **brandweer**, gebied **Tilburg** → tonen.
4. Dienst **brandweer**, minimale opschaling **Groot**, groter gebied → tonen met voorrang.

**De eerste passende regel wint. Alle ingevulde voorwaarden binnen die regel moeten overeenkomen.** Regels vervangen alleen de plaats-, dienst- en zoekwoordfilters van het scherm. De bronselectie uit de wizard, oefen-/urgentieprofielen, tijdvensters voor omroep, dempen, ouderdom en duplicaatcontrole blijven gelden. Een bron die je niet ophaalt kan de studio niet alsnog tonen.

Bij onbekende locatie geldt de ingestelde keuze zodra de eerste mogelijk passende gebiedsregel wordt bereikt. De monitor probeert alleen een kaartzoekopdracht wanneer de overige voorwaarden van een gebiedsregel passen. Hiervoor geldt op het scherm maximaal 2,5 seconden wachttijd; gevonden locaties en mislukte pogingen worden tijdelijk gecachet. De bronopslag wacht niet op deze kaartzoekopdracht. Een gevonden straatpunt is geen garantie voor het exacte huisnummer. Controleer de gebieden met voorbeelden, vooral langs grenzen.

**Controleer deze melding** toont de herkenning, winnaar en lagere regels. **Test laatste 100** gebruikt opgeslagen coördinaten, zonder honderd nieuwe kaartzoekopdrachten te starten. Onbekende locaties worden apart geteld.

## Waarom deze melding?

Het log begint bij installatie van v4.8.0 en bewaart de laatste 2.000 unieke ontvangsten, inclusief meldingen die de bronselectie afwijst. Iedere melding bevat de oorspronkelijke herkenning, lokale correctie, ontvangsttijd en de toenmalige instellingen. Herhaalde RSS-items worden niet telkens opnieuw naar schijf geschreven.

Schermen melden waarom zij een melding doorgeven of tegenhouden: bronselectie, schermregel, profiel, opstartgeschiedenis, ouderdom, duplicaat of een vastgezette melding. Er kunnen meerdere schermbeslissingen zijn. **Doorgegeven aan scherm** is een softwarebeslissing, geen meting van de fysieke tv. Bij ontbrekende terugmelding staat dat expliciet vermeld.

Vanuit het log kun je de melding openen in de regelbouwer of de parsercorrectie-editor.

## Omroepopbouw

Voeg onderdelen toe zoals `{incident}`, `{where}`, `{city}`, `{location}`, `{priority}`, `{scale}`, `{units}` en `{service}`. Zelf geschreven tekst en de volgorde blijven behouden. Lege onderdelen verdwijnen uit de tekst. De attentietoon gebruikt de bestaande tooninstellingen; per regel kan een andere diensttoon of geen toon worden gekozen.

Het tekstvoorbeeld gebruikt de echte lichtkrantfuncties in een inactief document, inclusief voertuigcatalogus en uitspraakwoordenboek. Dat document start geen monitor, ontvangst, audio of testopdracht. **Beluister op dit apparaat** leest die tekst met de browserstem van je telefoon/pc; die stem kan anders zijn dan die van het scherm. Het luistervoorbeeld speelt geen attentietoon.

Een eigen omroepopbouw vervangt ook de automatische verkorte vervolgtekst. Laat de eigen opbouw uit als je de bestaande automatische incidentteksten wilt gebruiken.

## Parsercorrecties en eigen regressievoorbeelden

Een exacte correctie past op dezelfde oorspronkelijke tekst, ongeacht hoofdletters. Een brede correctie zoekt een letterlijk fragment van minimaal acht tekens. De nieuwste passende correctie wint. Je kunt plaats, locatie, dienst, prioriteit of de voertuigenlijst corrigeren. Roepnummers voer je gescheiden door komma's in; een lege voertuigenlijst verwijdert de herkende voertuigen. De bestaande disciplinecontrole blijft actief, waaronder het verbod op brandweervoertuigen bij ambulanceprioriteiten buiten Baarle.

**Bekijk effect** toont zowel jouw voorbeeld als getroffen meldingen uit de laatste honderd ontvangsten. Daarna kun je de correctie bewaren. Veranderen de instellingen tussendoor, dan moet je opnieuw de verschillen bekijken. Correcties gelden voor nieuwe ontvangsten; het historische archief wordt niet herschreven.

Iedere correctie bewaart een eigen voorbeeld met de verwachte velden. **Controleer alle eigen testvoorbeelden** draait ze met de geïnstalleerde parser. Verwijderde correcties laten hun voorbeelden achter: zo zie je wanneer de parser het nog niet zelfstandig goed doet. Deze persoonlijke gegevens blijven lokaal en worden niet op GitHub gezet. De GitHub-tests controleren het correctiemechanisme en representatieve parsergevallen; je persoonlijke voorbeelden controleer je in de studio.

## Schermontwerper

Maak afzonderlijke scènes voor rust, één incident en meerdere incidenten. Blokken: melding, kaart, voertuigen, klok en incidentoverzicht. Sleep of gebruik de velden voor links/boven/breedte/hoogte. Met toetsenbordpijlen verplaats je een geselecteerd blok; Shift maakt de stap groter.

De editor en de echte lichtkrant gebruiken dezelfde canvasrenderer. Tekst blijft op minimaal de gekozen grootte, geschaald naar schermbreedte. Langere tekst wisselt iedere 6,5 seconden van pagina. De editor waarschuwt wanneer voorbeeldtekst meerdere pagina's nodig heeft. De losse kaartlaag wordt op het aangegeven blok gelegd; de canvasvoorvertoning bevat een kaartplaatsaanduiding. Het bestaande donkere scherm en de nachtregeling blijven werken.

De gekozen beeldverhouding stelt de ontwerpvoorvertoning in. De tv gebruikt zijn werkelijke afmetingen; kies dus de verhouding die bij jouw scherm hoort. De studio verandert geen Windows-/Linux-beeldschermresolutie.

## Opnamen terugspelen

Selecteer een periode op basis van **ontvangsttijd** en geef de opname een naam. Maximaal de 500 recentste ontvangsten uit die periode worden opgenomen, met toenmalige ontwerpen en schermbeslissingen. De laatste twintig opnamen blijven bewaard. De lopende registratie en de opnamen zijn begrensd; identieke instellingensnapshots worden gedeeld om schijf- en geheugengebruik te beperken.

De speler heeft pauze, volgende melding, een schuifbalk en 1×/10×/60×/300× snelheid. Je kunt de destijds opgeslagen regels/indeling vergelijken met het huidige ontwerp. De ontvangstintervallen bepalen het tempo. De speler draait volledig binnen de studio, zonder geluid, live invoer of opdrachten aan andere schermen.

De simulatie berekent per melding bron-, profiel-, gebieds- en ouderdomscontroles. De daadwerkelijke historische schermbeslissing staat erbij voor opstart-, duplicaat- en vastzetgedrag. Dit is geen video-opname: kaarttegels, audio en de volledige historische carrousel worden niet gereconstrueerd.

## Opslaan en herstel

Ontwerpen worden pas actief na **Wijzigingen toepassen**. Niet-toegepaste wijzigingen blijven tijdens die tabsessie beschikbaar. Een ander apparaat kan je ontwerp niet stil overschrijven: opslaan controleert de versie. Gebruik **Opgeslagen versie laden** als je het ontwerp wilt vervangen door de laatst opgeslagen versie.

Studio-ontwerpen, correcties en testvoorbeelden staan in `data/studio/design.json`; het log en de opnamen in `data/studio/recorder.sqlite3`. De updater behoudt `data`. De bestaande herstelpunten voor gewone lichtkrantinstellingen bevatten geen studio-ontwerpen. Maak voor een volledige eigen back-up een kopie van `data` wanneer de monitor is gestopt.
