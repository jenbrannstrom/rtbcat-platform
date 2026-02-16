# Reduce Phase Summary

**Date:** 2026-02-16  
**Branch:** `claude/codebase-review-orchestration-hRv5X`  
**Input:** `MAP_PHASE_FINDINGS.json` (18 findings)

---

## 1. Reduce Goals

1. Deduplicate overlapping findings.
2. Resolve factual contradictions before council review.
3. Build dependency-safe implementation batches.
4. Produce an execution-ready packet for LLM Council.

---

## 2. Map Output Rollup

| Priority | Count |
|---|---:|
| P0 | 4 |
| P1 | 4 |
| P2 | 6 |
| P3 | 3 |
| P4 | 3 |

| Chunk | Count |
|---|---:|
| `analytics_core_metrics` | 6 |
| `dashboard_query_caching` | 4 |
| `reliability_timeouts_retries` | 3 |
| `importers_data_normalization` | 2 |
| `language_currency_mismatch` | 2 |
| `recommendation_actionability` | 1 |

---

## 3. Deduped Clusters

## Cluster A: Recommendation Crash + Actionability

- Members: `ANALYTICS-001`, `ANALYTICS-002`, `RECS-001`
- Why grouped: Undefined constants can break recommendation generation; recommendation UI action gaps only matter if generation is reliable.
- Reduced action: Fix crashes first, then wire apply path.

## Cluster B: Buyer Context Integrity on Dashboard

- Members: `DASHBOARD-001`, `DASHBOARD-002`, `DASHBOARD-003`, `RELIABILITY-001`, `RELIABILITY-002`
- Why grouped: query-key correctness, seat init, retry policy, timeout policy, and fallback rendering together determine whether users trust dashboard numbers.
- Reduced action: Treat as one reliability track with shared acceptance tests.

## Cluster C: Metric Definition Accuracy

- Members: `ANALYTICS-003`, `ANALYTICS-004`, `ANALYTICS-005`, `ANALYTICS-006`
- Why grouped: Waste %, savings, QPS, and fraud thresholds all affect recommendation scoring and perceived optimization impact.
- Reduced action: Decide canonical metric contracts before changing formulas.

## Cluster D: Data Ingestion Quality

- Members: `IMPORT-001`, `IMPORT-002`
- Why grouped: normalization + continuity quality both influence downstream analytics reliability.
- Reduced action: canonicalize sizes + introduce import continuity alerting.

## Cluster E: Feature Surface Gaps

- Members: `LANGUAGE-001`, `LANGUAGE-002`, `UX-001`, `UX-002`
- Why grouped: mostly user-surface completeness and context persistence.
- Reduced action: implement after P0/P1 data correctness.

---

## 4. Contradictions Resolved

## 4.1 Geo mismatch wiring is partial, not absent

- Prior claim: dashboard does not call geo-mismatch endpoint.
- Verified now:
  - `dashboard/src/components/preview-modal/LanguageSection.tsx:29` calls `getCreativeGeoMismatch(...)`.
  - `dashboard/src/components/creative-card.tsx:222` shows language label but not mismatch alert.
- Reduced conclusion:
  - Keep as P3 partial-surface gap, not a complete missing integration.

## 4.2 Partial-failure UX has warning banner but still risks misread

- `dashboard/src/app/page.tsx:394` shows delayed-metrics warning.
- `dashboard/src/app/page.tsx:35-38` still falls back metric values to zero.
- Reduced conclusion:
  - Keep as P1/P2 UX-risk item with runtime validation gate, not a pure missing-error-state bug.

---

## 5. Dependency-Safe Execution Batches

## B1 (P0): Crash + Cache Integrity Guardrails

- Findings: `ANALYTICS-001`, `ANALYTICS-002`, `DASHBOARD-001`, `ANALYTICS-003` (contract decision only)
- Scope:
  - `analytics/creative_analyzer.py`
  - `analytics/geo_analyzer.py`
  - `dashboard/src/app/page.tsx`
  - metric-contract docs/tests for waste definition
- Acceptance gates:
  - No NameError in recommendation generation paths.
  - Buyer switch invalidates/refetches qps-summary correctly.
  - Waste metric contract documented and referenced by consumers.

## B2 (P1): Dashboard Reliability Cohesion

- Findings: `RELIABILITY-001`, `RELIABILITY-002`, `DASHBOARD-002`, `DASHBOARD-003`
- Scope:
  - `dashboard/src/lib/api/core.ts`
  - `dashboard/src/app/page.tsx`
- Acceptance gates:
  - Critical queries retry on transient timeout.
  - Seat initialization path has deterministic loading/failure UX.
  - Partial performance failure cannot silently look like healthy zeroes.

## B3 (P2): Metric Accuracy Normalization

- Findings: `ANALYTICS-004`, `ANALYTICS-005`, `ANALYTICS-006`
- Scope:
  - `analytics/waste_analyzer.py`
  - `analytics/geo_analyzer.py`
  - `analytics/fraud_analyzer.py`
  - any downstream recommendation weighting paths
- Acceptance gates:
  - CPM source uses account data fallback strategy.
  - Peak/avg QPS clarity exposed in payload or UI labels.
  - Fraud thresholds become format-aware or explicitly profiled.

## B4 (P2/P4): Import Quality Controls

- Findings: `IMPORT-001`, `IMPORT-002`
- Scope:
  - `importers/unified_importer.py`
  - `utils/size_normalization.py`
  - upload/import history surface (`storage/postgres_repositories/uploads_repo.py` + API/UI if needed)
- Acceptance gates:
  - Imported size fields normalized before persistence.
  - Missing-day continuity check and alert path exists.

## B5 (P3/P4): Feature Surface and UX Polish

- Findings: `LANGUAGE-001`, `LANGUAGE-002`, `RECS-001`, `UX-001`, `UX-002`
- Scope:
  - creative card/list surfaces
  - recommendation action wiring
  - model/schema additions for currency (if approved)
  - dashboard filter persistence
- Acceptance gates:
  - Geo mismatch visible where analysts triage creatives.
  - Recommendation actions can trigger apply flow (with safety controls).
  - Currency mismatch design decision finalized before schema work.

---

## 6. Council Input Packet (Ready)

Use these as source material for council prompting:

1. `docs/review/2026-02-16/REVIEW_ORCHESTRATION_PLAN.md`
2. `docs/review/2026-02-16/CHUNK_MAP.md`
3. `docs/review/2026-02-16/FINDINGS_VALIDATION.md`
4. `docs/review/2026-02-16/MAP_PHASE_FINDINGS.json`
5. `docs/review/2026-02-16/COUNCIL_MASTER_PROMPT.md`

Recommended council ask:

1. Confirm/adjust batch ordering (B1-B5).
2. Resolve metric contract decisions (waste denominator, CPM source, peak vs avg QPS).
3. Propose implementation-level acceptance tests for each batch.
4. Flag any migration/rollback risk before code changes begin.

---

## 7. Go/No-Go

Status: **GO** for council review phase.

Conditions:

1. Treat `ANALYTICS-003` (waste formula) as a decision item before broad code edits.
2. Keep runtime-flagged items (`needs_runtime_validation`) gated behind VM2 checks.
3. No production (VM1) changes until B1/B2 pass on local + VM2.
