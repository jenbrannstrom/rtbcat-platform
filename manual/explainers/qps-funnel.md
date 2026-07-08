# The QPS funnel for Google Authorized Buyers seats

**Atomic fact:** A typical seat requesting 50,000 QPS often receives far less, and the bidder then rejects the majority of what actually arrives.

The gap between what you asked Google to send and what your bidder can actually use is the central economic problem of running an Authorized Buyers seat.

## The stages (what each number actually means)

| Stage       | Definition                                                                 | Who pays / who cares          |
|-------------|----------------------------------------------------------------------------|-------------------------------|
| **QPS**     | The cap you set in pretargeting. Google throttles based on your account tier and recent performance. | You pay for the connection; Google decides how much actually flows |
| **Bid requests reached** | Queries that actually arrived at your endpoint | Your infrastructure cost |
| **Bids**    | Requests your bidder chose to bid on                                       | Your bidder's logic           |
| **Wins**    | Auctions you won (you only pay for these)                                  | Your actual media spend       |
| **Impressions** | Ads that were served after the win                                      | What the user actually saw    |
| **Clicks**  | User interactions                                                        | Creative + landing page quality |
| **Spend**   | Money that left your account                                             | The only number that ultimately matters |

**Atomic fact:** The largest single drop in most seats is between QPS (or reached queries) and Bids. This is the waste your pretargeting configuration is supposed to prevent.

## Waste ratio

Waste ratio = (QPS - Bids) / QPS

If your waste ratio is above 50%, you are paying for a firehose that your bidder is mostly ignoring. That volume could have been re-allocated to configs where the bidder actually bids and wins.

Cat-Scan surfaces this on the home page as the primary diagnostic.

## Why the funnel is harder in Authorized Buyers than in most DSPs

- You are limited to 10 pretargeting configurations per seat.
- Geographic targeting uses very coarse buckets.
- There is no real-time Reporting API; everything comes from the five daily CSVs.
- You cannot see "no-bid reasons" from the bidder side unless you ingest bidder logs yourself.

Google does a lot of filtering on its side before the traffic ever reaches you. What remains is still full of noise that only your pretargeting rules and creative coverage can fix.

## How Cat-Scan makes the funnel visible and actionable

- It reconstructs the full funnel from the five reports.
- It breaks it down by pretargeting config, geo, publisher, size, and creative.
- It shows allocated QPS vs actual realized volume per config.
- It lets you edit the pretargeting rules that control the top of the funnel, with preview and rollback.

See the live implementation in the Cat-Scan dashboard (home page + `/qps/*` routes) and the data model that powers the calculations.

## Key metrics derived from the funnel

- Win rate = Wins / Bids
- CTR = Clicks / Impressions
- CPM (what you actually paid)
- Effective waste (the QPS you requested but could never monetize)

When you connect post-click data (AppsFlyer or other MMP), the funnel gains a final "profitable outcome" stage. Until then, you optimize on bids + spend concentration + win rate.

## Related

- [Understanding Your QPS Funnel](../03-qps-funnel.md) (full manual chapter with screenshots)
- [Analyzing Waste by Dimension](qps-waste-analysis.md) in these explainers
- [Pretargeting configurations](pretargeting-configs.md)
- Optimization logic used in production: [OPTIMIZATION_LOGIC.md](https://github.com/jenbrannstrom/rtbcat-platform/blob/main/OPTIMIZATION_LOGIC.md)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.  
This funnel model is implemented and battle-tested in the open-source Cat-Scan platform.