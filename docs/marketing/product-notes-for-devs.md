# RTBcat Platform – Notes for RTB Developers

This app optimizes QPS for Google Authorized Buyers seats.
It exists because AB does not provide a Reporting API, so reporting has to be rebuilt from exports.

Blocking specific publishers is much simpler here than in the AB pretargeting UI.

It’s not a perfect app: we still depend on CSV imports because there is no other data source.

The practical goal is to reduce bidder bandwidth and improve efficiency.

DIAGRAM:

A common issue is ingesting ~50,000 QPS.
(Think of it like rainfall.)
About 30,000 of that QPS can be low‑value signal that your bidder ignores because the media buyer doesn’t want that inventory.

You only get 10 pretargeting settings per seat, plus a broad geo bucket (EUS, WUS, EU, Asia).
This app is about using those 10 settings as effectively as possible.

Even with that limit, it’s still a better control surface than what most SSPs provide.

## Features and why they matter

1) **Multi‑report ingestion (Gmail CSV → Parquet → BigQuery → Postgres)**
   - AB reporting is split across report types. The pipeline joins them into one schema so bids, wins, spend, and quality can be analyzed together.

2) **Canonical schema for QPS analysis**
   - One data model reduces join errors and duplicate logic. This is needed for correct win rate and waste rate.

3) **Precompute tables for UI speed**
   - Summary tables (home_*, config_*, rtb_*) keep the UI fast without expensive queries on every page load.

4) **Seat‑scoped analytics**
   - Buyers run multiple seats. Seat scoping avoids cross‑seat leakage and keeps optimization decisions accurate.

5) **Pretargeting config management with history**
   - Pretargeting changes are risky. The app stages changes, applies them in batches, and records rollback history.

6) **Publisher allow/deny editor**
   - Publisher lists are a direct lever on wasted QPS. The editor avoids CSV uploads and tracks pending changes.

7) **Creative‑level breakdowns and mismatch flags**
   - Creative issues are a common waste source. Creative‑level data helps you find assets that don’t match targeting or performance.

8) **Size coverage and waste analysis**
   - Size gaps reduce win rate. The size view shows request volume without matching creatives so you can add or block sizes.

9) **Bidstream funnel metrics**
   - Reached → bids → impressions is the core funnel. Keeping these together makes loss points obvious.

10) **App/publisher drill‑downs**
   - When performance drops, you need to find the inventory causing it. Drill‑downs make that visible.

11) **Deduplicated imports**
   - Gmail reports can repeat. The importer dedupes rows so metrics stay accurate after re‑processing.

12) **Operational traceability**
   - Refresh logs and precompute status show what ran, when it ran, and what data it produced.

## Intended users

- RTB/AB engineers maintaining pipelines and metrics.
- Optimization engineers reducing wasted QPS.
- Teams managing pretargeting at scale who need safe rollbacks.

## Deployment notes

- Production serving is Postgres‑only; SQLite is deprecated.
- CI builds images; VMs pull and restart.
- Daily refresh is expected for correct dashboards.
