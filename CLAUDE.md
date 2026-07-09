# RTBcat Platform — Development Rules

## Performance: Precompute-first for analytics queries

**Never query `rtb_daily` in batch.** This table has 460M+ rows / 327 GB (2026-07) and grows ~2.6M rows a day. Any endpoint that aggregates metrics for multiple creatives MUST use the precomputed tables first:

- `config_creative_daily` — creative-level daily spend/impressions (177K rows, sub-second)
- `performance_metrics` — creative-level metrics with geography/device breakdowns

Only fall back to `rtb_daily` for:
- Single-creative detail views (fast enough for 1 ID)
- Creatives missing from precomputed tables
- Queries that specifically need clicks (not available in precompute)

If you're writing a new endpoint that touches RTB performance data, check `config_creative_daily` first.

## Database: Index awareness

`rtb_daily` indexes that exist and work:
- `(buyer_account_id, metric_date, creative_id, spend_micros)` — use for buyer-scoped spend sorts
- `(metric_date, buyer_account_id)` — use for date-range + buyer queries
- `(metric_date, creative_id)` — use for date-range + creative queries

Note: `buyer_account_id` has composite indexes, `buyer_id` does not. Use `buyer_account_id` for indexed queries on `rtb_daily`.

## Auth: Webhook endpoints must be public

Conversion postback endpoints (`/conversions/*/postback`, `/conversions/pixel`) are server-to-server webhooks. They must be listed in `PUBLIC_PREFIXES` in `api/auth_public_paths.py`. They have their own webhook secret/HMAC verification.

The source of truth for public auth, scheduler, and webhook paths is
`api/auth_public_paths.py`. Do not add these paths separately to individual
middleware files.

## Deployment

- Deploy workflow is manual-only (GitHub Actions `workflow_dispatch`)
- Production is the only deploy target (staging retired May 2026; VM
  `catscan-production-sg2` is TERMINATED, snapshot kept)
- Production VM: `catscan-production-sg` (asia-southeast1-b)
- **Nothing serves traffic that isn't a pushed, sha-tagged image.** No
  hot-patching containers via `docker cp`, no unpushed commits on the VM,
  no `/app` edits: they survive restarts but not recreation, and they make
  the system's true state exist nowhere but on one box. For an urgent fix,
  push the commit and let CI build the image — deploy that.
