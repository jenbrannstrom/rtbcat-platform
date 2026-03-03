# Kapitel 15: Fejlfindingsrunbook

*Målgruppe: DevOps, platformingeniører*

## Login-loop

**Symptomer:** Brugeren rammer loginsiden, autentificerer sig, omdirigeres tilbage til loginsiden, og loopet gentager sig uendeligt.

**Grundårsagsmønster:** Enhver databasefejl forårsager, at `_get_or_create_oauth2_user()` fejler tavst. `/auth/check` returnerer `{authenticated: false}`. Frontenden omdirigerer til `/oauth2/sign_in`. Loop.

**Typiske udløsere:**
- Cloud SQL Proxy-containeren døde eller blev genstartet uden at genstarte API'et
- Netværkspartitionering mellem VM og Cloud SQL-instans
- Cloud SQL-instansvedligeholdelse eller genstart

**Detektion:**
- Browser: omdirigeringstælleren udløses efter 2 omdirigeringer inden for 30 sekunder og viser en fejl/genprøv-brugerflade i stedet for at loope
- API: `/auth/check` returnerer HTTP 503 (ikke 200), når databasen er utilgængelig, med `auth_error` i svaret
- Logfiler: kig efter "connection refused" eller timeout-fejl i catscan-api-logfilerne

**Løsning:**
1. Tjek Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. Hvis nede: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Vent 10 sekunder, genstart derefter API'et:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Verificér: `curl -sS http://localhost:8000/health`

**Forebyggelse:** Trelagsrettelsen (implementeret feb. 2026):
1. Backend propagerer DB-fejl via `request.state.auth_error`
2. `/auth/check` returnerer 503, når DB er utilgængelig
3. Frontend har omdirigeringstæller (maks. 2 på 30 s) + fejl/genprøv-brugerflade

## Datafriskheds-timeout

**Symptomer:** `/uploads/data-freshness` returnerer 500, timer ud, eller runtime-sundhedsgaten viser BLOCKED på datasundhed.

**Grundårsagsmønster:** Datafriskheds­forespørgslen scanner store tabeller (`rtb_daily` med 84M rækker, `rtb_bidstream` med 21M rækker). Hvis forespørgsels­planen degraderer til en sekventiel scanning i stedet for at bruge indekser, kan det tage 160+ sekunder.

**Detektion:**
1. Kald endpointet direkte fra VM'en:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. Hvis det timer ud eller returnerer 500, tjek forespørgselsplanen:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Kig efter `Parallel Seq Scan` på store tabeller. Det er problemet.

**Løsningsmønster:**
- Omskriv GROUP BY-forespørgsler som `generate_series + EXISTS` for at tvinge indeksopslag. Se [Databaseoperationer](14-database.md) for mønsteret.
- Sørg for at `SET LOCAL statement_timeout` bruges (ikke `SET` + `RESET`).
- Kontrollér at indekserne `(buyer_account_id, metric_date DESC)` eksisterer på alle måltabeller.

## Gmail-importfejl

**Symptomer:** Datafriskheds­gitteret viser "manglende" celler for nylige datoer. Importhistorikken har ingen nye poster.

**Detektion:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Tjek: `last_reason`, `unread`-antal, `latest_metric_date`.

**Typiske årsager:**
- Gmail OAuth-token udløbet: genautoriser på `/settings/accounts` > Gmail-fanen
- Cloud SQL Proxy nede: Gmail-import skriver til Postgres, så DB skal være tilgængelig
- Stort `unread`-antal (30+): import kan sidde fast i behandling, eller postkassen har en efterslæb

**Løsning:**
1. Hvis `last_reason` viser en fejl: genstart importjobbet fra brugerfladen eller API'et
2. Hvis tokenet er udløbet: genautoriser Gmail-integrationen
3. Hvis Cloud SQL er nede: løs databaseforbindelsen først (se login-loop)

## Container-genstartsrækkefølge

**Symptom:** API-logfiler viser "connection refused" til port 5432 ved opstart.

**Årsag:** API-containeren startede før Cloud SQL Proxy var klar.

**Løsning:** Genstart med korrekt rækkefølge:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Eller genstart alt (compose håndterer afhængigheder):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## SET statement_timeout-syntaksfejl

**Symptom:** Endpoint returnerer 500 med fejlen:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Årsag:** psycopg3 konverterer `%s` til `$1` for server-side parameterbinding, men PostgreSQL's `SET`-kommando understøtter ikke parameterplaceholders.

**Løsning:** Brug f-string med valideret integer:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Fejl i runtime-sundhedsgate

**Symptom:** Workflowet `v1-runtime-health-strict.yml` fejler.

**Fejlsøgning:**
1. Tjek workflowlogfilerne: `gh run view <id> --log-failed`
2. Kig efter FAIL vs. BLOCKED:
   - **FAIL** = noget gik i stykker, undersøg det
   - **BLOCKED** = afhængighed mangler (ingen data, intet endpoint), kan være forudeksisterende
3. Typiske forudeksisterende BLOCKED-årsager:
   - "rtb_quality_freshness state is unavailable": ingen kvalitetsdata for denne køber/periode
   - "proposal has no billing_id": dataopsætningsproblem
   - "QPS page API rollup missing required paths": analyseendpoint ikke udfyldt endnu
4. Sammenlign med tidligere kørsler for at identificere regressioner vs. forudeksisterende problemer.

## Relateret

- [Sundhedsovervågning](13-health-monitoring.md): overvågningsværktøjer
- [Databaseoperationer](14-database.md): forespørgsels- og indeksdetaljer
- [Udrulning](12-deployment.md): udrulning af rettelser
