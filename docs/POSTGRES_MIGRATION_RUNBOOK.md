# Postgres-Only Decommission Runbook (Remove SQLite Once and for All)

**Status:** Active cleanup plan  
**Date:** 2026-02-08  
**Policy:** Runtime and analytics are Postgres-only. Any SQLite dependency outside `docs/archive/sqlite_legacy/` is technical debt to remove.

## Objective

Remove all remaining SQLite runtime/config/docs leftovers and enforce Postgres-only operation across:
- API runtime
- Dashboard/runtime env config
- Import and ops scripts
- Terraform/startup scripts
- Documentation

Also remove non-actionable AI/assistant leftovers (for example, accidental "claude" notes) from operational docs.

## Non-Goals

- We are not deleting historical archives under `docs/archive/sqlite_legacy/`.
- We are not changing analytics logic in this runbook unless needed to remove SQLite coupling.

## Acceptance Criteria (Done Definition)

1. No runtime path can start with SQLite configuration.
2. No production compose/terraform/startup file sets `DATABASE_PATH`.
3. No active scripts used by ops/import path depend on `sqlite3`.
4. Docs outside archive do not instruct SQLite usage.
5. CI/verification guard fails if new SQLite runtime references are introduced.

## Phase 0: Immediate Safety Gate (Block SQLite at Runtime)

1. Add fail-fast guard in API startup/config:
- If `DATABASE_PATH` is set in production env, log error and refuse startup.

2. Confirm runtime version source remains image tag (`sha-*`) and not file fallback confusion.

3. Keep `docs/archive/sqlite_legacy/` as read-only historical reference.

## Phase 1: Runtime and Infra Cleanup

Remove SQLite env usage from active deployment paths:

- `docker-compose.production.yml`
- `docker-compose.simple.yml`
- `terraform/user_data.sh`
- `terraform/gcp_sg_vm2/startup.sh`

Actions:
- Remove `DATABASE_PATH` from container env.
- Ensure only `POSTGRES_DSN` and `POSTGRES_SERVING_DSN` are used.
- Remove cron tasks that assume local SQLite cleanup (`catscan-db-cleanup`) if they are SQLite-specific.

## Phase 2: Script and Import Path Cleanup

Migrate or retire active SQLite-based scripts used in normal operations:

- `scripts/gmail_import.py` (remove `DATABASE_PATH`/SQLite code path)
- `scripts/cleanup_old_data.py` (replace with Postgres cleanup or retire)
- `importers/*.py` modules still opening `sqlite3.connect(...)`
- `importers/utils.py` default db path usage

Actions:
- Replace direct `sqlite3` writes with Postgres repository/store calls.
- If a script is no longer needed, move to archive with explicit deprecation header.
- Update scheduler/ops commands to only call Postgres-compatible scripts.

## Phase 3: App and API Surface Cleanup

Remove user-facing SQLite traces:

- `api/routers/system.py` (remove `catscan.db` fallback/path exposure)
- Any endpoint/status output that suggests SQLite runtime path
- Any fallback behavior selecting SQLite when DSNs are missing

Actions:
- Standardize system health/version responses around Postgres-only assumptions.
- Return explicit misconfiguration errors when Postgres env is absent.

## Phase 4: Documentation Cleanup

Update all active docs to be Postgres-only and remove conversational leftovers.

Primary files:
- `INSTALL.md`
- `DATA_MODEL.md`
- `prompts/deploy-catscan.example.md`
- `CHANGELOG.md` (mark SQLite commands as historical, not active)
- This file: `docs/POSTGRES_MIGRATION_RUNBOOK.md`

Rules:
- No SQLite commands in active runbooks.
- If historical context is required, link to `docs/archive/sqlite_legacy/`.
- Remove accidental assistant artifacts (e.g., "claude:", pasted chat fragments).

For local UI work with partial data and strict schema compatibility, use:
- `docs/LOCAL_DEV_DATABASE.md`

## Phase 5: Verification and Regression Guard

Run repo checks (excluding archive):

```bash
rg -n "DATABASE_PATH|sqlite3|catscan\.db|sqlite_master|SQLite" \
  --glob '!docs/archive/**' \
  --glob '!docs/ai_logs/**' \
  .
```

Expected result after completion:
- Zero hits in runtime/deploy/import paths.
- Remaining hits allowed only in:
  - `docs/archive/sqlite_legacy/**`
  - historical AI logs (`docs/ai_logs/**`) if retained

Add CI guard:
- Fail PR if forbidden SQLite patterns appear outside approved archive paths.

## Work Plan Sequence

1. Runtime/infra env cleanup (Phase 1)
2. Script/import migration (Phase 2)
3. API/system surface hardening (Phase 3)
4. Docs cleanup (Phase 4)
5. Guardrails and CI enforcement (Phase 5)

## Rollback Strategy

- Keep changes per phase in separate commits.
- If Phase 2 migration causes regressions, rollback only script path commit while keeping runtime SQLite block in place.
- Do not reintroduce `DATABASE_PATH` in production compose.

## Owner Checklist

- [ ] Remove `DATABASE_PATH` from active deploy files
- [ ] Remove/replace SQLite ops scripts
- [ ] Remove SQLite fallback from API/system endpoints
- [ ] Clean active docs and remove assistant leftovers
- [ ] Add CI grep guard and pass verification
- [ ] Validate production containers start and serve using Postgres DSNs only
