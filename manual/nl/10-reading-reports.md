# Hoofdstuk 10: Uw rapporten lezen

*Doelgroep: media-inkopers, campagnemanagers*

Dit hoofdstuk legt de analysepanelen in Cat-Scan uit en hoe u de cijfers
moet interpreteren.

## Uitgavenstatistieken

Beschikbaar op de startpagina en in configuratie-detailweergaven.

| Metriek | Wat het u vertelt |
|---------|-------------------|
| **Totale uitgaven** | Bruto-uitgaven over de geselecteerde periode en seat. |
| **Uitgaventrend** | Recente periode vs. vorige periode. Stijgende uitgaven bij gelijkblijvende wins = kosteninflatie. |
| **Uitgaven per configuratie** | Welke pretargeting-configuratie verantwoordelijk is voor welk deel van de uitgaven. Helpt te bepalen welke configuraties het eerst geoptimaliseerd moeten worden. |

## Configuratieprestaties

Toont hoe elke pretargeting-configuratie in de loop van de tijd heeft gepresteerd.

- **Dagelijkse verdeling**: impressies, klikken, uitgaven, winratio, CTR en
  CPM per configuratie over de geselecteerde periode.
- **Trendlijnen**: signaleer configuraties waarvan de prestaties achteruitgaan.
- **Veldverdeling**: welke specifieke velden (geo's, formaten, typen) binnen
  een configuratie de cijfers bepalen.

## Endpoint-efficientie

Toont het QPS-gebruik per bidder-endpoint.

- **Efficientieratio**: nuttige QPS / totale QPS. Dichter bij 1,0 is beter.
- **Verdeling per endpoint**: als uw bidder meerdere endpoints heeft, kunt u
  zien welke het meest en het minst efficient zijn.
- Gebruik dit om te bepalen of het consolideren van endpoints zou helpen.

## Snapshotvergelijkingen

Na het terugdraaien van een pretargeting-wijziging (of het toepassen van een nieuwe)
toont het snapshotvergelijkingspaneel:

- **Voor**: configuratiestatus voor de wijziging
- **Na**: configuratiestatus na de wijziging
- **Verschil**: wat er precies is veranderd (velden toegevoegd/verwijderd/gewijzigd)

Dit is handig voor analyse na een wijziging: "Ik heb gisteren 5 geo's uitgesloten,
dus wat is er met mijn funnel gebeurd?"

## Aanbevolen optimalisaties

Cat-Scan kan AI-gegenereerde aanbevelingen tonen op basis van uw data. Deze
suggereren specifieke configuratiewijzigingen met een geschatte impact. Het zijn
suggesties, geen automatische acties. U kiest altijd zelf of u ze toepast.

## Tips voor het lezen van rapporten

1. **Controleer altijd de periodeselector.** Een weergave van 7 dagen en een
   weergave van 30 dagen kunnen heel verschillende verhalen vertellen.
2. **Vergelijk configuraties, kijk niet alleen naar totalen.** Een slechte
   configuratie kan de totaalcijfers naar beneden trekken terwijl andere
   configuraties goed presteren.
3. **Kijk naar trends, niet naar momentopnames.** De data van een enkele dag
   bevat veel ruis. Trends over 7-14 dagen zijn betrouwbaarder.
4. **Combineer dimensies.** Hoge verspilling in de geoweergave + hoge
   verspilling in de formaatweergave voor dezelfde configuratie = twee aparte
   optimalisatiekansen.

## Gerelateerd

- [Uw QPS-funnel begrijpen](03-qps-funnel.md): de samenvattingsweergave
- [Verspilling analyseren per dimensie](04-analyzing-waste.md): inzoomen op
  specifieke verspillingsbronnen
- [Pretargeting-configuratie](06-pretargeting.md): actie ondernemen op basis van rapportbevindingen
