# Seat Identity (`bidder_id`) Persistence — Production Verification

**Date:** 2026-02-25
**Operator:** Claude (automated)
**Prod VM:** `catscan-production-sg` (asia-southeast1-b)
**Container:** `catscan-api` (image `sha-5546ac5`)

**Scope:** This verification covers `bidder_id` coverage of rows already ingested into Postgres. It does not assess Gmail ingestion backlog/completeness or whether all source reports have been imported.

---

## 1. Backfill Dry-Run

```bash
sudo docker exec catscan-api python3 scripts/backfill_bidder_ids_pg.py --dry-run
```

**Output:**

```
============================================================
BIDDER_ID BACKFILL (Postgres)
============================================================

[DRY RUN - no changes will be made]

rtb_bidstream: would backfill bidder_id for 0 rows
rtb_bid_filtering: would backfill bidder_id for 0 rows
rtb_quality: would backfill bidder_id for 0 rows
rtb_daily: would backfill bidder_id via import_history for 0 rows
rtb_daily: would backfill bidder_id via billing_id mapping for 0 rows

Done.
```

**Result:** 0 ingested rows need backfill across all four raw fact tables.

---

## 2. Coverage Snapshot (Last 90 Days, Ingested Rows Only)

Query: `NULL` or blank (`BTRIM(bidder_id) = ''`) treated as missing.

```sql
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE bidder_id IS NULL OR BTRIM(bidder_id) = '') AS missing_bidder_id,
    CASE WHEN COUNT(*) > 0
         THEN ROUND(100.0 * COUNT(*) FILTER (WHERE bidder_id IS NULL OR BTRIM(bidder_id) = '') / COUNT(*), 2)
         ELSE 0 END AS pct_missing
FROM <table>
WHERE metric_date >= CURRENT_DATE - INTERVAL '90 days'
```

| Table | Total Rows | Missing `bidder_id` | % Missing |
|---|---|---|---|
| `rtb_daily` | 67,616,126 | 0 | 0.00% |
| `rtb_bidstream` | 16,973,687 | 0 | 0.00% |
| `rtb_bid_filtering` | 151,994 | 0 | 0.00% |
| `rtb_quality` | 0 | 0 | 0% |

**Result:** 100% `bidder_id` coverage on all ingested rows checked.
`rtb_quality` has no rows in the 90-day window (no quality report imports in this period).

---

## 3. Live Backfill Decision

**Not required.** Dry-run confirmed 0 ingested rows needing backfill; coverage snapshot confirmed 0 missing.

---

## 4. Conclusion

**PASS** — `bidder_id` is fully persisted across all ingested raw fact rows checked (last 90 days, 84.7M+ rows).

This verification does not assess Gmail ingestion backlog/completeness or whether all source reports have been imported.

- Code hardening (commit `710eed7`): `unified_importer.py` backfills `bidder_id` from `buyer_account_id` via `buyer_seats` lookup when filename parsing is missing; per-row resolution prevents cross-row leakage.
- Tooling hardening (commit `710eed7`): `audit_seat_identity.py` and `backfill_bidder_ids_pg.py` treat blank/whitespace as missing (not just NULL).
- SSH health diagnostic (commit `db2d905`): `scripts/check_gcloud_ssh_health.sh` added for operational verification connectivity.
- Production state is clean: 0 rows with NULL or blank `bidder_id` in 84.7M+ ingested rows checked.

**Roadmap item "Persist seat identity" is complete (ingested-row coverage verified).**
