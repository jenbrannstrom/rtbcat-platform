# Code Review Findings - Cat-Scan/RTB Platform

**Review Date:** 2026-01-10
**Status:** In Progress

---

## Executive Summary

Comprehensive code review of the Cat-Scan/RTB platform identifying security vulnerabilities, code quality issues, and architectural improvements needed to upgrade to a professional, secure application.

---

## 1. Files Over 1000 Lines (Refactoring Required)

| File | Lines | Status | Refactoring Plan |
|------|-------|--------|------------------|
| `dashboard/src/lib/api.ts` | 2,047 → ~800 | **PARTIAL** | 8 modules extracted to `api/` folder, legacy still has ~30 functions |
| `api/routers/settings/` | ~1,700 | **REFACTORED** | Split into subrouters (endpoints/pretargeting/snapshots/changes/actions) |
| ~~`dashboard/src/app/settings/accounts/page.tsx`~~ | ~~1,621~~ → 143 | **REFACTORED** | Split into 4 components in `components/` folder |
| `storage/sqlite_store.py` | 1,384 | Pending | Complete migration to repository pattern |
| ~~`storage/sqlite_store_new.py`~~ | ~~1,373~~ | **DELETED** | Was dead code - never imported |
| ~~`dashboard/src/app/page.tsx`~~ | ~~1,254~~ → 459 | **REFACTORED** | Split into 4 components in `components/waste-analyzer/` |
| `storage/repositories/user_repository.py` | 1,188 | Pending | Split into `auth_repo`, `permissions_repo`, `audit_repo` |
| `api/routers/creatives.py` | 1,181 | Pending | Extract language detection, preview generation logic |
| ~~`dashboard/src/components/preview-modal.tsx`~~ | ~~1,179~~ → 7 modules | **REFACTORED** | Split into `components/preview-modal/` (utils, renderers, sections) |
| ~~`dashboard/src/app/import/page.tsx`~~ | ~~1,168~~ → 615 | **REFACTORED** | Split into `components/import/` (6 components) |
| ~~`dashboard/src/app/campaigns/page.tsx`~~ | ~~1,094~~ → 736 | **REFACTORED** | Extracted types, utils, API, UI components to `components/campaigns/` |
| `cli/qps_analyzer.py` | 1,053 | Pending | Split into separate command modules under `cli/commands/` |

---

## 2. Security Vulnerabilities

### CRITICAL (Fixed)

| Issue | Location | Status | Fix Applied |
|-------|----------|--------|-------------|
| CORS wildcard with credentials | `api/main.py:131-137` | **FIXED** | Replaced `allow_origins=["*"]` with explicit allowlist via `ALLOWED_ORIGINS` env var |
| Weak password hashing fallback | `api/auth_oauth_proxy.py:49-56` | **FIXED** | Removed SHA-256 fallback, bcrypt now required |

### HIGH (Fixed)

| Issue | Location | Status | Fix Applied |
|-------|----------|--------|-------------|
| SQL injection in dynamic queries | `scripts/cleanup_old_data.py` | **FIXED** | Added whitelist validation for table/column names |

### MEDIUM (Partial)

| Issue | Location | Status | Notes |
|-------|----------|--------|-------|
| XSS via dangerouslySetInnerHTML | `dashboard/src/components/preview-modal.tsx` | Pending | Sanitize HTML content, use sandboxed iframe |
| ~~Session cookie not always secure~~ | ~~`api/auth_oauth_proxy.py`~~ | **N/A** | Removed - OAuth2 Proxy handles auth |
| ~~Email validation too weak~~ | ~~`api/auth_oauth_proxy.py`~~ | **N/A** | Removed - OAuth2 Proxy validates Google accounts |
| API keys logged in plaintext | Various files | Pending | Mask sensitive data in logs |

### Authentication Cleanup (Completed)

Password-based authentication has been removed. The app now uses **OAuth2 Proxy (Google Auth)** exclusively:
- Deleted: `dashboard/src/app/login/`, `initial-setup/`, `change-password/` pages
- Deleted: `dashboard/src/components/sensitive-route-guard.tsx`
- Cleaned: `api/auth_oauth_proxy.py` (693 lines → 177 lines) - removed password endpoints
- Updated: `dashboard/src/contexts/auth-context.tsx` - OAuth2-only flow
- Updated: `dashboard/src/lib/api/auth.ts` - removed login/changePassword functions

---

## 3. Code Quality Issues

### Dead Code (Fixed)

| Item | Location | Status |
|------|----------|--------|
| ~~Duplicate SQLite store~~ | ~~`storage/sqlite_store_new.py`~~ | **DELETED** |
| ~~Debug console.log statements~~ | ~~`dashboard/src/app/campaigns/page.tsx`~~ | **REMOVED** (18 statements) |
| ~~Debug console.log statements~~ | ~~`dashboard/src/components/preview-modal.tsx`~~ | **REMOVED** |
| ~~Debug console.log statements~~ | ~~`dashboard/src/app/history/page.tsx`~~ | **REMOVED** |

### Other Issues (Pending)

- **Overly broad exception handling**: `except Exception` used throughout, hiding bugs
- **Missing type annotations**: Several Python files lack complete type hints
- **Code duplication**: API response handling patterns repeated across frontend
- **Inconsistent coding patterns**: Mix of sync/async, different logging approaches

---

## 4. Architecture Improvements (Pending)

### Current Issues
- Business logic mixed into route handlers (no service layer)
- Environment variables read directly throughout codebase
- No centralized configuration validation
- Inconsistent log levels, no structured logging
- Missing request ID tracking for distributed tracing

### Recommended Structure
```
rtbcat-platform/
├── api/
│   ├── routers/          # Route handlers only
│   ├── services/         # Business logic (missing)
│   └── middleware/
├── domain/               # Domain models (missing)
├── infrastructure/
│   ├── database/
│   └── external/
└── tests/                # Sparse coverage
```

---

## 5. Testing Gaps

| Area | Current State | Target |
|------|---------------|--------|
| Python test files | 3 files | Full coverage of critical paths |
| TypeScript test files | 0 files | Component and integration tests |
| Estimated coverage | <5% | 70%+ for critical code |

### Missing Tests
- Authentication (login, session, rate limiting)
- API endpoints
- Repository layer
- Frontend components
- Integration/E2E tests

---

## 6. Action Plan

### Phase 1: Security Fixes - **COMPLETED**
- [x] Fix CORS wildcard configuration
- [x] Remove bcrypt SHA-256 fallback
- [x] Fix SQL injection in cleanup script
- [x] Delete dead code (`sqlite_store_new.py`)

### Phase 2: Dead Code & Debug Removal - **COMPLETED**
- [x] Remove console.log statements from `campaigns/page.tsx` (18 removed)
- [x] Audit for other debug statements (2 more files cleaned)
- [ ] Remove unused imports and variables (deferred to Phase 3)

### Phase 3: Large File Refactoring - **IN PROGRESS**
- [x] Create modular API structure (`dashboard/src/lib/api/`)
  - [x] `core.ts` - fetchApi, health, stats, system (85 lines)
  - [x] `auth.ts` - login, logout, session management (71 lines)
  - [x] `creatives.ts` - creative CRUD, thumbnails, language (140 lines)
  - [x] `campaigns.ts` - campaigns, AI campaigns, clustering (147 lines)
  - [x] `seats.ts` - buyer seats, discovery, sync (111 lines)
  - [x] `admin.ts` - user management, audit logs, settings (185 lines)
  - [x] `integrations.ts` - credentials, Gmail, GCP (213 lines)
  - [x] `analytics.ts` - waste, QPS, RTB funnel, performance (290 lines)
  - [x] `index.ts` - backward-compatible re-exports
  - [ ] Remaining in legacy: recommendations, history
- [x] Complete `settings` router refactor (~1,700 lines split)
  - [x] Create `api/routers/settings/` package structure
  - [x] Extract models to `settings/models.py` (210 lines)
  - [x] Create `settings/__init__.py` with re-exports
  - [x] Extract endpoints routes (~200 lines)
  - [x] Extract pretargeting routes (~300 lines)
  - [x] Extract snapshots routes (~200 lines)
  - [x] Extract changes routes (~350 lines)
  - [x] Extract actions routes (~350 lines)
  - [x] Remove legacy settings router file
- [x] Split `accounts/page.tsx` (1,621 → 143 lines) into components
  - [x] `ApiConnectionTab.tsx` - Service accounts and buyer seats (~500 lines)
  - [x] `GeminiApiKeySection.tsx` - AI language detection config (~210 lines)
  - [x] `GmailReportsTab.tsx` - Gmail auto-import config (~330 lines)
  - [x] `SystemTab.tsx` - System status and thumbnails (~200 lines)
  - [x] `index.ts` - Component exports
- [x] Split `page.tsx` (1,254 → 459 lines) into waste-analyzer components
  - [x] `FunnelCard.tsx` - RTB funnel visualization (~160 lines)
  - [x] `PublisherPerformanceSection.tsx` - Publisher win rates (~200 lines)
  - [x] `SizeAnalysisSection.tsx` - Size coverage analysis (~275 lines)
  - [x] `GeoAnalysisSection.tsx` - Geographic performance (~200 lines)
  - [x] `index.ts` - Component exports
- [x] Split `preview-modal.tsx` (1,179 lines) into modular components
  - [x] `utils.ts` - Formatting, data notes, tracking params (~150 lines)
  - [x] `SharedComponents.tsx` - CopyButton, MetricCard (~70 lines)
  - [x] `PreviewRenderers.tsx` - Video, HTML, Native previews (~210 lines)
  - [x] `CountrySection.tsx` - Country targeting (~170 lines)
  - [x] `LanguageSection.tsx` - Language detection (~260 lines)
  - [x] `PreviewModal.tsx` - Main modal (~330 lines)
- [x] Split `import/page.tsx` (1,168 → 615 lines) into components
  - [x] `ExportInstructions.tsx` - Google AB export guide (~250 lines)
  - [x] `RequiredColumnsTable.tsx` - Column requirements (~30 lines)
  - [x] `TroubleshootingSection.tsx` - Large file tips (~45 lines)
  - [x] `ColumnMappingCard.tsx` - Column mapping display (~32 lines)
  - [x] `ImportResultCard.tsx` - Import results (~130 lines)
  - [x] `ImportHistorySection.tsx` - Recent imports (~100 lines)
- [x] Split `campaigns/page.tsx` (1,094 → 736 lines) into components
  - [x] `types.ts` - Type definitions (~55 lines)
  - [x] `utils.ts` - Helper functions (~90 lines)
  - [x] `api.ts` - API functions (~70 lines)
  - [x] `NewCampaignDropZone.tsx` - Drop zone components (~70 lines)
  - [x] `SuggestionsPanel.tsx` - Auto-cluster suggestions (~100 lines)
  - [x] `SortFilterControls.tsx` - Sort/filter UI (~110 lines)
- [ ] Complete repository migration in `sqlite_store.py`
- [ ] Split remaining large files (creatives.py, qps_analyzer.py, user_repository.py)

### Phase 4: Testing Foundation
- [ ] Set up pytest infrastructure
- [ ] Add authentication unit tests
- [ ] Set up Jest for frontend
- [ ] Add critical API endpoint tests

### Phase 5: Architecture Improvements
- [ ] Introduce service layer
- [ ] Centralize configuration
- [ ] Implement structured logging

---

## 7. Dashboard Data Bug (CRITICAL - Pending Fix)

**Reported:** 2026-01-10
**Symptoms:**
- Home page shows empty data for seat "Tuky"
- All pretargeting settings show RED (0 reached, 0% win, 100% waste)
- Drill-down shows "No data available for this breakdown"

### Root Cause (Confirmed via SSH investigation)

**Database has data:**
- 1.3GB at `/home/rtbcat/.catscan/catscan.db`
- rtb_daily: 120,363 rows
- rtb_bidstream: 2,717,041 rows
- Tuky has 5,495 rows across 7 billing_ids with real metrics

**The Bug:** `/analytics/rtb-funnel/configs` endpoint uses "most recently synced" bidder_id instead of respecting the selected buyer seat.

### Fix Required

**1. Backend - Add buyer_id param:**

File: `api/routers/analytics/rtb_bidstream.py`
```python
@router.get("/analytics/rtb-funnel/configs")
async def get_config_performance(
    days: int = Query(7),
    buyer_id: Optional[str] = Query(None),  # ADD THIS
):
    valid_billing_ids = await get_valid_billing_ids_for_buyer(buyer_id)  # USE NEW FUNCTION
```

File: `api/routers/analytics/common.py`
```python
async def get_valid_billing_ids_for_buyer(buyer_id: Optional[str] = None) -> list[str]:
    """Get billing IDs for a specific buyer seat."""
    if buyer_id:
        seat = await db_query_one(
            "SELECT bidder_id FROM buyer_seats WHERE buyer_id = ?", (buyer_id,)
        )
        if seat:
            rows = await db_query(
                "SELECT DISTINCT billing_id FROM pretargeting_configs WHERE bidder_id = ?",
                (seat["bidder_id"],)
            )
            return [r["billing_id"] for r in rows]
    # Fallback: return all
    rows = await db_query("SELECT DISTINCT billing_id FROM pretargeting_configs")
    return [r["billing_id"] for r in rows]
```

**2. Frontend - Pass buyer_id:**

File: `dashboard/src/lib/api/analytics.ts`
```typescript
export async function getRTBFunnelConfigs(days: number = 7, buyerId?: string) {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) params.set('buyer_id', buyerId);
  return fetchApi(`/analytics/rtb-funnel/configs?${params}`);
}
```

File: `dashboard/src/app/page.tsx`
```typescript
// Pass selectedBuyerId to API call
const configPerf = await getRTBFunnelConfigs(7, selectedBuyerId);
```

**3. Gmail Import Progress (Minor UX fix):**

File: `dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx`
- Add visual progress indicator during import
- Show "Checking Gmail..." with spinner
- Toast success message with file count

### Files to Modify

| File | Change |
|------|--------|
| `api/routers/analytics/rtb_bidstream.py` | Add `buyer_id` param |
| `api/routers/analytics/common.py` | Add `get_valid_billing_ids_for_buyer()` |
| `dashboard/src/lib/api/analytics.ts` | Add `buyerId` param |
| `dashboard/src/app/page.tsx` | Pass `selectedBuyerId` |
| `dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx` | Add progress UI |

### Verification

```bash
# Test API directly after fix
curl "https://scan.rtb.cat/api/analytics/rtb-funnel/configs?days=7&buyer_id=299038253"
# Should return Tuky's config data
```

---

## 8. Production Setup Required

Add to production environment:
```bash
ALLOWED_ORIGINS=https://scan.rtb.cat
```

---

*Last updated: 2026-01-10*
