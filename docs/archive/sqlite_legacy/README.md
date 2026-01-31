# SQLite Legacy Archive

This directory contains archived SQLite-based code that is **no longer used at runtime**.

## Contents

- `sqlite_store.py` - Original SQLite storage backend (replaced by `storage/postgres_store.py`)
- `migrations.py` - SQLite migration utilities
- `migrations/` - SQLite schema migrations
- `user_repository.py` - SQLite-based user/auth repository (replaced by `services/auth_service.py` + Postgres repos)
- `campaign_repository.py` - SQLite-based campaign repository (replaced by `storage/postgres_repositories/campaign_repo.py` + `services/campaigns_service.py`)

## Status

These files are preserved for reference only. The platform now runs exclusively on PostgreSQL.

**Do not import or use these files in runtime code.**

## Migration Timeline

- 2026-01-30: SQLite storage archived
- 2026-01-31: User repository archived after auth split to Postgres repos
- 2026-01-31: Campaign repository archived after campaigns refactor to Postgres repo + service
