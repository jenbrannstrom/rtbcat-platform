# Chapter 10: Reading Your Reports

*Audience: media buyers, campaign managers*

This chapter explains the analytics panels across Cat-Scan and how to
interpret the numbers.

## Spend stats

Available on the home page and in config drill-downs.

| Metric | What it tells you |
|--------|------------------|
| **Total spend** | Gross spend across the selected period and seat. |
| **Spend trend** | Recent period vs. previous period. Rising spend with flat wins = cost inflation. |
| **Spend by config** | Which pretargeting config is responsible for how much spend. Helps identify which configs to optimize first. |

## Config performance

Shows how each pretargeting config performed over time.

- **Daily breakdown**: per-config impressions, clicks, spend, win rate, CTR,
  and CPM over the selected period.
- **Trend lines**: spot configs whose performance is degrading.
- **Field breakdown**: which specific fields (geos, sizes, formats) within a
  config are driving the numbers.

## Endpoint efficiency

Shows QPS utilization per bidder endpoint.

- **Efficiency ratio**: useful QPS / total QPS. Closer to 1.0 is better.
- **Per-endpoint breakdown**: if your bidder has multiple endpoints, see which
  ones are most and least efficient.
- Use this to decide whether consolidating endpoints would help.

## Snapshot comparisons

After rolling back a pretargeting change (or applying a new one), the snapshot
comparison panel shows:

- **Before**: config state prior to the change
- **After**: config state after the change
- **Delta**: what exactly changed (fields added/removed/modified)

This is useful for post-change analysis: "I excluded 5 geos yesterday, so what
happened to my funnel?"

## Recommended optimizations

Cat-Scan may display AI-generated recommendations based on your data. These
suggest specific config changes with estimated impact. They are suggestions,
not automatic actions. You always choose whether to apply them.

## Tips for reading reports

1. **Always check the period selector.** A 7-day view and a 30-day view can
   tell very different stories.
2. **Compare configs, don't just look at totals.** One bad config can drag
   down aggregate numbers while other configs perform well.
3. **Look at trends, not snapshots.** A single day's data is noisy. Trends
   over 7-14 days are more reliable.
4. **Cross-reference dimensions.** High waste in geo view + high waste in size
   view for the same config = two separate optimization opportunities.

## Related

- [Understanding Your QPS Funnel](03-qps-funnel.md): the summary view
- [Analyzing Waste by Dimension](04-analyzing-waste.md): drilling into
  specific waste sources
- [Pretargeting Configuration](06-pretargeting.md): acting on report findings
