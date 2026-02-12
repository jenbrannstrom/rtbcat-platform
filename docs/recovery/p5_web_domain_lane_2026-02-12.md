# Phase 5: Optional Web/Domain Data Lane

**Date:** 2026-02-12
**Status:** Implemented, feature-flagged OFF by default

## What Changed

Added an optional, lean domain data lane for buyers purchasing WEB inventory who need domain-level analytics. Feature-flagged off by default — no current buyers are affected.

### New Files
| File | Description |
|------|-------------|
| `docs/contracts/C-WEB-001_inventory_type.md` | Contract: inventory_type must be web/app/unknown |
| `docs/contracts/C-WEB-002_domain_lane.md` | Contract: domain lane isolation & cardinality control |
| `storage/postgres_migrations/040_web_domain_lane.sql` | web_domain_daily table with natural PK |
| `importers/domain_rollup.py` | Top-N + __OTHER__ aggregation (default N=200) |
| `tests/test_web_domain_lane.py` | 8 tests covering routing, derivation, rollup, allowlist |

### Modified Files
| File | Changes |
|------|---------|
| `importers/flexible_mapper.py` | Added `inventory_type` synonyms; removed "inventory type" from `environment` to avoid conflict; added column-based domain detection fallback |
| `importers/unified_importer.py` | Filename-first routing (`catscan-domains-*`), `ensure_table_exists` for web_domain_daily, `import_to_web_domain_daily()` with buyer allowlist, `derive_inventory_type()`, `is_web_lane_enabled()` |
| `scripts/contracts_check.py` | SKIP status support, `is_web_lane_enabled()`, `check_web_001()`, `check_web_002()` |

## Feature Flags

| Env Var | Default | Purpose |
|---------|---------|---------|
| `CATSCAN_WEB_LANE_ENABLED` | unset (disabled) | Global kill switch — must be `true` for any web checks or imports |
| `CATSCAN_WEB_LANE_BUYERS` | unset | Comma-separated buyer ID allowlist |
| `CATSCAN_DOMAIN_TOP_N` | `200` | Max distinct domains per (date, buyer, billing) group |

## How to Enable for a Buyer

```bash
export CATSCAN_WEB_LANE_ENABLED=true
export CATSCAN_WEB_LANE_BUYERS="9999999999,8888888888"
```

## Migration

Run migration 040:
```bash
psql $POSTGRES_DSN -f storage/postgres_migrations/040_web_domain_lane.sql
```

## Verification

1. `pytest tests/test_web_domain_lane.py -v` — 8 tests pass
2. Existing 28 tests pass (no regression)
3. Contract check with web lane disabled → C-WEB-001/002 show SKIP

## Rollback

1. Drop the table: `DROP TABLE IF EXISTS web_domain_daily;`
2. Remove migration record: `DELETE FROM schema_migrations WHERE version = 40;`
3. Unset env vars: `unset CATSCAN_WEB_LANE_ENABLED CATSCAN_WEB_LANE_BUYERS`
4. Revert code changes (git revert)
