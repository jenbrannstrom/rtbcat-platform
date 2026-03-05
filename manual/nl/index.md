# Cat-Scan Gebruikershandleiding

## Het probleem in één plaatje

![QPS-funnel](../assets/qps-funnel.svg)

Google stuurt uw bidder een stortvloed aan biedverzoeken. Elke seconde stromen
tienduizenden queries vanuit de Authorized Buyers-exchange richting uw endpoint.
Uw bidder beoordeelt elk verzoek, beslist of hij biedt en antwoordt, allemaal
binnen enkele milliseconden.

Dit is wat de meeste mensen missen: **het overgrote deel van dat signaal is
ruis.** Een typische seat die 50.000 QPS ontvangt, kan ontdekken dat 30.000 van
die queries betrekking hebben op inventaris die de mediakoper nooit zou kopen:
verkeerde regio's, irrelevante uitgeverdomeinen, advertentieformaten zonder
passende creative. Uw bidder moet ze allemaal nog steeds ontvangen, parsen en
afwijzen. Dat kost bandbreedte, rekenkracht en geld.

Het diagram hierboven laat het zien als regenval. De QPS van Google is de
sproeikop bovenaan; de druppels waaieren uit over een groot oppervlak. Uw bidder
is de kleine emmer onderaan. Alles wat de emmer mist (de druppels die links en
rechts terechtkomen) is verspilling. U hebt ervoor betaald. U hebt er niets
voor teruggekregen.

**Cat-Scan bestaat om de emmer breder en de regen smaller te maken.**

Het doet dit door u inzicht te geven in waar de verspilling plaatsvindt (welke
geo's, welke uitgevers, welke advertentieformaten, welke creatives) en de
middelen om het aan de bron te stoppen, met behulp van de pretargeting-
configuraties die Google biedt.

### Waarom dit moeilijker is dan het klinkt

Google Authorized Buyers geeft u slechts **10 pretargeting-configuraties per
seat**, plus grove geografische groepen (Oost-VS, West-VS, Europa, Azië). Er is
geen Reporting API. Alle prestatiedata komt uit CSV-exports die per e-mail
binnenkomen. De AB pretargeting-UI zelf is functioneel, maar maakt het lastig
om het volledige beeld te zien over configuraties heen, of om een verkeerde
wijziging ongedaan te maken.

Cat-Scan overbrugt deze tekortkomingen:

- Het **herbouwt rapportages vanuit CSV-exports** (handmatige upload of
  automatische Gmail-ingestie), met ontdubbeling bij import zodat herverwerking
  nooit dubbel telt.
- Het toont de **volledige RTB-funnel**, van ruwe QPS via biedingen, gewonnen
  veilingen, impressies, klikken en bestedingen, uitgesplitst naar elke
  dimensie: geografie, uitgever, advertentieformaat, creative, configuratie.
- Het biedt **veilig pretargetingbeheer** met geschiedenis, gefaseerde
  wijzigingen, dry-run voorvertoning en terugdraaien met één klik.
- Het draait een **optimizer** die segmenten scoort en configuratiewijzigingen
  voorstelt, met workflowwaarborgen (veilig / gebalanceerd / agressief) zodat
  geen enkele wijziging live gaat zonder beoordeling.

### Voor wie deze handleiding is

Deze handleiding heeft twee sporen omdat Cat-Scan twee zeer verschillende
rollen bedient:

**Mediakopers en campagnemanagers** gebruiken Cat-Scan om te begrijpen waar hun
budget naartoe gaat, verspilling te vinden, creatives te beheren, pretargeting
af te stemmen en optimalisatievoorstellen goed te keuren. Zij denken in CPM,
winstpercentages en ROAS. Hun hoofdstukken richten zich op wat de UI laat zien,
wat de cijfers betekenen en welke acties ze moeten ondernemen.

**DevOps- en platformengineers** gebruiken Cat-Scan om het systeem uit te
rollen, te monitoren en problemen op te lossen. Zij denken in containers,
health-endpoints en queryplannen. Hun hoofdstukken richten zich op architectuur,
uitrolpipelines, database-operaties en incidentrunbooks.

Beide sporen delen een gemeenschappelijke basis (aan de slag, woordenlijst) en
de hoofdstukken verwijzen naar elkaar waar workflows overlappen. Een mediakoper
die meldt dat "dataversheid niet werkt" en een DevOps-engineer die de
onderliggende query debugt, moeten naar dezelfde woordenlijstvermelding kunnen
wijzen en elkaar begrijpen.

---

## Hoe u deze handleiding leest

- **Deel 0** is voor iedereen. Begin hier.
- **Deel I** is het mediakoperspoor. Als u werkt met campagnes, optimalisatie of
  inkoop, is dit uw pad.
- **Deel II** is het DevOps-spoor. Als u Cat-Scan uitrolt, monitort of beheert,
  is dit uw pad.
- **Deel III** is gedeelde referentie: woordenlijst, veelgestelde vragen en
  API-index.

U hoeft niet lineair te lezen. Elk hoofdstuk staat op zichzelf. Volg de links
die bij uw rol passen.

---

## Inhoudsopgave

### Deel 0: Aan de slag

Iedereen leest dit.

- [Hoofdstuk 0: Wat is Cat-Scan?](00-what-is-cat-scan.md)
  Wat het platform doet, voor wie het is en de kernconcepten die u nodig hebt
  voordat u verder gaat: seats, QPS, pretargeting, de RTB-funnel.

- [Hoofdstuk 1: Inloggen](01-logging-in.md)
  Authenticatiemethoden (Google OAuth, lokale accounts), de inlogpagina, wat te
  doen bij inlogproblemen en hoe de stoelkeuze werkt.

- [Hoofdstuk 2: Navigeren door het dashboard](02-navigating-the-dashboard.md)
  De zijbalk, stoel wisselen, taalkeuze, de setup-checklist voor nieuwe accounts
  en hoe pagina's zijn georganiseerd.

### Deel I: Mediakoperspoor

Voor mediakopers, campagnemanagers en optimalisatie-engineers.

- [Hoofdstuk 3: Inzicht in uw QPS-funnel](03-qps-funnel.md)
  De startpagina. Hoe u de funneluitsplitsing leest: impressies, biedingen,
  gewonnen veilingen, besteding, winstpercentage, CTR, CPM. Wat "verspilling"
  in concrete termen betekent. Configuratiekaarten en wat hun velden regelen.

- [Hoofdstuk 4: Verspilling analyseren per dimensie](04-analyzing-waste.md)
  De drie verspillingsanalyseweergaven en wanneer u welke gebruikt:
  - **Geografisch** (`/qps/geo`): welke landen en steden QPS opslokken zonder
    te converteren.
  - **Uitgever** (`/qps/publisher`): welke domeinen en apps
    ondermaats presteren.
  - **Formaat** (`/qps/size`): welke advertentieformaten verkeer ontvangen maar
    geen passende creatives hebben. Google stuurt circa 400 verschillende
    formaten; de meeste zijn irrelevant voor vaste display-advertenties.

- [Hoofdstuk 5: Creatives beheren](05-managing-creatives.md)
  De creative-galerij (`/creatives`): bladeren per formaat, filteren op
  prestatieniveau, zoeken op ID. Thumbnails, formaatbadges,
  bestemmingsdiagnostiek. Campagneclustering (`/campaigns`): drag-and-drop,
  AI auto-clustering, de niet-toegewezen pool.

- [Hoofdstuk 6: Pretargeting-configuratie](06-pretargeting.md)
  Wat een pretargeting-configuratie regelt (geo's, formaten, advertentietypen,
  platformen, max QPS). Hoe u een configuratiekaart leest. Wijzigingen toepassen
  met dry-run voorvertoning. De wijzigingsgeschiedenistijdlijn (`/history`).
  Terugdraaien: hoe het werkt, waarom het bestaat en wanneer u het gebruikt.

- [Hoofdstuk 7: De Optimizer (BYOM)](07-optimizer.md)
  Bring Your Own Model: een extern scoring-endpoint registreren, valideren en
  activeren. De scoren-voorstellen-goedkeuren-toepassen levenscyclus.
  Workflowpresets: veilig, gebalanceerd, agressief. Economie: effectieve CPM,
  hostingkosten-basislijn, efficiëntiesamenvatting. Hoe een voorstel eruitziet
  en hoe u er een beoordeelt.

- [Hoofdstuk 8: Conversies en attributie](08-conversions.md)
  Een conversiebron aansluiten. Pixelintegratie. Webhook-setup: HMAC-
  handtekeningen, gedeelde geheimen, snelheidsbeperking. Gereedheids-checks.
  Ingestiestatistieken. Wat "conversiegezondheid" betekent en hoe u de
  beveiligingsstatuspagina leest.

- [Hoofdstuk 9: Data-import](09-data-import.md)
  Hoe data in Cat-Scan terechtkomt en waarom dit belangrijk is. Handmatige
  CSV-upload (`/import`): drag-drop, kolomkoppeling, validatie, gedeelde upload
  voor grote bestanden. Gmail auto-import: hoe het werkt, hoe u de status
  controleert, wat er gebeurt als het mislukt. Het dataversheidsraster: wat
  "geïmporteerd" vs. "ontbrekend" betekent per datum en rapporttype.
  Ontdubbelingsgaranties.

- [Hoofdstuk 10: Uw rapporten lezen](10-reading-reports.md)
  Bestedingsstatistieken, configuratieprestatievensters, endpoint-
  efficiëntiemetingen. Hoe u trends interpreteert. Wat de dagelijkse
  uitsplitsing toont. Snapshotvergelijkingen: voor en na een
  pretargetingwijziging.

### Deel II: DevOps-spoor

Voor platformengineers, SRE's en systeembeheerders.

- [Hoofdstuk 11: Architectuuroverzicht](11-architecture.md)
  Systeemtopologie: FastAPI-backend, Next.js 14 frontend, Postgres (Cloud SQL),
  BigQuery. Waarom beide databases bestaan (kosten, latentie, pre-aggregatie,
  verbindingsbeheer). Containerindeling: api, dashboard, oauth2-proxy,
  cloudsql-proxy, nginx. De auth-vertrouwensketen: OAuth2 Proxy zet `X-Email`,
  nginx geeft het door, API vertrouwt het.

- [Hoofdstuk 12: Uitrol](12-deployment.md)
  CI/CD-pipeline: GitHub Actions `build-and-push.yml` bouwt images bij push;
  `deploy.yml` is alleen handmatig te triggeren (met `DEPLOY`-bevestiging).
  Artifact Registry image-tags (`sha-XXXXXXX`). De uitrolvolgorde: git pull op
  VM, docker compose pull, recreate, prune. Verificatie na uitrol: health check,
  contractcheck. Waarom auto-deploy is uitgeschakeld (incident januari 2026).
  Hoe u een uitrol verifieert: `curl /api/health | jq .git_sha`.

- [Hoofdstuk 13: Gezondheidsmonitoring en diagnostiek](13-health-monitoring.md)
  Health-endpoints: `/api/health` (liveness), `/system/data-health`
  (datavolledigheid). De Systeemstatuspagina (`/settings/system`): Python, Node,
  FFmpeg, database, schijf, thumbnails. Runtime health-scripts:
  `diagnose_v1_buyer_report_coverage.sh`,
  `run_v1_runtime_health_strict_dispatch.sh`. Canary-authenticatie:
  `CATSCAN_CANARY_EMAIL`, `CATSCAN_BEARER_TOKEN`. CI-workflows:
  `v1-runtime-health-strict.yml` en wat PASS/FAIL/BLOCKED betekenen.

- [Hoofdstuk 14: Database-operaties](14-database.md)
  Uitsluitend Postgres in productie. Cloud SQL via proxy-container.
  Belangrijke tabellen en hun schaal: `rtb_daily` (~84M rijen), `rtb_bidstream`
  (~21M rijen), `rtb_quality`, `rtb_bid_filtering`. Kritieke indexen:
  `(buyer_account_id, metric_date DESC)`. Verbindingsmodel: per request (geen
  pool), `run_in_executor` voor async. Statement-timeouts
  (`SET LOCAL statement_timeout`). Instellingen voor dataretentie. Rol van
  BigQuery: batch-warehouse voor ruwe data; Postgres serveert pre-geaggregeerde
  data aan de applicatie.

- [Hoofdstuk 15: Probleemoplossing-runbook](15-troubleshooting.md)
  Bekende faalpatronen en hoe u ze oplost:
  - **Inlogloop**: Cloud SQL Proxy niet beschikbaar,
    `_get_or_create_oauth2_user` faalt stilletjes, `/auth/check` retourneert
    `{authenticated:false}`, frontend-redirectloop. Drielaagse oplossing. Hoe te
    detecteren: redirectteller in browser, 503 van `/auth/check`.
  - **Data-freshness timeout**: Grote tabellen doen sequentiële scans in plaats
    van indexen te gebruiken. Symptomen: `/uploads/data-freshness` geeft timeout
    of retourneert 500. Diagnose: `pg_stat_activity`, `EXPLAIN ANALYZE`.
    Oplossingspatroon: generate_series + EXISTS.
  - **Gmail-importfout**: `/gmail/status` toont fout. Controleer Cloud SQL
    Proxy-container. Controleer aantal ongelezen berichten.
  - **Volgorde containerherstart**: `cloudsql-proxy` moet gezond zijn voordat
    `api` start. Tekenen van verkeerde volgorde: connection refused in API-logs.

- [Hoofdstuk 16: Gebruikers- en rechtenbeheer](16-user-admin.md)
  Het adminpaneel (`/admin`): gebruikers aanmaken (lokaal en OAuth vooraf
  aanmaken), rolbeheer, rechten per stoel. Serviceaccounts: GCP-credential-JSON
  uploaden, wat het ontsluit (stoelontdekking, pretargeting-synchronisatie).
  Beperkte gebruikers: wat zij zien en wat verborgen is. Het auditlog: welke
  acties worden bijgehouden, hoe te filteren, bewaarperiode.

- [Hoofdstuk 17: Integraties](17-integrations.md)
  GCP-serviceaccounts en projectverbinding. Google Authorized Buyers API:
  stoelontdekking, pretargeting-configuratiesynchronisatie, RTB-endpoint-
  synchronisatie. Gmail-integratie: OAuth2 voor automatische rapportingestie.
  Taal-AI-providers: Gemini, Claude, Grok (voor detectie van creativetaal en
  mismatch-meldingen). Conversie-webhooks: endpointregistratie, HMAC-
  verificatie, snelheidsbeperking, versheidsmonitoring.

### Deel III: Referentie

Gedeeld door beide sporen.

- [Woordenlijst](glossary.md)
  Elke term in twee talen. Mediakoperkolom: "pretargeting" is "de regels die
  bepalen welke biedverzoeken uw bidder bereiken." DevOps-kolom: "pretargeting"
  is "een muteerbare entiteit gesynchroniseerd vanuit de AB API, opgeslagen in
  `pretargeting_configs`, beschikbaar via `/settings/pretargeting`." Beiden
  hebben hetzelfde woord nodig; geen van beiden gebruikt de definitie van de
  ander.

- [Veelgestelde vragen](faq.md)
  Per persona gelabeld. Vragen die een mediakoper stelt ("Waarom is mijn dekking
  74%?") naast vragen die een DevOps-engineer stelt ("Waarom is de runtime
  health strict gate mislukt?"). Antwoorden verwijzen naar het relevante
  hoofdstuk.

- [API Snelreferentie](api-reference.md)
  Alle 118+ endpoints gegroepeerd per domein: kern, seats, creatives, campagnes,
  analytics, instellingen, admin, optimizer, conversies, integraties, uploads,
  snapshots, auth. Methode, pad, belangrijkste parameters en wat het retourneert.
  Geen vervanging voor de OpenAPI-specificatie op `/api/docs`, maar een
  navigeerbare index.
