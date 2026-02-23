## Summary

- What changed:
- Why:

## Schema Impact

- [ ] No database schema changes in this PR
- [ ] If schema changed: added migration file(s) in `storage/postgres_migrations/`
- [ ] If schema changed: migration is backward-compatible (expand/contract)
- [ ] If schema changed: rollback notes are included

## Local Validation

- [ ] Ran migrations locally on a clean DB:
  - `POSTGRES_DSN=... ./venv/bin/python scripts/postgres_migrate.py`
- [ ] Re-ran migrations (idempotency):
  - `POSTGRES_DSN=... ./venv/bin/python scripts/postgres_migrate.py`
- [ ] Verified no pending migrations:
  - `POSTGRES_DSN=... ./venv/bin/python scripts/postgres_migrate.py --dry-run`
- [ ] If UI changed: verified with local subset data (`scripts/clone_subset_to_local.sh`)

## CI and Release Safety

- [ ] `Schema Compatibility` workflow passed
- [ ] No production-writer DSN used for local dev/testing
- [ ] Deployment order respected (expand schema first, contract later)

## Notes for Reviewers

- Risks:
- Follow-ups:
