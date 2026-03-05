# Local DB Workflow (UI + Schema Safety)

This is the standard workflow for UI/UX changes when local data is partial but production schema compatibility must stay guaranteed.

## Why this workflow

- UI development does not require full production volume.
- Schema compatibility does require a deterministic migration process.
- Keep those concerns separate: small local dataset + strict schema gates.

## Local setup (recommended)

1. Use a dedicated local Postgres database.
2. Apply migrations to local DB:

```bash
export POSTGRES_DSN="postgresql://LOCAL_USER:LOCAL_PASS@127.0.0.1:5432/rtbcat_local"
./venv/bin/python scripts/postgres_migrate.py
```

3. Clone a UI-focused subset from remote:

```bash
scripts/clone_subset_to_local.sh \
  --remote-dsn "postgresql://REMOTE_USER:REMOTE_PASS@REMOTE_HOST:5432/rtbcat_serving" \
  --local-dsn "postgresql://LOCAL_USER:LOCAL_PASS@127.0.0.1:5432/rtbcat_local" \
  --buyer-id <BUYER_ID> \
  --days 30
```

4. Point app env to local DB:

```bash
export POSTGRES_DSN="postgresql://LOCAL_USER:LOCAL_PASS@127.0.0.1:5432/rtbcat_local"
export POSTGRES_SERVING_DSN="postgresql://LOCAL_USER:LOCAL_PASS@127.0.0.1:5432/rtbcat_local"
```

## Team guardrails (required)

- Never use production writer DSN for feature branch local testing.
- Any schema change must be in `storage/postgres_migrations/*.sql`.
- Follow expand/contract:
  - Expand release: additive schema changes only.
  - Contract release: remove deprecated schema only after app no longer uses it.
- Re-run migrations on clean DB before merge:
  - `scripts/postgres_migrate.py`
  - `scripts/postgres_migrate.py --dry-run`
  - `scripts/postgres_migrate.py --audit-versions`

## CI enforcement

GitHub Actions workflow: `.github/workflows/schema-compatibility.yml`

It enforces:
- clean-room Postgres migration from zero
- migration idempotency (second run)
- no pending migrations
- marker audit
- critical table presence checks

Use `.github/pull_request_template.md` checklist to keep the same standard on every PR.
