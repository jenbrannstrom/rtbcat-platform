# Hoofdstuk 8: Conversies en attributie

*Doelgroep: media-inkopers, campagnemanagers*

Conversietracking stelt Cat-Scan in staat te meten wat er na een impressie
gebeurt: heeft de gebruiker een waardevolle actie uitgevoerd? Deze data voedt de
scoring van de optimizer en helpt u de werkelijke campagneprestaties te evalueren.

## Conversiebronnen

Cat-Scan ondersteunt twee integratiemethoden:

### Pixel

Een trackingpixel wordt geactiveerd op uw conversiepagina (bijv. bevestiging van bestelling).

- Endpoint: `/api/conversions/pixel`
- Parameters: `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- Er is geen server-side configuratie nodig, behalve het plaatsen van de pixel op uw pagina.

### Webhook

Uw server stuurt conversie-events naar het webhook-endpoint van Cat-Scan.

- Betrouwbaarder dan pixels (geen adblockers, geen client-side afhankelijkheden).
- Vereist server-side integratie.
- Ondersteunt HMAC-handtekeningverificatie voor beveiliging.

## Webhookbeveiliging

Cat-Scan biedt gelaagde webhookbeveiliging:

| Functie | Wat het doet |
|---------|-------------|
| **HMAC-verificatie** | Elk webhookverzoek wordt ondertekend met een gedeeld geheim. Cat-Scan weigert niet-ondertekende of verkeerd ondertekende verzoeken. |
| **Rate limiting** | Voorkomt misbruik door verzoeken per tijdsvenster te begrenzen. |
| **Versheidsmonitoring** | Waarschuwt als webhook-events niet meer binnenkomen (staleness-detectie). |

Configureer webhookbeveiliging bij `/settings/system` > Conversion Health.

## Gereedheidscontrole

Controleer de gereedheid voordat u op conversiedata vertrouwt:

1. Ga naar `/settings/system` of de setup-checklist.
2. Controleer **Conversion Readiness**: toont of een bron verbonden is en events
   levert binnen het verwachte versheidsvenster.
3. Controleer **Ingestion Stats**: event-aantallen per brontype en tijdsperiode.

## Conversiegezondheid

Het paneel Conversion Health toont:

- Ingestiestatus (ontvangt events of niet)
- Aggregatiestatus (events worden verwerkt tot metriek)
- Tijdstempel van het laatste event
- Foutaantallen indien van toepassing

## Gerelateerd

- [De Optimizer](07-optimizer.md): conversiedata verbetert de scoringsnauwkeurigheid
- [Data importeren](09-data-import.md): een ander pad voor data-invoer
- Voor DevOps: webhook-endpointconfiguratie en probleemoplossing, zie
  [Integraties](17-integrations.md).
