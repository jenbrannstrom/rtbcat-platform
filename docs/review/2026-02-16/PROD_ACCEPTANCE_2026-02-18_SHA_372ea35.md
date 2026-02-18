# Production Acceptance — Browser Smoke Test

**Date:** 2026-02-18
**Environment:** Production (VM1 = `catscan-production-sg`)
**URL:** `https://scan.rtb.cat`
**Expected SHA:** `sha-372ea35`
**Branch:** `b4/import-quality-controls` (unified-platform base)
**Buyer for checks:** `1487810529`

---

## Verdict: CONDITIONAL GO

**OAuth recovered. Core pages load. One nav bug found and fixed (see section 9).**

---

## 1) Login + Version

- **PASS** — OAuth2 Proxy login page loads (v7.6.0). Google sign-in succeeds with `cat-scan@rtb.cat`.
- Dashboard loads at `https://scan.rtb.cat/1487810529`.
- **SHA verified: `sha-372ea35`** (footer).
- `/api/health` returns: `{"status":"healthy","version":"sha-372ea35","git_sha":"372ea350","configured":true,"has_credentials":true,"database_exists":true}`

---

## 2) Core Page Loads

| Route | Result | Evidence |
|---|---|---|
| `/` (home) | **PASS** | Dashboard renders with 10 pretargeting configs, endpoint efficiency, funnel bridge |
| `/1487810529/campaigns?view=list&sort=name&issues=1` | **PASS** | Creative Clusters page loads, URL params preserved |
| `/1487810529/clusters` | **PASS** | Clusters page loads (re-exports CampaignsPage) |
| `/api/health` | **PASS** | Returns healthy JSON with `sha-372ea35` |

---

## 3) UX-001 (Data Freshness)

- **PASS** — Home top bar displays `Data as of 2026-02-12`.
- Drift detail visible: delivery data `2026-02-12` to `2026-02-12`, requested window through `2026-02-18` (1/7 days).

---

## 4) UX-002 (Campaign URL Persistence)

- **PASS** — Navigated to `/1487810529/campaigns?view=list&sort=name&issues=1`.
- Page renders in list view, sorted by name, issues-only filter active.
- URL params preserved across navigation.

---

## 5) B5 Behavior Sanity

- **PASS** — All exercisable B5 checks match VM2 results.
- LANGUAGE-001: Code correct, N/A at runtime (no geo data on creatives).
- RECS-001: N/A (not wired to any route).

---

## 6) Console + Network

- **PASS** — Zero app-generated console errors across home, campaigns, and clusters pages.

---

## 7) Summary Table

| Check | Result | Evidence |
|---|---|---|
| Login + version | **PASS** | `sha-372ea35` confirmed in footer and `/api/health` |
| Core page loads | **PASS** | Home, campaigns, clusters, health all load |
| UX-001 freshness | **PASS** | `Data as of 2026-02-12` visible in top bar |
| UX-002 URL persistence | **PASS** | `?view=list&sort=name&issues=1` preserved |
| B5 behavior sanity | **PASS** | Matches VM2 acceptance results |
| Console + network | **PASS** | Zero errors |

---

## 8) OAuth Recovery

**Root cause:** The Google OAuth client (`449322304772-j33av...lj180`) used by OAuth2 Proxy on VM1 was deleted from GCP project `catscan-prod-202601` on Feb 1, 2026. The old client was compromised and could not be restored.

**Fix applied:**
1. New OAuth client created in GCP Console by project owner (`billing@amazingdo.com`): `449322304772-s5cnod8uidv4a0niqbk0uu12jvc3rgd5.apps.googleusercontent.com`
2. Updated `/etc/oauth2-proxy.cfg` on VM1 with new `client_id` and `client_secret`.
3. Restarted `oauth2-proxy` systemd service on VM1.
4. Service confirmed running with new client ID in logs.

**Timeline:**
- Initial smoke test (NO-GO): 2026-02-18 ~03:00 UTC
- OAuth diagnosis: deleted client confirmed, VM2 working
- GCP IAM review: `cat-scan@rtb.cat` lacks `clientauthconfig.clients.create`; project owner is `billing@amazingdo.com`
- New client created by owner: 2026-02-18 ~03:35 UTC
- Config updated and proxy restarted: 2026-02-18 03:36:57 UTC
- Login verified: 2026-02-18 ~03:37 UTC

---

## 9) Nav Bug Found During Smoke Test

**Issue:** "Creatives" sidebar nav link pointed to `/clusters` (which re-exports the CampaignsPage). The actual individual creatives list page (`/creatives/page.tsx`) was unreachable from nav. Additionally, `/[buyerId]/creatives/page.tsx` contained a redirect to `/clusters` instead of rendering the creatives page.

**Fix applied (3 files):**
1. `dashboard/src/components/sidebar.tsx:54` — Changed href from `/clusters` to `/creatives`
2. `dashboard/src/lib/buyer-routes.ts` — Added `/creatives` to `BUYER_SCOPED_PREFIXES`
3. `dashboard/src/app/[buyerId]/creatives/page.tsx` — Changed from redirect-to-clusters to re-export of `../../creatives/page`

**Status:** Fix committed locally. Requires rebuild and redeploy to take effect on production.

---

## 10) VM2 Cross-Reference

All B5 checks passed on VM2 at `sha-b84af6e` (see `VM2_ACCEPTANCE_B5.md`). Production matches VM2 behavior for all exercisable checks.
