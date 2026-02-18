# Production Acceptance — Browser Smoke Test

**Date:** 2026-02-18
**Environment:** Production (VM1 = `catscan-production-sg`)
**URL:** `https://scan.rtb.cat`
**Expected SHA:** `sha-372ea35`
**Branch:** `b4/import-quality-controls` (unified-platform base)
**Buyer for checks:** `1487810529`

---

## Verdict: NO-GO

**Blocker: Google OAuth client deleted — cannot authenticate to production.**

---

## 1) Login + Version

- **FAIL / BLOCKED** — `https://scan.rtb.cat` loads the OAuth2 Proxy login page (v7.6.0).
  Clicking "Sign in with Google" returns:

  > **Access blocked: Authorization Error**
  > The OAuth client was deleted.
  > Error 401: deleted_client

- The OAuth client configured in the OAuth2 Proxy on VM1 has been deleted from the GCP project.
- No pages, API endpoints, or health checks are accessible — all routes are behind the OAuth proxy.
- **SHA could not be verified in UI.**

---

## 2) Core Page Loads

All pages blocked by OAuth failure. No pages could be loaded.

| Route | Result | Evidence |
|---|---|---|
| `/` | BLOCKED | Redirects to OAuth2 Proxy login |
| `/campaigns` | BLOCKED | OAuth proxy intercepts |
| `/1487810529/campaigns?view=list&sort=name&issues=1` | BLOCKED | OAuth proxy intercepts |
| `/clusters` | BLOCKED | OAuth proxy intercepts |
| `/qps/geo` | BLOCKED | OAuth proxy intercepts |
| `/api/health` | BLOCKED | OAuth proxy intercepts (not excluded from auth) |

---

## 3) UX-001 (Data Freshness)

- **BLOCKED** — Cannot reach home page.

---

## 4) UX-002 (Campaign URL Persistence)

- **BLOCKED** — Cannot reach campaigns page.

---

## 5) B5 Behavior Sanity

- **BLOCKED** — Cannot reach any app pages.

---

## 6) Console + Network

- **N/A** — No app pages loaded; only OAuth proxy error pages observed.
- No app console errors to report (app never loaded).

---

## 7) Summary Table

| Check | Result | Evidence |
|---|---|---|
| Login + version | **BLOCKED** | OAuth client deleted (Error 401: deleted_client) |
| Core page loads | **BLOCKED** | All routes behind OAuth proxy |
| UX-001 freshness | **BLOCKED** | Cannot reach home page |
| UX-002 URL persistence | **BLOCKED** | Cannot reach campaigns page |
| B5 behavior sanity | **BLOCKED** | Cannot reach any app pages |
| Console + network | **N/A** | App never loaded |

---

## 8) Blocker Details

**Root cause:** The Google OAuth client used by the OAuth2 Proxy on `scan.rtb.cat` (VM1 = `catscan-production-sg`) has been deleted from the GCP project.

**Impact:** 100% of production browser access is blocked. No authenticated route is reachable.

**Comparison:** VM2 (`vm2.scan.rtb.cat` = `catscan-production-sg2`) authentication works correctly — the B5 browser acceptance completed successfully on VM2.

**Required fix:**
1. Recreate or restore the Google OAuth client in the GCP Console (project: `catscan-prod-202601`).
2. Update the OAuth2 Proxy configuration on VM1 with the new client ID and secret.
3. Restart the OAuth2 Proxy service on VM1.
4. Re-run this production smoke test.

---

## 9) VM2 Cross-Reference

All B5 checks passed on VM2 at `sha-b84af6e` (see `VM2_ACCEPTANCE_B5.md`). The code is validated — only the production OAuth infrastructure is broken.
