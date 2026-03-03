# Hoofdstuk 15: Runbook voor probleemoplossing

*Doelgroep: DevOps, platform-engineers*

## Inloglus

**Symptomen:** De gebruiker komt op de inlogpagina, authenticeert, wordt teruggestuurd naar de inlogpagina en de lus herhaalt zich eindeloos.

**Patroon van de onderliggende oorzaak:** Elke databasefout zorgt ervoor dat `_get_or_create_oauth2_user()` stilletjes mislukt. `/auth/check` retourneert `{authenticated: false}`. De frontend verwijst door naar `/oauth2/sign_in`. Lus.

**Veelvoorkomende triggers:**
- Cloud SQL Proxy-container is gestopt of herstart zonder de API te herstarten
- Netwerkpartitie tussen de VM en de Cloud SQL-instantie
- Onderhoud of herstart van de Cloud SQL-instantie

**Detectie:**
- Browser: de omleidingsteller slaat aan na 2 omleidingen in 30 seconden en toont een foutmelding/herprobeerscherm in plaats van te blijven loopen
- API: `/auth/check` retourneert HTTP 503 (niet 200) wanneer de database onbereikbaar is, met `auth_error` in het antwoord
- Logs: zoek naar connection-refused- of time-outfouten in de catscan-api-logs

**Oplossing:**
1. Controleer Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. Als deze niet draait: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Wacht 10 seconden en herstart vervolgens de API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Verifieer: `curl -sS http://localhost:8000/health`

**Preventie:** De drielaagse fix (toegepast in februari 2026):
1. Backend propageert databasefouten via `request.state.auth_error`
2. `/auth/check` retourneert 503 wanneer de database onbereikbaar is
3. Frontend heeft een omleidingsteller (max 2 in 30s) + foutmelding/herprobeerscherm

## Data-versheids-timeout

**Symptomen:** `/uploads/data-freshness` retourneert 500, valt uit door een timeout, of de runtime-gezondheidspoort toont BLOCKED bij datagezondheid.

**Patroon van de onderliggende oorzaak:** De dataversheidsquery scant grote tabellen (`rtb_daily` met 84M rijen, `rtb_bidstream` met 21M rijen). Als het queryplan degradeert tot een sequential scan in plaats van indexen te gebruiken, kan het meer dan 160 seconden duren.

**Detectie:**
1. Roep het endpoint rechtstreeks aan vanaf de VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. Als het een timeout geeft of 500 retourneert, controleer het queryplan:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Zoek naar `Parallel Seq Scan` op grote tabellen. Dat is het probleem.

**Oplossingspatroon:**
- Herschrijf GROUP BY-queries als `generate_series + EXISTS` om index-lookups af te dwingen. Zie [Databasebeheer](14-database.md) voor het patroon.
- Zorg dat `SET LOCAL statement_timeout` wordt gebruikt (niet `SET` + `RESET`).
- Controleer dat de indexen `(buyer_account_id, metric_date DESC)` bestaan op alle doeltabellen.

## Gmail-importfout

**Symptomen:** Het dataversheidsraster toont "ontbrekende" cellen voor recente datums. De importgeschiedenis bevat geen recente vermeldingen.

**Detectie:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Controleer: `last_reason`, aantal `unread`, `latest_metric_date`.

**Veelvoorkomende oorzaken:**
- Gmail OAuth-token verlopen: autoriseer opnieuw via `/settings/accounts` > Gmail-tabblad
- Cloud SQL Proxy niet actief: Gmail-import schrijft naar Postgres, dus de database moet bereikbaar zijn
- Hoog aantal `unread` (30+): import kan vastzitten bij verwerking of de inbox heeft een achterstand

**Oplossing:**
1. Als `last_reason` een fout toont: herstart de importtaak via de UI of API
2. Als het token verlopen is: autoriseer de Gmail-integratie opnieuw
3. Als Cloud SQL niet actief is: los eerst het databaseverbindingsprobleem op (zie inloglus)

## Opstartvolgorde van containers

**Symptoom:** API-logs tonen "connection refused" naar poort 5432 bij het opstarten.

**Oorzaak:** De API-container is gestart voordat Cloud SQL Proxy gereed was.

**Oplossing:** Herstart in de juiste volgorde:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Of herstart alles (compose regelt de afhankelijkheden):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## SET statement_timeout syntaxfout

**Symptoom:** Endpoint retourneert 500 met de fout:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Oorzaak:** psycopg3 converteert `%s` naar `$1` voor serverside parameter-binding, maar het PostgreSQL `SET`-commando ondersteunt geen parameterplaceholders.

**Oplossing:** Gebruik een f-string met een gevalideerd geheel getal:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Falen van de runtime-gezondheidspoort

**Symptoom:** De workflow `v1-runtime-health-strict.yml` mislukt.

**Triage:**
1. Controleer de workflowlogs: `gh run view <id> --log-failed`
2. Kijk of het FAIL of BLOCKED is:
   - **FAIL** = er is iets kapot, onderzoek het
   - **BLOCKED** = afhankelijkheid ontbreekt (geen data, geen endpoint), kan een bestaand probleem zijn
3. Veelvoorkomende bestaande BLOCKED-redenen:
   - "rtb_quality_freshness state is unavailable": geen kwaliteitsdata voor deze koper/periode
   - "proposal has no billing_id": probleem met data-inrichting
   - "QPS page API rollup missing required paths": analytics-endpoint nog niet gevuld
4. Vergelijk met eerdere runs om regressies te onderscheiden van bestaande problemen.

## Gerelateerd

- [Gezondheidsmonitoring](13-health-monitoring.md): monitoringtools
- [Databasebeheer](14-database.md): query- en indexdetails
- [Deployment](12-deployment.md): fixes deployen
