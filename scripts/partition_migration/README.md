# rtb_daily partition migration kit

Rehearsal-gated migration of `rtb_daily` (327 GB / ~467M rows as of
2026-07-09, growing ~1.8 GB/day) to monthly RANGE partitions on
`metric_date`. Written for the GCP → Hetzner migration: the restore onto the
new box is the one free rewrite of this table. It also supports an in-place
cutover on the current instance if the migration is deferred.

**The rule: decide from rehearsal evidence, not nerves.** Rehearse on the
target box; if the rehearsal is clean, cut over onto partitions and get
retention-by-DROP forever. If it is hairy, migrate as-is and keep this kit
for later.

## Why (measured, not estimated)

| Fact | Value (2026-07-09) |
|---|---|
| Table size | 327 GB total: 188 GB heap + 138 GB across 16 indexes |
| Rows | ~467M, spanning 2026-01-07 → 2026-07-07 (6 months) |
| Growth | ~2.6M rows / ~1.8 GB per day |
| `id` sequence | 589,656,298 of INTEGER max 2,147,483,647 (~16 months left; `ON CONFLICT DO NOTHING` burns values ~26% faster than rows land) |
| Retention | `retention_config` page exists; never enforced on this table |

Partitioning fixes: retention becomes instant `DROP TABLE` of a monthly
partition (no vacuum storm, no bloat), the migration copies in month-sized
chunks instead of one 327 GB monolith, and the rebuild is the free moment to
make `id` BIGINT before the sequence exhausts the INTEGER column.

## Index changes (evidence: pg_stat_user_indexes, 2026-01-23 → 2026-07-09)

Kept (5 + PK + dedup unique):

| New index | Replaces | Scans on old |
|---|---|---|
| `(metric_date, row_hash)` UNIQUE | `rtb_daily_row_hash_key` | 589M (every insert) |
| `(metric_date, id)` PK | `rtb_daily_pkey` | 6 |
| `(creative_id, metric_date) INCLUDE (spend, imps, clicks)` | same + `idx_rtb_daily_creative` | 79,589 + 19,315 |
| `(billing_id)` | same + `idx_rtb_daily_metric_billing` | 18,013 + 1,066 |
| `(metric_date, country)` | same | 3,413 |
| `(buyer_account_id, metric_date, creative_id, spend_micros)` | same + `idx_rtb_daily_buyer` + `idx_rtb_daily_buyer_metric_date_desc` | 351 + 1,533 + 693 |
| `(metric_date, buyer_account_id)` | same | 623 |

Dropped outright (near-zero use in 5.5 months): `idx_rtb_daily_metric_app`
(5 scans), `idx_rtb_daily_bidder` (6), `idx_rtb_daily_buyer_id` (40),
`idx_rtb_daily_metric_creative` (27), `idx_rtb_daily_date` (partition
pruning covers pure date ranges). Net: 16 → 7 index structures. During
rehearsal, re-check the dashboard's heavy pages and compare plans; anything
that regressed gets its index added back on the parent — that's part of what
the rehearsal is for.

## Files

- `001_partitioned_schema.sql` — partitioned table (as `rtb_daily_p` by
  default; `-v parent=rtb_daily` on a bare target), `ensure_month_partitions()`
  helper, partitions for 2026 + headroom.
- `002_load_and_time.sh` — month-by-month copy with timings. Re-runnable.
- `003_validate.sql` — per-month row/hash/spend/impressions/clicks
  reconciliation. Zero rows = clean.
- `004_cutover.sql` — transactional rename swap + sequence handoff; includes
  rollback and the post-soak `DROP TABLE rtb_daily_unpart`.
- `partition_retention.py` — retention by DROP PARTITION + create-ahead;
  dry-run by default; `--from-config` reads the dashboard's
  `retention_config.raw_retention_days`.

## Path A — Hetzner restore (preferred)

1. Restore the production dump onto the target **excluding `rtb_daily`
   data** (`pg_restore -L` to edit the list, keep everything else).
2. `psql -v parent=rtb_daily -f 001_partitioned_schema.sql`
3. `pg_restore --data-only --table=rtb_daily` into the partitioned parent —
   COPY routes rows to partitions. Time it. (Alternative while the old
   instance is still reachable: point `002_load_and_time.sh` at a foreign
   table / dblink source, or restore the unpartitioned table under another
   name and use the script as-is.)
4. `psql -f 003_validate.sql -v source=<unpartitioned copy or run counts
   against the source instance> -v target=rtb_daily`
5. Point a test API instance at the restored DB; exercise the heavy
   dashboard pages; compare timings.
6. Record timings + validation below. Clean → proceed with cutover DNS/DSN
   switch on partitions. Hairy → restore as-is, revisit later.

## Path B — in-place cutover on the current instance

Only if migration is deferred and disk headroom exists (needs ~190 GB free —
note Cloud SQL auto-grows, and the copy is heavy I/O on live serving):

1. `psql -f 001_partitioned_schema.sql` (creates `rtb_daily_p`)
2. `./002_load_and_time.sh` during a quiet window, then re-run just before
   cutover to top up the current month (re-runnable by design).
3. `psql -f 003_validate.sql`; must return zero rows.
4. Pause importers/refreshes; `psql -1 -f 004_cutover.sql`; resume.
5. Soak 7 days (contract checks green), then `DROP TABLE rtb_daily_unpart`.

## Importer compatibility

`importers/unified_importer.py` and `scripts/bq_backfill_raw_facts.py` probe
`pg_partitioned_table` at connection time and use
`ON CONFLICT (metric_date, row_hash)` against a partitioned table,
`ON CONFLICT (row_hash)` otherwise. No deploy needs to be synchronized with
the cutover; the same build works before and after.

## After cutover

- Wire retention: daily
  `partition_retention.py --from-config --apply` (systemd timer on the
  Hetzner box, next to the contracts-check timer).
- `ensure_month_partitions` keeps 3 months of future partitions; a report
  arriving with a date beyond that horizon fails loudly rather than routing
  into a default partition — deliberate: an out-of-range `metric_date` has
  always meant a malformed CSV, and silence is how the Gmail incident got
  to 3.5 weeks.

## Rehearsal log (fill in)

| Date | Where | Step | Duration | Result |
|---|---|---|---|---|
| | | 002 full load | | |
| | | 003 validation | | |
| | | dashboard soak | | |
