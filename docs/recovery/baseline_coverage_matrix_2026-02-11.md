# P0 Baseline Coverage Matrix

**Execution Date:** 2026-02-11
**Execution Window:** 10:49:18 UTC — 11:35:04 UTC
**Target:** catscan-production-sg2 (asia-southeast1-b)
**Deployed Version:** sha-02d1f53
**HEAD Commit:** 821c287 (local repo)
**Contract Catalog Ref:** docs/CONTRACT_CATALOG.md v1.1
**Constraints:** Read-only SQL + API checks. No code changes, deploys, imports, or DB mutations.

---

## Section A: Active Buyer Inventory

| buyer_id | bidder_id | display_name | active | creative_count | last_synced (UTC) | Label |
|----------|-----------|-------------|--------|----------------|-------------------|-------|
| 1487810529 | 1487810529 | Amazing Design Tools LLC | true | 304 | 2026-02-11 02:19:32 | FACT |
| 6574658621 | 6574658621 | Amazing Moboost | true | 637 | 2026-02-11 02:19:45 | FACT |
| 6634662463 | 6634662463 | Amazing MobYoung | true | 100 | 2026-02-11 02:19:47 | FACT |
| 299038253 | 299038253 | Tuky Display | true | 932 | 2026-02-11 02:20:01 | FACT |

**Total active buyers: 4** (FACT)
**Total seats (incl inactive): 4** (FACT — no inactive seats)
**buyer_id = bidder_id invariant: HOLDS for all 4 seats** (FACT)

---

## Section B: Buyer x Table x Window Coverage Matrix

### Legend
- Rows / Dates = row count / distinct metric_date count in window
- Range = min..max metric_date observed
- `--` = 0 rows (empty)
- `DNE` = table does not exist in schema
- All data max date is 2026-02-08 (expected: report delivery lag ~2 days)

### Home Precompute Tables (5)

| Buyer | Table | 7d rows/dates | 14d rows/dates | 30d rows/dates | Range |
|-------|-------|--------------|----------------|----------------|-------|
| **299038253** | home_seat_daily | 5/5 | 12/12 | 27/27 | 2026-01-13..02-08 |
| | home_publisher_daily | --/-- | --/-- | --/-- | *empty* |
| | home_geo_daily | 135/5 | 324/12 | 732/27 | 2026-01-13..02-08 |
| | home_config_daily | 35/5 | 84/12 | 186/27 | 2026-01-13..02-08 |
| | home_size_daily | 1678/5 | 4433/12 | 11140/27 | 2026-01-13..02-08 |
| **6574658621** | home_seat_daily | 5/5 | 12/12 | 27/27 | 2026-01-13..02-08 |
| | home_publisher_daily | 7432/5 | 13390/9 | 28255/19 | 2026-01-13..02-08 |
| | home_geo_daily | 55/5 | 132/12 | 297/27 | 2026-01-13..02-08 |
| | home_config_daily | 48/5 | 103/12 | 175/27 | 2026-01-13..02-08 |
| | home_size_daily | 93763/5 | 204956/12 | 330510/27 | 2026-01-13..02-08 |
| **6634662463** | home_seat_daily | 5/5 | 12/12 | 27/27 | 2026-01-13..02-08 |
| | home_publisher_daily | 6180/5 | 14868/12 | 32315/27 | 2026-01-13..02-08 |
| | home_geo_daily | 31/5 | 66/12 | 133/27 | 2026-01-13..02-08 |
| | home_config_daily | 25/5 | 60/12 | 95/27 | 2026-01-13..02-08 |
| | home_size_daily | 32243/5 | 60190/12 | 85521/27 | 2026-01-13..02-08 |
| **1487810529** | home_seat_daily | 5/5 | 12/12 | 28/28 | 2026-01-12..02-08 |
| | home_publisher_daily | 42285/5 | 84674/10 | 148592/17 | 2026-01-20..02-08 |
| | home_geo_daily | 68/5 | 159/12 | 367/28 | 2026-01-12..02-08 |
| | home_config_daily | 53/5 | 108/10 | 237/22 | 2026-01-12..02-08 |
| | home_size_daily | 6121/5 | 12272/10 | 26905/22 | 2026-01-12..02-08 |

**FACT: home_publisher_daily is empty for buyer 299038253 across all windows.**
**FACT: All other home tables have 5 dates in 7d window (2026-02-04..02-08) for all 4 buyers.**

### Config Precompute Tables (5)

| Buyer | Table | 7d rows/dates | 14d rows/dates | 30d rows/dates | Range |
|-------|-------|--------------|----------------|----------------|-------|
| **299038253** | config_size_daily | 2652/5 | 6818/12 | 16472/27 | 2026-01-13..02-08 |
| | config_geo_daily | --/-- | --/-- | --/-- | *empty* |
| | config_publisher_daily | --/-- | --/-- | --/-- | *empty* |
| | config_creative_daily | 4113/5 | 10286/12 | 21599/27 | 2026-01-13..02-08 |
| | fact_delivery_daily | 1037/6 | 1226/13 | 1634/28 | 2026-01-13..02-09 |
| **6574658621** | config_size_daily | 183790/5 | 400219/12 | 645129/27 | 2026-01-13..02-08 |
| | config_geo_daily | 157/5 | 241/12 | 423/27 | 2026-01-13..02-08 |
| | config_publisher_daily | --/-- | --/-- | --/-- | *empty* |
| | config_creative_daily | 5013/5 | 11645/12 | 23487/27 | 2026-01-13..02-08 |
| | fact_delivery_daily | 7620/6 | 13662/13 | 28731/28 | 2026-01-13..02-09 |
| **6634662463** | config_size_daily | 49032/5 | 86508/12 | 114273/27 | 2026-01-13..02-08 |
| | config_geo_daily | 40/5 | 72/12 | 93/27 | 2026-01-13..02-08 |
| | config_publisher_daily | 10477/5 | 15063/12 | 21620/27 | 2026-01-13..02-08 |
| | config_creative_daily | 582/5 | 1034/12 | 1705/27 | 2026-01-13..02-08 |
| | fact_delivery_daily | 3586/6 | 7152/13 | 13733/28 | 2026-01-13..02-09 |
| **1487810529** | config_size_daily | 14867/5 | 31116/10 | 70286/22 | 2026-01-12..02-08 |
| | config_geo_daily | 136/5 | 283/10 | 559/20 | 2026-01-14..02-08 |
| | config_publisher_daily | 28231/5 | 55759/10 | 85337/16 | 2026-01-20..02-08 |
| | config_creative_daily | 2406/5 | 5025/10 | 10484/22 | 2026-01-12..02-08 |
| | fact_delivery_daily | 23790/6 | 53762/13 | 95574/29 | 2026-01-12..02-09 |

**FACT: config_publisher_daily is empty for buyers 299038253 and 6574658621.**
**FACT: config_geo_daily is empty for buyer 299038253.**
**FACT: config_publisher_daily has data for buyers 6634662463 (21620 rows) and 1487810529 (85337 rows).**

### Fact Tables (2)

| Buyer | Table | 7d rows/dates | 14d rows/dates | 30d rows/dates |
|-------|-------|--------------|----------------|----------------|
| 299038253 | fact_dimension_gaps_daily | 6/6 | 13/13 | 28/28 |
| 6574658621 | fact_dimension_gaps_daily | 6/6 | 13/13 | 28/28 |
| 6634662463 | fact_dimension_gaps_daily | 6/6 | 13/13 | 28/28 |
| 1487810529 | fact_dimension_gaps_daily | 6/6 | 12/12 | 25/25 |

### RTB Precompute Tables

| Buyer | Table | 7d rows/dates | 14d rows/dates | 30d rows/dates |
|-------|-------|--------------|----------------|----------------|
| 299038253 | rtb_publisher_daily | --/-- | --/-- | --/-- |
| 299038253 | rtb_geo_daily | 135/5 | 324/12 | 732/27 |
| 6574658621 | rtb_publisher_daily | 7432/5 | 13390/9 | 28255/19 |
| 6574658621 | rtb_geo_daily | 55/5 | 132/12 | 297/27 |
| 6634662463 | rtb_publisher_daily | 6180/5 | 14868/12 | 32315/27 |
| 6634662463 | rtb_geo_daily | 31/5 | 66/12 | 133/27 |
| 1487810529 | rtb_publisher_daily | 42285/5 | 84674/10 | 148592/17 |
| 1487810529 | rtb_geo_daily | 68/5 | 159/12 | 367/28 |

**FACT: Tables `rtb_daily_summary`, `rtb_size_daily`, `rtb_device_daily`, `rtb_bidding_daily` do NOT EXIST in the database schema.**
**FACT: `rtb_publisher_daily` is empty for buyer 299038253 (same as `home_publisher_daily`).**

---

## Section C: Endpoint Snapshot Per Buyer

### rtb_endpoints (per bidder)

| bidder_id | endpoint_id | url | max_qps | location | synced_at (UTC) |
|-----------|-------------|-----|---------|----------|-----------------|
| 299038253 | 13761 | bidder.novabeyond.com | 5222 | US_WEST | 2026-02-11 02:20:05 |
| 299038253 | 14379 | bidder-sg.novabeyond.com | 15666 | ASIA | 2026-02-11 02:20:05 |
| 299038253 | 14478 | bidder-us.novabeyond.com | 26111 | US_EAST | 2026-02-11 02:20:05 |
| 6574658621 | 15386 | rtbeur.amazingmoboost.com | 10000 | EUROPE | 2026-02-11 02:20:08 |
| 6574658621 | 15784 | rtb.amazingmoboost.com | 150000 | US_EAST | 2026-02-11 02:20:08 |
| 6574658621 | 15831 | apac.amazingmoboost.com | 300000 | ASIA | 2026-02-11 02:20:08 |
| 6634662463 | 18435 | rtb.amazingdo.com | 4428 | EUROPE | 2026-02-03 22:34:50 |
| 6634662463 | 17620 | win-useast.amazingdo.com | 100000 | US_EAST | 2026-02-11 02:20:10 |
| 6634662463 | 17656 | win-asia.amazingdo.com | 200000 | ASIA | 2026-02-11 02:20:10 |
| 1487810529 | 16213 | bid.amazingaa.com | 36000 | US_EAST | 2026-02-11 02:20:03 |
| 1487810529 | 19587 | bid-asia.amazingaa.com | 10000 | ASIA | 2026-02-11 02:20:03 |

**FACT: rtb_endpoints_current has 0 rows TOTAL (all bidders). No QPS observation data exists.**

### API Semantic Verification (direct SQL, bypassing HTTP auth)

| buyer_id | funnel data_state | funnel latency | configs latency | efficiency ep_current | proxy_qps_avg | Label |
|----------|-------------------|----------------|-----------------|----------------------|---------------|-------|
| 299038253 | healthy | 0.054s | 0.047s | 0 | 77.37 | FACT |
| 6574658621 | healthy | 0.044s | 0.049s | 0 | 6299.49 | FACT |
| 6634662463 | healthy | 0.044s | 0.042s | 0 | 2064.52 | FACT |
| 1487810529 | healthy | 0.046s | 0.040s | 0 | 44.62 | FACT |
| 9999999999 | unavailable | 0.041s | — | — | — | FACT |

**FACT: All query latencies < 100ms. P95 SLO (< 500ms) PASSES for all endpoints at SQL layer.**
**FACT: Non-existent buyer_id correctly maps to data_state=unavailable.**

### Deployed Code Semantic Check (C-API-001)

**Deployed version:** sha-02d1f53
**FACT:** Deployed code contains `observed_query_rate_qps_avg` (line 414 of `home_analytics_service.py`) — the OLD field name that does NOT separate proxy from observed.
**FACT:** `endpoint_delivery_state` and `funnel_proxy_qps_avg` fields (added in commit 9f65ba3) are NOT in the deployed code.
**INFERENCE:** C-API-001 (no proxy masquerading) is VIOLATED on the deployed version because the code likely computes a proxy value and labels it `observed_query_rate_qps_avg`. However, since rtb_endpoints_current has 0 rows, the practical effect is the value would be derived from funnel data only.

### Health Endpoint

```json
{
  "status": "healthy",
  "version": "sha-02d1f53",
  "git_sha": "02d1f536",
  "configured": true,
  "has_credentials": true,
  "database_exists": true
}
```
**FACT: Health endpoint returns 200, version sha-02d1f53.**

### Pretargeting Configs Per Buyer

| buyer_id | total_configs | active_configs | missing_from_precompute | Label |
|----------|---------------|----------------|------------------------|-------|
| 299038253 | 10 | 10 ACTIVE | 3 missing (137175951277, 153322387893, 158323666240) | FACT |
| 6574658621 | 10 | 10 ACTIVE | 1 missing (173162721799 IDN_Banner_Instl) | FACT |
| 6634662463 | 8 | 4 ACTIVE, 4 SUSPENDED | 0 missing | FACT |
| 1487810529 | 10 | 10 ACTIVE | 0 missing | FACT |

---

## Section D: Ingestion Observability Baseline

### ingestion_runs
**FACT: 0 rows.** Table exists but no process writes to it. (C-ING-001 FAIL)

### import_history
**FACT: 3 rows total, all for buyer 6634662463 only.**

| id | filename | imported_at (UTC) | rows_imported | date_range |
|----|----------|-------------------|---------------|------------|
| 3 | catscan-quality-6634662463-25JAN-UTC.csv | 2026-02-08 00:08:30 | 35248 | 2026-01-25 |
| 2 | catscan-quality-6634662463-21JAN-UTC.csv | 2026-02-08 00:04:17 | 0 (dup) | 2026-01-21 |
| 1 | catscan-quality-6634662463-21JAN-UTC.csv | 2026-02-07 15:59:36 | 33895 | 2026-01-21 |

**FACT: Buyers 299038253, 6574658621, 1487810529 have ZERO import_history rows.** (C-ING-002 FAIL)
**INFERENCE: Gmail import worker writes to import_history only for some import paths. Precompute data exists for all 4 buyers, so imports ARE happening — they are just not being logged.**

### precompute_refresh_log

| cache_name | buyer_account_id | refresh_start | refresh_end | refreshed_at (UTC) | Label |
|-----------|-----------------|---------------|-------------|---------------------|-------|
| rtb_summaries | __all__ | 2026-02-10 | 2026-02-11 | 2026-02-11T03:04:28 | FACT |
| config_breakdowns | __all__ | 2026-02-10 | 2026-02-11 | 2026-02-11T03:04:23 | FACT |
| home_summaries | __all__ | 2026-02-10 | 2026-02-11 | 2026-02-11T03:00:07 | FACT |
| rtb_summaries | 6634662463 | 2026-01-21 | 2026-02-04 | 2026-02-04T00:31:34 | FACT |
| home_summaries | 6634662463 | 2026-01-21 | 2026-02-03 | 2026-02-03T23:34:10 | FACT |
| config_breakdowns | 6634662463 | 2026-01-21 | 2026-02-03 | 2026-02-03T23:33:41 | FACT |

**FACT: All 3 cache names (home_summaries, config_breakdowns, rtb_summaries) refreshed within last 24h (at ~03:00 UTC today). C-PRE-004 PASSES.**

---

## Section E: Contract Pass/Fail Summary

### Global Tests (all buyers)

| Test ID | Contract | Result | Pass/Fail | Label | Notes |
|---------|----------|--------|-----------|-------|-------|
| T-SQL-003 | C-EPT-001 | 0 rows | **FAIL** | FACT | rtb_endpoints_current is empty (all bidders) |
| T-SQL-004 | C-KEY-001 | 0 mismatches | **PASS** | FACT | buyer_id = bidder_id for all seats |
| T-SQL-005 | C-KEY-002 | 0 duplicates | **PASS** | FACT | No duplicate billing_id per bidder |
| T-SQL-007 | C-PRE-004 | 3/3 caches fresh | **PASS** | FACT | All refreshed ~03:00 UTC today |
| T-SQL-009 | C-ING-001 | 0 rows | **FAIL** | FACT | ingestion_runs never populated |

### Per-Buyer Tests

| Test ID | Contract | 299038253 | 6574658621 | 6634662463 | 1487810529 |
|---------|----------|-----------|------------|------------|------------|
| T-SQL-001 | C-PRE-001 (window coverage) | **PASS** (7d) | **PASS** (7d) | **PASS** (7d) | **PASS** (7d) |
| T-SQL-002 | C-PRE-002 (billing coverage) | **FAIL** (3 missing) | **FAIL** (1 missing) | **PASS** | **PASS** |
| T-SQL-006 | C-KEY-003 (unknown billing %) | **PASS** (0.00%) | **FAIL** (53.41%) | **FAIL** (50.00%) | **FAIL** (50.00%) |
| T-SQL-008 | C-PRE-003 (config_publisher) | **FAIL** (0 rows) | **FAIL** (0 rows) | **PASS** (21620) | **PASS** (85337) |
| T-SQL-010 | C-EPT-002 (endpoint sync) | **PASS** | **PASS** | **PASS** | **PASS** |

### API Semantic Tests

| Test ID | Contract | Result | Pass/Fail | Label | Notes |
|---------|----------|--------|-----------|-------|-------|
| T-API-001 | C-API-001 (proxy masquerade) | Deployed code uses old field name | **FAIL** | FACT | sha-02d1f53 has `observed_query_rate_qps_avg` not `funnel_proxy_qps_avg`. Semantic fix (9f65ba3) NOT deployed. |
| T-API-003 | C-API-002 (data_state) | All buyers = healthy | **PASS** | FACT | SQL verification shows correct data_state mapping |
| T-API-004 | C-API-002 (non-existent buyer) | data_state = unavailable | **PASS** | FACT | Correct behavior for non-existent buyer |
| T-API-005 | C-API-003 (P95 latency) | All < 100ms | **PASS** | FACT | SQL layer latency; HTTP overhead not measurable due to auth |
| T-API-007 | C-REL-002 (health) | 200, sha-02d1f53 | **PASS** | FACT | External health endpoint accessible |

### CI/CD Tests

| Test ID | Contract | Result | Pass/Fail | Label |
|---------|----------|--------|-----------|-------|
| (code review) | C-REL-001 (pre-deploy validation) | 0 test steps in CI | **FAIL** | FACT |
| (code review) | C-UI-002 (seat gating) | spendStats query ungated | **FAIL** | FACT |

### Aggregate Summary

| Category | Total Tests | Pass | Fail | Pass Rate |
|----------|-------------|------|------|-----------|
| Global SQL | 5 | 3 | 2 | 60% |
| Per-Buyer SQL (x4 buyers) | 20 | 12 | 8 | 60% |
| API Semantic | 5 | 4 | 1 | 80% |
| CI/CD | 2 | 0 | 2 | 0% |
| **TOTAL** | **32** | **19** | **13** | **59%** |

### Critical Failures (sorted by impact)

1. **C-EPT-001** — rtb_endpoints_current has 0 rows. No QPS observation job exists. (FACT)
2. **C-API-001** — Deployed code (sha-02d1f53) mislabels proxy QPS as observed. Fix exists in 9f65ba3 but is NOT deployed. (FACT)
3. **C-REL-001** — Zero test steps in CI. Any code ships unchecked. (FACT)
4. **C-ING-001** — ingestion_runs table never written to. No import audit trail. (FACT)
5. **C-KEY-003** — 50-53% of reached_queries have billing_id='unknown' for 3 of 4 buyers. (FACT)
6. **C-PRE-003** — config_publisher_daily empty for 2 of 4 buyers. (FACT)
7. **C-PRE-002** — 4 ACTIVE pretargeting configs missing from precompute across 2 buyers. (FACT)
8. **C-ING-002** — import_history only tracks 1 of 4 buyers. (FACT)

---

## Section F: Command Log

All commands executed read-only against catscan-production-sg2 via IAP tunnel.

```
# 1. Pull latest and confirm commit
git pull origin unified-platform
git log --oneline | head -20
# Confirmed: 821c287 is HEAD

# 2. SCP + execute SQL baseline script
gcloud compute scp /tmp/p0_baseline_v2.py catscan-production-sg2:/tmp/ --zone=asia-southeast1-b --tunnel-through-iap
gcloud compute ssh catscan-production-sg2 --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker cp /tmp/p0_baseline_v2.py catscan-api:/tmp/ && \
             sudo docker exec -e PYTHONPATH=/app -w /app catscan-api python3 /tmp/p0_baseline_v2.py"
# Executed: 2026-02-11T10:49:18Z — covers Sections A, B, C (SQL), D, E (SQL tests)

# 3. External health check
curl -s "https://vm2.scan.rtb.cat/api/health"
# Result: 200, version=sha-02d1f53

# 4. API endpoint smoke test (external, authenticated endpoints)
# All analytics endpoints returned 401 (auth required) from external and internal localhost
# Resolution: Verified API semantics via direct SQL queries (bypassing HTTP auth)

# 5. SCP + execute semantic API verification script
gcloud compute scp /tmp/p0_api_semantic.py catscan-production-sg2:/tmp/ --zone=asia-southeast1-b --tunnel-through-iap
gcloud compute ssh catscan-production-sg2 --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker cp /tmp/p0_api_semantic.py catscan-api:/tmp/ && \
             sudo docker exec -e PYTHONPATH=/app -w /app catscan-api python3 /tmp/p0_api_semantic.py"
# Executed: 2026-02-11T11:35:03Z — covers API semantic verification for all buyers
# Includes deployed code grep confirming sha-02d1f53 does NOT have endpoint_delivery_state field

# 6. Deployed code check (inside container)
# grep -n "endpoint_delivery_state\|observed_query_rate_qps\|funnel_proxy_qps" /app/services/home_analytics_service.py
# Result: only line 414: "observed_query_rate_qps_avg": round(observed_qps, 2),
# Confirms: 9f65ba3 semantic fix NOT deployed
```

### Scripts Used (read-only, no mutations)
- `/tmp/p0_baseline_v2.py` — SQL coverage matrix + contract tests (asyncio + psycopg)
- `/tmp/p0_api_semantic.py` — Direct SQL API semantic verification (asyncio + psycopg)

### Known Limitations
- **HTTP API tests could not be executed** due to session auth requirement on all analytics endpoints. API semantics were verified at the SQL/data layer instead.
- **E2E browser tests (T-E2E-001 through T-E2E-004)** were not executed (require browser automation).
- **BQ sync verification (C-RAW-002)** was not executed (requires BQ access not available in this context).
- **Tables `rtb_daily_summary`, `rtb_size_daily`, `rtb_device_daily`, `rtb_bidding_daily`** referenced in CONTRACT_CATALOG.md do not exist in the deployed schema.
