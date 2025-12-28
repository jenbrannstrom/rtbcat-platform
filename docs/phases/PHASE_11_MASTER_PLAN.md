# Cat-Scan Phase 11: Decision Intelligence

**Version:** 11.0
**Goal:** Transform Cat-Scan from a data viewer into a decision engine
**North Star:** Every screen answers "What's wasting money and what should I do?"

---

## Guiding Principles

1. **Facts Over Assumptions** - Show the data, let users decide
2. **Context is King** - Metrics without timeframe are meaningless
3. **Evidence Trail** - Every signal explains WHY it was flagged
4. **Action-Oriented** - Every insight has a clear next step
5. **Scale by Default** - Pagination, lazy loading, chunked processing

---

## Phase 11.1: Decision Context Foundation (CRITICAL)

**Why First:** Without timeframe context, users can't make decisions. This is the single biggest gap.

### 11.1.1 API: Timeframe-Aware Endpoints

```
GET /campaigns?days=7          → Last 7 days aggregation
GET /campaigns?days=30         → Last 30 days aggregation
GET /creatives?days=7&active_only=true → Hide zero-activity
GET /analytics/waste?days=7    → Waste analysis with context
```

**Implementation:**
- [ ] Add `days` parameter to `/campaigns` endpoint
- [ ] Add `days` parameter to `/creatives` endpoint
- [ ] Return aggregated metrics (spend, imps, clicks, waste_score) per timeframe
- [ ] Add `active_only` filter to hide creatives with zero activity in timeframe

### 11.1.2 API: Campaign Aggregation

Currently campaigns return creative IDs. They need to return:

```json
{
  "id": "campaign_123",
  "name": "Brand X Videos",
  "creative_count": 45,
  "timeframe": "7d",
  "metrics": {
    "total_spend_micros": 125000000,
    "total_impressions": 450000,
    "total_clicks": 2250,
    "avg_cpm": 277.78,
    "avg_ctr": 0.50,
    "waste_score": 23.5
  },
  "warnings": {
    "broken_video_count": 3,
    "zero_engagement_count": 12,
    "high_spend_low_performance": 2
  }
}
```

**Implementation:**
- [ ] Create `campaign_aggregation_service.py`
- [ ] Join campaigns → creatives → performance_data with date filter
- [ ] Calculate waste_score: (reached_queries - impressions) / reached_queries * 100
- [ ] Add warning counts to response

### 11.1.3 Frontend: Timeframe Selector

**Location:** Campaign page header, global context

```
[Last 7 days ▼] [Last 30 days] [Last 90 days] [Custom]
```

**Implementation:**
- [ ] Add TimeframeSelector component
- [ ] Store selection in React Query context
- [ ] Propagate to all API calls
- [ ] Grey out/hide creatives with zero activity in timeframe

---

## Phase 11.2: Evidence-Based Waste Detection

**Why:** "broken_video" and "zero_engagement" are labels without evidence. Users need to see WHY.

### 11.2.1 Waste Signal Model

Replace boolean flags with evidence objects:

```json
{
  "creative_id": "cr-12345",
  "waste_signals": [
    {
      "signal_type": "broken_video",
      "confidence": "high",
      "evidence": {
        "thumbnail_status": "failed",
        "error_type": "media_timeout",
        "impressions": 45000,
        "observation": "45K impressions on unplayable video"
      },
      "recommendation": "Pause creative, contact advertiser"
    },
    {
      "signal_type": "low_engagement",
      "confidence": "medium",
      "evidence": {
        "impressions": 125000,
        "clicks": 12,
        "ctr": 0.0096,
        "percentile": 5,
        "observation": "CTR in bottom 5% of account"
      },
      "recommendation": "Review creative quality or targeting"
    }
  ]
}
```

**Implementation:**
- [ ] Create `waste_signals` table with evidence JSON
- [ ] Create WasteAnalyzer service class
- [ ] Generate signals on import (not just query time)
- [ ] Add `/creatives/{id}/waste-analysis` endpoint
- [ ] Store observation text explaining the signal

### 11.2.2 Fraud Signal Enhancement

Current fraud detection is too prescriptive. Enhance with context:

```json
{
  "signal_type": "suspicious_click_ratio",
  "evidence": {
    "clicks": 150,
    "impressions": 100,
    "ratio": 1.5,
    "occurrences": 7,
    "date_range": "2025-11-25 to 2025-12-01"
  },
  "context": "This pattern repeated 7 times in 7 days",
  "action": "FLAG_FOR_REVIEW"
}
```

---

## Phase 11.3: Campaign Clustering UX Fix

**Why:** DnD bugs frustrate users; missing stats prevent decisions.

### 11.3.1 Fix DnD Collision Detection

**Current Bug:** `closestCorners` causes accidental unassignment on click

**Fix:**
- [ ] Switch to `pointerWithin` collision strategy
- [ ] Add target validation (only drop on valid campaign zones)
- [ ] Disable campaign during mutation (prevent stale cache issues)
- [ ] Add optimistic UI updates

### 11.3.2 Campaign Card Enhancements

Each campaign card needs:

```
┌─────────────────────────────────────────┐
│ Brand X Videos                    [···] │
│ 45 creatives · $1,250 spend (7d)       │
│                                         │
│ ⚠ 3 broken  ⚠ 12 zero engagement       │
│ ▓▓▓▓▓▓▓▓░░ 78% healthy                 │
│                                         │
│ Waste Score: 23.5%                     │
│ [View Details] [Bulk Actions]          │
└─────────────────────────────────────────┘
```

**Implementation:**
- [ ] Add warning badges with counts
- [ ] Add health bar visualization
- [ ] Add waste score display
- [ ] Add bulk action menu (pause all broken, export list)

### 11.3.3 Grid/List View Improvements

- [ ] Grid: Add mini waste indicator (red/yellow/green dot)
- [ ] List: Add sortable columns (waste%, spend, CTR)
- [ ] Both: Respect timeframe filter

---

## Phase 11.4: Scale Readiness

**Why:** `/api/creatives?limit=1000` truncates large accounts. Enterprise users will leave.

### 11.4.1 Pagination Infrastructure

- [ ] Add cursor-based pagination to all list endpoints
- [ ] Return pagination metadata: `{ total, next_cursor, has_more }`
- [ ] Add infinite scroll to creative grid
- [ ] Add "Load More" button fallback

### 11.4.2 Performance Optimization

- [ ] Add database indexes for common queries (buyer_id, campaign_id + metric_date)
- [ ] Add query result caching (Redis or in-memory with TTL)
- [ ] Lazy load thumbnails (intersection observer)

---

## Phase 11.5: Documentation Reconciliation

**Why:** 10.2 vs 10.3 confusion wastes your time explaining to yourself.

- [ ] Consolidate to single authoritative version in README
- [ ] Archive old handover docs to `/docs/archive/`
- [ ] Add CHANGELOG.md with dated entries
- [ ] Update Handover doc to 11.0 on completion

---

## Implementation Priority Matrix

| Phase | Impact | Effort | Priority |
|-------|--------|--------|----------|
| 11.1 Timeframe Context | **HIGH** (enables decisions) | Medium | 🔴 P0 |
| 11.2 Evidence Signals | **HIGH** (builds trust) | Medium | 🔴 P0 |
| 11.3 DnD/UX Fix | **MEDIUM** (removes friction) | Low | 🟡 P1 |
| 11.4 Pagination | **HIGH** (enterprise ready) | Medium | 🟡 P1 |
| 11.5 Doc Cleanup | **LOW** (hygiene) | Low | 🟢 P2 |

---

## Success Metrics

After Phase 11:

1. **User can answer in <10 seconds:** "What's wasting money this week?"
2. **Every waste signal shows evidence:** Users trust the system
3. **Campaign view shows aggregated ROI:** Decisions at campaign level
4. **1000+ creatives load smoothly:** Enterprise ready
5. **Documentation matches reality:** No more version confusion

---

## Technical Implementation Notes

### Database Changes

```sql
-- New table for waste signals with evidence
CREATE TABLE waste_signals (
    id INTEGER PRIMARY KEY,
    creative_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',
    evidence JSON NOT NULL,
    recommendation TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (creative_id) REFERENCES creatives(creative_id)
);

CREATE INDEX idx_waste_signals_creative ON waste_signals(creative_id);
CREATE INDEX idx_waste_signals_type ON waste_signals(signal_type);

-- Add indexes for timeframe queries
CREATE INDEX idx_perf_date_creative ON performance_data(metric_date, creative_id);
CREATE INDEX idx_perf_date_billing ON performance_data(metric_date, billing_id);
```

### API Contract Changes

All list endpoints gain:
- `?days=N` - timeframe filter (default 7)
- `?cursor=X` - pagination cursor
- `?limit=N` - page size (default 50, max 200)

Response envelope:
```json
{
  "data": [...],
  "meta": {
    "timeframe_days": 7,
    "total": 1250,
    "returned": 50,
    "next_cursor": "abc123",
    "has_more": true
  }
}
```

---

## Recommended First Commit

Start with 11.1.1 (timeframe parameter on /campaigns):

1. Add `days` query param to campaigns router
2. Update SQL to filter by `metric_date >= date('now', '-{days} days')`
3. Return aggregated spend/imps/clicks with campaign
4. Write test coverage

This single change unlocks decision-making for users immediately.

---

**Author:** Claude (World-Class Software Dev Mode)
**Date:** December 2, 2025
**Philosophy:** Intelligence without assumptions. Facts that drive action.
