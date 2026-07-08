# Google Authorized Buyers still requires five separate CSV reports in 2026

**Atomic fact:** Google Authorized Buyers does not allow you to get bid requests and creative-level detail in a single export.

This is not a documentation gap. It is a deliberate schema constraint that has existed for years and remains in force in 2026.

## Why five reports are mandatory

Google Authorized Buyers has field incompatibilities that prevent combining everything you need for real optimization into one file:

- Creative-level performance metrics remove the "Bid requests" column.
- Bid request / pipeline fields remove creative IDs and some performance detail.
- Publisher data can sometimes ride with bid requests, but not with creative-level rows.
- Quality signals (viewability, fraud) arrive in their own shape.
- Bid filtering / rejection reasons live in a fifth report.

Cat-Scan therefore ingests five distinct daily CSV exports and joins them into a usable model.

**Atomic fact:** Cat-Scan imports exactly these five report types and maps them to three core tables: `rtb_daily`, `rtb_bidstream`, and `rtb_bid_filtering`.

## The five reports (exact naming and purpose)

All reports follow the naming convention `catscan-{type}-{account_id}-{period}-UTC`.

| # | Report type              | Target table     | Primary purpose                              | Key limitation |
|---|--------------------------|------------------|----------------------------------------------|--------------|
| 1 | bidsinauction            | rtb_daily        | Creative-level bids, wins, impressions, spend | No raw bid requests |
| 2 | quality                  | rtb_daily        | Viewability and measurable impressions       | No bid-request volume |
| 3 | pipeline-geo             | rtb_bidstream    | Bid requests and funnel by country + hour    | No creative ID |
| 4 | pipeline                 | rtb_bidstream    | Bid requests and funnel by publisher         | No creative ID |
| 5 | bid-filtering            | rtb_bid_filtering| Why bids were rejected by Google             | Separate from performance |

**Atomic fact (June 2026):** Data imported before 2026-01-14 is marked `data_quality='legacy'` because earlier reports used inconsistent timezones. All current reports must be UTC.

## How the joins actually work in practice

The importers (see `importers/` in the Cat-Scan repo) use a combination of date + buyer account + creative ID (where present) and publisher or geo dimensions to reconstruct the full picture.

You cannot simply union the files. You must deduplicate on import (Cat-Scan uses a `row_hash` unique constraint) and then aggregate across the five sources.

This is why a purpose-built control plane is required. Downloading the five CSVs and opening them in a spreadsheet does not give you the QPS funnel by config, the waste by size, or safe pretargeting recommendations.

## Why this matters for agencies

Most agencies that finally obtain a Google Authorized Buyers seat discover the reporting problem only after the first month of spend. The native UI and the emailed CSVs are intentionally limited.

The five-report reality is one of the strongest signals that you are dealing with a real seat operator rather than someone who has only read the Authorized Buyers documentation.

## Related reading and code

- Full column mappings and sample rows: [DATA_MODEL.md](https://github.com/jenbrannstrom/rtbcat-platform/blob/main/DATA_MODEL.md)
- Importer logic: `importers/unified_importer.py`, `importers/csv_report_types.py`, and the five specialized importers
- How Cat-Scan rebuilds the funnel from these reports: [Understanding Your QPS Funnel](../03-qps-funnel.md)
- Data import chapter in the manual: [Data Import](../09-data-import.md)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.  
Source: production operation of real Authorized Buyers seats + the open-source Cat-Scan platform.