# Woordenlijst

Elke term, twee perspectieven. De linkerkolom beschrijft hoe een mediakoper
erover denkt. De rechterkolom beschrijft hoe een DevOps-engineer het in het
systeem terugvindt.

| Term | Definitie mediakoper | DevOps / systeemdefinitie |
|------|---------------------|--------------------------|
| **Seat** | Een kopersaccount op Google Authorized Buyers. U scopt uw analyse en targeting per seat. | `buyer_account_id` in Postgres. Opgeslagen in de `seats`-tabel. Gesynchroniseerd via `GET /seats`. |
| **QPS** | Queries Per Second: het maximale tempo van biedverzoeken dat u Google vraagt te verzenden. Google beperkt het werkelijke volume op basis van uw accountniveau. | Geconfigureerde limiet per pretargeting-configuratie. Werkelijk inkomend tempo gemonitord via RTB-funnelmetingen in `rtb_daily`. |
| **Verspilling** | QPS verbruikt door biedverzoeken die uw bidder afwijst (verkeerde geo's, verkeerde formaten, geen passende creative). Geld uitgegeven aan niets. | `(total_qps - bids_placed) / total_qps`. Berekend uit `rtb_daily`-aggregaten. Zichtbaar in de funnel-API. |
| **Pretargeting-configuratie** | De regels die bepalen welke biedverzoeken uw bidder bereiken. U krijgt er 10 per seat. Regelt geo's, formaten, advertentietypen, platformen, uitgevers. | Muteerbare entiteit gesynchroniseerd vanuit de Google AB API. Opgeslagen in `pretargeting_configs`. Beheerd via `/settings/pretargeting`. Snapshots maken terugdraaien mogelijk. |
| **Funnel** | De voortgang van biedverzoek naar besteding: QPS -> Biedingen -> Gewonnen -> Impressies -> Klikken -> Besteding. Elke stap heeft uitval. | Berekend uit `rtb_daily`-metingen. Geserveerd door `GET /analytics/rtb-funnel`. Frontend cachet gedurende 30 minuten. |
| **Creative** | Een advertentie-asset: afbeelding, video, HTML of native. Heeft een formaat, afmeting, bestemmings-URL en prestatiegeschiedenis. | Rij in de `creatives`-tabel. Thumbnails in blob storage. Gesynchroniseerd vanuit de Google AB API. Prestaties via `rtb_daily`-joins. |
| **Campagne** | Een logische groepering van creatives. Gebruikt om analyse en rapportage te organiseren. | Rij in de `ai_campaigns`-tabel. Veel-op-veel met creatives. Ondersteunt AI auto-clustering. |
| **Configuratiekaart** | Het UI-paneel dat de status van een pretargeting-configuratie toont, met max QPS, geo's, formaten, advertentietypen en platformen. | `PretargetingConfigCard` React-component. Data van `GET /settings/pretargeting-configs`. |
| **Dataversheid** | Een raster dat toont welke datums geïmporteerde data hebben ("geïmporteerd") versus hiaten ("ontbrekend") per rapporttype. | `GET /uploads/data-freshness`. Gebruikt `generate_series + EXISTS` queries op `rtb_daily`, `rtb_bidstream`, `rtb_quality`, `rtb_bid_filtering`. 30s statement timeout. |
| **Import** | CSV-prestatiedata in Cat-Scan laden, hetzij via handmatige upload of Gmail auto-import. | CSV geparsed, gevalideerd, ontdubbeld (via `row_hash` unique constraint), ingevoegd in doeltabellen. Gedeelde upload voor bestanden > 5MB. |
| **Terugdraaien** | Een pretargeting-configuratiewijziging terugzetten naar de vorige staat. Voorvertoning met dry-run, daarna bevestigen. | Snapshotherstel: leest `pretargeting_snapshots`, past delta toe op Google AB API, registreert nieuwe snapshot. `POST /snapshots/rollback`. |
| **Optimizer / BYOM** | Geautomatiseerd systeem dat segmenten scoort en configuratiewijzigingen voorstelt. Gebruikt uw eigen externe model. | Score-endpoint aangeroepen via HTTP POST. Voorstellen opgeslagen in `optimizer_proposals`. Levenscyclus: scoren -> voorstellen -> goedkeuren -> toepassen. |
| **Workflowpreset** | Veilig, gebalanceerd of agressief. Bepaalt hoe gedurfd de voorstellen van de optimizer zijn. | `canary_profile` parameter voor de score-and-propose API. Beïnvloedt betrouwbaarheidsdrempels en limieten voor wijzigingsomvang. |
| **Effectieve CPM** | Wat u daadwerkelijk betaalt per duizend impressies, rekening houdend met verspilling en infrastructuurkosten. | Berekend in `OptimizerEconomicsService`. Combineert bestedingsdata uit `rtb_daily` met geconfigureerde hostingkosten. |
| **Conversie** | Een waardevolle gebruikersactie (aankoop, registratie) die wordt bijgehouden na een impressie. Wordt teruggekoppeld om targeting te optimaliseren. | Event geïngesteerd via pixel (`GET /conversions/pixel`) of webhook (`POST /conversions/webhook`). Opgeslagen in conversietabellen. HMAC-geverifieerd voor webhooks. |
| **Winstpercentage** | Gewonnen / Biedingen. Hoe concurrerend uw biedingen zijn in de veiling. | `auction_wins / bids_placed` uit `rtb_daily`. |
| **CTR** | Klikken / Impressies. Hoe aantrekkelijk uw creatives zijn. | `clicks / impressions` uit `rtb_daily`. |
| **Runtime health gate** | (Geen koperterm) | `v1-runtime-health-strict.yml` CI-workflow. Voert end-to-end checks uit: API-gezondheid, datagezondheid, conversies, optimizer, QPS SLO. Retourneert PASS/FAIL/BLOCKED per check. |
| **Contractcheck** | (Geen koperterm) | `scripts/contracts_check.py`. Valideert datacontracten (niet-onderhandelbare regels van import tot API-output). Draait na uitrol. Blokkeert release bij falen. |
| **Cloud SQL Proxy** | (Geen koperterm) | Sidecar-container die geauthenticeerde toegang biedt tot Cloud SQL Postgres. Moet gezond zijn voordat de API-container start. |
| **X-Email header** | (Geen koperterm) | HTTP-header gezet door OAuth2 Proxy na Google-authenticatie. Vertrouwd door de API wanneer `OAUTH2_PROXY_ENABLED=true`. Gestript door nginx voor externe verzoeken. |
