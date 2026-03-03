# Hoofdstuk 9: Data importeren

*Doelgroep: media-inkopers, campagnemanagers*

De analyse van Cat-Scan is volledig afhankelijk van prestatiedata uit Google Authorized
Buyers. Omdat Google geen Reporting API biedt, komen alle data uit CSV-exports.
Dit hoofdstuk legt uit hoe u data in Cat-Scan krijgt en hoe u controleert of
deze binnenkomt.

## Waarom dit belangrijk is

Zonder geimporteerde data heeft Cat-Scan niets om te analyseren. De funnel,
verspillingsweergaven, creatieve prestaties en de optimizer zijn allemaal afhankelijk
van actuele CSV-data. Als uw data verouderd is, baseert u beslissingen op oude
informatie.

## Twee manieren waarop data binnenkomt

### 1. Handmatige CSV-upload (`/import`)

Sleep een CSV-bestand dat uit Google Authorized Buyers is geexporteerd naar het uploadvak.

![Data-importpagina met uploadzone en versheidsraster](images/screenshot-import.png)

**Werkwijze:**

1. Exporteer het rapport vanuit uw Google Authorized Buyers-account.
2. Ga naar `/import` in Cat-Scan.
3. Sleep het bestand naar de dropzone (of klik om te bladeren).
4. Cat-Scan **detecteert automatisch het rapporttype** en toont een voorbeeld:
   - Vereiste kolommen vs. gevonden kolommen
   - Aantal rijen en datumbereik
   - Eventuele validatiefouten
5. Bekijk het voorbeeld. Als kolommen opnieuw toegewezen moeten worden, gebruik
   dan de kolomtoewijzingseditor.
6. Klik op **Import**.
7. Een voortgangsbalk toont de uploadstatus. Bestanden groter dan 5MB worden
   automatisch in delen geupload.
8. De resultaten tonen: geimporteerde rijen, overgeslagen duplicaten, eventuele fouten.

**Rapporttypen** worden automatisch gedetecteerd:

| Type | CSV-naampatroon | Wat het bevat |
|------|-----------------|---------------|
| bidsinauction | `catscan-report-*` | Dagelijkse RTB-prestaties: impressies, biedingen, wins, uitgaven |
| quality | `catscan-report-*` (kwaliteitsmetrieken) | Kwaliteitssignalen: zichtbaarheid, fraude, merkveiligheid |
| pipeline-geo | `*-pipeline-geo-*` | Geografische verdeling van de biedstroom |
| pipeline-publisher | `*-pipeline-publisher-*` | Verdeling per uitgeversdomein |
| bid-filtering | `*-bid-filtering-*` | Redenen en volumes van biedfiltering |

### 2. Automatische Gmail-import

Cat-Scan kan rapporten automatisch opnemen vanuit een gekoppeld Gmail-account.

- Google Authorized Buyers stuurt dagelijkse rapporten per e-mail.
- De Gmail-integratie van Cat-Scan leest deze e-mails en importeert de
  CSV-bijlagen automatisch.
- Controleer de status bij `/settings/accounts` > Gmail Reports-tab, of via
  `/gmail/status` in de API.

**Controleren of Gmail-import werkt:**
- Controleer het Gmail Status-paneel: `last_reason` moet `running` zijn.
- Controleer het `unread`-aantal: een groot aantal ongelezen e-mails kan erop
  wijzen dat de import vastloopt.
- Controleer de importgeschiedenis op recente vermeldingen.

## Versheidsraster

Het versheidsraster (zichtbaar op `/import` en gebruikt door de runtime health
gate) toont een **datum x rapporttype-matrix**:

```
              bidsinauction   quality   pipeline-geo   pipeline-publisher   bid-filtering
2026-03-02    imported        missing   imported       imported             imported
2026-03-01    imported        missing   imported       imported             imported
2026-02-28    imported        imported  imported       imported             imported
...
```

- **imported**: Cat-Scan heeft data voor deze datum en dit rapporttype.
- **missing**: geen data gevonden. Het rapport is niet geexporteerd, niet
  ontvangen door Gmail, of de import is mislukt.

**Dekkingspercentage** vat samen hoe compleet uw data is over het
terugkijkvenster. De runtime health gate gebruikt dit om te bepalen of het
systeem operationeel is.

## Deduplicatie

Dezelfde CSV opnieuw importeren (of Gmail hetzelfde e-mailbericht opnieuw laten
verwerken) zorgt er **niet** voor dat data dubbel geteld wordt. Elke rij wordt
gehasht en duplicaten worden bij het invoegen overgeslagen. Dit betekent dat
opnieuw importeren altijd veilig is.

## Importgeschiedenis

De tabel met importgeschiedenis op `/import` toont de laatste 20 imports:

- Tijdstempel
- Bestandsnaam
- Aantal rijen
- Importtrigger (handmatige upload vs. gmail-auto)
- Status (voltooid, mislukt, duplicaat)

## Probleemoplossing

| Probleem | Wat te controleren |
|----------|-------------------|
| "Missing"-cellen in het versheidsraster | Is het rapport op die datum uit Google geexporteerd? Controleer Gmail voor de e-mail. |
| Import mislukt met validatiefout | Kolommen komen niet overeen. Controleer de tabel met vereiste kolommen ten opzichte van uw CSV. |
| Gmail-import toont "stopped" | Controleer `/settings/accounts` > Gmail-tab. Mogelijk moet de import opnieuw gestart of opnieuw geautoriseerd worden. |
| Dekkingspercentage daalt | Rapporten komen binnen, maar voor minder datums dan verwacht. Controleer het exportschema in Google AB. |

## Gerelateerd

- [Uw QPS-funnel begrijpen](03-qps-funnel.md): is afhankelijk van geimporteerde data
- [Uw rapporten lezen](10-reading-reports.md): wat u kunt doen met de data
  na import
- Voor DevOps: internals en probleemoplossing van data-versheidsquery's, zie
  [Databasebeheer](14-database.md) en [Probleemoplossing](15-troubleshooting.md).
