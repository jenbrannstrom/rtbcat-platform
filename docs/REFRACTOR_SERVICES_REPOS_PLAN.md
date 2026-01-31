# Refactor Plan: Services/Repositories Split (Postgres-only)

Goal: unmix business logic from data access so routers are thin, services are testable, and SQL is isolated.

## Architectural Rules

- Routers: parse input, call a service, format output.
- Services: business rules + workflows + validation.
- Repositories: SQL only + row mapping.
- PostgresStore: temporary shim only; no new logic.
- File size cap: ~300-500 LOC; split by domain.

## Repository Location

Use `storage/postgres_repositories/*_repo.py` for all new data access modules.
SQLite legacy code is archived under `docs/archive/sqlite_legacy/`.

## First Principles (Why this split matters)

- Data access changes often (SQL shape, indexes, migrations). Business rules change for different reasons. Mixing them causes regressions.
- PostgresStore will keep growing unless we cap it to a thin facade. Repos prevent an ever-expanding monolith.
- Services centralize behavior used by multiple routers (and background jobs) so logic isn’t duplicated.

## Decision Tree (Where code goes)

1) Is it SQL or DB-specific filtering?
   - Repo.
2) Does it combine multiple queries, apply business rules, or shape response objects?
   - Service.
3) Is it request parsing, validation, or response formatting?
   - Router.
4) Does it access external APIs (Google, Gmail)?
   - Service (or collector). Keep routers thin.

## Patterns to Follow

- Repo methods return raw dicts or lightweight dataclasses; no HTTP logic.
- Service methods return domain dataclasses or dicts ready for response models.
- Routers convert service output into response models; no SQL.
- Avoid cross-domain calls inside repos. Services can coordinate multiple repos.
- No circular dependencies: routers → services → repos (one direction).

## Example Extraction (from a large router)

Before:
- Router uses `db_query()` directly and formats nested response objects.

After:
- `storage/postgres_repositories/foo_repo.py`
  - `get_foo_by_id(id)`
  - `get_foo_stats(id, days)`
- `services/foo_service.py`
  - `get_foo_detail(id, days)` -> combines repo calls + derives metrics
- Router:
  - parse params, call service, return response

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

## Large File Split Targets

- `api/routers/creatives.py`
  - Move: waste flag calc, geo breakdown, language detection, preview shaping.
  - Services: `CreativePerformanceService`, `CreativeGeoService`, `CreativePreviewService`.
  - Repos: `creative_performance_repo.py` for rtb_daily/perf_metrics queries.
- `api/routers/performance.py`
  - Move all SQL to `performance_repo.py`, business aggregation into `PerformanceService`.
- `storage/repositories/user_repository.py`
  - Split into `auth_repo.py`, `permissions_repo.py`, `audit_repo.py`.
- `dashboard/src/lib/api.ts`
  - Split by domain modules and export a single index.

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
