# Home Join-Safe Keys Audit (2026-02-25)

## Scope

Roadmap Phase 1 item:

- "Join-safe keys — Geo/publisher joins must include seat identity (`bidder_id` or `buyer_account_id`)"

Focus of this audit:

- Home/RTB serving repositories used by Home + QPS pages
- Config/Home precompute builders that generate geo/publisher keyed data used by config breakdowns

## What Was Audited

### 1. Serving repositories (Home / RTB bidstream)

Reviewed SQL joins in:

- `storage/postgres_repositories/home_repo.py`
- `storage/postgres_repositories/rtb_bidstream_repo.py`

Result:

- No geo/publisher cross-table joins were found in these repos that could mix seats.
- The only SQL join in the reviewed read repos is `LEFT JOIN creatives c ON c.id = d.creative_id` in `storage/postgres_repositories/rtb_bidstream_repo.py`, which is unrelated to geo/publisher seat joins.

### 2. Config precompute publisher attribution join (critical path)

Reviewed BigQuery config publisher attribution query in:

- `services/config_precompute.py`

Query shape (summary):

- Self-join `rtb_daily` as `q` (billing rows) to `b` (publisher rows) to derive `config_publisher_daily`
- Join keys include:
  - `metric_date`
  - `hour`
  - `creative_id`
  - `country`
  - `buyer_account_id`  <- seat identity guard

Result:

- Seat identity is already included in the join predicate (`q.buyer_account_id = b.buyer_account_id`), so publisher attribution does not cross buyer seats when other dimensions overlap.

Hardening applied:

- Added an inline code comment in `services/config_precompute.py` at the join predicate to preserve the seat-identity requirement during future edits.

### 3. Fallback buyer-level geo/publisher fact paths

Reviewed correlated `NOT EXISTS` checks in:

- `services/config_precompute.py` (`fact_delivery_daily` geo/publisher fallback inserts)

Result:

- Both geo and publisher fallback paths scope suppression checks by `buyer_account_id` (`f.buyer_account_id = g/p.buyer_account_id`), which prevents cross-seat suppression when deciding whether billing-scoped facts already exist.

## Outcome

- No unsafe geo/publisher joins (missing seat identity) were found in the audited Home/config paths.
- Roadmap item "Join-safe keys" is satisfied for the current Home + config precompute implementation.

## Remaining Adjacent Integrity Work

- "Identifier integrity" is still open and should be handled separately (ensuring `buyer_id`/seat identifiers are never used as substitutes for `billing_id` in APIs/queries).
