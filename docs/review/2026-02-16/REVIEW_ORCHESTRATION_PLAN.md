# Review Orchestration Plan

**Date:** 2026-02-16
**Branch:** `claude/codebase-review-orchestration-hRv5X`
**Base SHA:** `b221f687dd68e9c6fda9bd49389a147a404b9aea`
**Scope:** Full codebase review orchestration for RTBcat Platform (~450 files)

---

## 1. Architecture Summary

### System Overview

```
CSV Imports (Gmail / Manual Upload)
    ↓
Unified Importer (5 report types, flexible column mapping)
    ↓
PostgreSQL (rtb_daily, rtb_bidstream, rtb_bid_filtering, rtb_quality)
    ↓                                   ↑
BigQuery ←── Precompute Service ────→ Materialized Summaries
    ↓                                   (home_*_daily, rtb_*_daily, config_*_daily)
Analytics Engine                        ↓
    ↓                              FastAPI Routes (124 endpoints, 21 route groups)
Recommendation Engine                   ↓
    ↓                              Next.js 16 Dashboard ← TanStack React Query
    └───────────────────────────────────┘
```

### Layer Inventory

| Layer | Location | Files | Key Components |
|-------|----------|-------|----------------|
| **API** | `api/` | ~30 router modules | FastAPI, Pydantic schemas, 3 middleware layers |
| **Services** | `services/` | 45+ files | Business logic, precompute orchestration |
| **Analytics** | `analytics/` | 14 files | Waste, QPS, fraud, geo, creative analyzers, recommendation engine |
| **Importers** | `importers/` | 7 files | CSV report detection, flexible column mapper, unified importer |
| **Collectors** | `collectors/` | 10 files | Google Authorized Buyers API clients (creatives, pretargeting, endpoints) |
| **Storage** | `storage/` | 24+ repos | PostgreSQL (46 tables), BigQuery bridge, 17 migrations |
| **Dashboard** | `dashboard/src/` | ~100 files | Next.js 16 app router, 120+ API client functions, 3 contexts |
| **Config** | `config/` | 2 files | Config manager |
| **Utils** | `utils/` | 5 files | Size normalization, language-country maps, HTML thumbnail |
| **Scripts** | `scripts/` | 20+ files | Pipeline, deployment, migration, refresh scripts |

### API Route Groups (124 endpoints)

| Group | Count | Prefix |
|-------|-------|--------|
| Authentication | 9 | `/auth/*` |
| System/Health | 8 | `/health`, `/system/*`, `/stats`, `/sizes`, `/geos/*` |
| Creatives | 11 | `/creatives/*` |
| Campaigns | 13 | `/campaigns/*` |
| Seats | 5 | `/seats/*` |
| Settings/RTB | 18 | `/settings/*` |
| Performance | 7 | `/performance/*` |
| Analytics (Waste) | 6 | `/analytics/waste*`, `/analytics/fraud*` |
| Analytics (QPS) | 10 | `/analytics/qps*`, `/analytics/size*`, `/analytics/geo*` |
| Analytics (RTB/Traffic) | 10 | `/analytics/rtb-funnel/*`, `/analytics/app*`, `/analytics/spend*` |
| Analytics (Home) | 4 | `/analytics/home/*` |
| Recommendations | 4 | `/recommendations/*` |
| Collection | 2 | `/collect*` |
| Config | 8 | `/config/*` |
| Uploads | 4 | `/uploads/*` |
| Gmail | 3 | `/gmail/*` |
| Retention | 4 | `/retention/*` |
| Precompute | 2 | `/precompute/*` |
| Troubleshooting | 4 | `/api/troubleshooting/*`, `/api/evaluation` |
| Admin | 14 | `/admin/*` |

### Storage Architecture

- **46 core PostgreSQL tables** with 17 migrations applied
- **24 SQL-only repositories** in `storage/postgres_repositories/`
- **Dual storage**: BigQuery (OLAP/historical) + PostgreSQL (OLTP/serving)
- **Precompute pipeline**: BQ → ETL → PG summary tables → UI
- **Table aliases**: Canonical view aliases for backward compat (e.g., `pretarg_daily` → `home_config_daily`)

### Shared Contracts

| Contract | Python Location | TypeScript Location | Field Pattern |
|----------|----------------|---------------------|---------------|
| Creative ID | `storage/models.py` (creatives.id) | `types/api.ts` (Creative.id) | `TEXT` PK |
| Billing ID | `pretargeting_configs.billing_id` | `settings.ts` (PretargetingConfigResponse) | `TEXT` |
| Buyer Account | `buyer_seats.buyer_id` | `account-context.tsx` (selectedBuyerId) | `TEXT` |
| Spend | `performance_metrics.spend_micros` | Various (spend_micros) | `BIGINT` (USD × 1M) |
| Waste Rate | Multiple formulas | Various | `float` (0-100%) |
| Win Rate | `impressions/reached * 100` | Various | `float` (0-100%) |
| Metric Date | `DATE` (YYYY-MM-DD) | `string` | ISO format |
| Country | `geography` (ISO 3166-1 α-2) | `country` / `geography` | `TEXT` 2-letter |

### Key Thresholds and Constants

| Constant | Value | Location |
|----------|-------|----------|
| `ESTIMATED_COST_PER_1000` | $0.002 | `analytics/waste_analyzer.py:40` |
| `SUSPICIOUSLY_HIGH_CTR` | 10% | `analytics/fraud_analyzer.py:44` |
| `ZERO_ENGAGEMENT_CTR_THRESHOLD` | 0.1% | `analytics/creative_analyzer.py:33` |
| `DEFAULT_API_TIMEOUT_MS` | 15000ms | `dashboard/src/lib/api/core.ts:9` |
| `HIGH_VOLUME_THRESHOLD` | 10,000 req/day | `analytics/waste_analyzer.py:34` |
| `MIN_GEO_SPEND_USD` | $10 | `analytics/geo_analyzer.py:33` |
| `SECONDS_PER_DAY` | 86400 | Multiple files |

---

## 2. Review Methodology

### Input
- `docs/CODEBASE_REVIEW_2026-02-16.md` — the original review document with 19 prioritized findings

### Approach
1. **Map Phase**: Chunk the codebase into bounded domains with explicit dependency edges
2. **Validate Phase**: For each claim in the review doc, verify against actual code with `file:line` evidence
3. **Reduce Phase**: Deduplicate overlapping findings, resolve contradictions, produce prioritized implementation order
4. **Council Phase**: Generate a master prompt that enables a council of reviewers to produce a ranked implementation path

### Evidence Standard
- **Confirmed**: Exact `file:line` reference proving the claim
- **Not Found**: The claimed code/behavior does not exist in current codebase
- **Changed since review**: Code exists but differs from what the review describes
- **Needs Runtime Validation**: Code exists but behavior depends on runtime state (DB data, env vars, timing)

---

## 3. Chunking Strategy

See `CHUNK_MAP.md` for the complete chunking strategy with 8 bounded review chunks, each with:
- Scope globs
- Invariants
- Known dependencies
- Likely failure modes
- Verification checks

---

## 4. Map-Reduce Protocol

### Map Phase
Each chunk reviewer answers a fixed set of questions and produces structured findings in the schema defined in `FINDINGS_SCHEMA.json`.

### Reduce Phase
1. Deduplicate findings that span multiple chunks
2. Resolve conflicting assessments
3. Produce prioritized implementation order (P0/P1/P2/P3)
4. Generate dependency-safe execution sequence
5. Define acceptance tests per priority band

---

## 5. Deliverables Index

| # | File | Purpose |
|---|------|---------|
| 1 | `REVIEW_ORCHESTRATION_PLAN.md` | This file — architecture map and methodology |
| 2 | `CHUNK_MAP.md` | Bounded review chunks with dependencies and verification |
| 3 | `FINDINGS_VALIDATION.md` | Claim-by-claim validation with evidence |
| 4 | `FINDINGS_SCHEMA.json` | Structured schema for map-phase findings |
| 5 | `COUNCIL_MASTER_PROMPT.md` | Council-ready prompt package for implementation planning |
| 6 | `MAP_PHASE_FINDINGS.json` | Normalized findings dataset (P0-P4 + chunk labels) |
| 7 | `REDUCE_PHASE_SUMMARY.md` | Deduped clusters, contradiction resolution, and execution batches |

---

## 6. Environment Notes

- **VM1** = Production (Singapore GCP) — DO NOT modify
- **VM2** = Staging (Singapore GCP) — safe for validation
- **Local PostgreSQL** — available for UI testing
- No active users currently; temporary downtime acceptable on VM2
- No app source code changes in this phase
