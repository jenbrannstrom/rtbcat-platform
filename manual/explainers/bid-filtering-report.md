# Bid filtering reasons and the fifth Authorized Buyers report

**Atomic fact:** The fifth report (`catscan-bid-filtering`) is the only place Google tells you why it rejected a bid before it even reached your bidder.

Most operators never look at it because it arrives in its own CSV and is not joined to the performance data by default.

## What the bid-filtering report contains

It surfaces the reasons Google applied bid filtering on the exchange side for requests that matched your pretargeting but were then filtered before being sent.

Common categories include:
- Creative or size mismatches (from Google's perspective)
- Publisher or inventory quality signals
- Frequency or other policy filters
- Technical or format issues

When joined with the other four reports, it explains part of the "reached queries" to "bids" drop that is not under your bidder's control.

## Why it is valuable

Your bidder only sees what Google actually delivers. The bid-filtering report is the view into the last layer of filtering that happened on Google's side.

If a large fraction of potential volume is being filtered for "creative size not supported," the correct fix is usually in your pretargeting size list, not in the bidder.

## How Cat-Scan uses it

The report is imported into the `rtb_bid_filtering` table. It is available for analysis alongside the funnel and waste views.

It is one of the signals that can be fed into a custom optimizer (see the BYOM explainer).

## Related code and docs

- Target table and purpose in [DATA_MODEL.md](https://github.com/jenbrannstrom/rtbcat-platform/blob/main/DATA_MODEL.md)
- `importers/bid_filtering_importer.py`
- The fifth report is part of the standard five-report import flow described in the Data Import chapter

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.