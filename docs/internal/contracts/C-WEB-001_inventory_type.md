# C-WEB-001: Inventory Type Constraint

**Status:** Active (feature-flagged)
**Applies to:** `web_domain_daily` table only

## Rule

Every row ingested via the domain lane must have `inventory_type` set to one of:
- `web`
- `app`
- `unknown`

No other values are permitted.

## Source Precedence

1. **Explicit field** — if the CSV contains an `inventory_type` column, use it directly
2. **App/domain signals** — derive from `app_id`/`app_name` (→ `app`) or `publisher_domain` (→ `web`)
3. **Fallback** — `unknown`

## Enforcement

- **DB-level:** CHECK constraint on `web_domain_daily.inventory_type`
  ```sql
  CHECK (inventory_type IN ('web', 'app', 'unknown'))
  ```
- **Importer-level:** `import_to_web_domain_daily()` derives the value before INSERT
- **Contract check:** `check_web_001()` scans for any rows violating the constraint (should be impossible given the CHECK, but validates end-to-end)

## Feature Flag

This contract only applies when `CATSCAN_WEB_LANE_ENABLED` is set to `true`. When disabled, the contract check returns SKIP.
