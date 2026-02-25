# Home Data Source Audit (2026-02-25)

## Scope

Roadmap Phase 0 item:

- "Data source audit — For each Home section, list data tables used and % of rows missing `bidder_id`/`billing_id`"

This audit covers the user-facing Home analytics GET endpoints in `api/routers/analytics/home.py` and the tables queried by `storage/postgres_repositories/home_repo.py`.

## Home Section -> Data Tables

### Funnel (`GET /analytics/home/funnel`)

- `seat_daily` (funnel totals)
- `seat_publisher_daily` (top publishers + publisher count)
- `seat_geo_daily` (top geos + country count)

### Config Performance (`GET /analytics/home/configs`)

- `pretarg_daily`

### Endpoint Efficiency (`GET /analytics/home/endpoint-efficiency`)

- `seat_daily` (funnel proxy totals for derived rates)
- `rtb_bidstream` (bidstream / auction win / filtered bid metrics)
- `buyer_seats` (buyer -> bidder mapping)
- `rtb_endpoints` (allocated endpoint QPS / metadata)
- `rtb_endpoints_current` (observed endpoint QPS)

## Method

- Snapshot time: `2026-02-25T04:24:42Z` (UTC)
- Source: production Postgres (read-only query run inside `catscan-api`)
- Fact/precompute tables (`*_daily`, `rtb_bidstream`): audited over the last 30 days by `metric_date`
- Dimension/current tables (`buyer_seats`, `rtb_endpoints`, `rtb_endpoints_current`): audited across all rows
- "Missing" means `NULL` or empty/blank string after trimming

## Results

| Table | Scope | Rows | `bidder_id` missing % | `billing_id` missing % | Notes |
|---|---:|---:|---:|---:|---|
| `seat_daily` | last 30d | 104 | N/A (column absent) | N/A (column absent) | `buyer_account_id` present, 0.0% missing |
| `seat_publisher_daily` | last 30d | 230,150 | N/A (column absent) | N/A (column absent) | `buyer_account_id` present, 0.0% missing |
| `seat_geo_daily` | last 30d | 1,483 | N/A (column absent) | N/A (column absent) | `buyer_account_id` present, 0.0% missing |
| `pretarg_daily` | last 30d | 1,161 | N/A (column absent) | 0.0% (0 / 1,161) | `buyer_account_id` present, 0.0% missing |
| `rtb_bidstream` | last 30d | 10,635,851 | 0.0% (0 / 10,635,851) | N/A (column absent) | `buyer_account_id` present, 0.0% missing |
| `buyer_seats` | all rows | 4 | 0.0% (0 / 4) | N/A (column absent) | mapping table |
| `rtb_endpoints` | all rows | 11 | 0.0% (0 / 11) | N/A (column absent) | allocated QPS source |
| `rtb_endpoints_current` | all rows | 11 | 0.0% (0 / 11) | N/A (column absent) | observed QPS source |

## Interpretation

- Home funnel precompute tables (`seat_*`) are keyed by `buyer_account_id`, not `bidder_id` / `billing_id`, so `bidder_id` / `billing_id` missingness is not applicable there by design.
- `pretarg_daily` (Config Performance) has complete `billing_id` coverage in the audited 30-day window.
- Endpoint Efficiency source tables have complete `bidder_id` coverage in the audited snapshot (`rtb_bidstream`, `buyer_seats`, `rtb_endpoints`, `rtb_endpoints_current`).

## Outcome

Home Phase 0 "Data source audit" is complete for the current production snapshot.
