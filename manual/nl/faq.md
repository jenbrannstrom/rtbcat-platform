# Veelgestelde vragen

Vragen zijn gelabeld per doelgroep: **[Koper]** voor mediakopers en campagne-
managers, **[DevOps]** voor platformengineers, **[Beide]** voor gedeelde vragen.

---

### [Koper] Waarom is mijn dekkingspercentage lager dan 100%?

Dekking meet hoeveel datum x rapporttype-cellen data bevatten versus hoeveel
er verwacht worden. Veelvoorkomende oorzaken van hiaten:

- **Google heeft voor die datum geen rapport verzonden** (feestdag, exportvertraging).
- **Gmail-import heeft de e-mail gemist** (controleer de Gmail-status).
- **Een specifiek rapporttype is niet beschikbaar** voor uw stoel (bijv.
  kwaliteitsdata bestaat mogelijk niet voor alle kopers).

Controleer het dataversheidsraster op `/import` om precies te zien welke cellen
ontbreken. Zie [Data-import](09-data-import.md).

### [Koper] Wat is het verschil tussen "verspilling" en "laag winstpercentage"?

**Verspilling** = biedverzoeken die uw bidder *heeft afgewezen* zonder te bieden.
Dit is QPS waarvoor u hebt betaald maar die u helemaal niet kon gebruiken. Los
dit op met pretargeting.

**Laag winstpercentage** = biedverzoeken waarop uw bidder *heeft geboden* maar
de veiling verloor. Dit betekent dat uw biedingen niet concurrerend genoeg zijn.
Los dit op met biedstrategie, niet met pretargeting.

Beide verschijnen in de funnel maar vereisen verschillende acties. Zie
[Inzicht in uw QPS-funnel](03-qps-funnel.md).

### [Koper] Kan ik een pretargetingwijziging ongedaan maken?

Ja. Ga naar `/history`, zoek de wijziging, klik op "Voorbeeld terugdraaien"
om te zien wat wordt teruggedraaid en bevestig vervolgens. Het terugdraaien
zelf wordt ook vastgelegd. Zie [Pretargeting-configuratie](06-pretargeting.md).

### [Koper] Hoe vaak moet ik data opnieuw importeren?

Dagelijks. Gmail auto-import regelt dit automatisch. Als u handmatig importeert,
doe dit dan eenmaal per dag nadat de rapporten zijn binnengekomen. Verouderde
data leidt tot verouderde beslissingen.

### [Koper] Wat verandert de optimizer precies?

De optimizer stelt wijzigingen voor aan uw pretargeting-configuraties: het
toevoegen of verwijderen van geo's, formaten, uitgevers, enz. Hij past nooit
automatisch wijzigingen toe. U beoordeelt en keurt elk voorstel goed. Zie
[De Optimizer](07-optimizer.md).

---

### [DevOps] Waarom is de runtime health strict gate mislukt?

Controleer de workflowlogs: `gh run view <id> --log-failed`. Zoek naar FAIL vs.
BLOCKED:

- **FAIL** = er is iets misgegaan. De data-freshness timeout en SET
  statement_timeout problemen zijn veelvoorkomende oorzaken. Zie
  [Probleemoplossing](15-troubleshooting.md).
- **BLOCKED** = een afhankelijkheid ontbreekt, niet noodzakelijk een codebug.
  Voorbeelden: geen kwaliteitsdata voor deze koper, voorstel heeft geen
  billing_id. Vergelijk met eerdere runs om regressies te onderscheiden van
  reeds bestaande hiaten.

### [DevOps] Waarom is het data-freshness endpoint traag?

De query scant `rtb_daily` (~84M rijen) en `rtb_bidstream` (~21M rijen). Als
het queryplan degradeert naar een sequentiële scan in plaats van de
`(buyer_account_id, metric_date DESC)` indexen te gebruiken, duurt het minuten.

Oplossing: zorg ervoor dat queries het `generate_series + EXISTS` patroon
gebruiken (14 indexlookups in plaats van een volledige tabelscan). Zie
[Database-operaties](14-database.md).

### [DevOps] Hoe controleer ik welke versie is uitgerold?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

Dit retourneert de git SHA en de image-tag. Vergelijk met uw commitlog.

### [DevOps] Hoe rol ik een fix uit?

1. Push naar `unified-platform`
2. Wacht tot `build-and-push.yml` slaagt
3. Trigger `deploy.yml` via `gh workflow run` met `confirm=DEPLOY`
4. Verifieer met `/api/health`

Zie [Uitrol](12-deployment.md) voor de volledige procedure.

### [DevOps] Gebruikers zitten vast in een inlogloop. Wat moet ik doen?

Controleer Cloud SQL Proxy: `sudo docker ps | grep cloudsql`. Als deze niet
draait, herstart hem, wacht 10 seconden en herstart vervolgens de
API-container. Zie [Probleemoplossing](15-troubleshooting.md) voor de
volledige procedure.

---

### [Beide] Waar komen de gegevens van Cat-Scan vandaan?

CSV-exports van Google Authorized Buyers. Er is geen Reporting API. Data komt
binnen via handmatige CSV-upload of automatische Gmail-ingestie. Zie
[Data-import](09-data-import.md).

### [Beide] Is het veilig om dezelfde CSV opnieuw te importeren?

Ja. Elke rij wordt gehasht en ontdubbeld. Opnieuw importeren telt nooit dubbel.

### [Beide] Welke talen ondersteunt de gebruikersinterface?

Engels, Nederlands en Chinees (vereenvoudigd). De taalkeuze bevindt zich in de
zijbalk.
