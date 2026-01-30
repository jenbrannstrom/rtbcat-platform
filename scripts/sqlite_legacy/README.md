# SQLite Legacy Scripts (Deprecated)

These scripts are for SQLite database operations and are **deprecated** as of Jan 2026.

The platform has migrated to **Postgres-only** for all state and analytics data.

## Scripts in this folder

| Script | Purpose | Status |
|--------|---------|--------|
| `backup.sh` | SQLite database backup | Deprecated |
| `restore_backup.sh` | SQLite database restore | Deprecated |
| `reset_database.py` | Reset SQLite database | Deprecated |
| `reset_to_v40.py` | Reset to v40 schema | Deprecated |
| `migrate_schema_v12.py` | Schema migration v12 | Deprecated |

## For Postgres

Use the following instead:

- **Backup**: `pg_dump` with Cloud SQL
- **Restore**: `pg_restore` or `psql`
- **Migrations**: `sql/postgres/*.sql` files

## Do not use in production

These scripts will fail or cause issues if run against the current Postgres-only architecture.
