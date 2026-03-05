# Cat-Scan Brugermanual

## Problemet i ét billede

![QPS-tragt](../assets/qps-funnel.svg)

Google sender din bidder en strøm af budforespørgsler. Hvert sekund strømmer
titusindvis af forespørgsler ud fra Authorized Buyers-børsen mod dit endpoint.
Din bidder evaluerer hver enkelt, beslutter om der skal bydes, og svarer —
det hele inden for få millisekunder.

Her er det, de fleste overser: **langt størstedelen af det signal er støj.**
Et typisk seat, der modtager 50.000 QPS, kan opleve, at 30.000 af de
forespørgsler vedrører inventory, som mediakøberen aldrig ville have købt:
forkerte geografier, irrelevante publisher-domæner, annonceformater uden
matchende kreativ. Din bidder skal stadig modtage, parse og afvise hver enkelt.
Det koster båndbredde, compute og penge.

Diagrammet ovenfor viser det som regn. Googles QPS er dysen i toppen;
dråberne spredes over et bredt område. Din bidder er den lille spand i bunden.
Alt, der rammer ved siden af spanden (dråberne til venstre og højre), er spild.
Du betalte for det. Du fik intet tilbage.

**Cat-Scan eksisterer for at gøre spanden bredere og regnen smallere.**

Det gør den ved at give dig indsigt i, hvor spildet opstår (hvilke geografier,
hvilke publishers, hvilke annonceformater, hvilke kreativer) og kontrollen til
at stoppe det ved kilden, ved hjælp af de pretargeting-konfigurationer, som
Google stiller til rådighed.

### Hvorfor det er sværere, end det lyder

Google Authorized Buyers giver dig kun **10 pretargeting-konfigurationer per
seat**, plus grove geografiske grupper (østlige USA, vestlige USA, Europa,
Asien). Der er ingen Reporting API. Alle performancedata kommer fra
CSV-eksporter, der ankommer via e-mail. Authorized Buyers' pretargeting-UI er
funktionelt, men gør det vanskeligt at se det samlede billede på tværs af
konfigurationer eller at fortryde en ændring, der gik galt.

Cat-Scan lukker disse huller:

- Den **genopbygger rapportering fra CSV-eksporter** (manuel upload eller
  automatisk Gmail-indlæsning), med deduplikering ved import, så
  genbehandling aldrig dobbelttæller.
- Den viser den **fulde RTB-tragt**, fra rå QPS gennem bud, vindere,
  visninger, klik og forbrug, opdelt efter enhver dimension: geografi,
  publisher, annonceformat, kreativ, konfiguration.
- Den tilbyder **sikker pretargeting-styring** med historik, trinvise
  ændringer, dry-run-forhåndsvisning og rollback med ét klik.
- Den kører en **optimizer**, der scorer segmenter og foreslår
  konfigurationsændringer med workflow-sikkerhedsforanstaltninger (safe /
  balanced / aggressive), så ingen ændring går live uden gennemgang.

### Hvem denne manual er til

Denne manual har to spor, fordi Cat-Scan betjener to meget forskellige roller:

**Mediakøbere og kampagneansvarlige** bruger Cat-Scan til at forstå, hvor
deres budget ender, finde spild, administrere kreativer, finjustere
pretargeting og godkende optimeringsforslag. De tænker i CPM, vindrater og
ROAS. Deres kapitler fokuserer på, hvad UI'et viser, hvad tallene betyder, og
hvilke handlinger der skal foretages.

**DevOps- og platformingeniører** bruger Cat-Scan til at deploye, overvåge og
fejlsøge systemet. De tænker i containere, health-endpoints og query plans.
Deres kapitler fokuserer på arkitektur, deployment-pipelines, databaseoperationer
og fejlhåndteringsrunbooks.

Begge spor deler et fælles fundament (kom godt i gang, ordliste), og kapitlerne
krydshenviser til hinanden, hvor arbejdsgange overlapper. En mediakøber, der
rapporterer "datafriskheden er brudt", og en DevOps-ingeniør, der debugger den
underliggende query, bør kunne pege på den samme ordlistepost og forstå
hinanden.

---

## Sådan læser du denne manual

- **Del 0** er for alle. Start her.
- **Del I** er mediakøbersporet. Hvis du arbejder med kampagner, optimering
  eller indkøb, er dette din vej.
- **Del II** er DevOps-sporet. Hvis du deployer, overvåger eller administrerer
  Cat-Scan, er dette din vej.
- **Del III** er delt reference: ordliste, FAQ og API-indeks.

Du behøver ikke læse lineært. Hvert kapitel er selvstændigt. Følg de links,
der matcher din rolle.

---

## Indholdsfortegnelse

### Del 0: Kom godt i gang

Alle læser dette.

- [Kapitel 0: Hvad er Cat-Scan?](00-what-is-cat-scan.md)
  Hvad platformen gør, hvem den er til, og de kernebegreber, du skal kende,
  før noget andet: seats, QPS, pretargeting, RTB-tragten.

- [Kapitel 1: Log ind](01-logging-in.md)
  Autentificeringsmetoder (Google OAuth, lokale konti), login-siden, hvad du
  gør, når login fejler, og hvordan seat-vælgeren fungerer.

- [Kapitel 2: Navigering i dashboardet](02-navigating-the-dashboard.md)
  Sidepanelet, seat-skift, sprogvælger, opsætningstjeklisten for nye konti,
  og hvordan siderne er organiseret.

### Del I: Mediakøbersporet

For mediakøbere, kampagneansvarlige og optimeringsingeniører.

- [Kapitel 3: Forstå din QPS-tragt](03-qps-funnel.md)
  Forsiden. Sådan læser du tragtopdelingen: visninger, bud, vindere,
  forbrug, vindrate, CTR, CPM. Hvad "spild" betyder i konkrete termer.
  Konfigurationskort og hvad deres felter styrer.

- [Kapitel 4: Analyse af spild efter dimension](04-analyzing-waste.md)
  De tre spildanalysevisninger, og hvornår du bruger dem:
  - **Geografisk** (`/qps/geo`): hvilke lande og byer bruger QPS uden at
    konvertere.
  - **Publisher** (`/qps/publisher`): hvilke domæner og apps underpræsterer.
  - **Format** (`/qps/size`): hvilke annonceformater modtager trafik, men har
    ingen matchende kreativer. Google sender ca. 400 forskellige formater; de
    fleste er irrelevante for displayannoncer med faste mål.

- [Kapitel 5: Kreativstyring](05-managing-creatives.md)
  Kreativgalleriet (`/creatives`): gennemse efter format, filtrér efter
  performanceniveau, søg efter ID. Thumbnails, formatbadges,
  destinationsdiagnostik. Kampagneklyngning (`/campaigns`): drag-and-drop,
  AI-autoklyngning, den utildelte pulje.

- [Kapitel 6: Pretargeting-konfiguration](06-pretargeting.md)
  Hvad en pretargeting-konfiguration styrer (geografier, formater, platforme,
  maks. QPS). Sådan læser du et konfigurationskort. Anvend ændringer med
  dry-run-forhåndsvisning. Ændringshistorik-tidslinjen (`/history`). Rollback:
  hvordan det virker, hvorfor det findes, og hvornår du bruger det.

- [Kapitel 7: Optimizeren (BYOM)](07-optimizer.md)
  Bring Your Own Model: registrér et eksternt scoringsendpoint, validér det,
  aktivér det. Score-foreslå-godkend-anvend-livscyklussen. Workflow-presets:
  safe, balanced, aggressive. Økonomi: effektiv CPM, hostingomkostningsbaseline,
  effektivitetsresumé. Sådan ser et forslag ud, og hvordan du evaluerer det.

- [Kapitel 8: Konverteringer og attribution](08-conversions.md)
  Tilslut en konverteringskilde. Pixelintegration. Webhook-opsætning:
  HMAC-signaturer, delte hemmeligheder, rate limiting. Parathedstjek.
  Indlæsningsstatistik. Hvad "konverteringssundhed" betyder, og hvordan du
  læser sikkerhedsstatussiden.

- [Kapitel 9: Dataimport](09-data-import.md)
  Hvordan data kommer ind i Cat-Scan, og hvorfor det er vigtigt. Manuel
  CSV-upload (`/import`): drag-drop, kolonnemapping, validering, chunked upload
  til store filer. Gmail-autoimport: hvordan det virker, hvordan du tjekker
  status, hvad der sker, når det fejler. Datafriskheds-gitteret: hvad
  "importeret" vs. "manglende" betyder per dato og rapporttype.
  Deduplkeringsgarantier.

- [Kapitel 10: Forstå dine rapporter](10-reading-reports.md)
  Forbrugsstatistik, konfigurationsperformancepaneler, endpoint-effektivitetsmål.
  Sådan fortolker du tendenser. Hvad den daglige opdeling viser.
  Snapshot-sammenligninger: før og efter en pretargeting-ændring.

### Del II: DevOps-sporet

For platformingeniører, SRE'er og systemadministratorer.

- [Kapitel 11: Arkitekturoversigt](11-architecture.md)
  Systemtopologi: FastAPI-backend, Next.js 14-frontend, Postgres (Cloud SQL),
  BigQuery. Hvorfor begge databaser eksisterer (omkostning, latens,
  præaggregering, forbindelseshåndtering). Container-layout: api, dashboard,
  oauth2-proxy, cloudsql-proxy, nginx. Auth-tillidskæden: OAuth2 Proxy sætter
  `X-Email`, nginx videresender det, API'et stoler på det.

- [Kapitel 12: Deployment](12-deployment.md)
  CI/CD-pipeline: GitHub Actions `build-and-push.yml` bygger images ved push;
  `deploy.yml` er kun manuel trigger (med `DEPLOY`-bekræftelse). Artifact
  Registry image-tags (`sha-XXXXXXX`). Deploy-sekvensen: git pull på VM,
  docker compose pull, recreate, prune. Post-deploy-verifikation: health check,
  contract check. Hvorfor auto-deploy er deaktiveret (januar 2026-hændelsen).
  Sådan verificerer du en deploy: `curl /api/health | jq .git_sha`.

- [Kapitel 13: Sundhedsovervågning og diagnostik](13-health-monitoring.md)
  Health-endpoints: `/api/health` (liveness), `/system/data-health`
  (datakomplethed). Systemstatussiden (`/settings/system`): Python, Node,
  FFmpeg, database, disk, thumbnails. Runtime health-scripts:
  `diagnose_v1_buyer_report_coverage.sh`,
  `run_v1_runtime_health_strict_dispatch.sh`. Canary-autentificering:
  `CATSCAN_CANARY_EMAIL`, `CATSCAN_BEARER_TOKEN`. CI-workflows:
  `v1-runtime-health-strict.yml` og hvad PASS/FAIL/BLOCKED betyder.

- [Kapitel 14: Databaseoperationer](14-database.md)
  Kun Postgres i produktion. Cloud SQL via proxy-container. Nøgletabeller og
  deres skala: `rtb_daily` (~84M rækker), `rtb_bidstream` (~21M rækker),
  `rtb_quality`, `rtb_bid_filtering`. Kritiske indekser:
  `(buyer_account_id, metric_date DESC)`. Forbindelsesmodel: per-request
  (ingen pool), `run_in_executor` for async. Statement-timeouts
  (`SET LOCAL statement_timeout`). Dataopbevaringsindstillinger. BigQuerys
  rolle: batch-warehouse for rådata; Postgres serverer præaggregerede data til
  appen.

- [Kapitel 15: Fejlsøgningsrunbook](15-troubleshooting.md)
  Kendte fejlmønstre og hvordan de løses:
  - **Login-loop**: Cloud SQL Proxy nede, `_get_or_create_oauth2_user` fejler
    stille, `/auth/check` returnerer `{authenticated:false}`,
    frontend-redirect-loop. Trelagsløsning. Sådan opdager du det:
    redirect-tæller i browseren, 503 fra `/auth/check`.
  - **Datafriskheds-timeout**: Store tabeller laver sekventielle scanninger i
    stedet for at bruge indekser. Symptomer: `/uploads/data-freshness` timer
    ud eller returnerer 500. Diagnose: `pg_stat_activity`, `EXPLAIN ANALYZE`.
    Løsningsmønster: generate_series + EXISTS.
  - **Gmail-importfejl**: `/gmail/status` viser fejl. Tjek Cloud SQL
    Proxy-container. Tjek antal ulæste.
  - **Container-genstartsrækkefølge**: `cloudsql-proxy` skal være sund, før
    `api` starter. Tegn på forkert rækkefølge: connection refused i API-loggen.

- [Kapitel 16: Bruger- og rettighedsadministration](16-user-admin.md)
  Adminpanelet (`/admin`): brugeroprettelse (lokal og OAuth-preoprettelse),
  rollestyring, per-seat-rettigheder. Servicekonti: upload af GCP
  credential-JSON, hvad det låser op (seat discovery, pretargeting-synk).
  Begrænsede brugere: hvad de ser, og hvad der er skjult. Auditloggen: hvilke
  handlinger spores, hvordan man filtrerer, opbevaring.

- [Kapitel 17: Integrationer](17-integrations.md)
  GCP-servicekonti og projektforbindelse. Google Authorized Buyers API:
  seat discovery, pretargeting-konfigurationssynk, RTB-endpoint-synk.
  Gmail-integration: OAuth2 til automatisk rapportindlæsning.
  Sprog-AI-udbydere: Gemini, Claude, Grok (til kreativ sproggenkendelse og
  mismatch-advarsler). Konverterings-webhooks: endpoint-registrering,
  HMAC-verifikation, rate limiting, friskheds-monitorering.

### Del III: Reference

Delt af begge spor.

- [Ordliste](glossary.md)
  Hvert begreb på to niveauer. Mediakøberkolonnen: "pretargeting" er "de regler,
  der styrer, hvilke budforespørgsler der når din bidder." DevOps-kolonnen:
  "pretargeting" er "en muterbar entitet synkroniseret fra AB API'et, gemt i
  `pretargeting_configs`, tilgængelig via `/settings/pretargeting`." Begge har
  brug for det samme ord; ingen bruger den andens definition.

- [Ofte stillede spørgsmål](faq.md)
  Persona-tagget. Spørgsmål, en mediakøber stiller ("Hvorfor er min dækning
  på 74%?"), ved siden af spørgsmål, en DevOps-ingeniør stiller ("Hvorfor
  fejlede runtime health strict-gaten?"). Svar krydshenviser til det relevante
  kapitel.

- [API-hurtigreference](api-reference.md)
  Alle 118+ endpoints grupperet efter domæne: core, seats, creatives,
  campaigns, analytics, settings, admin, optimizer, conversions, integrations,
  uploads, snapshots, auth. Metode, sti, nøgleparametre og hvad det returnerer.
  Ikke en erstatning for OpenAPI-specifikationen på `/api/docs`, men et
  navigerbart indeks.
