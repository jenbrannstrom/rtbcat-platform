# CatScan Platform — Contract Catalog & Reliability Specification

**Status:** Normative specification (stable rules)  
**Version:** 1.1  
**As-of Date:** 2026-02-11 UTC

This document defines **what must be true** (contracts), not a point-in-time incident snapshot.

Execution rules:
- All contracts apply to **all active buyers**, not a single seat.
- Any buyer IDs in SQL snippets are examples and must be parameterized (`<BUYER_ID>` / buyer loop).
- Deployment SHA notes and live pass/fail outcomes belong in baseline artifacts, not this file.
- Current environment status must be recorded separately under `docs/recovery/`.

---

## Section A: Executive Answer

### What "Good" Looks Like

A correctly-operating CatScan instance satisfies all of the following simultaneously:

1. **Every registered buyer** has precomputed data for at least the last 7 calendar days across all 5 home_* tables and all 4 config_* tables.
2. **Every billing_id** in `pretargeting_configs` (state=ACTIVE) has corresponding rows in `home_config_daily` and `config_creative_daily` for the same 7-day window.
3. **`rtb_endpoints_current`** has at least 1 row per registered endpoint in `rtb_endpoints`, observed within the last 24 hours, so that endpoint-efficiency can report real QPS.
4. **API responses** never present proxy/estimated metrics as observed truth. Fields named `observed_*` come exclusively from `rtb_endpoints_current`; funnel-derived approximations are labeled explicitly as `proxy` or `estimated`.
5. **The UI** renders one of four explicit states per panel: `ready` (data present), `refreshing` (fetch in flight), `missing_feed` (API returned null/empty for a specific feed), or `no_data` (buyer has zero rows). It never shows stale data without a staleness indicator.
6. **Non-admin API P95** < 500ms for all analytics endpoints at the current single-buyer scale.
7. **Every deploy** passes a contract validation suite before the image tag is promoted to production.

### Overall Confidence: 0.72

### Key Caveats

1. **FACT**: `rtb_endpoints_current` is currently empty (0 rows, all bidders). No QPS observation job exists in the deployed codebase. Confidence that endpoint-efficiency can ever show observed QPS without new code: 0.0.
2. **FACT**: `ingestion_runs` table is empty and nothing writes to it in the current pipeline.
3. **FACT**: `config_publisher_daily` has 0 rows for buyer `<BUYER_ID>`. The BQ self-join that populates it requires `publisher_id` in `rtb_daily` which may be missing from CSV reports.
4. **FACT**: `import_history` only tracks buyer `<BUYER_ID>`, not <BUYER_ID>. Gmail import worker does not write to `import_history` for all buyers.
5. **FACT**: No tests run in CI. The build-and-push workflow has zero test steps.
6. **FACT**: No post-deploy health check or rollback mechanism exists.
7. **INFERENCE**: Precompute is triggered manually or after import — there is no cron schedule ensuring daily freshness.
8. **FACT**: The DELETE-then-INSERT pattern in all precompute services means a crash mid-transaction leaves the date range empty until retry.
9. **INFERENCE**: BigQuery tables may lag Postgres raw tables if the Parquet export pipeline is not run.
10. **FACT**: `billing_id=777777777777` (IDN_Banner_Instl) exists in pretargeting_configs but has no precomputed data.

---

## Section B: System Decomposition

### Subsystem 1: Sources (Gmail/GCS/Manual/API)

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| Gmail import fetches CSV from GCS or attachment | FACT: Dual-path implemented in `gmail_import.py` | 0.95 |
| OAuth token has correct scopes | FACT: Re-authed with gmail.modify + devstorage.read_only | 0.90 |
| Manual CSV upload via API | FACT: `/performance/import-csv` endpoint exists | 0.85 |
| Google API sync for seats/configs/endpoints | FACT: collectors and services exist | 0.85 |
| **Risk**: No scheduled trigger ensures daily import | INFERENCE: No cron job found in codebase | 0.80 |
| **Risk**: No monitoring of Gmail inbox for missed emails | INFERENCE: No alerting on unread count | 0.75 |

### Subsystem 2: Ingestion/Normalization

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| `unified_importer.py` auto-detects report type | FACT: Matches column patterns to rtb_daily/rtb_bidstream/rtb_bid_filtering | 0.90 |
| Dedup via `row_hash` ON CONFLICT DO NOTHING | FACT: Verified in code line 296 | 0.95 |
| `buyer_account_id` fallback to bidder_id from filename | FACT: Lines 369-372 | 0.90 |
| `billing_id` defaults to "unknown" if missing from CSV | FACT: Line 335 | 0.95 |
| **Risk**: `ingestion_runs` table never populated | FACT: Table exists but 0 rows, no writer found | 0.95 |
| **Risk**: `import_history` only populated for some buyers | FACT: Only buyer `<BUYER_ID>` in evidence | 0.85 |
| **Risk**: Spend conversion heuristic (< 1000 → multiply by 1M) | FACT: Line 376 — fragile threshold | 0.90 |

### Subsystem 3: Raw/Staging Tables

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| `rtb_daily` has data for buyer `<BUYER_ID>` | INFERENCE: Precompute succeeds, so raw data exists | 0.85 |
| `rtb_bidstream` has data | INFERENCE: home_seat_daily populated from it via BQ | 0.80 |
| BigQuery mirrors are current | INFERENCE: Precompute runs BQ queries successfully | 0.75 |
| **Risk**: No row-count monitoring on raw tables | INFERENCE: No alerts or checks found | 0.85 |
| **Risk**: Parquet export may not run automatically | INFERENCE: `run_pipeline.py` exists but no cron trigger found | 0.75 |

### Subsystem 4: Precompute/Serving Tables

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| 5 home_* tables populated via `refresh_home_summaries()` | FACT: Code verified, data present through 2026-02-08 | 0.95 |
| 4 config_* tables populated via `refresh_config_breakdowns()` | FACT: 3/4 have data; config_publisher_daily = 0 rows | 0.90 |
| 7 rtb_* tables populated via `refresh_rtb_summaries()` | FACT: Code verified | 0.85 |
| `precompute_refresh_log` tracks refreshes | FACT: Latest entry 2026-02-11T03:00:07 | 0.95 |
| **Risk**: DELETE-then-INSERT pattern is not crash-safe | FACT: A crash between DELETE and INSERT leaves a gap | 0.90 |
| **Risk**: `config_publisher_daily` requires self-join that fails when publisher_id missing | FACT: 0 rows for buyer `<BUYER_ID>` | 0.90 |
| **Risk**: No validation that precompute output row counts are non-zero | INFERENCE: Code has no post-insert count check | 0.85 |

### Subsystem 5: API Semantics

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| `/analytics/home/funnel` returns `data_state` field | FACT: "unavailable"/"degraded"/"healthy" | 0.95 |
| `/analytics/home/endpoint-efficiency` separates observed vs proxy | FACT: `endpoint_delivery_state`, `funnel_proxy_qps_avg` fields exist in code (commit 9f65ba3) | 0.90 |
| **Risk**: Deployed version may not include latest endpoint-efficiency semantic fields | FACT: Must be verified per baseline artifact (`docs/recovery/`) | 0.95 |
| **Risk**: Generic `except Exception` returns 500 with raw error string | FACT: All analytics routes use `raise HTTPException(500, detail=str(e))` | 0.90 |
| **Risk**: No request timeout on precompute API calls | INFERENCE: FastAPI default timeouts apply | 0.75 |

### Subsystem 6: UI State Semantics

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| Seat gating: queries fire only when `seatReady = !!selectedBuyerId` | FACT: Line 118+128+139+159+173+181 | 0.95 |
| Auto-selects first seat if none selected | FACT: Lines 74-78 | 0.95 |
| React Query `isLoading` / `isError` available per query | FACT: Standard React Query pattern | 0.95 |
| Client timeout 12s on configs and endpoint-efficiency | FACT: `timeoutMs: 12000` in analytics.ts | 0.90 |
| **Risk**: No explicit "missing_feed" UI state for empty rtb_endpoints_current | FACT: Panel shows "Feed missing" only after 9f65ba3 deployed | 0.90 |
| **Risk**: No staleness indicator when precompute data is >24h old | INFERENCE: UI shows date range but no "stale" warning | 0.80 |

### Subsystem 7: Observability/Control Plane

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| `/health` endpoint exists | FACT: Returns status, version, git_sha, configured, database_exists | 0.95 |
| `/system/data-health` endpoint exists | FACT: Returns source/serving freshness, coverage, ingestion_runs | 0.90 |
| **Risk**: No structured logging or metrics export | INFERENCE: Uses Python `logging` module only | 0.80 |
| **Risk**: No external monitoring (Prometheus, Datadog, etc.) | INFERENCE: No monitoring config found | 0.85 |
| **Risk**: No alerting on data freshness or pipeline failures | INFERENCE: No alert mechanism found | 0.90 |

### Subsystem 8: CI/CD Release Gates

| Aspect | Current State | Confidence |
|--------|--------------|------------|
| GitHub Actions builds and pushes Docker images | FACT: build-and-push.yml verified | 0.95 |
| `paths-ignore` skips docs/** and *.md | FACT: Verified in workflow | 0.95 |
| **Risk**: Zero test steps in CI | FACT: No `pytest`, `npm test`, or any test command in workflow | 0.95 |
| **Risk**: No health check after deploy | FACT: Deploy is manual `docker pull && restart` | 0.90 |
| **Risk**: No rollback mechanism | INFERENCE: Manual docker tag switch is only option | 0.85 |
| **Risk**: No contract validation gate | FACT: Nothing blocks deploy on data integrity failures | 0.95 |

---

## Section C: Contract Catalog

---

### CONTRACT GROUP 1: Source Coverage

#### C-SRC-001: Gmail Import Produces Rows

| Field | Value |
|-------|-------|
| **Contract ID** | C-SRC-001 |
| **Rule** | For every active buyer in `buyer_seats`, at least 1 CSV import must succeed per calendar day, producing ≥1 row in `rtb_daily`. |
| **Scope** | All active buyers, daily |
| **Why it matters** | If no CSV arrives, precompute produces stale data. The dashboard shows yesterday's numbers without warning. |
| **Detection method** | SQL: `SELECT bs.buyer_id, MAX(ih.imported_at) as last_import FROM buyer_seats bs LEFT JOIN import_history ih ON ih.filename LIKE '%' || bs.buyer_id || '%' WHERE bs.active = true GROUP BY bs.buyer_id HAVING MAX(ih.imported_at) < NOW() - INTERVAL '36 hours' OR MAX(ih.imported_at) IS NULL` |
| **Check frequency** | Every 6 hours |
| **Alert condition** | Any active buyer with no import in 36 hours → severity HIGH |
| **Failure behavior** | API must set `data_state: "degraded"` with `staleness_warning: "Last import >36h ago"`. UI shows amber staleness badge. |
| **Remediation runbook** | 1. Check Gmail inbox for unread emails: `python scripts/gmail_import.py --check-unread`. 2. If emails present, run import: `python scripts/gmail_import.py`. 3. If no emails, check Google Authorized Buyers scheduled report configuration. 4. After import, trigger precompute: `python scripts/refresh_precompute.py --days=7`. |
| **Pass criteria** | Every active buyer has import_history.imported_at within last 36 hours AND rows_imported > 0 |
| **Owner** | Pipeline team |
| **Confidence** | 0.85 |
| **Caveats** | `import_history` currently only tracks buyer `<BUYER_ID>`. This contract requires fixing the import worker to write import_history for ALL buyers. |

#### C-SRC-002: Gmail Unread Backlog Zero

| Field | Value |
|-------|-------|
| **Contract ID** | C-SRC-002 |
| **Rule** | The Gmail inbox monitored by `gmail_import.py` must have 0 unread messages matching the report subject pattern after each import run. |
| **Scope** | Gmail inbox, per import run |
| **Why it matters** | Unread emails = unprocessed reports = missing data for some days/buyers. |
| **Detection method** | Shell: `python scripts/gmail_import.py --check-unread` should return `unread_count: 0`. |
| **Check frequency** | After every import run |
| **Alert condition** | unread_count > 0 after import completes → severity MEDIUM |
| **Failure behavior** | Log warning with count and subject lines of unread messages. |
| **Remediation runbook** | 1. Run `python scripts/gmail_import.py` again (handles partial batches). 2. If still unread, check for parse errors in import log. 3. If OAuth token expired, re-auth: `python scripts/gmail_import.py --auth`. |
| **Pass criteria** | unread_count = 0 |
| **Owner** | Pipeline team |
| **Confidence** | 0.90 |
| **Caveats** | Requires gmail.modify scope to mark as read. Confirmed working after re-auth. |

---

### CONTRACT GROUP 2: Ingestion Run Logging

#### C-ING-001: Every Import Run Logged in ingestion_runs

| Field | Value |
|-------|-------|
| **Contract ID** | C-ING-001 |
| **Rule** | Every invocation of `unified_importer.py` must create exactly 1 row in `ingestion_runs` with status='success' or status='failed', non-null `started_at`, `finished_at`, and `row_count`. |
| **Scope** | All import invocations |
| **Why it matters** | `ingestion_runs` is currently empty (0 rows). Without it, there is no audit trail of what was imported when, making debugging data gaps impossible. |
| **Detection method** | SQL: `SELECT COUNT(*) as cnt FROM ingestion_runs` — must be > 0. Additionally: `SELECT COUNT(*) FROM ingestion_runs WHERE finished_at IS NULL AND started_at < NOW() - INTERVAL '1 hour'` — must be 0 (no stuck runs). |
| **Check frequency** | After every import |
| **Alert condition** | Table has 0 rows → severity HIGH. Any run with finished_at IS NULL older than 1 hour → severity MEDIUM. |
| **Failure behavior** | `/system/data-health` must report `ingestion_runs.total_runs: 0` as state "degraded". |
| **Remediation runbook** | 1. Verify `unified_importer.py` writes to `ingestion_runs` — CURRENTLY IT DOES NOT. 2. Add INSERT at start and UPDATE at end of `unified_import()`. 3. Columns: run_id (uuid), source_type ('csv'/'api'), buyer_id, started_at, finished_at, status, row_count, error_summary. |
| **Pass criteria** | `ingestion_runs` has ≥1 row per import, all with non-null finished_at |
| **Owner** | Pipeline team |
| **Confidence** | 0.95 |
| **Caveats** | FACT: This table is currently never written to. Contract requires code change to implement. |

#### C-ING-002: import_history Covers All Buyers

| Field | Value |
|-------|-------|
| **Contract ID** | C-ING-002 |
| **Rule** | For every active buyer in `buyer_seats`, `import_history` must contain at least 1 row with `rows_imported > 0` per 48-hour window. |
| **Scope** | All active buyers |
| **Why it matters** | Currently only buyer `<BUYER_ID>` appears in import_history. buyer `<BUYER_ID>` has no import tracking despite having precomputed data. |
| **Detection method** | SQL: `SELECT bs.buyer_id, COUNT(ih.id) as imports FROM buyer_seats bs LEFT JOIN import_history ih ON ih.filename LIKE '%' || bs.buyer_id || '%' AND ih.imported_at > NOW() - INTERVAL '48 hours' WHERE bs.active = true GROUP BY bs.buyer_id HAVING COUNT(ih.id) = 0` |
| **Check frequency** | Every 12 hours |
| **Alert condition** | Any active buyer with 0 imports in 48h → severity MEDIUM |
| **Failure behavior** | API should expose per-buyer import status in `/system/data-health`. |
| **Remediation runbook** | 1. Check that `gmail_import_worker.py` records to `import_history` for the missing buyer. 2. If filename pattern doesn't match, fix the filename-to-buyer mapping. 3. Manually run import for the missing buyer. |
| **Pass criteria** | All active buyers have ≥1 import_history row per 48h |
| **Owner** | Pipeline team |
| **Confidence** | 0.85 |
| **Caveats** | The filename LIKE pattern may not match all buyers if filenames don't contain buyer_id. May need a dedicated buyer_id column in import_history. |

---

### CONTRACT GROUP 3: Raw Table Freshness

#### C-RAW-001: rtb_daily Freshness

| Field | Value |
|-------|-------|
| **Contract ID** | C-RAW-001 |
| **Rule** | For every active buyer, `rtb_daily` must contain rows with `metric_date >= CURRENT_DATE - 3` (allowing for report delivery lag). |
| **Scope** | All active buyers, rtb_daily |
| **Why it matters** | Precompute reads from BigQuery which mirrors rtb_daily. If raw data is stale, all downstream tables are stale. |
| **Detection method** | SQL: `SELECT buyer_account_id, MAX(metric_date::date) as latest FROM rtb_daily WHERE buyer_account_id IN (SELECT buyer_id FROM buyer_seats WHERE active = true) GROUP BY buyer_account_id HAVING MAX(metric_date::date) < CURRENT_DATE - 3` |
| **Check frequency** | Every 12 hours |
| **Alert condition** | Any buyer with latest metric_date > 3 days old → severity HIGH |
| **Failure behavior** | API sets `data_state: "degraded"` with `stale_since` field. |
| **Remediation runbook** | 1. Check import_history for recent imports. 2. If no imports, run gmail_import.py. 3. If imports exist but data missing, check unified_importer logs for parse errors. |
| **Pass criteria** | All active buyers have rtb_daily rows within 3 days of current date |
| **Owner** | Pipeline team |
| **Confidence** | 0.80 |
| **Caveats** | Google report delivery can lag 1-2 days. 3-day threshold accounts for this. Metric_date is TEXT type, requires cast. |

#### C-RAW-002: BigQuery Sync Currency

| Field | Value |
|-------|-------|
| **Contract ID** | C-RAW-002 |
| **Rule** | BigQuery `rtb_daily` and `rtb_bidstream` tables must have MAX(metric_date) within 1 day of Postgres `rtb_daily` MAX(metric_date). |
| **Scope** | BigQuery ↔ Postgres sync |
| **Why it matters** | Precompute reads from BigQuery. If BQ is behind Postgres, precomputed tables miss recent days. |
| **Detection method** | Compare Postgres `SELECT MAX(metric_date) FROM rtb_daily` with BigQuery `SELECT MAX(metric_date) FROM rtb_daily`. Difference must be ≤ 1 day. |
| **Check frequency** | After every import + Parquet export |
| **Alert condition** | BQ behind Postgres by > 1 day → severity HIGH |
| **Failure behavior** | Precompute should refuse to run (or warn) if BQ is stale. |
| **Remediation runbook** | 1. Run Parquet export: `python scripts/export_csv_to_parquet.py`. 2. Load to BQ: `python scripts/load_parquet_to_bigquery.py`. 3. Verify: `bq query 'SELECT MAX(metric_date) FROM rtb_daily'`. |
| **Pass criteria** | |MAX(PG) - MAX(BQ)| ≤ 1 day |
| **Owner** | Pipeline team |
| **Confidence** | 0.75 |
| **Caveats** | Cannot verify BQ state from evidence alone. This is an INFERENCE-based contract. |

---

### CONTRACT GROUP 4: Endpoint Observed Feed

#### C-EPT-001: rtb_endpoints_current Populated

| Field | Value |
|-------|-------|
| **Contract ID** | C-EPT-001 |
| **Rule** | `rtb_endpoints_current` must have ≥1 row per endpoint in `rtb_endpoints`, with `observed_at` within the last 24 hours. |
| **Scope** | All bidders with endpoints |
| **Why it matters** | `rtb_endpoints_current` is the source of truth for observed endpoint QPS in endpoint-efficiency and related UI/API fields. If rows are missing or stale, observed QPS/utilization/overshoot become unavailable or misleadingly stale. |
| **Detection method** | SQL: `SELECT e.bidder_id, e.endpoint_id, ec.observed_at FROM rtb_endpoints e LEFT JOIN rtb_endpoints_current ec ON e.bidder_id = ec.bidder_id AND e.endpoint_id = ec.endpoint_id WHERE ec.id IS NULL OR ec.observed_at < NOW() - INTERVAL '24 hours'` |
| **Check frequency** | Every 1 hour |
| **Alert condition** | Any endpoint missing from rtb_endpoints_current or observed_at > 24h → severity HIGH |
| **Failure behavior** | API sets `endpoint_delivery_state: "missing"` and emits alert `ENDPOINT_DELIVERY_MISSING`. UI must show "Feed missing" in red. |
| **Remediation runbook** | 1. Trigger a refresh path that updates endpoint observations (for example `python scripts/refresh_precompute.py --days 7` or the scheduled precompute refresh endpoint). 2. Verify `rtb_endpoints_current` row count/freshness against `rtb_endpoints`. 3. If stale recurs, inspect active schedulers (`catscan-home-refresh` timer and/or `/api/precompute/refresh/scheduled`) and confirm endpoint observation refresh is included (fix shipped in `cabab81`, deployed 2026-02-25). |
| **Pass criteria** | Every endpoint in rtb_endpoints has a corresponding rtb_endpoints_current row with observed_at < 24h ago |
| **Owner** | Pipeline team |
| **Confidence** | 0.95 |
| **Caveats** | Freshness depends on scheduled refresh cadence/execution; contract can fail if precompute/home refresh jobs run but endpoint observation refresh is omitted or not running. |

#### C-EPT-002: Endpoint Config Sync

| Field | Value |
|-------|-------|
| **Contract ID** | C-EPT-002 |
| **Rule** | `rtb_endpoints` must have ≥1 row per active bidder in `buyer_seats`. `synced_at` must be within the last 48 hours. |
| **Scope** | All active bidders |
| **Why it matters** | If endpoint configs are stale, allocated_qps in the UI may not reflect reality. |
| **Detection method** | SQL: `SELECT bs.bidder_id, COUNT(e.id) as endpoints, MAX(e.synced_at) as last_sync FROM buyer_seats bs LEFT JOIN rtb_endpoints e ON bs.bidder_id = e.bidder_id WHERE bs.active = true GROUP BY bs.bidder_id HAVING COUNT(e.id) = 0 OR MAX(e.synced_at) < NOW() - INTERVAL '48 hours'` |
| **Check frequency** | Every 12 hours |
| **Alert condition** | Any bidder with 0 endpoints or sync > 48h → severity MEDIUM |
| **Failure behavior** | API should warn when endpoint data is stale. |
| **Remediation runbook** | 1. Trigger endpoint sync: call `/seats/sync` or run `services/endpoints_service.py`. 2. Verify endpoints exist: `SELECT * FROM rtb_endpoints WHERE bidder_id = ?`. |
| **Pass criteria** | All active bidders have ≥1 endpoint, synced < 48h ago |
| **Owner** | Pipeline team |
| **Confidence** | 0.85 |
| **Caveats** | Current data shows 3 endpoints for <BUYER_ID> synced 2026-02-11 02:20 — working correctly. |

---

### CONTRACT GROUP 5: Precompute Completeness

#### C-PRE-001: home_seat_daily Window Coverage

| Field | Value |
|-------|-------|
| **Contract ID** | C-PRE-001 |
| **Rule** | For every active buyer, `home_seat_daily` must have exactly 1 row per calendar day for the last N days (N = requested window: 7, 14, or 30). No gaps allowed. |
| **Scope** | All active buyers, windows 7/14/30 |
| **Why it matters** | Missing days cause incorrect funnel totals and misleading win_rate calculations. The API sums across the window — a missing day silently reduces the denominator. |
| **Detection method** | SQL: `WITH dates AS (SELECT generate_series(CURRENT_DATE - 7, CURRENT_DATE - 1, '1 day'::interval)::date as d) SELECT d FROM dates WHERE d::text NOT IN (SELECT metric_date FROM home_seat_daily WHERE buyer_account_id = '<BUYER_ID>')` — must return 0 rows. |
| **Check frequency** | After every precompute refresh |
| **Alert condition** | Any missing day in 7-day window → severity HIGH |
| **Failure behavior** | API must include `missing_dates: [...]` in response and set `data_state: "degraded"`. |
| **Remediation runbook** | 1. Check `precompute_refresh_log` for last refresh timestamp. 2. If stale, run: `python scripts/refresh_precompute.py --days=N`. 3. If BQ has no data for missing dates, check raw table and import pipeline. |
| **Pass criteria** | Zero missing days in the requested window |
| **Owner** | Pipeline team |
| **Confidence** | 0.90 |
| **Caveats** | Current data shows 27 rows covering 2026-01-13 to 2026-02-08. For a 7-day window from today (Feb 11), Feb 9-10 would be missing — this is expected due to report delivery lag. Threshold should be CURRENT_DATE - 3 as the latest expected date. |

#### C-PRE-002: home_config_daily Billing Coverage

| Field | Value |
|-------|-------|
| **Contract ID** | C-PRE-002 |
| **Rule** | For every ACTIVE pretargeting config (from `pretargeting_configs`), `home_config_daily` must have ≥1 row in the last 7 days. The set of billing_ids in home_config_daily must be a superset of ACTIVE billing_ids in pretargeting_configs. |
| **Scope** | Per buyer, 7-day window |
| **Why it matters** | FACT: billing_id 777777777777 (IDN_Banner_Instl) is ACTIVE in pretargeting_configs but has 0 rows in home_config_daily. This config is invisible in the dashboard. |
| **Detection method** | SQL: `SELECT pc.billing_id, pc.display_name FROM pretargeting_configs pc WHERE pc.bidder_id = '<BUYER_ID>' AND pc.state = 'ACTIVE' AND pc.billing_id NOT IN (SELECT DISTINCT billing_id FROM home_config_daily WHERE buyer_account_id = '<BUYER_ID>' AND metric_date >= (CURRENT_DATE - 7)::text)` |
| **Check frequency** | After every precompute refresh |
| **Alert condition** | Any ACTIVE config missing from precompute → severity MEDIUM |
| **Failure behavior** | API should include `missing_configs: [...]` in the config payload. UI shows the config card with a "No data" indicator. |
| **Remediation runbook** | 1. Check if the config's billing_id appears in `rtb_daily`: `SELECT COUNT(*) FROM rtb_daily WHERE billing_id = '777777777777'`. 2. If 0, the config may have no traffic yet or the CSV report doesn't include it. 3. If present in rtb_daily but not in BQ, re-run Parquet export + BQ load. 4. If present in BQ but not in precompute, re-run `refresh_config_breakdowns()`. |
| **Pass criteria** | All ACTIVE pretargeting configs have ≥1 row in home_config_daily within the window |
| **Owner** | Pipeline team |
| **Confidence** | 0.90 |
| **Caveats** | New configs with zero traffic are legitimately absent. Consider adding a `no_traffic` state. |

#### C-PRE-003: config_publisher_daily Non-Empty

| Field | Value |
|-------|-------|
| **Contract ID** | C-PRE-003 |
| **Rule** | For every active buyer with data in `home_config_daily`, `config_publisher_daily` must have ≥1 row in the same window. |
| **Scope** | Per buyer, 7-day window |
| **Why it matters** | FACT: `config_publisher_daily` has 0 rows for buyer `<BUYER_ID>`. The publisher breakdown panel returns empty. This is caused by the BQ self-join in `config_precompute.py` lines 487-523 failing when `publisher_id` is empty in the CSV. |
| **Detection method** | SQL: `SELECT COUNT(*) FROM config_publisher_daily WHERE buyer_account_id = '<BUYER_ID>'` — must be > 0 if home_config_daily has data. |
| **Check frequency** | After every precompute refresh |
| **Alert condition** | 0 rows when peer tables have data → severity MEDIUM |
| **Failure behavior** | API sets `data_state: "degraded"` with `fallback_reason: "publisher dimension unavailable"`. |
| **Remediation runbook** | 1. Check if `rtb_daily` has publisher_id populated: `SELECT COUNT(*), COUNT(NULLIF(publisher_id, '')) FROM rtb_daily WHERE buyer_account_id = '<BUYER_ID>'`. 2. If publisher_id is mostly empty, the CSV report type doesn't include publisher. Need a different report type or API fallback. 3. If publisher_id exists in raw data but not in precompute, check BQ self-join logic. |
| **Pass criteria** | config_publisher_daily row count > 0 when home_config_daily row count > 0 |
| **Owner** | Pipeline team |
| **Confidence** | 0.85 |
| **Caveats** | Some CSV report types genuinely don't include publisher_id. The contract should tolerate this with explicit state labeling. |

#### C-PRE-004: Precompute Refresh Recency

| Field | Value |
|-------|-------|
| **Contract ID** | C-PRE-004 |
| **Rule** | `precompute_refresh_log` must show a refresh for each cache_name (`home_summaries`, `config_breakdowns`, `rtb_summaries`) within the last 24 hours. |
| **Scope** | All cache names |
| **Why it matters** | If precompute hasn't run, the dashboard shows stale data without any indication. |
| **Detection method** | SQL: `SELECT cache_name, MAX(refreshed_at) as last_refresh FROM precompute_refresh_log WHERE buyer_account_id = '__all__' GROUP BY cache_name HAVING MAX(refreshed_at::timestamp) < NOW() - INTERVAL '24 hours'` |
| **Check frequency** | Every 6 hours |
| **Alert condition** | Any cache_name not refreshed in 24h → severity HIGH |
| **Failure behavior** | API must include `precompute_age_hours` in response. UI shows amber "Data may be stale" if > 24h. |
| **Remediation runbook** | 1. Run `python scripts/refresh_precompute.py --days=7`. 2. Verify: `SELECT * FROM precompute_refresh_log ORDER BY refreshed_at DESC LIMIT 5`. 3. If fails, check BigQuery connectivity and credentials. |
| **Pass criteria** | All 3 cache names refreshed within last 24h |
| **Owner** | Pipeline team |
| **Confidence** | 0.90 |
| **Caveats** | `refreshed_at` is TEXT type, not TIMESTAMPTZ. Parsing may vary. |

---

### CONTRACT GROUP 6: Key Consistency

#### C-KEY-001: buyer_id = bidder_id Invariant

| Field | Value |
|-------|-------|
| **Contract ID** | C-KEY-001 |
| **Rule** | In `buyer_seats`, every row must satisfy `buyer_id = bidder_id` (the Google Authorized Buyers platform uses the same ID for both). |
| **Scope** | buyer_seats table |
| **Why it matters** | The code uses buyer_id and bidder_id interchangeably in different contexts. If they diverge, joins between precompute tables (keyed on buyer_account_id) and dimension tables (keyed on bidder_id) break silently. |
| **Detection method** | SQL: `SELECT * FROM buyer_seats WHERE buyer_id != bidder_id` — must return 0 rows. |
| **Check frequency** | After every seat sync |
| **Alert condition** | Any row with buyer_id ≠ bidder_id → severity CRITICAL |
| **Failure behavior** | Seat sync must reject or flag mismatched IDs. |
| **Remediation runbook** | 1. Investigate the Google API response for the mismatched account. 2. Determine which ID is canonical. 3. Update buyer_seats accordingly. |
| **Pass criteria** | 0 rows with buyer_id ≠ bidder_id |
| **Owner** | Platform team |
| **Confidence** | 0.90 |
| **Caveats** | FACT: Current data shows buyer_id = bidder_id = '<BUYER_ID>'. This invariant may not hold for all Google account types. |

#### C-KEY-002: Pretargeting Config Billing ID Uniqueness

| Field | Value |
|-------|-------|
| **Contract ID** | C-KEY-002 |
| **Rule** | Every `billing_id` in `pretargeting_configs` must be unique within a `bidder_id`. No duplicate billing_ids per bidder. |
| **Scope** | pretargeting_configs table |
| **Why it matters** | Precompute tables use billing_id as a grouping key. Duplicate billing_ids would cause double-counting. |
| **Detection method** | SQL: `SELECT bidder_id, billing_id, COUNT(*) FROM pretargeting_configs GROUP BY bidder_id, billing_id HAVING COUNT(*) > 1` — must return 0 rows. |
| **Check frequency** | After every config sync |
| **Alert condition** | Any duplicate → severity HIGH |
| **Failure behavior** | Config sync must deduplicate or reject. |
| **Remediation runbook** | 1. Identify the duplicate rows. 2. Keep the most recent (by synced_at). 3. Delete the older duplicate. |
| **Pass criteria** | 0 duplicate billing_id per bidder_id |
| **Owner** | Platform team |
| **Confidence** | 0.95 |
| **Caveats** | None. |

#### C-KEY-003: "unknown" Billing ID Tracked

| Field | Value |
|-------|-------|
| **Contract ID** | C-KEY-003 |
| **Rule** | The presence of `billing_id = 'unknown'` in `home_config_daily` must be tracked and its percentage of total reached queries must be < 20%. |
| **Scope** | Per buyer, rolling 7 days |
| **Why it matters** | FACT: 'unknown' appears in home_config_daily for buyer `<BUYER_ID>`. This represents traffic that couldn't be attributed to a pretargeting config, making per-config analytics inaccurate. |
| **Detection method** | SQL: `SELECT SUM(CASE WHEN billing_id = 'unknown' THEN reached_queries ELSE 0 END) * 100.0 / NULLIF(SUM(reached_queries), 0) as unknown_pct FROM home_config_daily WHERE buyer_account_id = '<BUYER_ID>' AND metric_date >= (CURRENT_DATE - 7)::text` |
| **Check frequency** | After every precompute refresh |
| **Alert condition** | unknown_pct > 20% → severity MEDIUM; > 50% → severity HIGH |
| **Failure behavior** | API should include `unknown_traffic_pct` in config response. |
| **Remediation runbook** | 1. Check if CSV reports include billing_id column. 2. If missing, the report type needs to be changed to include pretargeting config breakdown. 3. Check `unified_importer.py` billing_id mapping — default is "unknown" when column missing. |
| **Pass criteria** | unknown_pct < 20% |
| **Owner** | Pipeline team |
| **Confidence** | 0.85 |
| **Caveats** | Some report types legitimately don't include billing_id. The "unknown" bucket may be irreducible for certain data sources. |

---

### CONTRACT GROUP 7: API Semantic Correctness

#### C-API-001: No Proxy Masquerading as Observed

| Field | Value |
|-------|-------|
| **Contract ID** | C-API-001 |
| **Rule** | The API field `observed_query_rate_qps` must come EXCLUSIVELY from `rtb_endpoints_current`. It must NEVER be computed from `home_seat_daily.reached_queries / window_seconds`. That derived value must be in a separately-named field (`funnel_proxy_qps_avg`). |
| **Scope** | `/analytics/home/endpoint-efficiency` response |
| **Why it matters** | Mixing proxy and observed metrics makes it impossible for the user to know if they're seeing real endpoint telemetry or a back-computed estimate. Commit 9f65ba3 fixed this but is NOT DEPLOYED. |
| **Detection method** | API test: Call `/analytics/home/endpoint-efficiency?buyer_id=<BUYER_ID>&days=7`. Verify: (1) `summary.observed_query_rate_qps` is null when `rtb_endpoints_current` has 0 rows. (2) `summary.funnel_proxy_qps_avg` is present and > 0. (3) `summary.endpoint_delivery_state` is "missing" when no observed data. |
| **Check frequency** | On every deploy, as part of smoke tests |
| **Alert condition** | `observed_query_rate_qps` is non-null when `rtb_endpoints_current` has 0 rows → severity CRITICAL |
| **Failure behavior** | Deploy must be rolled back. |
| **Remediation runbook** | 1. Deploy semantic-fix changes that separate observed endpoint telemetry from funnel proxies. 2. Verify API response schema matches `EndpointEfficiencyResponse` TypeScript type. |
| **Pass criteria** | observed_query_rate_qps is null IFF rtb_endpoints_current has 0 matching rows; funnel_proxy_qps_avg is always present |
| **Owner** | API team |
| **Confidence** | 0.95 |
| **Caveats** | Deployment state is environment-specific. Validate this contract against the latest baseline artifact before deciding pass/fail. |

#### C-API-002: data_state Semantic Consistency

| Field | Value |
|-------|-------|
| **Contract ID** | C-API-002 |
| **Rule** | Every analytics API response must include a `data_state` field with value "healthy", "degraded", or "unavailable", determined by: unavailable = 0 rows for buyer; degraded = partial dimension coverage (publisher or geo missing > 50%); healthy = all dimensions present. |
| **Scope** | All `/analytics/home/*` endpoints |
| **Why it matters** | The UI uses `data_state` to decide what to render. Incorrect state = user sees blank panel with no explanation. |
| **Detection method** | For each endpoint: (1) Call with a valid buyer_id → expect "healthy" or "degraded". (2) Call with a non-existent buyer_id → expect "unavailable". (3) Verify "degraded" only when actual dimension data is missing. |
| **Check frequency** | On every deploy |
| **Alert condition** | data_state is "healthy" when a dimension table has 0 rows → severity HIGH |
| **Failure behavior** | Must return correct state; UI renders accordingly. |
| **Remediation runbook** | 1. Check service code data_state logic in `home_analytics_service.py`. 2. Verify dimension table row counts. 3. Fix logic if state determination is wrong. |
| **Pass criteria** | data_state matches actual data availability for all test cases |
| **Owner** | API team |
| **Confidence** | 0.85 |
| **Caveats** | The 50% threshold for "degraded" is hardcoded in config_precompute.py. May need tuning. |

#### C-API-003: P95 Response Time

| Field | Value |
|-------|-------|
| **Contract ID** | C-API-003 |
| **Rule** | All non-admin analytics API endpoints must respond within 500ms at P95, measured over a 1-hour window, at current scale (1-4 buyers). |
| **Scope** | `/analytics/home/funnel`, `/analytics/home/configs`, `/analytics/home/endpoint-efficiency` |
| **Why it matters** | The frontend has a 12-second timeout. If P95 is > 500ms, P99 is likely > 5s, risking user-visible timeouts. |
| **Detection method** | Measure response times from the API access log or structured logging. Alternatively, synthetic check: `time curl -s -o /dev/null -w '%{time_total}' 'https://staging.example.com/api/analytics/home/configs?buyer_id=<BUYER_ID>&days=7'` |
| **Check frequency** | Continuously (access log analysis) or every 5 minutes (synthetic) |
| **Alert condition** | P95 > 500ms → severity MEDIUM; P95 > 2000ms → severity HIGH |
| **Failure behavior** | Add query-level caching or optimize slow queries. |
| **Remediation runbook** | 1. Identify slow endpoint from logs. 2. Check if precompute tables have proper indexes. 3. Check Postgres connection pool configuration. 4. If BQ queries are slow, increase precompute coverage to avoid fallback. |
| **Pass criteria** | P95 < 500ms for all analytics endpoints |
| **Owner** | API team |
| **Confidence** | 0.75 |
| **Caveats** | config-performance was observed at 3.8s during cold start. Connection pool warming may be needed. |

---

### CONTRACT GROUP 8: UI State Correctness

#### C-UI-001: Four-State Panel Rendering

| Field | Value |
|-------|-------|
| **Contract ID** | C-UI-001 |
| **Rule** | Every data panel in the dashboard must render one of exactly four states: (1) `ready` — data present, metrics shown. (2) `loading` — fetch in progress, spinner shown. (3) `missing_feed` — API returned successfully but specific feed is empty (e.g., endpoint_delivery_state="missing"). (4) `no_data` — buyer has zero data across all tables. The panel must NEVER show a blank/empty state without explanation. |
| **Scope** | All dashboard panels: funnel, config cards, endpoint-efficiency, breakdown |
| **Why it matters** | Users cannot distinguish "loading", "error", "no data", and "feed not configured" when the UI just shows nothing. |
| **Detection method** | E2E browser test: (1) Load page without buyer → expect seat selector. (2) Select buyer with data → expect "ready" state. (3) Select buyer with no rtb_endpoints_current → expect "Feed missing" in endpoint panel. (4) Disconnect API → expect error state. |
| **Check frequency** | On every deploy (E2E suite) |
| **Alert condition** | Any panel renders blank without a state indicator → severity HIGH |
| **Failure behavior** | Must show contextual message for every empty state. |
| **Remediation runbook** | 1. Check component rendering logic for the affected panel. 2. Add conditional rendering for `isLoading`, `isError`, and empty data cases. 3. For endpoint-efficiency: deploy 9f65ba3 which adds "Feed missing" state. |
| **Pass criteria** | All 4 states render correctly for all panels |
| **Owner** | Frontend team |
| **Confidence** | 0.80 |
| **Caveats** | "Feed missing" state must be verified in the currently deployed frontend build via baseline artifact. |

#### C-UI-002: Seat Gating Prevents Empty Fetches

| Field | Value |
|-------|-------|
| **Contract ID** | C-UI-002 |
| **Rule** | No analytics API call fires until a buyer seat is selected (`selectedBuyerId` is non-null). All `useQuery` hooks must have `enabled: !!selectedBuyerId` (or equivalent). |
| **Scope** | All data-fetching hooks in dashboard |
| **Why it matters** | Without gating, the API receives `buyer_id=undefined` or no buyer_id, potentially returning aggregate data or errors. |
| **Detection method** | Code review: grep all `useQuery` calls in page.tsx, verify `enabled` includes `seatReady` or `!!selectedBuyerId`. Browser test: open page, check network tab for any API calls before seat selection. |
| **Check frequency** | On every frontend change |
| **Alert condition** | Any useQuery without seat gating → severity MEDIUM |
| **Failure behavior** | Query fires without buyer_id, API returns aggregate or error. |
| **Remediation runbook** | 1. Add `enabled: seatReady` to the offending useQuery. 2. Verify `seatReady = !!selectedBuyerId` is defined. |
| **Pass criteria** | Zero API calls fire before seat selection (verified via browser network tab) |
| **Owner** | Frontend team |
| **Confidence** | 0.90 |
| **Caveats** | FACT: spendStats query (line 146-149) does NOT have `enabled: seatReady`. It fires regardless of seat selection. This is a known violation. |

---

### CONTRACT GROUP 9: Performance SLOs

#### C-PERF-001: Cold Start Recovery

| Field | Value |
|-------|-------|
| **Contract ID** | C-PERF-001 |
| **Rule** | After a container restart, the API must respond to all analytics endpoints within 5 seconds within 60 seconds of container start. |
| **Scope** | Post-deploy, post-restart |
| **Why it matters** | FACT: After deploying sha-02d1f53, the API hung for several minutes (connection pool cold start). Users saw timeouts. |
| **Detection method** | Post-deploy smoke test: `for i in 1 2 3 4 5; do curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' 'https://staging.example.com/api/health'; sleep 10; done` — all must return 200 within 5s. |
| **Check frequency** | After every deploy/restart |
| **Alert condition** | Any endpoint returns > 5s or non-200 within 60s of start → severity HIGH |
| **Failure behavior** | Connection pool should be warmed on startup (eager initialization). |
| **Remediation runbook** | 1. Add connection pool warm-up to `run.sh` or app startup. 2. Add a startup probe/readiness check that queries the database. 3. Consider a pre-warm endpoint that the deploy script calls. |
| **Pass criteria** | All analytics endpoints respond 200 in < 5s within 60s of container start |
| **Owner** | Platform team |
| **Confidence** | 0.85 |
| **Caveats** | Observed hang was transient and self-resolved. May be Postgres connection pool or BQ client initialization. |

---

### CONTRACT GROUP 10: Release Blocking Gates

#### C-REL-001: Pre-Deploy Contract Validation

| Field | Value |
|-------|-------|
| **Contract ID** | C-REL-001 |
| **Rule** | Before promoting a new image tag to production, the CI pipeline must run a contract validation suite that checks: (1) API health returns 200, (2) All precompute tables have rows for the most recent refresh window, (3) API semantic tests pass (C-API-001, C-API-002), (4) No Python import errors. |
| **Scope** | CI/CD pipeline |
| **Why it matters** | FACT: The current CI pipeline has zero test steps. Any code change — including ones that break imports, precompute, or API contracts — ships to production unchecked. |
| **Detection method** | The CI workflow must include a `test` job that runs before `build-and-push`. |
| **Check frequency** | On every push to unified-platform (that passes paths-ignore) |
| **Alert condition** | Test job failure → severity CRITICAL (blocks deploy) |
| **Failure behavior** | CI marks the commit as failed. Image is not pushed to registry. |
| **Remediation runbook** | 1. Read test failure output. 2. Fix the failing test. 3. Push fix. 4. CI re-runs. |
| **Pass criteria** | All contract validation tests pass |
| **Owner** | Platform team |
| **Confidence** | 0.95 |
| **Caveats** | FACT: This does not exist today. Must be implemented from scratch. |

#### C-REL-002: Post-Deploy Smoke Test

| Field | Value |
|-------|-------|
| **Contract ID** | C-REL-002 |
| **Rule** | Within 2 minutes of deploying a new image, a smoke test must verify: (1) `/health` returns 200 with the new git_sha, (2) `/analytics/home/configs?buyer_id=<primary>&days=7` returns 200 with `data_state != "unavailable"`, (3) Response time < 5s. |
| **Scope** | Both VMs (catscan-vm, catscan-vm) |
| **Why it matters** | Detects deployment failures, broken imports, and cold start issues before users notice. |
| **Detection method** | Shell script run after deploy: check health, check analytics, check response time. |
| **Check frequency** | After every deploy |
| **Alert condition** | Any check fails → severity CRITICAL (trigger rollback) |
| **Failure behavior** | Rollback to previous image tag: `docker pull $REGISTRY/catscan-api:$PREV_TAG && docker-compose up -d`. |
| **Remediation runbook** | 1. Check container logs: `docker logs catscan-api --tail 50`. 2. If startup error, fix code. 3. If database connection error, check Postgres. 4. Rollback if unfixable within 10 minutes. |
| **Pass criteria** | All 3 checks pass on both VMs |
| **Owner** | Platform team |
| **Confidence** | 0.90 |
| **Caveats** | Currently done manually. Should be automated in deploy.sh. |

---

## Section D: Test Plan

Note on execution:
- This section defines reusable tests/contracts.
- Live outcomes (PASS/FAIL, known failures, deployed SHA context) must be written to:
  - `docs/recovery/baseline_coverage_matrix_<date>.md`
  - `docs/recovery/baseline_endpoint_snapshot_<date>.json`

### SQL Validation Suite

| test_id | contract | setup | query | expected | failure interpretation |
|---------|----------|-------|-------|----------|----------------------|
| T-SQL-001 | C-PRE-001 | None (reads production) | `SELECT COUNT(DISTINCT metric_date) FROM home_seat_daily WHERE buyer_account_id = '<BUYER_ID>' AND metric_date >= (CURRENT_DATE - 9)::text AND metric_date <= (CURRENT_DATE - 2)::text` | ≥ 5 (7 days minus 2 for lag) | Precompute gap — missing days |
| T-SQL-002 | C-PRE-002 | None | `SELECT pc.billing_id FROM pretargeting_configs pc WHERE pc.bidder_id = '<BUYER_ID>' AND pc.state = 'ACTIVE' AND pc.billing_id NOT IN (SELECT DISTINCT billing_id FROM home_config_daily WHERE buyer_account_id = '<BUYER_ID>' AND metric_date >= (CURRENT_DATE - 9)::text)` | 0 rows (or only newly-created configs) | Active config has no precomputed data |
| T-SQL-003 | C-EPT-001 | None | `SELECT COUNT(*) FROM rtb_endpoints_current` | > 0 | **KNOWN FAIL**: rtb_endpoints_current is empty |
| T-SQL-004 | C-KEY-001 | None | `SELECT COUNT(*) FROM buyer_seats WHERE buyer_id != bidder_id` | 0 | buyer/bidder ID mismatch |
| T-SQL-005 | C-KEY-002 | None | `SELECT bidder_id, billing_id, COUNT(*) FROM pretargeting_configs GROUP BY bidder_id, billing_id HAVING COUNT(*) > 1` | 0 rows | Duplicate billing_id |
| T-SQL-006 | C-KEY-003 | None | See C-KEY-003 detection query | unknown_pct < 20 | Too much unattributed traffic |
| T-SQL-007 | C-PRE-004 | None | `SELECT cache_name FROM (SELECT cache_name, MAX(refreshed_at) as last FROM precompute_refresh_log WHERE buyer_account_id = '__all__' GROUP BY cache_name) sub WHERE last::timestamp < NOW() - INTERVAL '24 hours'` | 0 rows | Stale precompute |
| T-SQL-008 | C-PRE-003 | None | `SELECT COUNT(*) FROM config_publisher_daily WHERE buyer_account_id = '<BUYER_ID>'` | > 0 | **KNOWN FAIL**: 0 rows |
| T-SQL-009 | C-ING-001 | None | `SELECT COUNT(*) FROM ingestion_runs` | > 0 | **KNOWN FAIL**: 0 rows |
| T-SQL-010 | C-EPT-002 | None | See C-EPT-002 detection query | 0 rows returned | Missing or stale endpoint config |

### API Contract Tests

| test_id | contract | setup | command | expected | failure interpretation |
|---------|----------|-------|---------|----------|----------------------|
| T-API-001 | C-API-001 | None | `curl -s 'https://staging.example.com/api/analytics/home/endpoint-efficiency?buyer_id=<BUYER_ID>&days=7' \| jq '.summary.endpoint_delivery_state'` | `"missing"` | Proxy masquerading as observed (**KNOWN FAIL on sha-02d1f53**: field doesn't exist until 9f65ba3 deployed) |
| T-API-002 | C-API-001 | None | `curl -s 'https://staging.example.com/api/analytics/home/endpoint-efficiency?buyer_id=<BUYER_ID>&days=7' \| jq '.summary.observed_query_rate_qps'` | `null` | Non-null would mean proxy is mislabeled |
| T-API-003 | C-API-002 | None | `curl -s 'https://staging.example.com/api/analytics/home/funnel?buyer_id=<BUYER_ID>&days=7' \| jq '.data_state'` | `"healthy"` or `"degraded"` | Incorrect state determination |
| T-API-004 | C-API-002 | None | `curl -s 'https://staging.example.com/api/analytics/home/funnel?buyer_id=<BUYER_ID>&days=7' \| jq '.data_state'` | `"unavailable"` | Should be unavailable for non-existent buyer |
| T-API-005 | C-API-003 | None | `curl -s -o /dev/null -w '%{time_total}' 'https://staging.example.com/api/analytics/home/configs?buyer_id=<BUYER_ID>&days=7'` | < 0.5 | P95 SLO violated |
| T-API-006 | C-API-003 | None | `curl -s -o /dev/null -w '%{time_total}' 'https://staging.example.com/api/analytics/home/endpoint-efficiency?buyer_id=<BUYER_ID>&days=7'` | < 0.5 | P95 SLO violated |
| T-API-007 | C-REL-002 | Post-deploy | `curl -s 'https://staging.example.com/api/health' \| jq '.status'` | `"healthy"` | Deployment failed |

### Browser E2E State Tests

| test_id | contract | setup | action | expected | failure interpretation |
|---------|----------|-------|--------|----------|----------------------|
| T-E2E-001 | C-UI-001 | Load `/` with no seat selected | Observe | Seat selector visible, no data panels shown | Queries fired without seat |
| T-E2E-002 | C-UI-001 | Select buyer `<BUYER_ID>` | Observe | Config cards render with reached/impressions > 0 | Data not loading or rendering |
| T-E2E-003 | C-UI-001 | Select buyer `<BUYER_ID>`, observe endpoint panel | Observe | "Feed missing" text visible (requires 9f65ba3) | Missing state not rendered |
| T-E2E-004 | C-UI-002 | Load `/`, open browser Network tab | Count API calls before seat selection | 0 analytics API calls (only /seats) | Seat gating violated |

### Failure Injection Tests

| test_id | contract | injection | expected behavior | failure interpretation |
|---------|----------|-----------|-------------------|----------------------|
| T-FI-001 | C-PRE-001 | DELETE FROM home_seat_daily WHERE metric_date = (CURRENT_DATE - 3)::text | API returns `data_state: "degraded"` or includes missing_dates | Silent data gap |
| T-FI-002 | C-EPT-001 | TRUNCATE rtb_endpoints_current | API returns `endpoint_delivery_state: "missing"`, alert ENDPOINT_DELIVERY_MISSING fires | Observed QPS shown as non-null |
| T-FI-003 | C-API-002 | Kill Postgres, restart | API returns 500 (not hang), recovers within 60s of PG restart | Permanent hang or crash |
| T-FI-004 | C-PRE-004 | UPDATE precompute_refresh_log SET refreshed_at = '2026-01-01T00:00:00' | System detects staleness, alerts fire | Stale data served without warning |

### Go/No-Go Criteria

| Criterion | Threshold | Status |
|-----------|-----------|--------|
| All SQL validation tests pass | 10/10 | **FAIL** (T-SQL-003, T-SQL-008, T-SQL-009 known failures) |
| All API contract tests pass | 7/7 | **FAIL** (T-API-001 fails on current deploy) |
| All E2E tests pass | 4/4 | **UNKNOWN** (not yet automated) |
| Zero CRITICAL contract violations | 0 | **FAIL** (C-EPT-001, C-REL-001 violated) |
| P95 < 500ms for analytics endpoints | All | **LIKELY PASS** (needs measurement) |

**Current production readiness:** Determined by the latest baseline artifact run in `docs/recovery/` (do not hardcode pass/fail here).

---

## Section E: Phase Execution Prompts

### P0: Baseline Evidence Collection

```
PHASE: P0 — Baseline Contract Status
ALLOWED: Read-only SQL queries, API GET calls, code reads
FORBIDDEN: Any INSERT/UPDATE/DELETE, code changes, deploys, imports
REQUIRED ARTIFACTS:
  - baseline_sql_results.json: Results of T-SQL-001 through T-SQL-010
  - baseline_api_results.json: Results of T-API-001 through T-API-007
  - baseline_summary.md: Pass/fail matrix with timestamps
PASS CRITERIA: All 17 tests executed, results recorded
FAIL CRITERIA: Any test cannot be executed (query error, API unreachable)
EVIDENCE FORMAT: JSON with {test_id, timestamp_utc, query, result, pass_fail, notes}
```

### P1: Ingestion Observability

```
PHASE: P1 — Ingestion Run Logging
ALLOWED: Code changes to unified_importer.py, gmail_import_worker.py. Schema migration for ingestion_runs. Unit tests.
FORBIDDEN: Deploys, production data mutations, BigQuery changes
REQUIRED ARTIFACTS:
  - Migration SQL: ALTER or INSERT INTO ingestion_runs
  - Modified unified_importer.py with ingestion_runs writes
  - Unit test: test_ingestion_run_logged.py
  - import_history buyer coverage fix
PASS CRITERIA:
  - T-SQL-009 passes (ingestion_runs has rows after import)
  - C-ING-002 passes (import_history covers all buyers)
FAIL CRITERIA: Any import that doesn't write to ingestion_runs
EVIDENCE FORMAT: Git diff of changed files + test output
```

### P2: Source/Feed Completeness

```
PHASE: P2 — rtb_endpoints_current Population
ALLOWED: New code for QPS observation job. New migration if needed. Tests.
FORBIDDEN: Modifying existing precompute or API logic. Production deploys until P2 tests pass locally.
REQUIRED ARTIFACTS:
  - New script/service: qps_observation_job.py
  - Writes to rtb_endpoints_current with (bidder_id, endpoint_id, current_qps, observed_at)
  - Unit test: test_qps_observation.py
  - Integration test against staging/dev database
PASS CRITERIA:
  - T-SQL-003 passes (rtb_endpoints_current > 0 rows)
  - C-EPT-001 passes (every endpoint has recent observation)
FAIL CRITERIA: rtb_endpoints_current still empty after job runs
EVIDENCE FORMAT: SQL query results showing populated table + job execution log
```

### P3: Universal Precompute Completion

```
PHASE: P3 — Precompute Gap Resolution
ALLOWED: Code changes to config_precompute.py (publisher self-join fix), precompute scheduling. Running precompute manually.
FORBIDDEN: Modifying API response schemas. Deploying without P3 tests passing.
REQUIRED ARTIFACTS:
  - Fixed config_precompute.py: config_publisher_daily produces rows even when publisher_id sparse
  - Precompute cron schedule or post-import trigger
  - T-SQL-008 passes (config_publisher_daily > 0)
  - T-SQL-001 passes with full window coverage
  - billing_id 777777777777 either has data or is explicitly labeled no_traffic
PASS CRITERIA: All 5 home_* and all 4 config_* tables have data for all active buyers in 7-day window
FAIL CRITERIA: Any table has 0 rows for an active buyer with traffic
EVIDENCE FORMAT: SQL counts per table per buyer + precompute_refresh_log entries
```

### P4: API Semantic Hardening

```
PHASE: P4 — Deploy 9f65ba3 + API Contract Tests
ALLOWED: Deploy commit 9f65ba3. Write API contract test suite. Minor API fixes.
FORBIDDEN: Changing precompute logic. Changing frontend without corresponding API change.
REQUIRED ARTIFACTS:
  - Deployed 9f65ba3 on both VMs
  - API contract test script: test_api_contracts.sh
  - T-API-001 through T-API-007 all passing
  - Documented API response schemas with field-level semantics
PASS CRITERIA:
  - C-API-001 passes (no proxy masquerading)
  - C-API-002 passes (correct data_state)
  - C-API-003 passes (P95 < 500ms)
FAIL CRITERIA: Any API contract test fails after deploy
EVIDENCE FORMAT: curl commands + responses + timing
```

### P5: UI State Integrity

```
PHASE: P5 — Frontend Four-State Rendering
ALLOWED: Frontend code changes. Component test additions.
FORBIDDEN: API schema changes. Production database mutations.
REQUIRED ARTIFACTS:
  - Updated endpoint-efficiency-panel.tsx with "Feed missing" state
  - Updated all panels with explicit loading/error/empty/ready states
  - Staleness indicator when precompute > 24h old
  - Fix C-UI-002: add enabled: seatReady to spendStats query
  - E2E test: T-E2E-001 through T-E2E-004 passing
PASS CRITERIA: All 4 UI state tests pass in browser
FAIL CRITERIA: Any panel shows blank/empty without contextual message
EVIDENCE FORMAT: Screenshots of each state + network tab captures
```

### P6: CI/CD Guardrails + Alerts

```
PHASE: P6 — CI Test Gate + Post-Deploy Smoke
ALLOWED: Modify .github/workflows/build-and-push.yml. Add test scripts. Add deploy.sh enhancements.
FORBIDDEN: Removing paths-ignore. Changing image naming convention.
REQUIRED ARTIFACTS:
  - Updated build-and-push.yml with test job before build
  - pytest suite: tests/test_contracts.py (runs T-SQL-001..010 against test DB)
  - Post-deploy smoke script in deploy.sh
  - Rollback procedure documented and tested
  - Alert mechanism (webhook, email, or log-based) for contract violations
PASS CRITERIA:
  - CI blocks deploy when any contract test fails
  - Post-deploy smoke test runs automatically
  - Failed deploy triggers rollback within 5 minutes
FAIL CRITERIA: A broken commit reaches production
EVIDENCE FORMAT: CI run logs showing test execution + blocked deploy example
```

---

## Section F: Weighted Synthesis

### Confidence by Subsystem

| Subsystem | Weight | Confidence | Weighted |
|-----------|--------|------------|----------|
| 1. Sources | 0.15 | 0.85 | 0.128 |
| 2. Ingestion | 0.15 | 0.70 | 0.105 |
| 3. Raw tables | 0.10 | 0.78 | 0.078 |
| 4. Precompute | 0.20 | 0.75 | 0.150 |
| 5. API semantics | 0.15 | 0.65 | 0.098 |
| 6. UI state | 0.10 | 0.80 | 0.080 |
| 7. Observability | 0.05 | 0.40 | 0.020 |
| 8. CI/CD | 0.10 | 0.15 | 0.015 |
| **TOTAL** | **1.00** | — | **0.674** |

### Overall System Confidence: 0.67

### Top 5 Unresolved Uncertainties

1. **No writer for `rtb_endpoints_current` exists** (confidence gap: 0.95). Until a QPS observation job is built, the endpoint-efficiency feature cannot function as designed. No evidence that this was ever implemented or planned beyond the table schema.

2. **BigQuery sync currency is unverifiable** (confidence gap: 0.75). We cannot confirm from the evidence whether BQ tables are current with Postgres. The Parquet export pipeline may or may not run automatically. If BQ is stale, precompute silently produces outdated data.

3. **No precompute scheduling exists** (confidence gap: 0.80). No cron job, no systemd timer, no post-import hook was found that automatically triggers precompute. It appears to be run manually or ad-hoc. This means data freshness depends on human memory.

4. **`config_publisher_daily` self-join failure root cause** (confidence gap: 0.70). The BQ self-join that populates this table requires `publisher_id` in `rtb_daily`. It's unclear whether the CSV reports for buyer `<BUYER_ID>` include publisher_id at all, or whether the join condition is too restrictive.

5. **CI has zero test coverage** (confidence gap: 0.95). Any code change ships to production without automated validation. The blast radius of a broken commit is unlimited.

### What Would Raise Confidence Above 0.9

| Evidence needed | Current confidence | Target impact |
|-----------------|-------------------|---------------|
| Implement + run QPS observation job, verify rtb_endpoints_current populated | 0.00 → 0.90 | +0.08 overall |
| Verify BQ MAX(metric_date) matches Postgres within 1 day | 0.75 → 0.95 | +0.02 overall |
| Add automated precompute trigger (cron or post-import hook) | 0.20 → 0.90 | +0.04 overall |
| Add CI test job with contract validation suite | 0.15 → 0.90 | +0.08 overall |
| Fix config_publisher_daily (or explicitly mark as unsupported) | 0.70 → 0.95 | +0.02 overall |
| Deploy 9f65ba3 and verify API semantic contracts pass | 0.65 → 0.95 | +0.05 overall |
| Add post-deploy smoke test to deploy.sh | 0.10 → 0.90 | +0.03 overall |

Combined potential: 0.67 → **0.99** with all evidence items addressed.
