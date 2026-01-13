# Cat-Scan Data Science Evaluation

**Created:** January 4, 2026
**Purpose:** Evaluate data model sufficiency for effective QPS optimization

---

## Executive Summary

**Question:** Is the current data collection sufficient to make intelligent pretargeting decisions?

**Answer:** **Yes, for binary optimization decisions. No, for bid price optimization.**

The data model is well-designed for **pretargeting optimization** (what to include/exclude). It correctly handles Google's field incompatibility constraints and joins multiple reports to reconstruct the full funnel.

However, the app **cannot** optimize **bid prices** because Google's CSV exports don't include bid amounts—only bid counts. This is a fundamental platform limitation, not an app deficiency.

---

## Part 1: The RTB Optimization Problem

### What You're Trying to Optimize

**Goal:** Maximize value extracted from limited QPS (Queries Per Second).

**The Constraint:** Google sends you N bid requests/second. You pay for processing capacity. Not all requests lead to wins. Inefficiency = requests that never become revenue.

**Optimization Levers:**
1. **Pretargeting** - Tell Google which traffic to send (geos, sizes, formats, platforms)
2. **Bid decisions** - Decide which requests to actually bid on
3. **Bid prices** - How much to bid (if you have a custom bidder)

### What Cat-Scan Controls

| Lever | Cat-Scan Control? | Data Available? |
|-------|-------------------|-----------------|
| Pretargeting config | ✅ Yes (via API) | ✅ Yes |
| Bid/no-bid decision | ❌ No (bidder decides) | ✅ Partial |
| Bid price | ❌ No (bidder decides) | ❌ No |

**Implication:** Cat-Scan is a **pretargeting optimizer**, not a bidder optimizer. It decides what traffic to request, not how to bid on it.

---

## Part 2: Data Sources Analysis

### Available Data Sources

#### A. Google RTB API (Real-time)

| Data Type | Endpoint | Use in Optimization |
|-----------|----------|---------------------|
| Creatives | `buyers.creatives.list` | Know what sizes/formats you have |
| Pretargeting Configs | `bidders.pretargetingConfigs` | Read/write targeting rules |
| Buyer Seats | `bidders` | Account hierarchy |
| RTB Endpoints | `bidders.endpoints` | QPS limits, trading locations |

**Verdict:** ✅ Complete - All necessary API data is collected.

#### B. CSV Reports (Daily Batch)

| Report | Table | Key Metrics | Critical for Optimization? |
|--------|-------|-------------|---------------------------|
| Performance Detail | `rtb_daily` | Reached, Impressions, Clicks, Spend | ✅ Yes - revenue attribution |
| RTB Funnel (Geo) | `rtb_bidstream` | Full bid pipeline by country | ✅ Yes - funnel analysis |
| RTB Funnel (Publisher) | `rtb_bidstream` | Full bid pipeline by publisher | ✅ Yes - publisher quality review |
| Bid Filtering | `rtb_bid_filtering` | Why bids filtered | ⚠️ Optional - policy debugging |
| Quality Signals | `rtb_quality` | Non-human traffic rate, viewability | ⚠️ Optional - traffic quality review |

**Verdict:** ✅ Complete - All 5 report types are supported.

---

## Part 3: The Critical Constraint

### Google's Field Incompatibility

When creating reports in Google Authorized Buyers, certain dimensions are **mutually exclusive**:

```
ERROR: "Mobile app ID is not compatible with [Bid requests],
        [Inventory matches] and 4 more field(s)."
```

**What this means:**

| If you want... | You CANNOT get... |
|----------------|-------------------|
| Creative ID, Creative size, Mobile app ID | Bid requests, Inventory matches, Bids, Bids in auction |
| Bid requests → Auctions won funnel | Creative-level breakdown |

### Why This Matters

You can NEVER directly answer:
- "How many bid requests were for 300x250?"
- "What's the complete funnel for creative #123?"
- "Which creative sizes have the highest bid-to-win conversion?"

### How Cat-Scan Works Around This

**Solution:** JOIN reports on common dimensions.

```
Performance Detail (creative-level)     RTB Funnel (geo/publisher)
─────────────────────────────────       ───────────────────────────
day, country, publisher_id              day, country, publisher_id
creative_id, creative_size              bid_requests, bids, auctions_won
impressions, spend                      inventory_matches
        │                                       │
        └───────────JOIN ON─────────────────────┘
              (day, country, publisher_id)
                         │
                         ▼
            APPROXIMATE Creative Funnel
            (assumes uniform distribution within segment)
```

**Accuracy:** Good for aggregate analysis, loses precision at creative level.

**Verdict:** ✅ Correctly implemented - The app handles this constraint appropriately.

---

## Part 4: Metric-to-Decision Mapping

### What Optimization Decisions Need What Data

| Decision | Required Metrics | Available? | Source |
|----------|------------------|------------|--------|
| Exclude publisher X | Publisher win rate, traffic quality, viewability | ✅ Yes | rtb_bidstream + rtb_quality |
| Exclude geo X | Geo win rate, spend efficiency | ✅ Yes | rtb_bidstream + rtb_daily |
| Add creative size X | Size request volume, coverage gap | ✅ Yes | rtb_daily |
| Remove size X | Size inefficiency rate | ✅ Yes | rtb_daily |
| Pause creative X | Creative impressions = 0 with reached > 0 | ✅ Yes | rtb_daily |
| Hour dayparting | Hourly bid/win patterns | ✅ Yes | rtb_bidstream (with Hour) |
| Platform optimization | Platform win rate | ⚠️ Partial | Needs Platform dimension |
| App vs Web strategy | Environment split | ⚠️ Partial | Needs Environment dimension |
| Bid price optimization | Bid price vs win rate | ❌ No | Not in exports |
| Publisher price elasticity | Price response curves | ❌ No | Not in exports |

### Current Coverage

```
PRETARGETING DECISIONS (Binary: Include/Exclude)
════════════════════════════════════════════════
✅ Publisher quality filtering  → Full data available
✅ Geo exclusion               → Full data available
✅ Size management             → Full data available
✅ Creative pausing            → Full data available
✅ Traffic quality review      → Full data available
✅ Viewability filtering       → Full data available
⚠️ Platform targeting         → Partial (add dimension)
⚠️ Environment (App/Web)      → Partial (add dimension)

BIDDING DECISIONS (Continuous: How much to bid)
════════════════════════════════════════════════
❌ CPM optimization           → No bid price data
❌ Price elasticity           → No bid price data
❌ Bid shading               → No bid price data
```

---

## Part 5: Identified Gaps

### Gap 1: Platform Dimension Not Captured

**Impact:** Cannot optimize Desktop vs Mobile vs Tablet targeting.

**Solution:** Add "Platform" dimension to Performance Detail and RTB Funnel reports.

**Fields to add:**
- `Platform` (Desktop, Mobile, Tablet)

**Effort:** Low - Just modify the scheduled reports in Google AB.

### Gap 2: Environment Dimension Not Captured

**Impact:** Cannot distinguish App traffic from Web traffic for targeting.

**Solution:** Add "Environment" dimension to reports.

**Fields to add:**
- `Environment` (App, Web)

**Effort:** Low - Just modify the scheduled reports.

### Gap 3: Transaction Type Not Captured

**Impact:** Cannot analyze Open Exchange vs Private Marketplace performance separately.

**Solution:** Add "Transaction type" dimension to Funnel reports.

**Effort:** Low - Just modify the scheduled reports.

### Gap 4: No Bid Price Data (FUNDAMENTAL)

**Impact:** Cannot optimize bid amounts.

**Root Cause:** Google's CSV exports do not include bid prices, only bid counts.

**Solution:** None within Cat-Scan. This would require:
- Access to the actual bidder's logs
- Integration with bidder's price optimization system

**Verdict:** Accept this limitation. Cat-Scan optimizes pretargeting, not bidding.

### Gap 5: No Creative-Level Funnel (FUNDAMENTAL)

**Impact:** Cannot get bid_requests for a specific creative_id.

**Root Cause:** Google's field incompatibility constraint.

**Solution:** Continue using the JOIN approximation:
- Join on (date, country, publisher_id)
- Accept that creative-level funnel is estimated, not exact

**Verdict:** Already handled correctly by the app.

---

## Part 6: Current Analysis Engines Evaluation

### Engines Implemented

| Engine | Purpose | Data Used | Quality |
|--------|---------|-----------|---------|
| `QPSOptimizer` | Full optimization report | rtb_bidstream + rtb_daily + rtb_quality | ✅ Excellent |
| `WasteAnalyzer` | Size coverage gaps | creatives + traffic | ✅ Excellent |
| `RecommendationEngine` | Generate actionable recs | All sources | ✅ Excellent |
| `PretargetingRecommender` | Optimal config generation | creatives + performance | ✅ Good |
| `TrafficQualityAnalyzer` | Non-human traffic identification | rtb_quality | ✅ Good |

### QPSOptimizer Methods

| Method | What It Does | Business Value |
|--------|--------------|----------------|
| `get_publisher_inefficiency_ranking` | Ranks publishers by inefficiency % | Identify low-performing publishers |
| `get_platform_efficiency` | Compares Desktop/Mobile/Tablet | Platform targeting |
| `get_hourly_patterns` | 24-hour bid/win analysis | Dayparting decisions |
| `get_size_coverage_gaps` | Finds unserved size demand | Creative production priorities |
| `get_pretargeting_efficiency` | Inventory match rates by geo | Pretargeting tuning |
| `get_bid_filtering_analysis` | Filtering reasons breakdown | Policy compliance |
| `get_traffic_quality_publishers` | High non-human-traffic publishers | Traffic quality review |
| `get_viewability_inefficiency` | Low-viewability publishers | Quality filtering |
| `get_full_optimization_report` | Everything combined | Complete assessment |

**Verdict:** ✅ Analysis engines are comprehensive and well-designed.

---

## Part 7: Recommendations

### Immediate Actions (Low Effort, High Value)

1. **Add Platform dimension** to all CSV reports
   - Modify scheduled reports in Google AB
   - Enables device-type optimization
   - ~30 min effort

2. **Add Environment dimension** to Performance Detail report
   - Enables App vs Web strategy
   - ~30 min effort

3. **Add Transaction Type** to Funnel reports
   - Enables Open vs Private analysis
   - ~30 min effort

### Medium-Term Improvements

4. **Hourly report granularity**
   - Ensure Hour dimension is included in Funnel reports
   - Enables dayparting recommendations

5. **Historical trend analysis**
   - Add week-over-week change metrics to recommendations
   - Identify performance changes

### Long-Term (If Building Custom Bidder)

6. **Bid price logging**
   - If you have access to bidder logs, ingest bid prices
   - Enable CPM optimization
   - Requires custom development

---

## Part 8: Data Collection Efficiency

### Current State

| Metric | Value | Assessment |
|--------|-------|------------|
| CSV report types | 5 | ✅ Optimal |
| Required reports | 3 | ✅ Correctly prioritized |
| Optional reports | 2 | ✅ Good for advanced analysis |
| Data freshness | T+1 (daily) | Acceptable for pretargeting |
| Storage efficiency | 90-day retention + S3 archive | ✅ Appropriate |

### Are You Collecting the Right Data?

**Yes.** The 5 report types capture the maximum available information from Google Authorized Buyers given the field incompatibility constraints.

The only additions recommended are extra dimensions (Platform, Environment, Transaction Type) within existing reports—not new report types.

---

## Part 9: Automated Configuration Feasibility

### The Chicken-and-Egg Problem

**Critical insight:** CSV data cannot identify excluded opportunities.

If a creative size (e.g., 320x50) is excluded in pretargeting, then:
- Google sends **zero** bid requests for that size
- CSV reports show **zero** traffic
- Analysis engines see **no signal to optimize**

**This means:** You cannot use CSV data alone to identify new creative opportunities.

### Two Types of Automated Updates

| Type | Trigger | Data Source | Purpose |
|------|---------|-------------|---------|
| **Proactive** | New creative approved | API (creatives) | Enable traffic for new sizes |
| **Reactive** | Performance issues | CSV (daily reports) | Exclude low-performing publishers/geos |

### Proactive Updates (API-Driven)

**Solution:** Use the creative data from the API directly.

When you sync creatives via `buyers.creatives.list`, each creative record contains:
- `creative_id`
- `creative_size` (e.g., "300x250")
- `creative_format` (DISPLAY, VIDEO, NATIVE)
- `status` (APPROVED, PENDING_REVIEW, DISAPPROVED)

**The simple flow:**
```
Creative approved (API sync)
        │
        ▼
Read size/format from creative data
        │
        ▼
Check pretargeting config
        │
        ▼
Size missing? ──► Add via add_sizes_to_config()
        │
        ▼
Traffic now flows for that size
```

**Existing code support:** `collectors/pretargeting/client.py:264` - `add_sizes_to_config()`

No CSV analysis needed. No complex identification logic. Just use the API data.

### Reactive Updates (CSV-Driven)

For ongoing performance optimization, CSV data is appropriate:

1. ✅ Identify high-inefficiency publishers → Add to exclusion list
2. ✅ Identify high non-human-traffic publishers → Exclude for quality
3. ✅ Identify underperforming geos → Exclude
4. ✅ Identify problematic creatives → Pause

```
┌─────────────────────────────────────────────────────────────────┐
│                  REACTIVE OPTIMIZATION LOOP                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DAILY CSV IMPORT                                            │
│     Performance + Funnel + Quality reports                      │
│                    │                                            │
│                    ▼                                            │
│  2. ANALYSIS ENGINES                                            │
│     QPSOptimizer, WasteAnalyzer, TrafficQualityAnalyzer         │
│                    │                                            │
│                    ▼                                            │
│  3. RECOMMENDATION ENGINE                                       │
│     Generate recommendations with confidence scores             │
│                    │                                            │
│                    ▼                                            │
│  4. APPLY CHANGES (if confidence > threshold)                   │
│     patch_pretargeting() to exclude low-performers              │
│                    │                                            │
│                    ▼                                            │
│  5. MONITOR OUTCOMES                                            │
│     Compare before/after, adjust thresholds                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### What's Missing for Automated Updates

**Proactive (API-driven):**

| Component | Status | Needed |
|-----------|--------|--------|
| Creative data sync | ✅ Complete | `collectors/creatives/client.py` |
| Pretargeting API client | ✅ Complete | `collectors/pretargeting/client.py` |
| Add sizes helper | ✅ Complete | `add_sizes_to_config()` |
| **On-approval workflow** | ❌ Missing | Watch for status change to APPROVED |
| **Automated config update** | ❌ Missing | Call `add_sizes_to_config()` automatically |

**Reactive (CSV-driven):**

| Component | Status | Needed |
|-----------|--------|--------|
| Identification logic | ✅ Complete | QPSOptimizer, WasteAnalyzer |
| Recommendation engine | ✅ Complete | RecommendationEngine |
| Confidence scoring | ⚠️ Partial | Add statistical confidence intervals |
| Update logic | ❌ Missing | Build the optimization loop |
| Outcome tracking | ⚠️ Partial | Add before/after comparison |

---

## Part 10: Final Assessment

### Data Model Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| API Data Collection | 10/10 | All relevant endpoints covered |
| CSV Report Coverage | 9/10 | Add Platform/Environment dimensions |
| Field Mapping | 10/10 | Correctly handles all column variants |
| JOIN Logic | 9/10 | Works around Google's constraints well |
| Analysis Depth | 9/10 | Comprehensive recommendation types |
| Storage Efficiency | 10/10 | 90-day + S3 archive is appropriate |

**Overall: 9.5/10** - Excellent data model for pretargeting optimization.

### Conclusion

The Cat-Scan data model is **well-designed and sufficient** for its purpose: optimizing pretargeting configurations to maximize QPS efficiency.

**Strengths:**
- Correctly handles Google's field incompatibility constraint
- All 5 report types provide comprehensive funnel coverage
- JOIN logic enables approximate creative-level analysis
- Analysis engines generate actionable recommendations

**Limitations (Platform-level, not app-level):**
- Cannot optimize bid prices (no price data in exports)
- Cannot get exact creative-level funnel (Google constraint)

**Next Steps:**
1. Build proactive optimization: enable `add_sizes_to_config()` when creatives are approved (high priority)
2. Add Platform/Environment/Transaction Type dimensions to CSV reports (low effort)
3. Build reactive optimization loop for publisher/geo exclusions (medium effort)
4. Add outcome tracking and learning (medium effort)

---

*This evaluation was conducted on January 4-5, 2026 based on comprehensive codebase analysis.*
