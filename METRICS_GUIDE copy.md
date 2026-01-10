# Cat-Scan Metrics Guide

**Version:** 1.0 | **Last Updated:** January 2026

A data science perspective on Cat-Scan's metrics, analyses, and optimization opportunities.

---

## Overview

Cat-Scan collects data from two sources:
1. **Google Authorized Buyers API** - Creative metadata, pretargeting configs
2. **CSV Reports** - Performance metrics, RTB funnel data

This guide explains how to interpret and use this data for QPS optimization.

---

## The RTB Optimization Problem

### What You're Optimizing

**Goal:** Maximize value extracted from limited QPS (Queries Per Second).

**The Constraint:** Google sends N bid requests/second. You pay for processing capacity. Not all requests lead to wins. Inefficiency = requests that never become revenue.

### Optimization Levers

| Lever | Cat-Scan Control? | Data Available? |
|-------|-------------------|-----------------|
| Pretargeting config | Yes (via API) | Yes |
| Bid/no-bid decision | No (bidder decides) | Partial |
| Bid price | No (bidder decides) | No |

**Key Insight:** Cat-Scan optimizes pretargeting (what traffic to request), not bidding (how to bid on it).

---

## Data Sources

### 1. Google RTB API Data

| Data Type | Refresh | Use |
|-----------|---------|-----|
| Creatives | On-demand sync | Know your inventory |
| Pretargeting Configs | On-demand sync | Understand current targeting |
| RTB Endpoints | On-demand sync | QPS allocation |
| Buyer Seats | On-demand sync | Account hierarchy |

### 2. CSV Report Data

| Report | Table | Key Metrics |
|--------|-------|-------------|
| Performance Detail | `rtb_daily` | Creative-level: Reached, Impressions, Clicks, Spend |
| RTB Funnel (Regional) | `rtb_funnel` | Bid pipeline: Requests → Bids → Wins |
| RTB Funnel (Publisher) | `rtb_funnel` | Same + Publisher dimension |
| Bid Filtering | `rtb_bid_filtering` | Why bids were filtered |
| Quality Signals | `rtb_quality` | IVT rate, Viewability |

---

## Key Metrics

### Funnel Metrics

```
Bid Requests          (from Google to your bidder)
      │
      ▼
Inventory Matches     (matches pretargeting rules)
      │
      ▼
Reached Queries       (reached your bidder)
      │
      ▼
Bids                  (your bidder decided to bid)
      │
      ▼
Bids in Auction       (entered the auction)
      │
      ▼
Auctions Won          (you won)
      │
      ▼
Impressions           (ad served)
```

### Efficiency Rates

| Metric | Formula | Target | Meaning |
|--------|---------|--------|---------|
| **Pretargeting Filter Rate** | `1 - (Inventory Matches / Bid Requests)` | Minimize | Traffic filtered by pretargeting |
| **Reach Rate** | `Reached Queries / Bid Requests` | Maximize | Traffic that reaches your bidder |
| **Bid Rate** | `Bids / Reached Queries` | Maximize | % of requests your bidder bids on |
| **Auction Participation** | `Bids in Auction / Bids` | Maximize | Bids that enter auction |
| **Win Rate** | `Auctions Won / Bids in Auction` | Optimize | % of auctions won |
| **Efficiency Rate** | `Impressions / Reached Queries` | Maximize | Overall funnel efficiency |

### Cost Metrics

| Metric | Formula | Use |
|--------|---------|-----|
| **CPM** | `(Spend / Impressions) × 1000` | Cost per 1000 impressions |
| **CPC** | `Spend / Clicks` | Cost per click |
| **CTR** | `(Clicks / Impressions) × 100` | Click-through rate |
| **Revenue per QPS** | `Spend / Bid Requests` | Revenue efficiency |
| **QPS Efficiency** | `Impressions / Bid Requests` | Impression yield |

---

## Analysis Types

### 1. Size Coverage Analysis

**Question:** Are we missing inventory due to creative gaps?

**Endpoint:** `/analytics/size-coverage`

**Key Metrics:**
- `sizes_with_creatives` - Sizes where you have active creatives
- `sizes_without_creatives` - Sizes in traffic but no creatives
- `wasted_qps` - Estimated QPS wasted on missing sizes

**Action:** Create creatives for high-traffic missing sizes.

### 2. Regional Efficiency Analysis

**Question:** Which regions are performing poorly?

**Endpoint:** `/analytics/regional-efficiency` (via rtb_funnel)

**Key Metrics:**
- Win rate by region
- Spend per impression by region
- CTR by region

**Action:** Exclude underperforming regions from pretargeting.

### 3. Publisher Efficiency Analysis

**Question:** Which publishers should we block?

**Endpoint:** `/analytics/rtb-funnel/publishers`

**Key Metrics:**
- Publisher win rate
- Publisher IVT rate (from quality signals)
- Publisher viewability

**Action:** Add low-quality publishers to exclusion list.

### 4. Config Performance Comparison

**Question:** Which pretargeting config performs best?

**Endpoint:** `/analytics/rtb-funnel/configs`

**Key Metrics:**
- Win rate per config
- Waste rate per config (`1 - Win Rate`)
- Impressions per config

**Action:** Reallocate QPS from underperforming configs.

### 5. Traffic Quality Analysis

**Question:** How much of my traffic is invalid?

**Tables:** `rtb_quality`, `rtb_bid_filtering`

**Key Metrics:**
- Invalid Traffic (IVT) rate
- Viewability rate
- Bid filtering reasons

**Action:** Exclude high-IVT publishers, adjust bid filters.

---

## Waste Detection

### Types of Waste

| Waste Type | Detection | Impact | Solution |
|------------|-----------|--------|----------|
| **Size Gap** | High traffic for uncovered sizes | Lost impressions | Add creatives |
| **Low Win Rate** | Win rate < threshold | Wasted bid processing | Adjust bid strategy |
| **High IVT** | IVT rate > 5% | Paying for fraud | Block publishers |
| **Low Viewability** | Viewability < 50% | Wasted impressions | Block placements |
| **Regional Waste** | Region CTR < average | Poor targeting | Exclude regions |

### Waste Signals Table

Cat-Scan stores detected waste in `inefficiency_signals`:

```sql
SELECT signal_type, segment_type, segment_value, waste_pct, wasted_qps
FROM inefficiency_signals
WHERE detected_at > date('now', '-7 days')
ORDER BY wasted_qps DESC
```

---

## Recommendation Engine

### How Recommendations Are Generated

1. **Data Collection** - Import CSV reports
2. **Analysis** - Run efficiency calculations
3. **Threshold Check** - Compare to benchmarks
4. **Impact Estimation** - Calculate potential savings
5. **Action Generation** - Suggest specific changes

### Recommendation Types

| Type | Trigger | Typical Action |
|------|---------|----------------|
| `size_gap` | Missing creatives for high-traffic size | Add creative |
| `publisher_block` | Low win rate or high IVT | Add to blocklist |
| `regional_exclusion` | Poor regional performance | Exclude from pretargeting |
| `creative_pause` | Zero impressions with reached > 0 | Investigate creative |
| `config_underperforming` | Config win rate < average | Reallocate QPS |

### Confidence Scoring

Recommendations include confidence based on:
- Sample size (more data = higher confidence)
- Statistical significance
- Historical accuracy

---

## Google's Field Incompatibility

### The Constraint

Google's CSV exports have mutually exclusive fields:

```
ERROR: "Mobile app ID is not compatible with [Bid requests],
        [Inventory matches] and 4 more field(s)."
```

**What this means:**

| If you want... | You CANNOT get... |
|----------------|-------------------|
| Creative ID, Creative size, Mobile app ID | Bid requests, Inventory matches |
| Bid requests → Auctions won funnel | Creative-level breakdown |

### Cat-Scan's Solution

JOIN reports on common dimensions:

```
Performance Detail (creative-level)     RTB Funnel (regional)
─────────────────────────────────       ───────────────────────────
day, region, publisher_id               day, region, publisher_id
creative_id, creative_size              bid_requests, bids, auctions_won
impressions, spend                      inventory_matches
        │                                       │
        └───────────JOIN ON─────────────────────┘
              (day, region, publisher_id)
                         │
                         ▼
            APPROXIMATE Creative Funnel
```

**Accuracy:** Good for aggregate analysis, approximate at creative level.

---

## SQL Query Examples

### Top Wasted Sizes

```sql
SELECT
    creative_size,
    SUM(reached_queries) as total_reached,
    SUM(impressions) as total_impressions,
    ROUND(1.0 - (SUM(impressions) * 1.0 / SUM(reached_queries)), 3) as waste_rate
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
GROUP BY creative_size
ORDER BY waste_rate DESC
LIMIT 10;
```

### Regional Performance

```sql
SELECT
    region,
    SUM(bids) as total_bids,
    SUM(auctions_won) as total_wins,
    ROUND(SUM(auctions_won) * 100.0 / NULLIF(SUM(bids_in_auction), 0), 2) as win_rate_pct
FROM rtb_funnel
WHERE metric_date >= date('now', '-7 days')
GROUP BY region
ORDER BY win_rate_pct ASC
LIMIT 10;
```

### Publisher Quality

```sql
SELECT
    p.publisher_name,
    SUM(f.impressions) as impressions,
    AVG(q.non_human_traffic_pct) as avg_ivt_pct,
    AVG(q.viewable_impressions_pct) as avg_viewability
FROM rtb_funnel f
LEFT JOIN rtb_quality q ON f.publisher_id = q.publisher_id AND f.metric_date = q.metric_date
LEFT JOIN publishers p ON f.publisher_id = p.publisher_id
WHERE f.metric_date >= date('now', '-7 days')
GROUP BY f.publisher_id
HAVING avg_ivt_pct > 5
ORDER BY impressions DESC;
```

---

## API Endpoints Reference

### Analytics Endpoints

| Endpoint | Returns |
|----------|---------|
| `/analytics/size-coverage` | Size gap analysis |
| `/analytics/waste` | Waste report |
| `/analytics/qps-summary` | Overall efficiency summary |
| `/analytics/rtb-funnel` | Full funnel metrics |
| `/analytics/rtb-funnel/publishers` | Publisher breakdown |
| `/analytics/rtb-funnel/configs` | Config performance |

### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 7 | Analysis period |
| `billing_id` | all | Filter to specific config |
| `limit` | varies | Result limit |

---

## Benchmarks & Thresholds

### Industry Benchmarks (approximate)

| Metric | Good | Average | Poor |
|--------|------|---------|------|
| Win Rate | > 20% | 10-20% | < 10% |
| CTR | > 0.5% | 0.1-0.5% | < 0.1% |
| Viewability | > 70% | 50-70% | < 50% |
| IVT Rate | < 2% | 2-5% | > 5% |

### Cat-Scan Default Thresholds

Configurable in recommendation engine:

```python
THRESHOLDS = {
    "min_win_rate": 0.05,          # 5% minimum
    "max_ivt_rate": 0.05,          # 5% maximum
    "min_viewability": 0.50,       # 50% minimum
    "min_sample_size": 1000,       # queries for confidence
}
```

---

## Best Practices

### Data Quality

1. **Import regularly** - Daily CSV imports for fresh data
2. **Full period coverage** - Ensure no gaps in date range
3. **Multiple report types** - Import all 5 report types for complete picture

### Analysis

1. **Use sufficient timeframes** - 7 days minimum for stable metrics
2. **Consider seasonality** - Compare same periods across weeks
3. **Statistical significance** - Don't act on small sample sizes

### Optimization

1. **Start with high-impact** - Address critical recommendations first
2. **Test incrementally** - Make one change at a time
3. **Monitor outcomes** - Use snapshots to track before/after
4. **Rollback if needed** - Use pretargeting snapshots for quick rollback

---

## Glossary

| Term | Definition |
|------|------------|
| **QPS** | Queries Per Second - bid requests from Google |
| **Pretargeting** | Rules that filter which traffic you receive |
| **RTB** | Real-Time Bidding |
| **IVT** | Invalid Traffic (bot/fraud) |
| **Funnel** | Conversion path from request to impression |
| **Win Rate** | % of auctions won |
| **Waste** | Traffic that doesn't convert to value |

---

*This guide is based on Cat-Scan v24.0 and Google Authorized Buyers reporting as of January 2026.*
