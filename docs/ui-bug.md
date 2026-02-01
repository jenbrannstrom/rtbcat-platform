# Cat-Scan Dashboard UI Testing Report

## Test Environment
- URL: https://scan.rtb.cat/
- Version: v0.9.1 (Build: 29d7966)
- Account: Amazing Design Tools LLC (buyer_id: 1487810529)
- Date: 2026-01-31

---

## Critical Issues Found

### 1. All Data API Endpoints Returning 500 Internal Server Error

Every API endpoint that requires authentication is failing:

| Endpoint | Status |
|----------|--------|
| `/api/auth/me` | 500 |
| `/api/settings/pretargeting?buyer_id=...` | 500 |
| `/api/settings/endpoints?buyer_id=...` | 500 |
| `/api/analytics/home/configs?days=7&buyer_id=...` | 500 |
| `/api/analytics/qps-summary?days=7&buyer_id=...` | 500 |
| `/api/analytics/home/funnel?days=7&buyer_id=...` | 500 |
| `/api/creatives?buyer_id=...&limit=1000` | 500 |
| `/api/sizes` | 500 |

**Root Cause Hypothesis:** The `SessionAuthMiddleware` is throwing an exception rather than cleanly handling authentication. All failing endpoints use the `get_current_user` dependency (`api/dependencies.py:106-123`). The fact that errors are 500 (not 401) suggests the middleware crashes before returning a proper auth failure.

---

### 2. "Sync All" Does Not Sync Pretargeting Configs

**Observed Behavior:**
- User clicks "Sync All" → Message: "1400 creatives downloaded"
- Home page still shows: "Pretargeting Configs (0 active)"

**Root Cause:** This is expected behavior based on code analysis:
- "Sync All" appears to call creative sync endpoints (syncs from buyer seats)
- Pretargeting configs require a separate API call to `/settings/pretargeting/sync`
- The UI message is misleading - it implies everything synced but only creatives were fetched

**Evidence from `api/routers/settings/pretargeting.py:31-165`:** The pretargeting sync is a separate POST to `/settings/pretargeting/sync` that must be called explicitly.

---

## Page-by-Page Test Results

### Home Page (`/`)
| Component | Status | Issue |
|-----------|--------|-------|
| RTB Endpoints | FAIL | "Failed to load endpoint data" |
| Pretargeting Configs | FAIL | Shows "0 active", suggests using Sync All |
| Period selector (7d/14d/30d) | Loads | Cannot test functionality due to API failures |

### Creatives Page (`/creatives`)
| Component | Status | Issue |
|-----------|--------|-------|
| Creative list | FAIL | Empty - API returns 500 |
| Sizes filter | FAIL | `/api/sizes` returns 500 |

### Creative Clusters Page (`/campaigns`)
| Component | Status | Issue |
|-----------|--------|-------|
| Cluster list | FAIL | Empty - cannot load creatives |

### QPS Optimizer - Pub QPS (`/qps/publisher`)
| Component | Status | Issue |
|-----------|--------|-------|
| Header/Period selector | OK | Renders correctly |
| Data | FAIL | Analytics funnel endpoint fails |

### Connected Accounts (`/settings/accounts`)
| Component | Status | Notes |
|-----------|--------|-------|
| Service Accounts | OK | Shows connected account |
| Buyer Seats | OK | Shows 4 seats with creative counts |
| Sync Now buttons | Present | Could not test (would trigger actual sync) |
| Gemini API Key | OK | Input field present |

**Data Observed:**
- Amazing Design Tools LLC: 304 creatives
- Amazing Moboost: 449 creatives
- Amazing MobYoung: 35 creatives
- Tuky Display: 859 creatives
- **Total: 1647 creatives**

### System Status (`/settings/system`)
| Component | Status | Notes |
|-----------|--------|-------|
| API Status | OK | Shows "healthy" |
| Version | OK | 0.9.1 |
| Configured | OK | Yes |
| Python | OK | 3.11.14 |
| Node.js | WARN | "Not found" |
| ffmpeg | OK | 7.1.3 |
| Disk Space | OK | 16.3 GB free |
| Database Path | INFO | Shows "N/A" (expected for Postgres) |
| Database Size | INFO | Shows "0 MB" (hardcoded for Postgres) |
| Creatives | OK | 1647 |
| Creative Clusters | OK | 0 |
| Video Thumbnails | WARN | 0/792 (0% coverage) |

### Change History (`/history`)
| Component | Status | Notes |
|-----------|--------|-------|
| Page load | OK | Renders correctly |
| Data | OK | Shows "No changes found" (expected with 0 pretargeting configs) |

---

## Suspected Root Causes

### Primary: Authentication Middleware Failure
The `SessionAuthMiddleware` (`api/session_middleware.py`) is likely encountering an exception when processing requests. Evidence:
1. Endpoints that don't require auth (`/health`, `/system/status`) work fine
2. Endpoints requiring `get_current_user` dependency all fail with 500
3. 500 = unhandled exception, not 401 = proper auth denial

**To investigate:** Check server logs for the actual exception being thrown in the auth middleware.

### Secondary: Database Query Issues
Some endpoints like `/api/sizes` should work even without complex auth. The fact that it also fails suggests either:
- The auth middleware fails before the route handler runs
- There's a cascading failure from the auth system

### Tertiary: Misleading Sync UI
The "Sync All" button behavior creates user confusion:
- Button text implies comprehensive sync
- Actually only syncs creatives, not pretargeting configs
- No separate UI element to sync pretargeting

---

## Recommendations

1. **Immediate:** Check API server logs for the exception causing 500 errors
2. **Fix:** Debug `SessionAuthMiddleware` to find why authentication is crashing
3. **UX:** Clarify what "Sync All" actually syncs, or make it sync pretargeting configs too
4. **Monitoring:** Add better error logging to catch auth failures before they become 500s
5. **UI:** The System Status page shows "Database Path: N/A" which is misleading for Postgres - consider removing or showing actual connection info
