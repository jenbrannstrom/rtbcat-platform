# RTBcat Platform Refactor & Migration Plan

> **Last Updated:** January 2026
> **Status:** 10/10 deliverables complete (pending dead code removal after 2026-06-30)

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

3. **Deprecation dates for legacy endpoints** ✅
   - `/config/credentials` endpoints marked deprecated with removal date 2026-06-30
   - Docstrings include migration path to new `/config/service-accounts` endpoints
   - Endpoints still functional but redirect to new multi-account system

**Exit criteria**: zero duplicate utility functions, importer usage documented, deprecation dates published.

## Phase 2 — Targeted Migrations (Medium Effort / Medium Risk)

**Goals**: complete in-progress migrations with strict compatibility guarantees.

1. **Settings router migration** ✅
   - Split `settings_legacy.py` into `endpoints.py`, `pretargeting.py`, `snapshots.py`, `changes.py`, `actions.py`
   - Created `api/routers/settings/` package with subrouters
   - Legacy file removed, all routes migrated

2. **Frontend API migration** ✅
   - All functions migrated from `api-legacy.ts` to modular files:
     - `core.ts`: fetchApi, health, stats, sizes, system status, geo lookup
     - `auth.ts`: logout, session, user info
     - `creatives.ts`: creative CRUD, thumbnails, language detection
     - `campaigns.ts`: standard and AI campaigns
     - `seats.ts`: buyer seats, discovery, sync
     - `analytics.ts`: waste, QPS, RTB funnel, recommendations
     - `settings.ts`: RTB endpoints, pretargeting
     - `integrations.ts`: credentials, Gemini, Gmail, GCP
     - `admin.ts`: users, audit, settings
     - `uploads.ts`: import tracking
   - `api-legacy.ts` now deprecated (removal date: 2026-06-30)
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

- [x] `qps/utils.py` with consolidated helpers
- [x] `qps/README.md` importer overview
- [x] Deprecation policy + dated deprecation notices (removal date: 2026-06-30)
- [x] Settings router split completed
- [x] Frontend API migration completed (all functions in modular files, `api-legacy.ts` deprecated)
- [x] Analyzer naming clarified (TrafficWasteAnalyzer, CreativeHealthService + READMEs)
- [x] Repositories consolidated under `storage/repositories/`
- [x] Unified database access pattern (repositories + facade pattern)
- [x] `sqlite_store` refactor completed (1412→1156 lines, extracted AnomalyRepository + migrations.py)
- [ ] Dead code removed per schedule

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
| QPS utilities | `qps/utils.py` |
| Analytics docs | `analytics/README.md` |
| Services docs | `services/README.md` |
| Settings API | `api/routers/settings/` |

### Deprecation Policy

**Standard deprecation cycle:**
1. **Announcement** - Add `DEPRECATED` to docstring with removal date (minimum 6 months notice)
2. **Warning period** - Log deprecation warnings when endpoint is called
3. **Removal** - Remove after scheduled date, coordinate with any dependent teams

**Currently deprecated:**

| Endpoint | Replacement | Removal Date |
|----------|-------------|--------------|
| `GET /config/credentials` | `GET /config/service-accounts` | 2026-06-30 |
| `POST /config/credentials` | `POST /config/service-accounts` | 2026-06-30 |
| `DELETE /config/credentials` | `DELETE /config/service-accounts/{id}` | 2026-06-30 |

**Code aliases (backward compatibility):**

| Old Name | New Name | Removal Date |
|----------|----------|--------------|
| `WasteAnalyzer` | `TrafficWasteAnalyzer` | TBD (after all usages updated) |
| `CreativeWasteSignalService` | `CreativeHealthService` | TBD (after all usages updated) |

**Frontend files (deprecated):**

| File | Replacement | Removal Date |
|------|-------------|--------------|
| `dashboard/src/lib/api-legacy.ts` | `dashboard/src/lib/api/` (modular files) | 2026-06-30 |

### Remaining Work

1. **Dead Code Cleanup**: Remove deprecated files/endpoints after 2026-06-30:
   - `api-legacy.ts` - frontend API legacy file (now just re-exports)
   - `/config/credentials` - legacy single-account endpoints
   - Backend compatibility aliases (`WasteAnalyzer`, `CreativeWasteSignalService`)
