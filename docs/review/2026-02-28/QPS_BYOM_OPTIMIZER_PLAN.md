# QPS BYOM Optimizer Plan

**Date:** 2026-02-28  
**Scope:** Define the best optimizer we can build now from current Cat-Scan ingestion, plus the forward model with conversion pixel and MMP (AppsFlyer-style) data.

## EXEC Summary

- Build a **BYOM skill** now: `byom-qps-optimizer` (Bring Your Own Model), focused on **traffic allocation and pretargeting actions**, not bid-pricer control.
- Use current data to optimize for **business-efficient inventory** via a fallback objective stack:
  1. Conversion value / CPA / ROAS when available.
  2. If unavailable, proxy value from win efficiency + click efficiency + cost efficiency (CPC/CPM) + quality penalties.
- Current visibility is fundamentally **after-the-fact CSV**; we do not observe all live bid opportunities or full bidder internals. The optimizer must be explicit about confidence and uncertainty.
- Several ingestion/data-model gaps currently reduce optimizer quality (highest priority):
  - `quality_signals -> rtb_quality` is detected but not imported through `unified_importer`.
  - `rtb_bidstream` drops mapped fields (`platform`, `environment`, `transaction_type`) on insert.
  - Missing-field defaults to zero/unknown can hide data availability problems.
- If we add conversion pixel + AppsFlyer/MMP signals, we can move from proxy optimization to **outcome optimization** (incremental conversions/value), including better intent and fraud discrimination.

---

## 1) What Report Data Is Ingested Today

### A. Ingested now (usable now)

- `rtb_daily` (performance detail style)
  - Core: `metric_date`, `billing_id`, `creative_id`, `creative_size`, `country`, `publisher_id`, `app_id`, `reached_queries`, `impressions`, `clicks`, `spend_micros`.
- `rtb_bidstream` (funnel geo/publisher)
  - Core: `metric_date`, `hour`, `country`, `buyer_account_id`, `publisher_id`, `inventory_matches`, `bid_requests`, `successful_responses`, `reached_queries`, `bids`, `bids_in_auction`, `auctions_won`, `impressions`, `clicks`.
- `rtb_bid_filtering`
  - Core: `metric_date`, `country`, `buyer_account_id`, `filtering_reason`, `creative_id`, `bids`, `bids_in_auction`, `opportunity_cost_micros`.
- `web_domain_daily` (optional domain lane)
  - Core: domain-level reached/impressions/spend and derived `inventory_type`.

### B. Important current constraints

- We optimize pretargeting and allocation, but do not control bidder internals directly.
- We mostly observe outcomes after bidder decisions, not complete real-time request universe.
- Report completeness varies by buyer seat (some seats receive fewer scheduled CSV types).

### C. Confirmed implementation gaps impacting optimizer quality

- `quality_signals` can route to `rtb_quality` in type detection, but `unified_importer` has no `rtb_quality` import branch.
- `rtb_bidstream` row mapping captures `platform/environment/transaction_type`, but insert SQL excludes them.
- Defaults treat many missing metrics as `0`, which can conflate “unknown” and “zero”.

---

## 2) Skill To Build Now: `byom-qps-optimizer`

### Purpose

Allow a user to plug in their own model (or rules engine) and generate actionable QPS optimization recommendations from existing Cat-Scan data.

### What it should optimize now

- Primary: maximize expected business utility per QPS under spend/risk guardrails.
- Current fallback objective (no conversion labels):
  - Higher: win efficiency, impression yield, click efficiency.
  - Lower cost: CPM/CPC where available.
  - Penalize: high filtering, fraud/viewability risk (when available), unstable/low-sample segments.

### Plugin contract (minimal)

Input: segment-level feature rows (daily/hourly) keyed by:
- `buyer_account_id`, `billing_id`, `publisher_id`, `country`, `creative_size`, `platform`, `environment`, `hour`.

Output per segment:
- `score`, `confidence`, `recommended_action`, `reason_codes`.

Actions:
- `INCREASE_QPS_SHARE`, `DECREASE_QPS_SHARE`, `MONITOR`, `BLOCK_PUBLISHER`, `REVIEW_CONFIG`.

### Guardrails for hidden buyer intent

Because buyer intent can diverge (e.g., lead capture vs product sale), skill output must include:
- **Intent mode** (declared by buyer): `conversion`, `reach`, `lead-gen`, `traffic-quality`, etc.
- **Policy/compliance override**: block non-compliant patterns regardless of model score.
- **Uncertainty-aware recommendations**: no aggressive action on weak evidence windows.

---

## 3) Missing Data Points To Improve Success Odds

### P0 (highest)

1. True outcome labels: conversion count, conversion value, qualified lead markers.
2. Auction price context: next-in-rank CPC / clearing-like signals / floor context.
3. Quality ingestion path completion: operational `rtb_quality` imports in current pipeline.
4. Preserve funnel dimensions already mapped: `platform`, `environment`, `transaction_type` in `rtb_bidstream` writes.
5. Missingness semantics: distinguish `NULL` unknown from numeric `0` true zero.

### P1

1. Currency normalization and explicit currency code lineage for spend fields.
2. More robust report_type persistence in raw facts for cleaner joins and precompute filters.
3. Compliance/intention features at campaign/creative level (landing URL category, tracking-domain class).

### Evidence snapshot (code references used)

- `METRICS_GUIDE.md` defines current optimization scope and CSV constraints.
- `importers/flexible_mapper.py` routes IVT/quality to `rtb_quality` (`detect_best_report_type`).
- `importers/unified_importer.py` has no `rtb_quality` import branch in final table routing.
- `importers/unified_importer.py` maps `platform/environment/transaction_type` for bidstream rows.
- `importers/unified_importer.py` bidstream INSERT excludes those mapped columns.
- `importers/flexible_mapper.py` applies broad zero/unknown defaults for missing fields.
- `importers/csv_report_types.py` still documents IVT quality report as not yet implemented.
- `analytics/qps_optimizer.py` expects `rtb_quality` for IVT/viewability analysis.

---

## 4) Best-Practice Optimizer Data Model (Target)

### Core dimensions

- `dim_segment`
  - `segment_id` (hash), `buyer_account_id`, `billing_id`, `publisher_id`, `country`, `app_id`, `creative_size`, `platform`, `environment`, `hour`, `transaction_type`.

### Core facts

- `fact_funnel_segment_day`
  - from `rtb_bidstream`: bid/funnel metrics.
- `fact_delivery_segment_day`
  - from `rtb_daily`: impressions/clicks/spend/reached.
- `fact_filtering_segment_day`
  - from `rtb_bid_filtering`: rejection reasons/opportunity cost.
- `fact_quality_segment_day`
  - from `rtb_quality`: IVT/viewability.
- `fact_conversion_segment_day` (new)
  - pixel/MMP-attributed conversions + value.

### Model and decision lineage

- `model_feature_snapshot`
  - full feature vector + generation timestamp.
- `optimizer_decision_log`
  - segment, score, confidence, action, policy checks.
- `optimizer_outcome_log`
  - realized post-action outcomes for closed-loop learning.

---

## 5) Extrapolation: Future Data Additions

### A) Add conversion tracking pixel

What changes:
- Add event stream for click/impression -> conversion with attribution window.
- Build `fact_conversion_segment_day` and outcome labels for training/evaluation.

Likely impact:
- Moves optimizer from proxy efficiency to true business outcomes.
- Improves separation between cheap-but-low-value inventory vs scalable profitable inventory.

Risks:
- Attribution lag and dedup rules can mislead model if not standardized.
- Pixel loss/blocked tracking can bias observed winners.

### B) Ingest AppsFlyer/MMP data

What changes:
- Add external attribution events (install, in-app event, value) with campaign/creative mapping.
- Enables quality of downstream events, not just top-of-funnel click/impression.

Likely impact:
- Stronger intent and fraud discrimination.
- Better optimization for app advertisers where post-install value matters.

Risks:
- ID/key mismatch across systems; require deterministic + probabilistic mapping strategy.
- Different attribution methodologies across buyers can reduce comparability.

---

## 6) Concise Rollout Plan

1. **Foundation hardening (now)**
   - Fix ingestion gaps (`rtb_quality` path, bidstream dimension persistence, missing-vs-zero).
2. **BYOM skill MVP (current data)**
   - Segment scoring, action ranking, confidence and policy guardrails.
3. **Conversion pixel phase**
   - Add conversion facts + offline evaluation (uplift vs baseline policies).
4. **MMP phase (AppsFlyer-like)**
   - Add post-install value loop and retrain objective toward business-value growth.

## Success Criteria

- Recommendation acceptance and execution rate by media buyers.
- Lower wasted QPS at equal or better business outcome.
- Improved stability: fewer reversals/rollbacks from noisy signals.
- Clear compliance pass/fail traceability per recommendation.
