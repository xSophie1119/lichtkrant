# v4.4.17 — lichtkranttest vindt ieder open scherm

- Vervangt de harde fout `Geen lichtkrant-tabblad verbonden` door een robuuste server-side display-opdrachtwachtrij.
- Test-, stop- en herhaalopdrachten krijgen een oplopend commandonummer en worden naast SSE kort op de backend bewaard.
- De lichtkrant pollt iedere circa 1,5 seconde als fallback en verwerkt daardoor ook opdrachten die tijdens een SSE-reconnect zijn verstuurd.
- Ieder lichtkrant-tabblad/browservenster krijgt een eigen sessie-client-id en meldt iedere 10 seconden een heartbeat.
- Beheer en lichtkrant hoeven niet in dezelfde browser of op hetzelfde apparaat te staan; ze moeten alleen dezelfde backend/installatie gebruiken.
- Dubbele aflevering via SSE + polling wordt met het commandonummer tegengehouden.
- Omroep-/deuntjetests blijven op een echte afspeelbevestiging wachten, zodat een gesloten lichtkrant niet ten onrechte als succesvol wordt gemeld.
