# Ordliste

Hvert begreb, to perspektiver. Den venstre kolonne er, hvordan en mediakøber
tænker om det. Den højre kolonne er, hvordan en DevOps-ingeniør finder det i
systemet.

| Begreb | Mediakøberdefinition | DevOps / systemdefinition |
|--------|---------------------|--------------------------|
| **Seat** | En køberkonto på Google Authorized Buyers. Du afgrænser din analyse og targeting per seat. | `buyer_account_id` i Postgres. Gemt i `seats`-tabellen. Synkroniseret via `GET /seats`. |
| **QPS** | Queries Per Second: den maksimale rate af budforespørgsler, du beder Google om at sende. Google begrænser den faktiske mængde baseret på dit kontoniveau. | Konfigureret loft per pretargeting-konfiguration. Faktisk indgående rate overvåges via RTB-tragtmetrikker i `rtb_daily`. |
| **Spild** | QPS forbrugt af budforespørgsler, din bidder afviser (forkerte geografier, forkerte formater, ingen matchende kreativ). Penge brugt på ingenting. | `(total_qps - bids_placed) / total_qps`. Beregnet fra `rtb_daily`-aggregater. Synlig i tragt-API'et. |
| **Pretargeting-konfiguration** | De regler, der styrer, hvilke budforespørgsler der når din bidder. Du får 10 per seat. Styrer geografier, formater, platforme, publishers. | Muterbar entitet synkroniseret fra Google AB API. Gemt i `pretargeting_configs`. Administreret via `/settings/pretargeting`. Snapshots muliggør rollback. |
| **Tragt** | Progressionen fra budforespørgsel til forbrug: QPS -> Bud -> Vindere -> Visninger -> Klik -> Forbrug. Hvert trin har frafald. | Beregnet fra `rtb_daily`-metrikker. Serveret af `GET /analytics/rtb-funnel`. Frontend cacher i 30 minutter. |
| **Kreativ** | Et annonceaktiv: billede, video, HTML eller native. Har et format, en størrelse, en destinations-URL og en performancehistorik. | Række i `creatives`-tabellen. Thumbnails i blob storage. Synkroniseret fra Google AB API. Performance fra `rtb_daily`-joins. |
| **Kampagne** | En logisk gruppering af kreativer. Bruges til at organisere analyse og rapportering. | Række i `ai_campaigns`-tabellen. Many-to-many med kreativer. Understøtter AI-autoklyngning. |
| **Konfigurationskort** | UI-panelet, der viser en pretargeting-konfigurations tilstand, maks. QPS, geografier, formater og platforme. | `PretargetingConfigCard` React-komponent. Data fra `GET /settings/pretargeting-configs`. |
| **Datafriskhed** | Et gitter, der viser, hvilke datoer der har importerede data ("importeret") vs. huller ("manglende") for hver rapporttype. | `GET /uploads/data-freshness`. Bruger `generate_series + EXISTS`-queries mod `rtb_daily`, `rtb_bidstream`, `rtb_quality`, `rtb_bid_filtering`. 30s statement-timeout. |
| **Import** | At få CSV-performancedata ind i Cat-Scan, enten via manuel upload eller Gmail-autoimport. | CSV parset, valideret, deduplikeret (via `row_hash` unique constraint), indsat i måltabeller. Chunked upload for filer > 5MB. |
| **Rollback** | Tilbageføring af en pretargeting-konfigurationsændring til dens tidligere tilstand. Forhåndsvis med dry-run, derefter bekræft. | Snapshot-gendannelse: læser `pretargeting_snapshots`, anvender delta til Google AB API, registrerer nyt snapshot. `POST /snapshots/rollback`. |
| **Optimizer / BYOM** | Automatiseret system, der scorer segmenter og foreslår konfigurationsændringer. Bruger din egen eksterne model. | Score-endpoint kaldet via HTTP POST. Forslag gemt i `optimizer_proposals`. Livscyklus: score -> foreslå -> godkend -> anvend. |
| **Workflow-preset** | Safe, balanced eller aggressive. Styrer, hvor dristige optimizerens forslag er. | `canary_profile`-parameter til score-and-propose API. Påvirker konfidenstærskler og ændringsomfangsgrænser. |
| **Effektiv CPM** | Hvad du faktisk betaler per tusind visninger, når spild og infrastrukturomkostninger medregnes. | Beregnet i `OptimizerEconomicsService`. Kombinerer forbrugsdata fra `rtb_daily` med konfigurerede hostingomkostninger. |
| **Konvertering** | En værdifuld brugerhandling (køb, tilmelding) sporet efter en visning. Fødes tilbage for at optimere targeting. | Hændelse indlæst via pixel (`GET /conversions/pixel`) eller webhook (`POST /conversions/webhook`). Gemt i konverteringstabeller. HMAC-verificeret for webhooks. |
| **Vindrate** | Vindere / Bud. Hvor konkurrencedygtige dine bud er i auktionen. | `auction_wins / bids_placed` fra `rtb_daily`. |
| **CTR** | Klik / Visninger. Hvor engagerende dine kreativer er. | `clicks / impressions` fra `rtb_daily`. |
| **Runtime health-gate** | (Ikke et køberbegreb) | `v1-runtime-health-strict.yml` CI-workflow. Kører end-to-end-tjek: API health, data health, konverteringer, optimizer, QPS SLO. Returnerer PASS/FAIL/BLOCKED per tjek. |
| **Contract check** | (Ikke et køberbegreb) | `scripts/contracts_check.py`. Validerer datakontrakter (ufravigelige regler fra import til API-output). Køres efter deploy. Blokerer release ved fejl. |
| **Cloud SQL Proxy** | (Ikke et køberbegreb) | Sidecar-container, der giver autentificeret adgang til Cloud SQL Postgres. Skal være sund, før API-containeren starter. |
| **X-Email header** | (Ikke et køberbegreb) | HTTP-header sat af OAuth2 Proxy efter Google-autentificering. Betroet af API'et, når `OAUTH2_PROXY_ENABLED=true`. Fjernet af nginx for eksterne forespørgsler. |
