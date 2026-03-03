# Kapitel 9: Dataimport

*Målgruppe: medieindkøbere, kampagneansvarlige*

Cat-Scans analyse afhænger helt af ydelsesdata fra Google Authorized
Buyers. Da Google ikke tilbyder et Reporting API, kommer alle data fra CSV-
eksporter. Dette kapitel forklarer, hvordan du får data ind i Cat-Scan, og hvordan du
verificerer, at de ankommer.

## Hvorfor dette er vigtigt

Uden importerede data har Cat-Scan intet at analysere. Tragten, spildvisninger,
kreativ ydelse og optimeringsværktøjet afhænger alle af friske CSV-data. Hvis
dine data er forældede, er dine beslutninger baseret på gammel information.

## To måder data ankommer på

### 1. Manuel CSV-upload (`/import`)

Træk og slip en CSV-fil eksporteret fra Google Authorized Buyers.

![Dataimportside med uploadzone og ferskhedsgitter](images/screenshot-import.png)

**Arbejdsgang:**

1. Eksporter rapporten fra din Google Authorized Buyers-konto.
2. Gå til `/import` i Cat-Scan.
3. Træk filen ind i dropzonen (eller klik for at gennemse).
4. Cat-Scan **registrerer automatisk rapporttypen** og viser en forhåndsvisning:
   - Påkrævede kolonner vs. fundne kolonner
   - Rækkeantal og datointerval
   - Eventuelle valideringsfejl
5. Gennemgå forhåndsvisningen. Hvis kolonner skal ommappes, brug kolonne-
   mapping-editoren.
6. Klik på **Import**.
7. En fremskridtslinje viser uploadstatus. Filer over 5 MB uploades automatisk
   i bidder.
8. Resultater viser: importerede rækker, oversprungne dubletter, eventuelle fejl.

**Rapporttyper**, der registreres automatisk:

| Type | CSV-navnemønster | Hvad den indeholder |
|------|-----------------|---------------------|
| bidsinauction | `catscan-report-*` | Daglig RTB-ydelse: visninger, bud, gevinster, forbrug |
| quality | `catscan-report-*` (kvalitetsmetrikker) | Kvalitetssignaler: synlighed, svindel, brandsikkerhed |
| pipeline-geo | `*-pipeline-geo-*` | Geografisk fordeling af budstrømmen |
| pipeline-publisher | `*-pipeline-publisher-*` | Fordeling pr. udgiverdomæne |
| bid-filtering | `*-bid-filtering-*` | Budfiltreringsårsager og -mængder |

### 2. Gmail-autoimport

Cat-Scan kan automatisk indlæse rapporter fra en tilknyttet Gmail-konto.

- Google Authorized Buyers sender daglige rapporter pr. e-mail.
- Cat-Scans Gmail-integration læser disse e-mails og importerer CSV-
  vedhæftningerne automatisk.
- Tjek status under `/settings/accounts` > Gmail Reports-fanen, eller via
  `/gmail/status` i API'et.

**For at verificere at Gmail-import virker:**
- Tjek Gmail Status-panelet: `last_reason` bør være `running`.
- Tjek `unread`-antal: et stort antal ulæste e-mails kan indikere, at
  importen hænger.
- Tjek importhistorikken for nylige poster.

## Dataferskhedsgitter

Dataferskhedsgitteret (synligt på `/import` og brugt af runtime-sundhedsporten)
viser en **dato x rapporttype-matrix**:

```
              bidsinauction   quality   pipeline-geo   pipeline-publisher   bid-filtering
2026-03-02    imported        missing   imported       imported             imported
2026-03-01    imported        missing   imported       imported             imported
2026-02-28    imported        imported  imported       imported             imported
...
```

- **imported**: Cat-Scan har data for denne dato og rapporttype.
- **missing**: ingen data fundet. Enten blev rapporten ikke eksporteret, ikke
  modtaget af Gmail, eller importen fejlede.

**Dækningsprocent** opsummerer, hvor komplette dine data er henover
tilbagekigsvinduet. Runtime-sundhedsporten bruger dette til at afgøre, om systemet
er operationelt.

## Deduplikering

Genimport af den samme CSV (eller at Gmail genbehandler den samme e-mail) tæller
**ikke** data dobbelt. Hver række hashes, og dubletter springes over ved
indsættelse. Det betyder, at det altid er sikkert at genimportere.

## Importhistorik

Importhistoriktabellen på `/import` viser de seneste 20 importer:

- Tidsstempel
- Filnavn
- Rækkeantal
- Importudløser (manuel upload vs. gmail-auto)
- Status (færdig, fejlet, dublet)

## Fejlsøgning

| Problem | Hvad der skal tjekkes |
|---------|----------------------|
| "Missing"-celler i ferskhedsgitteret | Blev rapporten eksporteret fra Google på den dato? Tjek Gmail for e-mailen. |
| Import fejler med valideringsfejl | Kolonneuoverensstemmelse. Tjek tabellen med påkrævede kolonner op mod din CSV. |
| Gmail-import viser "stopped" | Tjek `/settings/accounts` > Gmail-fanen. Skal måske genstartes eller genautentificeres. |
| Dækningsprocenten falder | Rapporter ankommer, men for færre datoer end forventet. Tjek eksportplanen i Google AB. |

## Relateret

- [Forstå din QPS-tragt](03-qps-funnel.md): afhænger af importerede data
- [Læs dine rapporter](10-reading-reports.md): hvad du kan gøre med
  dataene, når de er importeret
- For DevOps: interne data-ferskhedsforespørgsler og fejlsøgning, se
  [Databaseoperationer](14-database.md) og [Fejlsøgning](15-troubleshooting.md).
