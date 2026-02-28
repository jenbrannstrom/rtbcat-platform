# Claude Prompt: "Amazing Design Tools" Observed-QPS Mismatch Reconciliation (Seat-Specific)

```text
Run a focused reconciliation for seat **Amazing Design Tools** to determine why Home endpoint "Observed QPS" appears far lower than Google Authorized Buyers reached queries imply.

This is a seat-specific check (not a full pipeline RCA).

Target seat
- Display name: `Amazing Design Tools`
- buyer_id / seat ID: `1487810529` (from screenshot)
- Window: `2026-02-18` through `2026-02-24` (last 7 days shown in screenshot)

User evidence (from AB screenshot)
- Reached queries are ~2.53M to ~2.62M/day
- Expected seat-average QPS should be about `AVG(reached_queries) / 86400 ≈ 29.8 QPS`
- Home UI reportedly shows endpoint observed values `2.3` and `6.5` (~`8.8` total), which is too low

Important context
- Old deployed UI version (`sha-2b45dd9`) explains missing label update, but **not** numeric QPS math
- We need to localize the mismatch to one of:
  1) raw imports incomplete
  2) `home_seat_daily` precompute incomplete/incorrect
  3) `rtb_endpoints_current` endpoint observation precompute incorrect
  4) UI/API serving stale or wrong-seat data

Constraints
- Prefer read-only queries
- Do not run reimports/backfills unless evidence requires it
- Produce concrete numbers and a conclusion

Environment
- VM: `catscan-production-sg`
- API container: `catscan-api`
- Use `gcloud compute ssh ... --tunnel-through-iap`
- Use `python + psycopg` inside container for SQL (`psql` may not be installed)

PHASE 1 — Seat identity + expected QPS from Home precompute (read-only)
1) Confirm seat mapping
- Query `buyer_seats` for `buyer_id='1487810529'`
- Capture `buyer_id`, `bidder_id`, `display_name`, `active`

2) Query `home_seat_daily` for the 7-day window
Return per-day rows and a summary:
- `metric_date, reached_queries, impressions`
- `AVG(reached_queries)`
- `AVG(reached_queries)/86400` (expected seat observed QPS)

Required output:
- Exact 7 daily reached query values from DB
- Computed average reached/day and derived QPS
- Compare with screenshot (~2.5M/day)

PHASE 2 — Endpoint observed-QPS data path (read-only)
1) Query `rtb_endpoints` + `rtb_endpoints_current` for bidder/seat `1487810529`
Return:
- endpoint_id
- maximum_qps
- current_qps
- sum(current_qps)
- observed_at (if available in `rtb_endpoints_current`)

2) Compare:
- `SUM(rtb_endpoints_current.current_qps)` vs `AVG(home_seat_daily.reached_queries)/86400`

Interpretation:
- If sums match (~29.8 QPS): UI/API rendering/staleness issue
- If endpoint sum is low (~8.8) but `home_seat_daily` is ~29.8: endpoint observation precompute bug
- If both are low: upstream import/raw/precompute completeness issue

PHASE 3 — Raw data sanity checks for same window (read-only)
Goal: determine whether raw imports support the AB screenshot scale.

1) `rtb_daily` for buyer `1487810529`, grouped by `metric_date`
Return:
- row count
- SUM(reached_queries)
- SUM(impressions)
- indicators of report subtype coverage:
  - rows with non-null/nonnull `billing_id`
  - rows with non-null `bids_in_auction` / `auctions_won`

2) `rtb_bidstream` for buyer `1487810529`, grouped by `metric_date`
Split counts into:
- geo rows (no publisher_id)
- publisher rows (with publisher_id)

3) `rtb_bid_filtering` for buyer `1487810529`, grouped by `metric_date`

Interpretation:
- If raw tables are complete and near screenshot scale, mismatch is in precompute or endpoint observation
- If raw tables are incomplete, mismatch is import completeness

PHASE 4 — Import completeness for the 5 expected report types (read-only)
Query TUKY-style but for seat `1487810529` over `2026-02-18..2026-02-24` (or from `2026-02-11` if needed):

1) `ingestion_runs` grouped by `report_type`, `status`, day
2) `import_history` recent rows (filenames, rows_imported, status, imported_at)

Goal:
- confirm whether all 5 report types are arriving/importing daily for this seat
- identify missing categories if any

PHASE 5 — Recompute path checks (read-only first)
If `home_seat_daily` matches AB but `rtb_endpoints_current` is low:
1) Inspect `rtb_endpoints_current` recency and rows for this bidder
2) Check whether endpoint observation refresh job has run recently
3) Verify the query logic in prod data matches expected formula (if possible via code ref + data behavior)

If `home_seat_daily` is low vs AB:
1) localize whether `rtb_daily` is low or `home_seat_daily` aggregation is low
2) report which stage is dropping data

Required output format (strict)
Return a structured summary with:

1. **Findings (Evidence-backed)**
- key numbers and severity

2. **Seat QPS Reconciliation**
- AB screenshot implied avg reached/day and implied QPS
- `home_seat_daily` avg reached/day and derived QPS
- `rtb_endpoints_current` endpoint qps + sum
- conclusion: where mismatch occurs

3. **Import Completeness (5 report types)**
- which report types are present/missing for `1487810529` in the window

4. **Root Cause Hypothesis (with evidence)**
- raw import gap vs precompute gap vs endpoint observation gap vs stale UI/API

5. **Next Fix / Action Plan**
- exact file/function or operational action to verify/fix

Documentation (required)
- Write/update:
  - `docs/review/2026-02-25/audit/AMAZING_DESIGN_TOOLS_OBSERVED_QPS_RECON.md`

Do not make code changes in this pass unless you find a one-line obviously safe fix and call it out separately.
```

