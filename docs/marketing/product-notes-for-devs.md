# RTBcat Platform – Notes for RTB Developers

These notes describe concrete capabilities and why they matter in RTB workflows. The goal is clarity, not marketing language.

## Features and why they are useful

1) **Multi‑report ingestion (Gmail CSV → Parquet → BigQuery → Postgres)**
   - Google AB reporting is fragmented across multiple report types. The pipeline stitches them into a consistent schema so you can analyze bids, wins, spend, and quality together.

2) **Canonical schema aligned to RTB/QPS optimization**
   - A single data model reduces mismatched joins and duplicated logic. This is critical for correct win rate, waste rate, and performance breakdowns.

3) **Precompute tables for UI performance**
   - Summary tables (home_*, config_*, rtb_*) serve the UI quickly without running expensive queries on every request. This keeps dashboards responsive on large datasets.

4) **Seat‑scoped analytics (buyer_account_id)**
   - Large buyers operate multiple seats. Seat scoping avoids cross‑seat data leakage and makes optimization decisions correct per seat.

5) **Pretargeting config management (write + history + rollback)**
   - Changes to AB pretargeting are risky. RTBcat stages changes, applies them in batches, and records full history so you can roll back safely.

6) **Publisher allow/deny editor (per config)**
   - Publisher lists are a practical lever for waste reduction. A dedicated editor with pending changes lets you control targeting without manual CSV work.

7) **Creative‑level breakdowns and language mismatch flags**
   - Creative issues often drive wasted spend. Seeing creatives with their targeting and language mismatch quickly surfaces underperforming assets.

8) **Size coverage and waste analysis**
   - Size gaps are a common cause of low win rate. The size analysis highlights request volumes without matching creatives so you can add assets or block sizes.

9) **Bidstream funnel views**
   - Reached → bids → impressions are the core RTB funnel metrics. The platform keeps these together so you can track conversion from requests to wins.

10) **App/publisher drill‑downs**
   - When performance tanks, you need to see which apps/sites are driving it. Drill‑downs reveal wasteful inventory quickly.

11) **Batch‑safe imports with deduplication**
   - Gmail reports can be duplicated. The importer prevents duplicate rows so metrics remain accurate when re‑processing emails.

12) **Operational tooling (refresh logs, precompute status)**
   - For data systems, correctness matters. The refresh log and precompute status provide traceability for what data was processed and when.

## Intended users

- RTB/AB engineers who maintain data pipelines and UI metrics.
- Optimization engineers working on QPS waste reduction.
- Teams managing pretargeting at scale and needing safe rollbacks.

## Deployment notes (non‑marketing)

- Production serving is Postgres‑only; SQLite is deprecated.
- CI builds images; VMs only pull and restart.
- The system expects daily data refreshes for accurate dashboards.
