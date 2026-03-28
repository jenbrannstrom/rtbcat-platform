# RTBcat Platform — Development Rules

## Performance: Precompute-first for analytics queries

**Never query `rtb_daily` in batch.** This table has 138M+ rows and grows daily. Any endpoint that aggregates metrics for multiple creatives MUST use the precomputed tables first:

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

Conversion postback endpoints (`/conversions/*/postback`, `/conversions/pixel`) are server-to-server webhooks. They must be listed in `PUBLIC_PREFIXES` in both `session_middleware.py` and `auth.py`. They have their own webhook secret/HMAC verification.

## Deployment

- Deploy workflow is manual-only (GitHub Actions `workflow_dispatch`)
- Must deploy to staging first, then production
- Production VM: `catscan-production-sg` (asia-southeast1-b)
- Staging VM: `catscan-production-sg2`
- Hot-patching via `docker cp` + `docker restart` is acceptable for urgent API fixes when Docker Hub rate limits block builds
