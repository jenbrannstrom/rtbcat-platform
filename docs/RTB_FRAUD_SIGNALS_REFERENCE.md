# RTB Fraud & Anomaly Signals Reference

**Purpose:** Document real-world patterns that indicate fraud, bot traffic, or data quality issues in RTB (Real-Time Bidding) data. Use this when building detection algorithms, AI clustering prompts, or quality scoring systems.

---

## 🎯 Key Principle: Context Matters

A single anomaly isn't proof of fraud. **Patterns over time** are what matter.

```
Single occurrence:  Could be timing, tracking glitch, edge case
Repeated pattern:   Likely systematic issue (fraud, bots, bad inventory)
```

---

## 📊 Fraud Signal Categories

### 1. Click Fraud Signals

#### Pattern: Clicks > Impressions

| Frequency | Interpretation | Confidence |
|-----------|----------------|------------|
| Once | Timing issue - click registered after daily cutoff | Low |
| Occasionally | Tracking discrepancy between systems | Low |
| Frequently (same app) | Click injection / click fraud | High 🚨 |
| Always (specific app) | Definitely fraudulent app | Very High 🚨 |

**Why it happens legitimately:**
- Impression counted at 11:59 PM, click at 12:01 AM → different days
- Different tracking pixels with different latencies
- Viewability filtering removed impression but click still counted

**Why it indicates fraud:**
- App injects fake clicks without ever showing the ad
- Malware clicking in background
- Click farms

**Detection query:**
```sql
-- Apps with suspicious click/impression ratios
SELECT 
    app_id,
    app_name,
    SUM(clicks) as total_clicks,
    SUM(impressions) as total_impressions,
    COUNT(*) as days_of_data,
    SUM(CASE WHEN clicks > impressions THEN 1 ELSE 0 END) as suspicious_days
FROM performance_metrics
GROUP BY app_id
HAVING suspicious_days > 3  -- More than 3 days of clicks > impressions
ORDER BY suspicious_days DESC;
```

---

#### Pattern: Extremely High CTR (> 5-10%)

| CTR | Interpretation |
|-----|----------------|
| < 1% | Normal for most display/video |
| 1-3% | Good performance |
| 3-5% | Excellent (or suspicious) |
| 5-10% | Very suspicious unless highly targeted |
| > 10% | Almost certainly fraud 🚨 |

**Industry benchmarks:**
- Display ads: 0.1% - 0.5% typical
- Video ads: 0.5% - 2% typical
- Native ads: 0.5% - 1.5% typical
- Retargeting: Can be higher (2-5%)

---

### 2. Bot Traffic Signals

#### Pattern: High Impressions, Zero Clicks (Over Time)

| Timeframe | 0 Clicks | Interpretation |
|-----------|----------|----------------|
| 1 day | Normal | Users might not engage that day |
| 3 days | Watch | Could be bad creative or placement |
| 7+ days | Suspicious | Likely bot traffic 🚨 |
| 30+ days, thousands of imps | Definite bots | 99% bot farm 🚨 |

**Why it indicates bots:**
- Bots "view" ads to generate impression revenue for publishers
- Bots don't click (clicking would be too obvious/traceable)
- Real humans occasionally click, even on bad ads

**Detection query:**
```sql
-- Apps with high impressions but zero engagement over time
SELECT 
    app_id,
    app_name,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    COUNT(DISTINCT metric_date) as days_active,
    MIN(metric_date) as first_seen,
    MAX(metric_date) as last_seen
FROM performance_metrics
WHERE impressions > 0
GROUP BY app_id
HAVING 
    total_clicks = 0 
    AND total_impressions > 1000
    AND days_active > 7
ORDER BY total_impressions DESC;
```

---

#### Pattern: Perfect Metrics (Too Consistent)

Real traffic has variance. Bot traffic is often suspiciously consistent.

| Signal | Why It's Suspicious |
|--------|---------------------|
| Exactly same impressions every hour | Bots running on schedule |
| CTR exactly 1.00% or 2.00% | Configured bot behavior |
| No weekend/weekday variance | Real users have patterns |
| Same impressions across all geos | Real traffic varies by region |

**Detection approach:**
```sql
-- Check for suspiciously consistent daily impressions
SELECT 
    app_id,
    AVG(impressions) as avg_imps,
    STDEV(impressions) as stdev_imps,
    STDEV(impressions) / AVG(impressions) as coefficient_of_variation
FROM performance_metrics
GROUP BY app_id
HAVING coefficient_of_variation < 0.1  -- Less than 10% variance is suspicious
```

---

### 3. Video-Specific Fraud Signals

#### Pattern: High Starts, Zero Completions

| Start/Complete Ratio | Interpretation |
|---------------------|----------------|
| 30-50% completion | Normal for skippable video |
| 70-90% completion | Normal for non-skippable |
| < 10% completion | Suspicious - auto-skip or hidden player 🚨 |
| 0% completion (many starts) | Fraud - video never plays 🚨 |

**Detection query:**
```sql
SELECT 
    app_id,
    SUM(video_starts) as starts,
    SUM(video_completions) as completions,
    CAST(SUM(video_completions) AS REAL) / NULLIF(SUM(video_starts), 0) as completion_rate
FROM video_metrics v
JOIN performance_metrics p ON p.id = v.performance_id
GROUP BY app_id
HAVING starts > 100 AND completion_rate < 0.05
ORDER BY starts DESC;
```

---

#### Pattern: High VAST Errors

VAST errors indicate the video player had issues. Some errors are normal, but high rates indicate:
- Fake/broken video players
- Inventory that doesn't actually support video
- Technical fraud (claiming video when it's not)

| VAST Error Rate | Interpretation |
|-----------------|----------------|
| < 5% | Normal |
| 5-15% | Technical issues |
| > 15% | Suspicious inventory 🚨 |
| > 30% | Likely fraud 🚨 |

---

### 4. Spend Anomalies

#### Pattern: Spend Without Impressions

| Scenario | Interpretation |
|----------|----------------|
| Small spend, 0 imps | Rounding/timing issue |
| Large spend, 0 imps | Billing fraud or major tracking failure 🚨 |

---

#### Pattern: Wildly Inconsistent CPMs

| CPM Variance | Interpretation |
|--------------|----------------|
| $1-5 range | Normal for most inventory |
| $0.01 CPM | Junk/fraud inventory |
| $50+ CPM | Premium or data error |
| Same app: $0.10 one day, $20 next | Data integrity issue |

---

### 5. Geographic Anomalies

#### Pattern: Wrong Geography for App

| Signal | Example | Interpretation |
|--------|---------|----------------|
| US-only app, India traffic | TrueCaller showing US ads in India | Likely low-quality/misattributed |
| Japanese app, 90% Brazil traffic | Gaming app with wrong geo targeting | Suspicious |

**Note from Jen:** *"TrueCaller inventory is good in India. Outside it, non-converting garbage. But this may not be for ALL campaigns - it has to be looked at for every campaign."*

---

### 6. Timing Anomalies

#### Pattern: Traffic Spikes at Odd Hours

| Time Pattern | Interpretation |
|--------------|----------------|
| Gradual increase 6AM-9PM | Normal human behavior |
| Spike at 3AM local time | Bot traffic (no humans awake) |
| Exactly same volume 24/7 | Bots running continuously |

---

## 🧮 Composite Fraud Score

Combine signals into a single score:

```python
def calculate_fraud_score(app_metrics: dict) -> float:
    """
    Calculate fraud score from 0 (clean) to 1 (definitely fraud).
    """
    score = 0.0
    signals = []
    
    # Signal 1: Clicks > Impressions frequency
    if app_metrics['suspicious_days'] > 0:
        ratio = app_metrics['suspicious_days'] / app_metrics['total_days']
        if ratio > 0.5:
            score += 0.3
            signals.append('frequent_click_excess')
        elif ratio > 0.2:
            score += 0.15
            signals.append('occasional_click_excess')
    
    # Signal 2: Zero clicks over time
    if app_metrics['total_clicks'] == 0 and app_metrics['total_impressions'] > 1000:
        if app_metrics['days_active'] > 7:
            score += 0.4
            signals.append('zero_engagement_bot')
        elif app_metrics['days_active'] > 3:
            score += 0.2
            signals.append('low_engagement')
    
    # Signal 3: Abnormally high CTR
    if app_metrics['total_impressions'] > 0:
        ctr = app_metrics['total_clicks'] / app_metrics['total_impressions']
        if ctr > 0.10:
            score += 0.3
            signals.append('extremely_high_ctr')
        elif ctr > 0.05:
            score += 0.15
            signals.append('suspicious_ctr')
    
    # Signal 4: Video completion issues
    if app_metrics.get('video_starts', 0) > 100:
        completion_rate = app_metrics.get('video_completions', 0) / app_metrics['video_starts']
        if completion_rate < 0.05:
            score += 0.25
            signals.append('video_never_completes')
    
    # Signal 5: Consistency (lack of variance)
    if app_metrics.get('impression_variance', 1) < 0.1:
        score += 0.15
        signals.append('too_consistent')
    
    return {
        'score': min(score, 1.0),  # Cap at 1.0
        'signals': signals,
        'tier': 'fraud' if score > 0.7 else 'suspicious' if score > 0.4 else 'watch' if score > 0.2 else 'clean'
    }
```

---

## 📋 App Quality Tiers

Based on fraud score and performance:

| Tier | Fraud Score | Action |
|------|-------------|--------|
| **Premium** | < 0.1 | Bid higher, good inventory |
| **Standard** | 0.1 - 0.3 | Normal bidding |
| **Watch** | 0.3 - 0.5 | Monitor closely |
| **Suspicious** | 0.5 - 0.7 | Reduce bids or pause |
| **Fraud** | > 0.7 | Block from bidding |

---

## 🔮 Using This for AI Clustering

When building campaign clusters or optimization algorithms, include fraud signals:

```python
# Example prompt context for AI clustering
"""
When grouping creatives into campaigns, consider these fraud signals:

Apps with fraud_score > 0.5 should be:
- Separated from clean inventory analysis
- Not used for performance benchmarking
- Flagged for potential blocking

When a creative has:
- Good performance on clean apps (fraud_score < 0.3)
- Poor performance on suspicious apps (fraud_score > 0.5)
→ This is EXPECTED and healthy. Don't penalize the creative.

When a creative has:
- Only performs well on suspicious apps
→ Investigate. May indicate the "performance" is fake.
"""
```

---

## 📝 Notes for Future Development

### Signals to Add Later

1. **Device fingerprint diversity** - Same app, only 3 device types = suspicious
2. **SDK version patterns** - Old SDK versions often indicate fraud
3. **Referer chain analysis** - Suspicious redirect patterns
4. **Bid response time** - Instant responses may indicate pre-computed fraud
5. **Creative size mismatch** - Requested 300x250, delivered in 1x1 = fraud

### Data Needed for Better Detection

- Hourly data (not just daily) for timing analysis
- User-agent strings for device analysis
- Bid request → win → impression → click full funnel
- Post-click conversion data

---

## 🎓 Key Takeaways

1. **One anomaly ≠ fraud** - Look for patterns over time
2. **Context matters** - TrueCaller in India = good; TrueCaller elsewhere = garbage
3. **Both extremes are signals** - Too many clicks AND too few clicks can indicate fraud
4. **Real traffic has variance** - Perfect consistency is suspicious
5. **Campaign-specific analysis** - What's fraud for one campaign might be normal for another

---

**Last Updated:** November 30, 2025  
**Contributors:** Jen (domain expertise), Claude (documentation)

---

*This document should be updated as new fraud patterns are discovered.*
