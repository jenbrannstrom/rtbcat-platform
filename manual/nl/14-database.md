# Hoofdstuk 14: Databasebeheer

*Doelgroep: DevOps, platform-engineers*

## Postgres in productie

Cat-Scan gebruikt Cloud SQL (Postgres 15) als enige operationele database. De API maakt verbinding via een Cloud SQL Auth Proxy sidecar-container op `localhost:5432`.

### Belangrijke tabellen en schaal

| Tabel | Geschat aantal rijen | Wat het opslaat |
|-------|----------------------|-----------------|
| `rtb_daily` | ~84 miljoen | Dagelijkse RTB-prestaties per koper, creative, geo, enz. |
| `rtb_bidstream` | ~21 miljoen | Bidstream-uitsplitsing per uitgever, geo |
| `rtb_quality` | varieert | Kwaliteitsmetrieken (viewability, brand safety) |
| `rtb_bid_filtering` | ~188 duizend | Redenen en volumes van bidfiltering |
| `pretargeting_configs` | klein | Snapshots van pretargeting-configuraties |
| `creatives` | klein | Creative-metadata en miniaturen |
| `import_history` | klein | CSV-importrecords |
| `users`, `permissions`, `audit_log` | klein | Authenticatie- en beheerdata |

### Kritieke indexen

Het meest prestatiegevoelige indexpatroon is:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

Dit bestaat op `rtb_daily`, `rtb_bidstream`, `rtb_quality` en
`rtb_bid_filtering`. Het ondersteunt de dataversheidsquery en kopersgerichte analytics.

Overige belangrijke indexen:
- `(metric_date, buyer_account_id)`: voor datumbereik + koperfilters
- `(metric_date, billing_id)`: voor factureringsgerichte queries
- `(row_hash)` UNIQUE: deduplicatie bij import

### Deduplicatie

Elke geimporteerde rij wordt gehasht (kolom `row_hash`). De unique-constraint op `row_hash` voorkomt dubbele inserts, waardoor herimport veilig is.

## Verbindingsmodel

De API gebruikt **verbindingen per verzoek** (geen connection pool). Elke query maakt een nieuwe `psycopg.connect()`-aanroep aan, gewrapped in `run_in_executor` voor asynchrone compatibiliteit.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

Overweeg bij productiebelasting het toevoegen van `psycopg_pool` als verbindingsoverhead een knelpunt wordt.

## Statement-timeouts

Voor dure queries (bijv. dataversheid over grote tabellen) gebruikt de API `pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Belangrijke details:
- `SET LOCAL` beperkt de timeout tot de huidige transactie en reset automatisch wanneer de transactie eindigt (commit of rollback).
- Standaard dataversheids-timeout: 30 seconden.
- Configureerbaar via de omgevingsvariabele `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (minimaal 1000ms).
- `SET LOCAL` voorkomt het probleem van een afgebroken transactie dat optreedt bij het gebruik van `SET` + `RESET` in een `try/finally`-blok (als de query wordt afgebroken door de timeout, komt de transactie in een afgebroken status terecht en mislukt `RESET`).

## Querypatroon voor dataversheid

Het dataversheidsendpoint moet weten welke datums data hebben per rapporttype. Het performante patroon gebruikt `generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

Dit doet N index-lookups (een per dag in het venster) in plaats van miljoenen rijen te scannen. Voor een venster van 14 dagen: 14 lookups van ~0,1ms elk versus een volledige parallelle sequential scan die meer dan 160 seconden duurt.

**Waarom GROUP BY hier niet werkt:** Zelfs met `1 AS row_count` (geen COUNT) kiest de planner een sequential scan wanneer de GROUP BY-resultaatset groot is ten opzichte van de tabel. De index `(buyer_account_id, metric_date DESC)` bestaat, maar de planner schat in dat het goedkoper is om 84M rijen te scannen dan 4,4M index-reads te doen.

## De rol van BigQuery

BigQuery slaat ruwe, gedetailleerde data op en voert batch-analyticsjobs uit. Het wordt niet gebruikt voor realtime API-queries. Het patroon:

1. Ruwe CSV-data wordt geladen in BigQuery-tabellen.
2. Batchjobs aggregeren de data.
3. Voorgeaggregeerde resultaten worden naar Postgres geschreven.
4. De API serveert vanuit Postgres.

## Dataretentie

Configureerbaar via `/settings/retention`. Bepaalt hoe lang historische data in Postgres wordt bewaard voordat deze veroudert.

## Gerelateerd

- [Architectuuroverzicht](11-architecture.md): waar de database past
- [Probleemoplossing](15-troubleshooting.md): databasefaalpatronen
- Voor mediakopers: [Data-import](09-data-import.md) behandelt het gebruikersgerichte dataversheidsraster.
