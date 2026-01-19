# Code Analysis: RTBcat Platform

## Executive Summary

This is a real-time bidding (RTB) analytics platform for Google Authorized Buyers. After analyzing the codebase, I found significant redundancy, incomplete migrations, inconsistent organization, and tech debt. The codebase works but has accumulated cruft over time.

---

## Critical Issues

### 1. Duplicate Utility Functions (HIGH)

The same functions are copied across 5-6 files instead of being centralized:

| Function | Files |
|----------|-------|
| `DB_PATH = os.path.expanduser("~/.catscan/catscan.db")` | 10 files |
| `parse_date()` | 5 files (qps/importer.py, quality_importer.py, bid_filtering_importer.py, unified_importer.py, funnel_importer.py) |
| `parse_int()` | 5 files |
| `parse_float()` | 3 files |

**Impact:** Bug fixes or changes must be replicated in 5-10 places. High risk of inconsistency.

**Recommendation:** Create `qps/utils.py` with shared functions.

---

### 2. Duplicate Analyzer Classes (HIGH)

Two `SizeCoverageAnalyzer` classes exist doing similar things:

1. **`analytics/size_coverage_analyzer.py:37`** - Used by `api/routers/analytics/qps.py`
2. **`qps/size_analyzer.py:60`** - Used by `qps/__init__.py` and CLI tool

Both analyze creative size coverage against traffic. Confusing which to use.

**Similarly confusing:**
- `analytics/waste_analyzer.py` has `WasteAnalyzer` (size/traffic waste)
- `services/waste_analyzer.py` has `WasteAnalyzerService` (creative health signals)

Different purposes but confusing naming.

---

### 3. Incomplete Settings Router Migration (MEDIUM-HIGH)

A migration to split `settings_legacy.py` (1800+ lines) was planned but never completed:

```python
# api/routers/settings/__init__.py
"""
Migration plan:
1. Extract endpoints routes (~200 lines) (TODO)
2. Extract pretargeting routes (~300 lines) (TODO)
3. Extract snapshots routes (~200 lines) (TODO)
4. Extract changes routes (~350 lines) (TODO)
5. Extract actions routes (~350 lines) (TODO)
"""
# TODO: Replace with individual sub-routers as migration completes
from ..settings_legacy import router
```

The `settings/` package exists with models extracted but the actual routes still live in `settings_legacy.py`.

---

### 4. Deprecated API Endpoints Still Active (MEDIUM)

Three deprecated endpoints exist with no removal date:

```python
# api/routers/config.py
@router.get("/config/credentials")
"""DEPRECATED: Use /config/service-accounts instead"""

@router.post("/config/credentials")
"""DEPRECATED: Use POST /config/service-accounts instead"""

@router.delete("/config/credentials")
"""DEPRECATED: Use DELETE /config/service-accounts/{id} instead"""
```

These proxy to new endpoints but add maintenance burden.

---

### 5. Incomplete Frontend API Migration (MEDIUM)

Frontend has two API systems:

1. **`dashboard/src/lib/api-legacy.ts`** - 2063 lines, monolithic
2. **`dashboard/src/lib/api/*.ts`** - New modular structure (8 files)

Migration is partial - `api/index.ts` re-exports ~90 items from `api-legacy.ts`:

```typescript
// dashboard/src/lib/api/index.ts
// Legacy file still contains: recommendations, RTB settings/pretargeting,
// upload tracking, import history, snapshots, pending changes, traffic.
// These can be migrated in future refactoring passes.
```

---

### 6. Repository Organization Inconsistency (LOW-MEDIUM)

Storage repositories are split between two locations:

**In `/storage/` (root level):**
- `campaign_repository.py`
- `seat_repository.py`
- `performance_repository.py`

**In `/storage/repositories/`:**
- `creative_repository.py`
- `user_repository.py`
- `account_repository.py`
- `thumbnail_repository.py`
- `traffic_repository.py`
- `base.py`

No clear pattern for which goes where.

---

## Minor Issues

### 7. Six CSV Importers

Six different importers exist in `/qps/`:

| File | Purpose |
|------|---------|
| `importer.py` | Original performance detail importer |
| `unified_importer.py` | Flexible auto-mapping importer |
| `smart_importer.py` | Auto-detects type and routes to correct handler |
| `funnel_importer.py` | Bid pipeline data |
| `quality_importer.py` | Viewability/quality metrics |
| `bid_filtering_importer.py` | Bid filtering reasons |

This is actually necessary (different CSV formats) but confusing. `smart_importer.py` is the recommended entry point but this isn't clear from the code structure.

### 8. Two Auth Modules

- `api/auth.py` - API key authentication (middleware)
- `api/auth_v2.py` - OAuth2 Proxy authentication (user sessions)

These are complementary (not redundant) but naming suggests version evolution rather than parallel systems.

### 9. Large Files Needing Refactoring

| File | Lines | Issue |
|------|-------|-------|
| `storage/sqlite_store.py` | ~1400 | God object with too many responsibilities |
| `api/routers/settings_legacy.py` | ~1800 | Migration incomplete |
| `dashboard/src/lib/api-legacy.ts` | ~2063 | Migration incomplete |
| `creative-intelligence/cli/qps_analyzer.py` | ~1000 | CLI tool, acceptable |

### 10. Removed Features Still Referenced in Code Comments

The password-based login system was removed (migration 018) but some references remain:
- `dashboard/src/lib/api-legacy.ts:1779` - "Login and changePassword functions have been removed"
- Various comments about OAuth2 Proxy migration

---

## Unused/Dead Code

### Confirmed Dead Code

1. **`login_attempts` table** - Created in migration 011, dropped in 018
2. **Legacy credentials endpoints** - `/config/credentials` endpoints proxy to new system
3. **Password auth code** - Removed, only OAuth2 Proxy now

### Potentially Dead Code (Needs Verification)

1. `qps/unified_importer.py` - May be superseded by `smart_importer.py`
2. Legacy config system in `config/config_manager.py` - Newer multi-account system exists

---

## Architecture Issues

### 1. No Clear Module Boundaries

The project mixes concerns across directories:

```
/analytics      - Analysis engines
/qps            - Also has analysis (size_analyzer.py)
/services       - Also has analysis (waste_analyzer.py)
/api/analysis   - Also has analysis (language_analyzer.py)
```

### 2. Database Access Patterns

Multiple ways to access the database:

1. Direct `sqlite3.connect(DB_PATH)` - Used in qps/* modules
2. Via `SQLiteStore` class - Used in API routers
3. Via Repository classes - Mixed usage

### 3. Async/Sync Mismatch

Some repositories use `async def`, others use regular `def`. The `SQLiteStore` is async but often wraps synchronous SQLite operations.

---

## Recommendations

### Immediate (Low Effort, High Impact)

1. **Create `qps/utils.py`** - Extract `DB_PATH`, `parse_date`, `parse_int`, `parse_float`
2. **Document importer hierarchy** - Add README in `/qps/` explaining when to use which importer
3. **Add deprecation dates** - Set removal targets for deprecated endpoints

### Medium Term

1. **Complete settings router migration** - Split `settings_legacy.py` per the documented plan
2. **Complete frontend API migration** - Move remaining functions from `api-legacy.ts`
3. **Consolidate analyzer classes** - Rename `WasteAnalyzerService` to something distinct

### Long Term

1. **Refactor `sqlite_store.py`** - Split into focused modules
2. **Standardize repository locations** - All in `/storage/repositories/`
3. **Unify database access pattern** - Either all direct or all via store

---

## Metrics

| Metric | Count |
|--------|-------|
| Python files | ~151 |
| TypeScript/TSX files | ~100+ |
| Database tables | 41 |
| API endpoints | ~118 |
| Deprecated endpoints | 3 |
| Duplicate utility functions | ~15 instances |
| Incomplete migrations | 2 major |
| Large files (>1000 lines) | 4 |

---

## Conclusion

The codebase is functional but carries significant technical debt from:
1. Incomplete refactoring efforts (settings router, frontend API)
2. Copy-paste coding (utility functions)
3. Organic growth without architectural guidance (analyzer classes spread across 4 directories)

The core functionality works. The issues are maintainability and onboarding complexity.
