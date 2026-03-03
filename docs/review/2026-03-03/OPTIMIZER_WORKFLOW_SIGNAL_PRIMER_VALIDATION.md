# Optimizer Workflow Signal Primer — Production Validation

- **Date**: 2026-03-03 UTC
- **Buyer**: 1487810529 (Amazing Design Tools LLC)
- **Deployed SHA**: `sha-b92a021`
- **Script commit**: `3370740` (ops(v1): auto-resolve billing_id in workflow signal primer)
- **Validator**: Claude Code (automated)

## 1. Executive Summary

The `scripts/prime_v1_optimizer_workflow_signal.sh` script now produces lifecycle-eligible
proposals for buyer `1487810529`. The root cause of the prior `scores_considered=0` /
`top_proposals_count=0` failure was missing `billing_id` on seeded conversion events.
Commit `3370740` added auto-resolve logic that queries pretargeting configs to extract
the active `billing_id` before seeding events. After pulling the fix and re-running, the
full pipeline works end-to-end: pixel events are seeded with `billing_id=162974537887`,
aggregates refresh correctly, scoring produces billing_id-backed scores, and
score-and-propose generates 3 draft proposals.

## 2. Evidence Table (Before / After)

| Metric | Before (old script) | After (commit 3370740) |
|--------|--------------------|-----------------------|
| `seed_billing_id` | (not printed / empty) | `162974537887` |
| `pixel_accepted` | 20 | 5 (plus 65 from earlier runs) |
| `aggregates_upserted_rows` | 1 (no billing_id) | 2 (one per billing_id bucket) |
| `top_row_event_count` | 20 (billing_id="") | 70 (billing_id=162974537887) |
| `workflow_segments_scanned` | unknown | 3 |
| `workflow_scores_written` | 0 | 3 |
| `workflow_scores_considered` | 0 | 3 |
| `workflow_proposals_created` | 0 | 3 |
| `top_proposals_count` | 0 | **3** |
| `first_proposal_id` | (none) | `prp_6d9b39b6de314c9cb77615b4ff2544da` |
| Script exit code | 1 (FAIL) | **0 (PASS)** |

## 3. Root Cause

The optimizer's proposal engine requires `billing_id` on segment scores to match them
against pretargeting configs for QPS adjustment. Without `billing_id`, scores are created
with `billing_id=""` which the proposer skips as ineligible (`missing_billing_id_scores`
counter). The old script never passed `billing_id` when seeding pixel events, so all
aggregates and downstream scores had empty `billing_id`.

The auto-resolve fix in `3370740`:
1. Queries `GET /settings/pretargeting?buyer_id=...&summary_only=true`
2. Picks the first ACTIVE config's `billing_id` (falls back to any non-empty)
3. Passes `billing_id=<resolved>` on all pixel event calls
4. Result: aggregates, scores, and proposals all carry the correct `billing_id`

For buyer `1487810529`, the resolved billing_id is `162974537887`.

## 4. What Changed

| Commit | Description |
|--------|-------------|
| `3370740` | `ops(v1): auto-resolve billing_id in workflow signal primer` — added `--auto-resolve-billing-id` flag (default true), pretargeting config lookup, `seed_billing_id` output line |

No additional script fixes were needed. The script at `3370740` works correctly.

## 5. Go/No-Go for Strict Runtime Health Rerun

**GO** — The optimizer workflow signal pipeline is fully functional:

- Auto-resolve billing_id: working (`162974537887` from pretargeting config)
- Pixel ingestion: 70 events accepted with correct billing_id
- Aggregate refresh: 2 rows upserted (1 with billing_id, 1 legacy without)
- Scoring: 3 segments scanned, 3 scores written (billing_id-backed)
- Proposals: 3 draft proposals created (`current_qps=10.0 → proposed_qps=11.0`)
- Script exit code: 0 (PASS)

Safe to proceed with strict runtime health rerun and daily automation.

## Artifacts

### Final Script Run

```
Run dir: /tmp/v1-prime-workflow-signal-1487810529-20260303T232241Z
seed_billing_id=162974537887
pixel_accepted=5 pixel_rejected=0
aggregates_refresh_http=200
aggregates_upserted_rows=2 aggregates_deleted_rows=2
aggregates_total=2 top_row_event_count=70
model_id=mdl_86695be95a7a4c7a81884ffa8d0e511a
workflow_segments_scanned=3
workflow_scores_written=3
workflow_scores_considered=3
workflow_proposals_created=3
top_proposals_count=3
first_proposal_id=prp_6d9b39b6de314c9cb77615b4ff2544da
Result: PASS
```

### Proposal Details

```json
[
  {
    "proposal_id": "prp_6d9b39b6de314c9cb77615b4ff2544da",
    "billing_id": "162974537887",
    "current_qps": 10.0,
    "proposed_qps": 11.0,
    "delta_qps": 1.0,
    "rationale": "Based on score 0.600, confidence 0.300, signals: high_event_volume, low_cpa, no_value_signal.",
    "status": "draft"
  },
  {
    "proposal_id": "prp_5f0b5b7146c5421bb5d6e42db2162bb7",
    "billing_id": "162974537887",
    "current_qps": 10.0,
    "proposed_qps": 11.0,
    "delta_qps": 1.0,
    "status": "draft"
  },
  {
    "proposal_id": "prp_5980c5c3fdf0414f9fe6a3f78c00c318",
    "billing_id": "162974537887",
    "current_qps": 10.0,
    "proposed_qps": 11.0,
    "delta_qps": 1.0,
    "status": "draft"
  }
]
```

### Aggregate Snapshot

| agg_date | billing_id | event_count | event_value_total |
|----------|-----------|-------------|-------------------|
| 2026-03-03 | 162974537887 | 70 | 70.0 |
| 2026-03-03 | (empty) | 20 | 20.0 |

### Segment Scores (billing_id-backed)

| score_id | billing_id | score_date | value_score | confidence |
|----------|-----------|------------|-------------|------------|
| scr_c923... | 162974537887 | 2026-03-03 | 0.60 | 0.30 |
| scr_e352... | 162974537887 | 2026-03-03 | 0.60 | 0.30 |
| scr_4a20... | 162974537887 | 2026-03-03 | 0.60 | 0.30 |
