# Creative Modal Performance Clicks Parity Fix

**Date:** 2026-02-25
**Author:** Claude (AI Dev)
**Status:** Implemented

## Root Cause

The creative performance summary path used `pretarg_creative_daily` (a view over `config_creative_daily`), which has **no clicks column**. The code hard-coded `total_clicks = 0`:

```python
# storage/postgres_store.py:1425 (BEFORE)
"total_clicks": 0,  # pretarg_creative_daily has no clicks column
```

This caused the preview modal to show `Clicks: 0` alongside valid CPM values, which was misleading.

## Source Tables: Before vs After

| Metric | Before (pretarg_creative_daily) | After (rtb_daily) |
|--------|-------------------------------|-------------------|
| impressions | SUM(impressions) | SUM(impressions) |
| clicks | **hard-coded 0** | SUM(clicks) |
| spend_micros | SUM(spend_micros) | SUM(spend_micros) |
| CPM | computed from spend/impressions | computed from spend/impressions |
| CPC | always None | computed from spend/clicks |
| CTR | always None | computed from clicks/impressions |

**Primary source:** `rtb_daily` (from CSV imports, has full click data)
**Fallback:** `pretarg_creative_daily` (when rtb_daily has no data for a creative)

## Scoping Correction

The previous query did not filter by `buyer_account_id`:
```sql
-- BEFORE: No buyer scoping
FROM pretarg_creative_daily WHERE creative_id = %s
```

The new query applies buyer scoping when the creative's buyer_id is known:
```sql
-- AFTER: Buyer-scoped
FROM rtb_daily WHERE creative_id = ANY(%s) AND buyer_account_id = %s
```

This prevents potential cross-seat contamination.

## Batch Query Optimization

The batch endpoint (`POST /performance/metrics/batch`) previously called `get_creative_performance_summary()` per creative (N+1 pattern).

The new implementation:
1. Single batch query to `rtb_daily` for all creative_ids
2. Only falls back to per-creative legacy path for IDs not found in rtb_daily

## Data Provenance Metadata

New response fields added to `CreativePerformanceSummary` and `PerformanceSummaryResponse`:

| Field | Type | Description |
|-------|------|-------------|
| `metric_source` | `string?` | `"rtb_daily"` or `"pretarg_creative_daily"` |
| `clicks_available` | `bool` | `true` if source has real click data |

## Frontend Changes

- **PreviewModal.tsx:** Renders `N/A` for clicks/CTR/CPC when `clicks_available === false`
- **utils.ts:** Data-note logic only triggers click-related warnings when `clicks_available` is true

## Files Modified

### Backend
- `storage/postgres_repositories/creative_performance_repo.py` - Added `get_creative_summaries()` batch method
- `api/schemas/performance.py` - Added `metric_source`, `clicks_available` fields
- `api/routers/performance.py` - Updated single + batch endpoints to use rtb_daily

### Frontend
- `dashboard/src/types/api.ts` - Added `metric_source`, `clicks_available` to interface
- `dashboard/src/components/preview-modal/PreviewModal.tsx` - N/A handling for unavailable clicks
- `dashboard/src/components/preview-modal/utils.ts` - Click data-note gated by availability

## Validation

- [ ] Creative `2016792147219165185`: clicks in modal match `rtb_daily` aggregate
- [ ] CPM remains consistent between old and new paths
- [ ] Batch endpoint returns click data for all creatives with rtb_daily data
- [ ] Creatives only in pretarg_creative_daily show `N/A` for clicks (not fake 0)
