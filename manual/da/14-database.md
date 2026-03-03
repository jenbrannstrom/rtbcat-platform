# Kapitel 14: Databaseoperationer

*Målgruppe: DevOps, platformingeniører*

## Postgres i produktion

Cat-Scan bruger Cloud SQL (Postgres 15) som sin eneste operationelle database. API'et forbinder via en Cloud SQL Auth Proxy sidecar-container på `localhost:5432`.

### Vigtige tabeller og skala

| Tabel | Omtrentligt rækkeantal | Hvad den gemmer |
|-------|------------------------|-----------------|
| `rtb_daily` | ~84 millioner | Daglig RTB-performance pr. køber, kreativ, geografi osv. |
| `rtb_bidstream` | ~21 millioner | Bidstream-opdeling pr. udgiver, geografi |
| `rtb_quality` | varierer | Kvalitetsmetrikker (viewability, brand safety) |
| `rtb_bid_filtering` | ~188 tusind | Årsager til budfiltrering og mængder |
| `pretargeting_configs` | lille | Snapshots af pretargeting-konfiguration |
| `creatives` | lille | Kreativmetadata og miniaturer |
| `import_history` | lille | CSV-importposter |
| `users`, `permissions`, `audit_log` | lille | Autentificerings- og administrationsdata |

### Kritiske indekser

Det mest performancefølsomme indeksmønster er:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

Dette findes på `rtb_daily`, `rtb_bidstream`, `rtb_quality` og
`rtb_bid_filtering`. Det understøtter datafriskheds­forespørgslen og køberbaserede analyser.

Andre vigtige indekser:
- `(metric_date, buyer_account_id)`: til datointerval + køberfiltre
- `(metric_date, billing_id)`: til faktureringsbaserede forespørgsler
- `(row_hash)` UNIQUE: deduplikering ved import

### Deduplikering

Hver importeret række hashes (`row_hash`-kolonnen). Unique-constrainten på `row_hash` forhindrer duplikerede indsættelser, hvilket gør genimport sikkert.

## Forbindelsesmodel

API'et bruger **forbindelser pr. forespørgsel** (ingen connection pool). Hver forespørgsel opretter et nyt `psycopg.connect()`-kald, pakket ind i `run_in_executor` for asynkron kompatibilitet.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

For produktionsbelastninger kan det overvejes at tilføje `psycopg_pool`, hvis forbindelsesoverhead bliver en flaskehals.

## Statement-timeouts

For dyre forespørgsler (f.eks. datafriskhed på tværs af store tabeller) bruger API'et `pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Vigtige detaljer:
- `SET LOCAL` begrænser timeoutet til den aktuelle transaktion og nulstilles automatisk, når transaktionen afsluttes (commit eller rollback).
- Standard datafriskheds-timeout: 30 sekunder.
- Konfigurerbar via miljøvariablen `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (minimum 1000 ms).
- `SET LOCAL` undgår problemet med afbrudte transaktioner, som opstår ved brug af `SET` + `RESET` i en `try/finally`-blok (hvis forespørgslen annulleres af timeoutet, går transaktionen i en afbrudt tilstand, og `RESET` fejler).

## Forespørgselsmønster for datafriskhed

Datafriskheds-endpointet skal vide, hvilke datoer der har data for hver rapporttype. Det performante mønster bruger `generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

Dette udfører N indeksopslag (ét pr. dag i vinduet) i stedet for at scanne millioner af rækker. For et 14-dages vindue: 14 opslag á ~0,1 ms hver mod en fuld parallel sekventiel scanning, der tager 160+ sekunder.

**Hvorfor GROUP BY ikke virker her:** Selv med `1 AS row_count` (ingen COUNT) vælger queryplanlæggeren en sekventiel scanning, når GROUP BY-resultatsættet er stort i forhold til tabellen. Indekset `(buyer_account_id, metric_date DESC)` eksisterer, men planlæggeren estimerer, at det er billigere at scanne 84M rækker end at udføre 4,4M indeksopslag.

## BigQuerys rolle

BigQuery gemmer rå, granulære data og kører batchanalysejobs. Det bruges ikke til realtids-API-forespørgsler. Mønsteret:

1. Rå CSV-data indlæses i BigQuery-tabeller.
2. Batchjobs aggregerer dataene.
3. Foraggregerede resultater skrives til Postgres.
4. API'et serverer fra Postgres.

## Dataopbevaring

Konfigurerbar via `/settings/retention`. Styrer hvor længe historiske data bevares i Postgres, før de fjernes.

## Relateret

- [Arkitekturoversigt](11-architecture.md): hvor databasen passer ind
- [Fejlfinding](15-troubleshooting.md): databasefejlmønstre
- For mediekøbere: [Dataimport](09-data-import.md) dækker det brugervendte datafriskheds­gitter.
