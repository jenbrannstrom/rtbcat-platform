# Kapitel 10: Læs dine rapporter

*Målgruppe: medieindkøbere, kampagneansvarlige*

Dette kapitel forklarer analysepanelerne i Cat-Scan, og hvordan du
fortolker tallene.

## Forbrugsstatistik

Tilgængelig på forsiden og i konfigurationsdetaljer.

| Metrik | Hvad den fortæller dig |
|--------|----------------------|
| **Samlet forbrug** | Bruttoforbrug henover den valgte periode og seat. |
| **Forbrugstendens** | Nylig periode vs. foregående periode. Stigende forbrug med flade gevinster = omkostningsinflation. |
| **Forbrug pr. konfiguration** | Hvilken pretargeting-konfiguration er ansvarlig for hvor meget forbrug. Hjælper med at identificere, hvilke konfigurationer der skal optimeres først. |

## Konfigurationsydelse

Viser, hvordan hver pretargeting-konfiguration har klaret sig over tid.

- **Daglig fordeling**: visninger, klik, forbrug, vindrate, CTR
  og CPM pr. konfiguration over den valgte periode.
- **Tendenslinjer**: spot konfigurationer, hvis ydelse er faldende.
- **Feltfordeling**: hvilke specifikke felter (geografier, størrelser, formater) inden for en
  konfiguration, der driver tallene.

## Endpoint-effektivitet

Viser QPS-udnyttelse pr. bidder-endpoint.

- **Effektivitetsforhold**: nyttigt QPS / totalt QPS. Tættere på 1,0 er bedre.
- **Fordeling pr. endpoint**: hvis din bidder har flere endpoints, se hvilke
  der er mest og mindst effektive.
- Brug dette til at afgøre, om konsolidering af endpoints ville hjælpe.

## Snapshot-sammenligninger

Efter tilbagerulning af en pretargeting-ændring (eller anvendelse af en ny) viser
snapshot-sammenligningspanelet:

- **Før**: konfigurationstilstand før ændringen
- **Efter**: konfigurationstilstand efter ændringen
- **Delta**: hvad der præcis ændrede sig (felter tilføjet/fjernet/ændret)

Dette er nyttigt til analyse efter ændringer: "Jeg ekskluderede 5 geografier i går,
så hvad skete der med min tragt?"

## Anbefalede optimeringer

Cat-Scan kan vise AI-genererede anbefalinger baseret på dine data. Disse
foreslår specifikke konfigurationsændringer med estimeret effekt. Det er forslag,
ikke automatiske handlinger. Du vælger altid selv, om du vil anvende dem.

## Tips til læsning af rapporter

1. **Tjek altid periodevalget.** En 7-dages visning og en 30-dages visning kan
   fortælle meget forskellige historier.
2. **Sammenlign konfigurationer, kig ikke kun på totaler.** Én dårlig konfiguration kan trække
   de samlede tal ned, mens andre konfigurationer klarer sig godt.
3. **Se på tendenser, ikke øjebliksbilleder.** En enkelt dags data er støjfyldt. Tendenser
   over 7-14 dage er mere pålidelige.
4. **Krydsreferer dimensioner.** Højt spild i geografivisning + højt spild i størrelsesvisning
   for den samme konfiguration = to separate optimeringsmuligheder.

## Relateret

- [Forstå din QPS-tragt](03-qps-funnel.md): opsummeringsvisningen
- [Analyse af spild pr. dimension](04-analyzing-waste.md): dyk ned i
  specifikke spildkilder
- [Pretargeting-konfiguration](06-pretargeting.md): handl på rapportfund
