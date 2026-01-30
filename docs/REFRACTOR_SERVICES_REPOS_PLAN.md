# Refactor Plan: Services/Repositories Split (Postgres-only)

Goal: unmix business logic from data access so routers are thin, services are testable, and SQL is isolated.

## Architectural Rules

- Routers: parse input, call a service, format output.
- Services: business rules + workflows + validation.
- Repositories: SQL only + row mapping.
- PostgresStore: temporary shim only; no new logic.
- File size cap: ~300-500 LOC; split by domain.

## Open Decision

Pick a home for Postgres repositories:

1) `storage/repositories/postgres/*_repo.py`
2) `storage/postgres_repositories/*_repo.py`

Either is fine; choose one and keep SQLite repositories marked as legacy.

## Phased Execution

Phase A (prep, no router edits):
- Add repo modules and service modules for small domains.
- Do not change router behavior yet.

Phase B (first slice):
- Move endpoints logic into repo + service.
- Keep PostgresStore shim delegating to new repo/service.
- Add repo + service tests.

Phase C (router handoff):
- Update endpoints router to call service directly.

Phase D (iterate by domain):
- Snapshots
- Changes
- Pretargeting
- Actions
- Seats Sync
- Uploads
- Retention
- System/Thumbnails
- Analytics/Performance

Phase E (cleanup):
- Remove dual-store paths.
- Delete unused store methods.

## First Slice: Endpoints

Repo:
- upsert endpoints
- list endpoints
- current_qps summary

Service:
- validate payload
- call repo methods

Router:
- call service only

## Test Strategy

- Repo tests: SQL shape, edge cases, empty input.
- Service tests: validation and workflow behavior.
- Router tests: response contract.
