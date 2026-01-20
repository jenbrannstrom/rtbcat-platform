# RTBcat Platform Refactor & Migration Plan

This plan turns the audit findings into an actionable, phased roadmap focused on safety, correctness, and minimal service disruption. It prioritizes quick wins that reduce duplication and risk, then proceeds to larger migrations with guardrails, while preserving uptime and data integrity.

## Guiding Principles

1. **Safety first**: every refactor is accompanied by validation steps and clear rollback paths.
2. **Incremental delivery**: small, reviewable changes that land frequently.
3. **Backward compatibility**: deprecations are time-bound and communicated; default behavior remains stable.
4. **Single source of truth**: consolidate shared logic and document ownership.

## Phase 0 — Preparation (1–2 weeks)

**Objectives**: establish visibility, guardrails, and a shared baseline for safe refactoring.

- **Create a migration tracker** in `docs/` (single checklist with owners, status, target releases).
- **Add lint/format/typing guardrails** if missing in CI (flake8/ruff/mypy + eslint/prettier as appropriate).
- **Define deprecation policy** (removal cadence, version tagging, and customer notification).
- **Set performance baselines** for critical APIs and importers (latency, throughput, error rates).

## Phase 1 — Immediate Fixes (Low Effort / High Impact)

**Goals**: reduce duplication and clarify entry points without changing behavior.

1. **Centralize QPS utilities**
   - Create `qps/utils.py` and move `DB_PATH`, `parse_date`, `parse_int`, `parse_float`.
   - Update all importers to use the shared utility module.
   - Add unit tests for parsing edge cases and DB path resolution.

2. **Document importer hierarchy**
   - Add `qps/README.md` describing each importer and recommended entry points.
   - Explicitly state that `smart_importer.py` is the default entry point.

3. **Deprecation dates for legacy endpoints**
   - Add explicit `@deprecated` metadata (and a removal date) for `/config/credentials` endpoints.
   - Add logging/metrics to track usage before removal.

**Exit criteria**: zero duplicate utility functions, importer usage documented, deprecation dates published.

## Phase 2 — Targeted Migrations (Medium Effort / Medium Risk)

**Goals**: complete in-progress migrations with strict compatibility guarantees.

1. **Settings router migration**
   - Split `settings_legacy.py` by functional domain (routes, pretargeting, snapshots, changes, actions).
   - Create individual sub-routers under `api/routers/settings/` and replace imports.
   - Add integration tests for each migrated route.

2. **Frontend API migration**
   - Move remaining functions from `dashboard/src/lib/api-legacy.ts` into modular files under `dashboard/src/lib/api/`.
   - Reduce the re-export surface in `api/index.ts` until `api-legacy.ts` is minimal or removed.
   - Add API contract tests or smoke tests for key flows (settings, snapshots, traffic).

3. **Analyzer naming clarity**
   - Rename `WasteAnalyzerService` to a purpose-specific name (e.g., `CreativeHealthAnalyzer`).
   - Document distinctions between analyzers (`analytics/`, `qps/`, `services/`).

**Exit criteria**: settings routes fully migrated, frontend API legacy file substantially reduced, analyzers disambiguated.

## Phase 3 — Architecture Consolidation (High Effort / High Risk)

**Goals**: remove structural inconsistencies and align module boundaries.

1. **Repository location standardization**
   - Move all repositories to `storage/repositories/`.
   - Create backward-compatible import paths (temporary re-exports).

2. **Database access unification**
   - Pick one pattern (repository + store) and migrate direct `sqlite3` usage behind it.
   - Remove redundant direct connections once all modules are updated.

3. **Refactor `sqlite_store.py`**
   - Split into focused modules (connections, migrations, querying, transaction helpers).
   - Maintain API stability with wrapper class or compatibility layer.

**Exit criteria**: repositories consolidated, one database access pattern, `sqlite_store` decomposed without breaking imports.

## Phase 4 — Cleanup & Dead Code Removal (Ongoing)

**Goals**: remove technical debt safely after usage drops to zero.

- Remove deprecated `/config/credentials` endpoints after the published date.
- Delete dead tables/migrations in safe cycles.
- Remove legacy authentication references and stale comments.

## Validation & Rollback Strategy

- **Feature flags** for risky migrations (settings and frontend API).
- **Database migrations** guarded with pre-checks, backups, and dry runs.
- **Revert strategy**: each PR should include a clear rollback section in its description.
- **Monitoring**: error rates, latency, and importer throughput monitored before and after each phase.

## Ownership & Governance

- Assign a module owner for each subsystem (API, QPS, analytics, storage, dashboard).
- Require sign-off for changes that touch shared utilities or storage access.
- Quarterly architecture review to prevent re-introduction of drift.

## Deliverables Checklist

- [ ] `qps/utils.py` with consolidated helpers
- [ ] `qps/README.md` importer overview
- [ ] Deprecation policy + dated deprecation notices
- [ ] Settings router split completed
- [ ] Frontend API migration completed
- [ ] Analyzer naming clarified
- [ ] Repositories consolidated under `storage/repositories/`
- [ ] Unified database access pattern
- [ ] `sqlite_store` refactor completed
- [ ] Dead code removed per schedule
