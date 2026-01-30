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

## Features and user benefits

1) **Works with single‑seat or multi‑seat AB accounts**
   - You can scope analysis and actions per seat so decisions match how the buyer account is actually set up.

2) **History & rollback for pretargeting changes**
   - Every change is recorded and can be rolled back. Changes are staged before applying for safety.

3) **Publisher allow/deny editor (per config)**
   - You can block or allow publishers directly, without CSV uploads or the AB UI.

4) **Clear win‑rate and waste visibility**
   - The app shows where bids drop off in the funnel so you can target the biggest waste first.

5) **Size coverage insight**
   - You can see which sizes get traffic but have no matching creatives, and decide to add or block.

6) **Creative‑level diagnostics**
   - You can inspect individual creatives with targeting context to find assets that underperform or mismatch.

7) **App/publisher drill‑downs**
   - You can trace performance drops to specific apps or sites and act on them quickly.

8) **Fast UI on large datasets**
   - Precomputed summaries keep the dashboard responsive even when daily volume is large.

9) **Deduplicated imports**
   - Re‑processing Gmail reports won’t double‑count results, so metrics stay accurate.

10) **Operational traceability**
   - Refresh logs show what ran and when, so you can trust the numbers you are looking at.

## Intended users

- RTB/AB engineers maintaining pipelines and metrics.
- Optimization engineers reducing wasted QPS.
- Teams managing pretargeting at scale who need safe rollbacks.

## Deployment notes

- Production serving is Postgres‑only; SQLite is deprecated.
- CI builds images; VMs pull and restart.
- Daily refresh is expected for correct dashboards.
