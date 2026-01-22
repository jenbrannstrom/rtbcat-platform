# RTBcat Platform Refactor & Migration Plan

> **Last Updated:** January 2026
> **Status:** 15/15 deliverables complete (Phase 5 restructuring added)

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
   - Create `importers/utils.py` and move `DB_PATH`, `parse_date`, `parse_int`, `parse_float`.
   - Update all importers to use the shared utility module.
   - Add unit tests for parsing edge cases and DB path resolution.

2. **Document importer hierarchy**
   - Add `importers/README.md` describing each importer and recommended entry points.
   - Explicitly state that `smart_importer.py` is the default entry point.

3. **Deprecation dates for legacy endpoints** ✅
   - `/config/credentials` endpoints removed (previously deprecated)
   - Migration complete to `/config/service-accounts` endpoints

**Exit criteria**: zero duplicate utility functions, importer usage documented, deprecation dates published.

## Phase 2 — Targeted Migrations (Medium Effort / Medium Risk)

**Goals**: complete in-progress migrations with strict compatibility guarantees.

1. **Settings router migration** ✅
   - Split `settings_legacy.py` into `endpoints.py`, `pretargeting.py`, `snapshots.py`, `changes.py`, `actions.py`
   - Created `api/routers/settings/` package with subrouters
   - Legacy file removed, all routes migrated

2. **Frontend API migration** ✅
   - All functions in modular files under `dashboard/src/lib/api/`:
     - `core.ts`: fetchApi, health, stats, sizes, system status, geo lookup
     - `auth.ts`: logout, session, user info
     - `creatives.ts`: creative CRUD, thumbnails, language detection
     - `campaigns.ts`: standard and AI campaigns
     - `seats.ts`: buyer seats, discovery, sync
     - `analytics.ts`: waste, QPS, RTB funnel, recommendations
     - `settings.ts`: RTB endpoints, pretargeting
     - `integrations.ts`: service accounts, Gemini, Gmail, GCP
     - `admin.ts`: users, audit, settings
     - `uploads.ts`: import tracking
   - `api-legacy.ts` deleted
   - `api/index.ts` re-exports from modular files only

3. **Analyzer naming clarity** ✅
   - Renamed `WasteAnalyzer` → `TrafficWasteAnalyzer` (traffic waste analysis)
   - Renamed `CreativeWasteSignalService` → `CreativeHealthService` (creative health signals)
   - Added `analytics/README.md` and `services/README.md` documenting all analyzers
   - Backward compatibility aliases maintained

**Exit criteria**: settings routes fully migrated, frontend API legacy file substantially reduced, analyzers disambiguated.

## Phase 3 — Architecture Consolidation (High Effort / High Risk)

**Goals**: remove structural inconsistencies and align module boundaries.

1. **Repository location standardization** ✅
   - All repositories now in `storage/repositories/`
   - Includes: AccountRepository, CampaignRepository, CreativeRepository, PerformanceRepository, SeatRepository, ThumbnailRepository, TrafficRepository, UserRepository

2. **Database access unification**
   - Pick one pattern (repository + store) and migrate direct `sqlite3` usage behind it.
   - Remove redundant direct connections once all modules are updated.

3. **Refactor `sqlite_store.py`** ✅
   - Extracted `AnomalyRepository` for import anomalies and fraud detection
   - Extracted `storage/migrations.py` for data migration utilities
   - SQLiteStore now delegates to repositories (facade pattern)
   - Reduced from 1412 to 1156 lines while maintaining API stability

**Exit criteria**: repositories consolidated, one database access pattern, `sqlite_store` decomposed without breaking imports.

## Phase 4 — Cleanup & Dead Code Removal ✅

**Goals**: remove technical debt safely after usage drops to zero.

- ✅ Removed `/config/credentials` legacy endpoints
- ✅ Deleted `api-legacy.ts` frontend file
- ✅ Removed legacy credentials functions from `integrations.ts`
- Delete dead tables/migrations in safe cycles (as needed)
- Remove legacy authentication references and stale comments (as needed)

## Phase 5 — Module Restructuring ✅

**Goals**: eliminate confusing directory structure and clarify module boundaries.

1. **Move CLI + tests to root** ✅
   - Moved `creative-intelligence/cli/` → `cli/`
   - Moved `creative-intelligence/tests/` → `tests/`
   - Removed empty `creative-intelligence/` directory
   - Updated all documentation references

2. **Clarify importers/ as import-only** ✅
   - Updated `importers/__init__.py` docstring to emphasize data import purpose
   - Updated `importers/README.md` to document import vs analysis separation
   - Added deprecation notes to legacy analyzers in `importers/`

3. **Consolidate analyzers in analytics/** ✅
   - Added cross-references between duplicate analyzers
   - `analytics/size_analyzer.py` is canonical (async, structured Recommendations)
   - `importers/size_analyzer.py` maintained for CLI compatibility (sync, text reports)
   - Same pattern for fraud analyzers
   - Exported all analyzers from `analytics/__init__.py`

4. **Fold analysis/ into analytics/** ✅
   - Added deprecation notices to `analysis/` pointing to `analytics/`
   - Exported Recommendation engine components from `analytics/__init__.py`
   - `analysis/evaluation_engine.py` maintained for `/api/evaluation` endpoint

5. **Documentation sync** ✅
   - Updated ARCHITECTURE.md with current module descriptions
   - Updated this refactor-plan.md

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

- [x] `importers/utils.py` with consolidated helpers
- [x] `importers/README.md` importer overview
- [x] Deprecation policy + dated deprecation notices (removal date: 2026-06-30)
- [x] Settings router split completed
- [x] Frontend API migration completed (all functions in modular files, `api-legacy.ts` deprecated)
- [x] Analyzer naming clarified (TrafficWasteAnalyzer, CreativeHealthService + READMEs)
- [x] Repositories consolidated under `storage/repositories/`
- [x] Unified database access pattern (repositories + facade pattern)
- [x] `sqlite_store` refactor completed (1412→1156 lines, extracted AnomalyRepository + migrations.py)
- [x] Dead code removed (api-legacy.ts, /config/credentials endpoints, legacy credentials functions)
- [x] CLI + tests moved to root (`cli/`, `tests/`)
- [x] `creative-intelligence/` directory removed
- [x] `importers/` clarified as import-only with legacy analyzer deprecation notes
- [x] `analytics/` consolidated as canonical analyzer module
- [x] `analysis/` deprecated in favor of `analytics/`

---

## Implementation Notes for Developers

### Backward Compatibility Aliases

The following aliases are maintained for backward compatibility. **New code should use the new names.**

| Old Name | New Name | Module | Removal Target |
|----------|----------|--------|----------------|
| `WasteAnalyzer` | `TrafficWasteAnalyzer` | `analytics/` | TBD |
| `CreativeWasteSignalService` | `CreativeHealthService` | `services/` | TBD |
| `analyze_waste()` | `analyze_creative_health()` | `services/` | TBD |

### Architecture Patterns

#### Storage Layer (Facade + Repository Pattern)

```
SQLiteStore (facade)
    ├── CreativeRepository
    ├── AccountRepository
    ├── TrafficRepository
    ├── ThumbnailRepository
    └── AnomalyRepository
```

- **SQLiteStore** is the public API - use this for all storage operations
- **Repositories** handle specific entity types and are internal implementation
- **migrations.py** contains one-time data migration utilities

#### API Layer (Router + Subrouter Pattern)

```
api/routers/settings/
    ├── __init__.py (mounts all subrouters)
    ├── endpoints.py
    ├── pretargeting.py
    ├── snapshots.py
    ├── changes.py
    └── actions.py
```

### Key Files Reference

| Purpose | Location |
|---------|----------|
| Storage facade | `storage/sqlite_store.py` |
| All repositories | `storage/repositories/` |
| Data migrations | `storage/migrations.py` |
| QPS utilities | `importers/utils.py` |
| Analytics docs | `analytics/README.md` |
| Services docs | `services/README.md` |
| Settings API | `api/routers/settings/` |

### Deprecation Policy

**Standard deprecation cycle:**
1. **Announcement** - Add `DEPRECATED` to docstring with removal date (minimum 6 months notice)
2. **Warning period** - Log deprecation warnings when endpoint is called
3. **Removal** - Remove after scheduled date, coordinate with any dependent teams

**Code aliases (backward compatibility):**

| Old Name | New Name | Status |
|----------|----------|--------|
| `WasteAnalyzer` | `TrafficWasteAnalyzer` | Alias maintained |
| `CreativeWasteSignalService` | `CreativeHealthService` | Alias maintained |

### Completed Cleanup

The following items have been removed:
- `api-legacy.ts` - frontend API legacy file (deleted)
- `/config/credentials` - backend legacy endpoints (deleted)
- Legacy credentials functions from `integrations.ts` (deleted)
