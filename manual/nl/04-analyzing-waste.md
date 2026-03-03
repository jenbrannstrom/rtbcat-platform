# Hoofdstuk 4: Verspilling analyseren per dimensie

*Doelgroep: mediakopers, campagnemanagers*

Zodra u weet *hoeveel* verspilling u heeft (via de [trechter](03-qps-funnel.md)),
laten deze drie weergaven zien *waar* het vandaan komt.

## Geografische verspilling (`/qps/geo`)

Toont QPS-verbruik en prestaties per land en stad.

![Geografische QPS-uitsplitsing per land](images/screenshot-geo-qps.png)

**Waar u op moet letten:**
- Landen met hoge QPS maar nul of vrijwel nul winsten. Google stuurt u
  verkeer uit regio's die uw kopers niet targeten.
- Steden met een onevenredig groot QPS-aandeel maar lage uitgaven --
  long-tail-geo's die volume toevoegen maar geen waarde.

**Wat u eraan kunt doen:**
- Voeg ondermaats presterende geo's toe aan uw pretargeting-uitsluitingslijst.
  Zie [Pretargeting-configuratie](06-pretargeting.md).

**Bedieningselementen:** Periodeselector (7/14/30 dagen), seat-filter.

## Uitgeververspilling (`/qps/publisher`)

Toont prestaties uitgesplitst naar uitgeversdomein of app.

![Uitgever-QPS met winstpercentage-analyse](images/screenshot-pub-qps.png)

**Waar u op moet letten:**
- Domeinen met hoog biedvolume maar nul impressies. Uw bidder besteedt
  rekenkracht aan inventaris die nooit wordt weergegeven.
- Apps of sites met abnormaal lage winstpercentages. U biedt maar verliest
  consequent, wat betekent dat u rekentijd voor biedevaluatie verspilt.
- Bekende domeinen van lage kwaliteit.

**Wat u eraan kunt doen:**
- Blokkeer specifieke uitgevers in de deny-lijst van uw pretargeting-configuratie.
  De uitgever-editor van Cat-Scan maakt dit eenvoudiger dan de Authorized
  Buyers-interface.

**Bedieningselementen:** Periodeselector, geo-filter, zoeken op domein.

## Formaatverspilling (`/qps/size`)

Toont welke advertentieformaten verkeer ontvangen en of u daarvoor creatives heeft.

![Uitsplitsing QPS per formaat](images/screenshot-size-qps.png)

**Waar u op moet letten:**
- Formaten met hoge QPS maar **geen bijpassende creative**. Google stuurt
  circa 400 verschillende advertentieformaten. Als u vaste display-advertenties
  draait (geen HTML), zijn de meeste van die formaten irrelevant. Elk verzoek
  voor een niet-overeenkomend formaat is pure verspilling.
- Formaten met creatives die onderpresteren. Overweeg of de creative-assets
  geschikt zijn voor dat formaat.

**Wat u eraan kunt doen:**
- Voeg irrelevante formaten toe aan de uitsluitingslijst van uw pretargeting.
  Dit is de optimalisatie met de grootste hefboomwerking voor display-kopers.

**Bedieningselementen:** Periodeselector, seat-filter, dekkingsuitsplitsingsdiagram.

## Dimensies combineren

De drie weergaven zijn complementair. Een typische optimalisatiecyclus:

1. Controleer **geo**: sluit landen uit die u niet nodig heeft.
2. Controleer **uitgever**: blokkeer domeinen die biedingen verspillen.
3. Controleer **formaat**: sluit formaten uit zonder bijpassende creative.
4. Pas wijzigingen toe via [Pretargeting-configuratie](06-pretargeting.md)
   met dry-run-preview.
5. Wacht één datacyclus (doorgaans één dag) en controleer de trechter opnieuw.

## Gerelateerd

- [Uw QPS-trechter begrijpen](03-qps-funnel.md): het startpunt
- [Pretargeting-configuratie](06-pretargeting.md): handelen op basis van
  verspillingsbevindingen
- [Uw rapporten lezen](10-reading-reports.md): de impact volgen
