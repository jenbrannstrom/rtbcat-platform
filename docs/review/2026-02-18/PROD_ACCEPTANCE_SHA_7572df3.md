# Production Acceptance — sha-7572df3

**Date:** 2026-02-18
**Environment:** Production (VM1 = `catscan-production-sg`)
**URL:** `https://scan.rtb.cat`
**Branch:** `unified-platform`
**Deployed SHA:** `sha-7572df3`
**Buyer:** `1487810529`
**Verdict:** **GO**

---

## Executive Summary

Production acceptance for `sha-7572df3` passes all checks. OAuth login works (previously broken by deleted client, now fixed with new client). The creatives routing bug (sidebar linking to `/clusters` instead of `/creatives`, plus middleware redirect) is confirmed fixed in live production. All core pages load, zero console errors, all key API endpoints return 200. Data freshness and campaign URL persistence features function correctly.

---

## Environment + SHA Validated

| Item | Value |
|---|---|
| Footer SHA | `sha-7572df3` |
| `/api/health` version | `sha-7572df3` |
| `/api/health` git_sha | `7572df3d` |
| `/api/health` status | `healthy` |
| `/api/health` database_exists | `true` |
| `/api/health` has_credentials | `true` |

---

## Checklist Table

| # | Check | Result | Evidence |
|---|---|---|---|
| A1 | Login (OAuth) | **PASS** | Google sign-in succeeds with `cat-scan@rtb.cat`; no OAuth error pages |
| A2 | Version in UI | **PASS** | Footer: `sha-7572df3` |
| A3 | Version in API | **PASS** | `/api/health` returns `{"version":"sha-7572df3"}` |
| B1 | `/` (home) loads | **PASS** | RTB Endpoints, Endpoint Efficiency, 10 pretargeting configs rendered |
| B2 | `/campaigns` loads | **PASS** | Creative Clusters page renders |
| B3 | `/campaigns?view=list&sort=name&issues=1` | **PASS** | URL params preserved, page renders in list view |
| B4 | `/clusters` loads | **PASS** | Renders CampaignsPage (expected behavior) |
| B5 | `/creatives` loads creatives page | **PASS** | URL stays `/1487810529/creatives`; h1="Creatives"; 304 of 304 creatives; format/size/approval filters; creative cards with IDs and thumbnails |
| B6 | `/1487810529/creatives` no redirect | **PASS** | No redirect to `/clusters`; stays at `/creatives` |
| B7 | Sidebar "Creatives" href | **PASS** | Points to `/1487810529/creatives` (not `/clusters`) |
| C1 | UX-001 data freshness | **PASS** | "Data as of 2026-02-12" visible in top bar; drift detail: delivery 2026-02-12, requested through 2026-02-18 (1/7 days) |
| C2 | UX-002 campaign URL persistence | **PASS** | `?view=list&sort=name&issues=1` preserved in URL after navigation |
| D1 | Console errors | **PASS** | Zero red console errors across home, campaigns, clusters, creatives |
| D2 | `/api/analytics/home/configs` | **PASS** | 200 |
| D3 | `/api/analytics/home/funnel` | **PASS** | 200 |
| D4 | `/api/analytics/home/endpoint-efficiency` | **PASS** | 200 |
| D5 | `/api/seats` | **PASS** | 200 |
| D6 | All network requests | **PASS** | 24/24 fetch/xhr requests returned 200; zero failures |

---

## Creatives Routing Bug Verification

**Bug:** Sidebar "Creatives" linked to `/clusters` (which re-exported `CampaignsPage`). Additionally, middleware in `route-normalization.ts` contained a legacy alias `"/creatives": "/clusters"` that redirected any `/creatives` navigation to `/clusters`.

**Fix (3 commits):**
1. `sidebar.tsx:54` — `href: "/clusters"` changed to `href: "/creatives"`
2. `buyer-routes.ts` — `/creatives` added to `BUYER_SCOPED_PREFIXES`
3. `[buyerId]/creatives/page.tsx` — redirect replaced with re-export of actual creatives page
4. `route-normalization.ts` — removed `/creatives → /clusters` legacy alias

**Live production verification:**

| Test | Before (broken) | After (sha-7572df3) |
|---|---|---|
| Sidebar "Creatives" href | `/1487810529/clusters` | `/1487810529/creatives` |
| Navigate to `/1487810529/creatives` | Redirected to `/1487810529/clusters` | Stays at `/1487810529/creatives` |
| Page content at `/creatives` | CampaignsPage (clusters grid) | CreativesPage (304 creative cards, format/size/approval filters, thumbnails, search) |

**Distinguishing evidence:** CreativesPage shows `h1="Creatives"`, `304 of 304` count, format buttons (Video/Display Img/Display HTML/Native), approval counts (Approved 291 / Not Approved 13), size dropdown with 100+ options, sort-by-spend dropdown, and individual creative cards with IDs, thumbnails, Copy ID/Copy HTML buttons, and Google Console links. This is clearly distinct from CampaignsPage which shows "Creative Clusters" heading with cluster-level groupings.

---

## Console / Network Findings

- **Console errors:** 0 across all tested pages (home, campaigns, clusters, creatives)
- **Network:** 24/24 fetch/xhr requests returned HTTP 200
- **Key API endpoints all healthy:**
  - `/api/auth/check` — 200
  - `/api/auth/me` — 200
  - `/api/health` — 200
  - `/api/seats?active_only=true` — 200
  - `/api/settings/endpoints` — 200
  - `/api/settings/pretargeting` — 200
  - `/api/analytics/qps-summary` — 200
  - `/api/analytics/home/funnel` — 200
  - `/api/analytics/spend-stats` — 200
  - `/api/analytics/home/configs` — 200
  - `/api/analytics/home/endpoint-efficiency` — 200

---

## Risks / Open Items

1. **Data staleness:** Delivery data only through 2026-02-12 (1/7 requested days). Not a code issue — data pipeline lag.
2. **Creative cache age:** Multiple creatives show "Stale cache (342h old)". Consider scheduling a creative sync.
3. **Pretargeting config breakdowns:** All 10 configs show "No creative data for this config". Precompute job may need to run.

---

## Final Decision

**GO** — All acceptance criteria met. OAuth fixed. Creatives routing bug confirmed fixed in live production. Core pages load. Zero console errors. All API endpoints healthy.
