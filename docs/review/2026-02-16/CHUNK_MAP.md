# Chunk Map — Bounded Review Domains

**Date:** 2026-02-16
**Purpose:** Divide the codebase into bounded review chunks with explicit dependencies, invariants, and verification checks for the map-reduce review protocol.

---

## Chunk 1: Analytics Core Metrics

### Scope Globs
```
analytics/waste_analyzer.py
analytics/waste_models.py
analytics/qps_optimizer.py
analytics/rtb_bidstream_analyzer.py
analytics/recommendation_engine.py
analytics/fraud_analyzer.py
analytics/creative_analyzer.py
analytics/geo_analyzer.py
analytics/geo_waste_analyzer.py
analytics/config_analyzer.py
analytics/size_analyzer.py
analytics/size_coverage_analyzer.py
analytics/pretargeting_recommender.py
```

### Invariants
- All waste percentages MUST use the same formula (either `100 - impressions/reached*100` OR `100 * (bid_requests - auctions_won) / bid_requests`, but not both)
- All thresholds used in SQL queries MUST be defined as module-level constants
- QPS calculations MUST document whether they represent average or peak
- Recommendation severity levels MUST be consistent across all analyzers

### Known Dependencies
- **Reads from:** `storage/serving_database.py` (db_query, db_query_one)
- **Tables queried:** `performance_metrics`, `creatives`, `rtb_bidstream`, `rtb_daily`, `rtb_bid_filtering`
- **Imported by:** `services/recommendations_service.py`, `services/evaluation_service.py`, `api/routers/analytics/*.py`
- **Shared types:** `analytics/recommendation_engine.py` defines `Recommendation`, `Evidence`, `Impact`, `Action`, `Severity`, `Confidence`

### Likely Failure Modes
1. **Undefined constant crash** — `LOW_WIN_RATE_THRESHOLD` (creative_analyzer.py:379), `HIGH_WASTE_RATE_THRESHOLD` (geo_analyzer.py:211)
2. **Inconsistent denominators** — `reached_queries` vs `bid_requests` for waste_pct across modules
3. **Average QPS misleading** — dividing by 86400 seconds vs peak-hour concentration
4. **Hardcoded CPM** — $0.002/1000 ignores actual account CPMs
5. **Fraud false positives** — 10% CTR threshold not format-aware (video vs display)

### Verification Checks
- [ ] Every constant referenced in SQL/code is defined in the same module or explicitly imported
- [ ] `waste_pct` formula is consistent: grep all modules and compare denominators
- [ ] QPS calculations clearly labeled "average" vs "peak"
- [ ] `ESTIMATED_COST_PER_1000` has a code path to use real CPM from SpendStats API
- [ ] Fraud thresholds are parameterized by creative format

---

## Chunk 2: Importers / Data Normalization

### Scope Globs
```
importers/unified_importer.py
importers/flexible_mapper.py
importers/csv_report_types.py
importers/constants.py
importers/models.py
importers/utils.py
importers/account_mapper.py
importers/domain_rollup.py
importers/parquet_pipeline.py
utils/size_normalization.py
utils/country_codes.py
```

### Invariants
- CSV column mapping MUST be deterministic (same CSV → same mapping every time)
- Size strings MUST be canonicalized before storage via `utils/size_normalization.canonical_size()`
- Date parsing MUST handle all Google CSV export formats consistently
- Deduplication hashing MUST include all key fields to prevent false dupes
- Spend conversion MUST preserve precision to at least micros (6 decimal places)

### Known Dependencies
- **Writes to:** `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality`, `import_history`
- **Read by:** All analytics modules, precompute services
- **Uses:** `storage/postgres_store.py` for DB operations
- **Column synonyms:** Defined in `importers/csv_report_types.py` COLUMN_SYNONYMS dict

### Likely Failure Modes
1. **Size not canonicalized** — importers do NOT call `canonical_size()` before storage
2. **Date gaps silent** — no check that imported data covers expected date ranges
3. **Spend precision** — `int(spend * 1_000_000)` truncates; compounding over millions of rows
4. **Timezone assumption** — dates from CSV assumed to match system timezone
5. **Report type misdetection** — if CSV has ambiguous columns, wrong table gets data

### Verification Checks
- [ ] `canonical_size()` is called in the import path before `INSERT`
- [ ] Import validates date range continuity (alerts on missing days)
- [ ] Spend conversion uses `round()` instead of `int()` for micro precision
- [ ] Timezone handling is explicit (UTC assumption documented)
- [ ] Report type detection has a confidence score with human-verifiable logging

---

## Chunk 3: Storage / Models / Schema Contracts

### Scope Globs
```
storage/models.py
storage/postgres_store.py
storage/postgres_database.py
storage/postgres_schema.sql
storage/postgres_migrations/*.sql
storage/postgres_repositories/*.py
storage/adapters.py
storage/bigquery.py
storage/serving_database.py
storage/s3_writer.py
sql/postgres/*.sql
```

### Invariants
- Table schemas in migrations MUST match repository SQL queries exactly
- All foreign keys MUST have corresponding indexes
- Canonical alias views (`pretarg_daily` → `home_config_daily`) MUST stay in sync with underlying tables
- Spend fields MUST consistently use micros (BIGINT) or USD (REAL), never mixed in same context
- All repositories MUST handle NULL buyer_id gracefully for single-account deployments

### Known Dependencies
- **Read by:** All services, all analytics, all API routers
- **Managed by:** `scripts/postgres_migrate.py`
- **Precompute targets:** `home_*_daily`, `rtb_*_daily`, `config_*_daily` tables
- **Migration chain:** 001 → 027 → 030-044 (17 migrations, non-sequential)

### Likely Failure Modes
1. **Schema drift** — migration adds column but repository SQL doesn't use it (or vice versa)
2. **Alias view mismatch** — canonical views out of sync with actual table DDL
3. **NULL buyer_id** — some queries assume buyer_id is always set; single-account mode breaks
4. **Mixed spend units** — some tables use `spend_micros` (BIGINT), others `spend_usd` (REAL)
5. **Missing indexes** — precompute tables queried by date+buyer but index only on date

### Verification Checks
- [ ] Every column in repository SQL exists in the corresponding migration/schema
- [ ] Canonical alias views (migration 044) match underlying table DDL
- [ ] Spend unit is consistent within each table (never mix micros/USD)
- [ ] All precompute tables have composite indexes matching query patterns
- [ ] buyer_id handling is explicit in every repository method signature

---

## Chunk 4: API Serialization / Contracts

### Scope Globs
```
api/main.py
api/dependencies.py
api/auth.py
api/auth_*.py
api/session_middleware.py
api/routers/**/*.py
api/schemas/**/*.py
api/analysis/**/*.py
api/clustering/**/*.py
```

### Invariants
- Every endpoint MUST have a corresponding Pydantic response model (no raw dicts)
- All endpoints accepting `buyer_id` MUST validate access via `resolve_buyer_id()`
- API response field names MUST match TypeScript `types/api.ts` interface definitions
- Error responses MUST use consistent format (`{detail: string}`)
- Pagination MUST use consistent `limit/offset/has_more` pattern

### Known Dependencies
- **Calls:** Services layer (services/*.py)
- **Returns:** Pydantic schemas (api/schemas/*.py)
- **Consumed by:** Dashboard API client (dashboard/src/lib/api/*.ts)
- **Auth:** SessionAuthMiddleware → APIKeyAuthMiddleware → CORSMiddleware

### Likely Failure Modes
1. **Schema mismatch** — Python response model has field that TS type lacks (or vice versa)
2. **Missing buyer_id validation** — some endpoints skip access control
3. **Inconsistent error format** — some return `{detail}`, others `{error}`, others `{message}`
4. **Missing response models** — endpoints returning raw dicts bypass validation
5. **Timeout cascades** — slow service calls block API response past client timeout

### Verification Checks
- [ ] Every route function has `response_model=` or returns a Pydantic model
- [ ] All `buyer_id` parameters go through access control
- [ ] Error response format is `{detail: string}` everywhere
- [ ] Field names in Pydantic schemas exactly match TypeScript interfaces
- [ ] No endpoint calls a service synchronously that could block >15s

---

## Chunk 5: Dashboard Query Keys + Caching

### Scope Globs
```
dashboard/src/lib/api/**/*.ts
dashboard/src/types/api.ts
dashboard/src/app/**/page.tsx
dashboard/src/contexts/**/*.tsx
dashboard/src/components/**/*.tsx
dashboard/src/lib/utils.ts
dashboard/src/middleware.ts
```

### Invariants
- Every `useQuery` call MUST include ALL parameters that affect the API response in its `queryKey`
- `selectedBuyerId` MUST be in query keys for any buyer-scoped API call
- Timeout values MUST be >= expected API response time for analytics queries
- Context providers MUST fully initialize before child queries fire
- Mutation success callbacks MUST invalidate all related query keys

### Known Dependencies
- **Calls:** Backend API via `fetchApi()` (dashboard/src/lib/api/core.ts)
- **State:** AccountContext (selectedBuyerId), AuthContext (user, permissions)
- **Routing:** Next.js 16 App Router with `[buyerId]` dynamic segments

### Likely Failure Modes
1. **Cross-buyer cache contamination** — `selectedBuyerId` missing from query keys (CONFIRMED: page.tsx:128)
2. **Race condition** — queries fire before buyer context initialized
3. **No retry** — `retry: 0` on critical queries (page.tsx:162,176)
4. **Stale cache** — default staleTime=0 but no explicit refetchInterval
5. **Partial failure** — 6 parallel queries; some fail, others succeed → mixed state

### Verification Checks
- [ ] Every `useQuery` with `selectedBuyerId` in `queryFn` also has it in `queryKey`
- [ ] No `enabled: seatReady` query fires before seats query resolves
- [ ] Critical queries have `retry: 2` or higher
- [ ] All analytics queries have timeout >= 30s
- [ ] Partial failure shows explicit error state, never zero-data

---

## Chunk 6: Recommendation / Actionability

### Scope Globs
```
services/recommendations_service.py
services/evaluation_service.py
analytics/recommendation_engine.py
api/routers/recommendations.py
api/schemas/recommendations.py
dashboard/src/components/recommendations/**/*.tsx
dashboard/src/lib/api/analytics.ts  (recommendations section)
```

### Invariants
- Every recommendation MUST have at least one Evidence with `file:line` or metric reference
- Impact calculations MUST use real data, not hardcoded CPM
- Recommendations MUST be deduped (same creative shouldn't get same recommendation twice)
- "Apply" actions MUST validate preconditions before executing
- Resolution MUST be idempotent

### Known Dependencies
- **Generates from:** Analytics chunk (waste, fraud, geo, creative, config analyzers)
- **Writes to:** `recommendations` table
- **Displayed by:** Dashboard recommendation-card, recommendations-panel
- **Actions target:** `settings/pretargeting/*` apply endpoints

### Likely Failure Modes
1. **No "Apply" buttons** — recommendations show but user can't execute actions
2. **Hardcoded CPM in impact** — savings estimates use $0.002/1000 instead of real CPM
3. **Stale recommendations** — generated once but not refreshed; recommendations expire but UI doesn't show staleness
4. **Analyzer crash propagates** — undefined constant in creative/geo analyzer crashes entire recommendation generation

### Verification Checks
- [ ] Dashboard recommendation cards have "Apply" button for actionable recommendations
- [ ] Impact.potential_savings_monthly uses actual account CPM
- [ ] Recommendation expiry is enforced in the API query
- [ ] Each analyzer is wrapped in try/except so one failure doesn't block others

---

## Chunk 7: Language / Currency Mismatch Flow

### Scope Globs
```
services/creative_language_service.py
api/analysis/language_analyzer.py
api/routers/creative_language.py
utils/language_country_map.py
dashboard/src/components/preview-modal/LanguageSection.tsx
dashboard/src/components/preview-modal/CountrySection.tsx
dashboard/src/components/creative-card.tsx
dashboard/src/lib/api/creatives.ts  (language/geo-mismatch section)
```

### Invariants
- Language detection results MUST persist to `creatives` table (detected_language, confidence)
- Geo-mismatch endpoint MUST be called and displayed in creative cards/lists
- Currency mismatch MUST have a data model and detection logic (currently missing)
- Language-country mapping MUST be exhaustive for top 40 RTB countries

### Known Dependencies
- **Uses:** Gemini API for language detection (api/analysis/language_analyzer.py)
- **Reads:** `creatives.detected_language_code`, `performance_metrics.geography`
- **Maps:** `utils/language_country_map.py` (40+ language-country pairs)

### Likely Failure Modes
1. **Geo-mismatch is only partially surfaced** — preview modal calls geo-mismatch, but card/list triage surfaces do not show mismatch alerts (CONFIRMED)
2. **No currency field** — creative model has no `currency_code` (CONFIRMED)
3. **Gemini API unavailable** — no fallback for language detection when Gemini is down
4. **Incomplete country map** — some RTB-heavy countries may be missing

### Verification Checks
- [ ] `getCreativeGeoMismatch()` (or equivalent mismatch data flow) is surfaced in creative card/list triage rendering, not only preview modal
- [ ] Currency mismatch has a data model (creative.currency_code field)
- [ ] Language detection has a non-Gemini fallback
- [ ] Country-language map covers top 40 RTB traffic countries

---

## Chunk 8: Reliability / Timeouts / Retries

### Scope Globs
```
dashboard/src/lib/api/core.ts
dashboard/src/app/**/page.tsx
collectors/base.py
services/home_precompute.py
services/rtb_precompute.py
services/config_precompute.py
services/precompute_service.py
services/precompute_utils.py
services/precompute_validation.py
scripts/refresh_precompute.py
scripts/refresh_home_cache.py
scripts/refresh_creative_cache.py
```

### Invariants
- API client timeout MUST be >= backend processing time for analytics queries
- Collector API calls MUST have exponential backoff with jitter
- Precompute jobs MUST be idempotent (re-running doesn't corrupt data)
- Precompute staleness MUST be surfaced prominently in the UI
- All network calls MUST have explicit timeout and retry policies

### Known Dependencies
- **Client-side:** fetchApi with DEFAULT_API_TIMEOUT_MS (15s)
- **Collector-side:** BaseAuthorizedBuyersClient with MAX_RETRIES=5, BASE_DELAY=1.0
- **Precompute:** BigQuery queries → PostgreSQL upsert → health check

### Likely Failure Modes
1. **15s timeout too short** — analytics queries can take 20-30s on large datasets
2. **No client retry** — failed fetch → error state → manual refresh required
3. **Precompute stale** — BQ query fails silently → old data served → no prominent indicator
4. **BQ rate limits** — concurrent precompute jobs can hit BQ quota
5. **No circuit breaker** — repeated failures to same endpoint keep trying

### Verification Checks
- [ ] Analytics query timeout ≥ 30s
- [ ] Client has retry policy (retry: 2+) for all analytics queries
- [ ] Precompute health endpoint returns staleness with "last refreshed" timestamp
- [ ] UI shows prominent "Data as of X" when precompute is stale
- [ ] BQ queries have explicit timeout and retry

---

## Dependency Graph

```
Chunk 2 (Importers)
    ↓ writes data to
Chunk 3 (Storage/Schema)
    ↓ provides data to
Chunk 1 (Analytics Core) ←──── Chunk 7 (Language/Currency)
    ↓ generates
Chunk 6 (Recommendations)
    ↓ serialized by
Chunk 4 (API Contracts)
    ↓ consumed by
Chunk 5 (Dashboard Queries) ←── Chunk 8 (Reliability)
```

### Execution Order (dependency-safe)
1. **Chunk 3** (Storage) — foundational, no dependencies
2. **Chunk 2** (Importers) — depends on storage schema
3. **Chunk 1** (Analytics) — depends on stored data
4. **Chunk 7** (Language/Currency) — depends on analytics + storage
5. **Chunk 6** (Recommendations) — depends on analytics output
6. **Chunk 4** (API) — depends on services and schemas
7. **Chunk 5** (Dashboard) — depends on API contracts
8. **Chunk 8** (Reliability) — cross-cutting, review last
