# Analyzing QPS waste by publisher, geo, and size in Authorized Buyers

**Atomic fact:** Google sends you hundreds of ad sizes and thousands of publishers. Most of them have zero matching creatives or zero bids from your bidder.

The three dimension views in Cat-Scan (geo, publisher, size) turn the raw funnel numbers into actionable exclusion lists.

## The three views

### Geographic waste (`/qps/geo`)

Shows QPS, bids, wins, spend, and waste ratio by country and city.

Typical findings:
- Large QPS from countries where you have no creatives or no budget.
- Cities that receive disproportionate volume but almost no wins.
- Entire regions that the bidder completely ignores.

Action: Add the worst geos to the excluded list of the relevant pretargeting config.

### Publisher waste (`/qps/publisher`)

Ranks domains and app bundles by volume received vs bids placed and spend.

Typical findings:
- High-QPS publishers where the bidder bids on <5% of requests.
- Apps that deliver volume but zero wins (often due to floor or creative mismatch).
- A long tail of low-quality inventory that still consumes your QPS allocation.

Action: Use the per-config publisher editor to block the worst performers. This is dramatically easier than Google's CSV template dance.

**Atomic fact:** Cat-Scan's publisher block/allow editor works per pretargeting config and supports search + bulk changes with preview.

### Size waste (`/qps/size`)

Google will happily send you 300+ different ad sizes even if you only have creatives for a handful.

Typical finding: 80%+ of QPS in sizes for which you have no creative at all.

Action: Explicitly list only the sizes you actually support in the pretargeting config. This is one of the highest-leverage single changes most new seats can make.

## How the data is built

All three views are computed from the joined five-report dataset after import. No additional Google API calls are required for the analysis itself (the pretargeting sync is separate).

The same data powers the home-page funnel and the optimizer proposals.

## Why this analysis is rare

Most agencies never see these breakdowns because they never join the five CSVs and never build the per-dimension aggregates. They look at the high-level performance reports Google emails and assume "the bidder will sort it out."

The bidder can only sort out what actually reaches it. Everything that reaches it but gets rejected has already cost you QPS allocation and infrastructure.

## Related

- [The QPS funnel](qps-funnel.md)
- [Pretargeting configurations](pretargeting-configs.md)
- [Safe pretargeting changes](safe-pretargeting-changes.md)
- Full manual treatment: [Analyzing Waste by Dimension](../04-analyzing-waste.md)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.  
These three views are live in every Cat-Scan deployment.