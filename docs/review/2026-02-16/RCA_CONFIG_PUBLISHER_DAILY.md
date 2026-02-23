# RCA & Fix: `config_publisher_daily` missing in CI schema-compatibility check

## Context

The `schema-compatibility.yml` CI workflow is failing at the "Verify critical tables
exist" step with:

```
Missing critical tables after migrations: config_publisher_daily
```

## Root Cause (already identified)

The table `config_publisher_daily` is NOT created by any file in
`storage/postgres_migrations/`. The migration runner only runs files from that
directory. The table is defined in two other places that CI never executes:

1. **`sql/postgres/001_precompute_tables.sql:198-208`** — standalone SQL setup
   script, not wired into the migration runner
2. **`services/config_precompute.py:59-116`** — created at runtime via
   `CREATE TABLE IF NOT EXISTS` when precompute first runs

The CI workflow (`.github/workflows/schema-compatibility.yml:77-109`) runs
`scripts/postgres_migrate.py` which only applies `storage/postgres_migrations/*`,
then checks for `config_publisher_daily` — which was never created.

Migration `044_canonical_alias_views.sql:11` references `config_publisher_daily`
as a source for an alias view, but it gracefully SKIPs with a NOTICE if the source
table doesn't exist (line 28-30: `IF to_regclass(...) IS NULL THEN ... CONTINUE`).

## Your task

1. **Verify** this diagnosis on VM2:
   ```bash
   # Connect to the staging DB
   psql "$POSTGRES_DSN" -c "SELECT to_regclass('public.config_publisher_daily');"
   # Expected: NULL if table is missing, or the table OID if it exists

   # Check which migrations have been applied
   psql "$POSTGRES_DSN" -c "SELECT version FROM schema_migrations ORDER BY applied_at;"

   # Check if the precompute service ever ran (it creates the table at runtime)
   psql "$POSTGRES_DSN" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'config_publisher_daily';"
   ```

2. **Determine the right fix** — two options:

   **Option A (recommended): Add a migration that creates the precompute tables**

   Create `storage/postgres_migrations/045_precompute_tables.sql` that runs the
   same DDL from `sql/postgres/001_precompute_tables.sql` wrapped in
   `CREATE TABLE IF NOT EXISTS`. This ensures migrations alone produce a complete
   schema. The tables affected are:
   - `home_config_daily` (alias: `pretarg_daily`)
   - `config_size_daily`
   - `config_geo_daily`
   - `config_publisher_daily`
   - `config_creative_daily`
   - `home_size_daily` (alias: `seat_size_daily`)
   - `home_geo_daily` (alias: `seat_geo_daily`)
   - `home_publisher_daily` (alias: `seat_publisher_daily`)
   - `home_seat_daily` (alias: `seat_daily`)
   - `campaign_daily_summary`

   Reference DDL: `sql/postgres/001_precompute_tables.sql` (full file) and
   `sql/postgres/004_config_breakdown_bigint.sql` (BIGINT column types).

   Include the `schema_migrations` version marker at the end:
   ```sql
   INSERT INTO schema_migrations (version, applied_at, description)
   VALUES ('045_precompute_tables', CURRENT_TIMESTAMP,
           'Create precompute summary tables if not already present')
   ON CONFLICT (version) DO NOTHING;
   ```

   **Option B (quick patch): Remove the table from CI's expected list**

   Edit `.github/workflows/schema-compatibility.yml:90` and remove
   `config_publisher_daily` (and `campaign_daily_summary` if also missing) from
   the `expected_tables` list. This papers over the problem — the table still
   won't exist until the precompute service runs.

3. **Validate the fix on VM2** before touching VM1:
   ```bash
   # After applying the migration
   POSTGRES_DSN="$POSTGRES_DSN" python scripts/postgres_migrate.py --status
   POSTGRES_DSN="$POSTGRES_DSN" python scripts/postgres_migrate.py

   # Verify the table now exists
   psql "$POSTGRES_DSN" -c "\d config_publisher_daily"

   # Verify alias views from migration 044 now resolve
   psql "$POSTGRES_DSN" -c "SELECT * FROM pretarg_publisher_daily LIMIT 0;"
   ```

4. **Check for other tables with the same gap** — these tables from
   `sql/postgres/001_precompute_tables.sql` may also be missing from migrations:
   ```bash
   # Compare tables created by 001_precompute_tables.sql vs actual schema
   psql "$POSTGRES_DSN" -c "
     SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public'
     AND table_name IN (
       'home_config_daily', 'config_size_daily', 'config_geo_daily',
       'config_publisher_daily', 'config_creative_daily',
       'home_size_daily', 'home_geo_daily', 'home_publisher_daily',
       'home_seat_daily', 'campaign_daily_summary'
     )
     ORDER BY table_name;
   "
   ```

## Key files

| File | Role |
|------|------|
| `.github/workflows/schema-compatibility.yml:77-109` | CI check that fails |
| `sql/postgres/001_precompute_tables.sql:198-208` | DDL for `config_publisher_daily` |
| `sql/postgres/004_config_breakdown_bigint.sql:14` | BIGINT column upgrade |
| `storage/postgres_migrations/044_canonical_alias_views.sql:11,28-30` | Alias view that gracefully skips |
| `services/config_precompute.py:59-116` | Runtime table creation |
| `scripts/postgres_migrate.py` | Migration runner (only reads `storage/postgres_migrations/`) |

## Constraints

- Do NOT modify VM1 (production) without explicit approval
- VM2 (staging) is safe for validation
- Option A is preferred — it makes the migration chain self-contained
- All precompute tables should use `CREATE TABLE IF NOT EXISTS` to be idempotent
- Commit only the migration file and push to the current branch
