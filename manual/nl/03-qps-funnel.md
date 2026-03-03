# Hoofdstuk 3: Uw QPS-trechter begrijpen

*Doelgroep: mediakopers, campagnemanagers*

Dit is de startpagina van Cat-Scan (`/`). Alles begint hier.

## Wat u ziet

De QPS Waste Optimizer-pagina toont uw RTB-trechter (de reis van biedverzoek
naar uitgaven) en maakt zichtbaar waar het volume afneemt.

![Startpagina QPS Waste Optimizer](images/screenshot-qps-home.png)

### De trechter

| Fase | Wat het betekent |
|-------|---------------|
| **QPS** | Het maximale aantal biedverzoeken per seconde dat u Google vraagt te sturen. Google beperkt het werkelijke volume op basis van uw accountniveau, dus u ontvangt doorgaans minder dan uw limiet. |
| **Biedingen** | Hoeveel van die verzoeken uw bidder heeft gekozen om op te bieden. De rest werd afgewezen (verkeerde inventaris, geen bijpassende creative, onder de bodemprijs). |
| **Winsten** | Veilingen die uw bidder heeft gewonnen. U betaalt alleen voor winsten. |
| **Impressies** | Advertenties die daadwerkelijk aan gebruikers zijn vertoond na het winnen. |
| **Klikken** | Gebruikersinteracties met uw vertoonde advertenties. |
| **Uitgaven** | Totaal besteed bedrag aan gewonnen impressies. |

De kloof tussen elke fase is waar de optimalisatiekans ligt. Een grote
daling van QPS naar Biedingen betekent dat uw bidder het meeste afwijst
van wat Google stuurt -- klassieke verspilling die pretargeting kan verhelpen.

### Belangrijke statistieken

- **Winstpercentage**: Winsten / Biedingen. Hoe competitief uw biedingen zijn.
- **CTR**: Klikken / Impressies. Hoe aantrekkelijk uw creatives zijn.
- **CPM**: Kosten per duizend impressies. Wat u betaalt voor zichtbaarheid.
- **Verspillingsratio**: (QPS - Biedingen) / QPS. Het aandeel verkeer dat u niet kunt gebruiken.

### Pretargeting-configuratiekaarten

Onder de trechter ziet u kaarten voor elk van uw pretargeting-configuraties
(maximaal 10 per seat). Elke kaart toont:

- **Status**: Actief of Opgeschort
- **Maximale QPS**: Het plafond voor biedverzoeken dat deze configuratie accepteert
- **Formaten**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE
- **Platformen**: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV
- **Geo's**: Opgenomen en uitgesloten geografische doelen
- **Formaten**: Opgenomen advertentieformaten (of alle indien ongefilterd)

### Bedieningselementen

- **Periodeselector**: 7, 14 of 30 dagen aan gegevens
- **Seat-filter**: beperken tot een specifieke buyer-seat
- **Config-schakelaar**: inzoomen op een specifieke pretargeting-configuratie

## Hoe u het leest

Begin met de verspillingsratio. Als deze boven de 50% ligt, heeft u
aanzienlijke ruimte voor verbetering. Kijk vervolgens welke configuraties de
meeste verspilling veroorzaken. Klik door naar de dimensieanalyses
([Geo](04-analyzing-waste.md), [Uitgever](04-analyzing-waste.md),
[Formaat](04-analyzing-waste.md)) om de specifieke bronnen te vinden.

## Gerelateerd

- [Verspilling analyseren per dimensie](04-analyzing-waste.md): inzoomen op
  geo, uitgever en formaat
- [Pretargeting-configuratie](06-pretargeting.md): actie ondernemen op basis
  van uw bevindingen
