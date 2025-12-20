# Prompt: Enhance Cat-Scan for Full QPS Optimization

**Created:** December 17, 2025
**Purpose:** Instructions for Claude Code to implement enhanced QPS optimization schema, importers, and analytics

---

## Context

Cat-Scan is a QPS optimization platform for Google Authorized Buyers RTB bidders. It imports CSV reports from Google AB and analyzes waste/efficiency.

**Current state:**
- `rtb_daily` table stores Performance Detail CSVs (creative_id, size, app_id, impressions, spend)
- `rtb_funnel` table stores RTB Funnel CSVs (bid_requests, bids, auctions_won by country/publisher)
- These tables have overlapping dimensions (date, country, publisher_id) but are NOT currently joined
- The smart importer (`qps/smart_importer.py`) auto-detects CSV type and routes to correct table

**Problem:**
The current schema is insufficient for AI-driven QPS optimization because:
1. No hourly granularity in performance data (can't correlate hourly funnel patterns with wins)
2. Missing `inventory_matches` (can't measure pretargeting efficiency)
3. No `platform` or `environment` dimensions (can't optimize by device/app-vs-web)
4. No bid filtering analysis (can't understand WHY bids fail)
5. No fraud/viewability signals (can't identify wasteful publishers)
6. No actual JOIN queries exist - data sits in separate tables unused

---

## Task 1: Create Migration for Enhanced Schema

**File:** `migrations/009_enhanced_qps_optimization.sql`

**Add to existing tables:**
```sql
-- rtb_daily enhancements
ALTER TABLE rtb_daily ADD COLUMN hour INTEGER;
ALTER TABLE rtb_daily ADD COLUMN platform TEXT;  -- 'Desktop', 'Mobile', 'Tablet'
ALTER TABLE rtb_daily ADD COLUMN environment TEXT;  -- 'App', 'Web'
ALTER TABLE rtb_daily ADD COLUMN publisher_domain TEXT;
ALTER TABLE rtb_daily ADD COLUMN viewable_impressions INTEGER DEFAULT 0;
ALTER TABLE rtb_daily ADD COLUMN measurable_impressions INTEGER DEFAULT 0;

-- rtb_funnel enhancements
ALTER TABLE rtb_funnel ADD COLUMN platform TEXT;
ALTER TABLE rtb_funnel ADD COLUMN environment TEXT;
ALTER TABLE rtb_funnel ADD COLUMN transaction_type TEXT;  -- 'Open auction', 'Private auction', etc.
ALTER TABLE rtb_funnel ADD COLUMN inventory_matches INTEGER DEFAULT 0;
```

**Create new tables:**

1. `rtb_bid_filtering` - stores bid filtering reasons (why bids fail)
   - metric_date, country, buyer_account_id, filtering_reason, creative_id (nullable)
   - Metrics: bids, bids_in_auction, opportunity_cost_micros

2. `rtb_quality` - stores fraud/viewability signals per publisher
   - metric_date, publisher_id, publisher_name, country
   - Metrics: impressions, pre_filtered_impressions, ivt_credited_impressions, billed_impressions, measurable_impressions, viewable_impressions

**Add indexes** for the new columns to support AI queries (platform, environment, hour, filtering_reason).

**Why:** These fields come from Google AB reports but we're not capturing them. Without them, AI cannot answer: "Which platform wastes QPS?", "Why are bids being filtered?", "Which publishers have fraud?"

---

## Task 2: Update Smart Importer for New Fields

**Files to modify:**
- `qps/csv_report_types.py` - add new column mappings
- `qps/importer.py` - handle new rtb_daily columns
- `qps/funnel_importer.py` - handle new rtb_funnel columns
- `qps/smart_importer.py` - add detection for new report types

**New column mappings to add:**

For Performance Detail (rtb_daily):
```python
"hour": ["Hour", "#Hour"],
"platform": ["Platform", "#Platform"],
"environment": ["Environment", "#Environment"],
"publisher_domain": ["Publisher domain", "#Publisher domain"],
"viewable_impressions": ["Active View viewable", "Active view viewable"],
"measurable_impressions": ["Active View measurable", "Active view measurable"],
```

For RTB Funnel (rtb_funnel):
```python
"platform": ["Platform", "#Platform"],
"environment": ["Environment", "#Environment"],
"transaction_type": ["Transaction type", "#Transaction type"],
"inventory_matches": ["Inventory matches", "#Inventory matches"],
```

**Add two new report types:**

1. `ReportType.BID_FILTERING` - detected by presence of "Bid filtering reason" column
   - Create `qps/bid_filtering_importer.py`
   - Imports to `rtb_bid_filtering` table

2. `ReportType.QUALITY_SIGNALS` - detected by presence of "IVT credited impressions" or "Pre-filtered impressions"
   - Create `qps/quality_importer.py`
   - Imports to `rtb_quality` table

**Why:** Users will add these new dimensions/metrics to their Google AB reports. The importer must recognize and store them. Optional columns should be handled gracefully (NULL if not present in CSV).

---

## Task 3: Build JOIN Queries and Analytics Views

**File:** `analytics/qps_optimizer.py` (NEW)

Create a `QPSOptimizer` class with methods that JOIN rtb_funnel + rtb_daily + rtb_quality to answer optimization questions:

**Required methods:**

### 1. `get_publisher_waste_ranking(days=7, limit=50)`
JOIN funnel + daily on date/country/publisher

```sql
SELECT
    f.publisher_id, f.publisher_name,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.auctions_won) as auctions_won,
    SUM(p.impressions) as impressions,
    SUM(p.spend_micros) as spend,
    100.0 * (SUM(f.bid_requests) - SUM(f.auctions_won)) / NULLIF(SUM(f.bid_requests), 0) as waste_pct
FROM rtb_funnel f
LEFT JOIN rtb_daily p ON f.metric_date = p.metric_date
    AND f.country = p.country
    AND f.publisher_id = p.publisher_id
GROUP BY f.publisher_id
ORDER BY waste_pct DESC
```

**Returns:** Publishers ranked by QPS waste. AI uses this to recommend pretargeting blocks.

### 2. `get_platform_efficiency(days=7)`
Efficiency by device type.

**Returns:** Win rate and spend by platform (Desktop/Mobile/Tablet). AI uses this to recommend platform bid adjustments.

### 3. `get_hourly_patterns(days=7)`
JOIN on date + hour + country.

**Returns:** Bid requests, win rate, efficiency by hour of day. AI uses this to recommend hourly QPS throttling.

### 4. `get_size_coverage_gaps(days=7)`
Sizes with high demand but low wins.

**Returns:** Creative sizes where reached_queries >> impressions. AI uses this to recommend new creative sizes.

### 5. `get_pretargeting_efficiency(days=7)`
inventory_matches vs bid_requests.

**Returns:** Countries/publishers where pretargeting filters too much (or too little). AI uses this to tune pretargeting configs.

### 6. `get_bid_filtering_analysis(days=7)`
From rtb_bid_filtering table.

**Returns:** Reasons why bids are filtered, ranked by volume and opportunity cost. AI uses this to fix creative policies or publisher issues.

### 7. `get_fraud_risk_publishers(days=7, threshold_pct=5)`
From rtb_quality table.

**Returns:** Publishers with IVT rate > threshold. AI uses this to recommend blocking fraudulent publishers.

### 8. `get_viewability_waste(days=7, threshold_pct=50)`
From rtb_quality + rtb_daily.

**Returns:** Publishers with low viewability but high spend. AI uses this to recommend reducing bids on low-viewability inventory.

### 9. `get_full_optimization_report(days=7)`
Calls all above methods.

**Returns:** Complete optimization summary for AI to analyze. Structure:
```python
{
    "summary": {
        "total_bid_requests": int,
        "total_auctions_won": int,
        "overall_efficiency": float,
        "estimated_waste_usd": float
    },
    "recommendations": [
        {"type": "block_publisher", "publisher_id": "...", "reason": "...", "impact_pct": float},
        {"type": "add_creative_size", "size": "300x250", "opportunity_queries": int},
        ...
    ],
    "publisher_waste": [...],
    "platform_efficiency": {...},
    "hourly_patterns": [...],
    "bid_filtering": [...],
    "fraud_risk": [...],
    "viewability_issues": [...]
}
```

---

## API Endpoints

**File:** `api/routers/analytics.py` - add endpoints

Add API endpoints that expose the optimizer:
- `GET /analytics/qps-optimization` - returns full optimization report
- `GET /analytics/publisher-waste` - returns publisher waste ranking
- `GET /analytics/bid-filtering` - returns bid filtering analysis

**Why:** The whole point of collecting this data is to JOIN it and extract insights. Without these queries, the data sits unused. The `get_full_optimization_report()` method is specifically designed for an AI agent to consume and generate actionable recommendations.

---

## Testing

After implementation, verify with:

1. Run migration:
   ```bash
   sqlite3 ~/.catscan/catscan.db < migrations/009_enhanced_qps_optimization.sql
   ```

2. Test importer with CSV that has new columns (hour, platform, etc.) - should import without error

3. Test API endpoint:
   ```bash
   curl http://localhost:8000/analytics/qps-optimization
   ```

4. Verify JOIN queries return data when both rtb_funnel and rtb_daily have matching date/country/publisher rows

---

## Files Summary

**New files:**
- `migrations/009_enhanced_qps_optimization.sql`
- `qps/bid_filtering_importer.py`
- `qps/quality_importer.py`
- `analytics/qps_optimizer.py`

**Modified files:**
- `qps/csv_report_types.py`
- `qps/importer.py`
- `qps/funnel_importer.py`
- `qps/smart_importer.py`
- `api/routers/analytics.py`

**Documentation to update:**
- `docs/CSV_REPORTS_GUIDE.md` - add new report types and recommended fields
- `dashboard/src/app/import/page.tsx` - update ExportInstructions component with new fields

---

## Reference: Google AB Fields Analysis

### Critical Missing Fields for QPS Optimization

| Priority | Field | Report | Reason |
|----------|-------|--------|--------|
| **CRITICAL** | Hour | Report 1 | Hourly patterns |
| **CRITICAL** | Inventory matches | Report 2,3 | Pretargeting efficiency |
| **CRITICAL** | Bid filtering reason | NEW Report 4 | Root cause analysis |
| **HIGH** | Platform | Report 1,2,3 | Device optimization |
| **HIGH** | Environment | Report 1,2,3 | App vs Web strategy |
| **HIGH** | Active View viewable | Report 1, NEW Report 5 | Viewability |
| **MEDIUM** | IVT credited | NEW Report 5 | Fraud detection |
| **MEDIUM** | Transaction type | Report 2,3 | Deal vs open auction |
| **LOW** | Publisher domain | Report 1 | Web inventory detail |

### Google AB Field Incompatibilities (Cannot Combine)

- `Bid requests` + `Mobile app ID` = NOT ALLOWED
- `Bid requests` + `Creative ID` = NOT ALLOWED

This is why we need separate reports and JOIN queries to correlate funnel metrics with creative/app performance.
