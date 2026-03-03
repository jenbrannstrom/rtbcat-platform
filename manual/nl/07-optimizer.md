# Hoofdstuk 7: De Optimizer (BYOM)

*Doelgroep: media-inkopers, optimalisatie-engineers*

De optimizer is de geautomatiseerde optimalisatie-engine van Cat-Scan. "BYOM" staat
voor Bring Your Own Model: u registreert een extern scoring-endpoint, en Cat-Scan
gebruikt dit om voorstellen voor configuratiewijzigingen te genereren.

## Hoe het werkt

```
  Score          Voorstel       Beoordelen     Toepassen
────────────> ────────────> ────────────> ────────────>
Uw model       Cat-Scan       U (mens)       Google AB
evalueert      genereert      keurt goed     configuratie
segmenten      configuratie-  of wijst af    wordt
               wijzigingen                   bijgewerkt
```

1. **Score**: Cat-Scan stuurt segmentdata naar uw model-endpoint. Het model
   retourneert een score per segment (geo, formaat, uitgever).
2. **Voorstel**: Op basis van scores genereert Cat-Scan specifieke pretargeting-
   configuratiewijzigingen (bijv. "sluit deze 5 geo's uit", "voeg deze 3 formaten toe").
3. **Beoordelen**: U ziet het voorstel met verwachte impact. U keurt goed of
   wijst af.
4. **Toepassen**: Goedgekeurde voorstellen worden toegepast op de pretargeting-
   configuratie aan de kant van Google. De wijziging wordt vastgelegd in de geschiedenis.

## Modelbeheer

### Een model registreren

Ga naar `/settings/system` en zoek het gedeelte Optimizer.

1. Klik op **Register Model**.
2. Vul in: naam, modeltype, endpoint-URL (uw scoringservice).
3. Het endpoint moet POST-verzoeken met segmentdata accepteren en gescoorde
   resultaten retourneren.
4. Sla op.

### Het endpoint valideren

Test uw model voordat u het activeert:

1. Klik op **Validate endpoint** op de modelkaart.
2. Cat-Scan stuurt een testpayload naar uw endpoint.
3. De resultaten tonen: responstijd, geldigheid van het responsformaat, scoreverdeling.
4. Los eventuele problemen op voordat u activeert.

### Activeren en deactiveren

- **Activeren**: het model wordt de actieve scorer voor deze seat.
- **Deactiveren**: het model wordt niet meer gebruikt, maar de configuratie
  blijft bewaard. Er kan slechts een model tegelijk actief zijn per seat.

## Werkstroom-presets

Bij het uitvoeren van score-en-voorstel kiest u een preset:

| Preset | Gedrag | Wanneer te gebruiken |
|--------|--------|----------------------|
| **Veilig** | Stelt alleen wijzigingen voor met hoge betrouwbaarheid en laag risico. Kleinere verbeteringen, kleinere kans op fouten. | Eerste keer dat u de optimizer gebruikt, of bij conservatieve accounts. |
| **Gebalanceerd** | Gemiddelde betrouwbaarheidsdrempel. Goede balans tussen impact en veiligheid. | Standaard voor de meeste toepassingen. |
| **Agressief** | Stelt grotere wijzigingen voor met hogere potentiele impact. Meer risico op overoptimalisatie. | Ervaren gebruikers die dagelijks monitoren en snel kunnen terugdraaien. |

## Economie

De optimizer houdt ook de economische aspecten van optimalisatie bij:

- **Effectieve CPM**: wat u daadwerkelijk betaalt per duizend impressies,
  rekening houdend met verspilling.
- **Hostingkosten-basislijn**: de infrastructuurkosten van uw bidder, geconfigureerd
  in de optimizer-setup. Wordt gebruikt om te berekenen of besparingen door
  QPS-reductie opwegen tegen de hosting.
- **Efficientiesamenvatting**: totaalverhouding van nuttige QPS tot totale QPS.

Configureer uw hostingkosten bij `/settings/system` > Optimizer Setup.

## Voorstellen beoordelen

Elk voorstel toont:
- **Segmentscores** die de aanbeveling hebben gestuurd
- **Specifieke wijzigingen** aan pretargeting-velden (toevoegingen, verwijderingen, updates)
- **Verwachte impact** op QPS, verspillingsratio en uitgaven

U kunt:
- **Approve**: markeer het voorstel als geaccepteerd
- **Apply**: pas de goedgekeurde wijzigingen toe bij Google
- **Reject**: verwerp het voorstel
- **Check apply status**: controleer of de wijzigingen aan de kant van Google zijn doorgevoerd

## Gerelateerd

- [Pretargeting-configuratie](06-pretargeting.md): de configuraties die de optimizer
  aanpast
- [Conversies en attributie](08-conversions.md): conversiedata verbetert de
  scoringskwaliteit
- [Uw rapporten lezen](10-reading-reports.md): de impact van de optimizer volgen
