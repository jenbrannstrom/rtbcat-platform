# VM2 Acceptance Checklist (B5)

**Date:** 2026-02-18  
**Target branch:** `b4/import-quality-controls`  
**Target commits:** `cd745f3`, `b84af6e`  
**Deployed SHA:** `sha-b84af6e`  
**Scope:** Validate B5 Feature Surface and UX Polish (`LANGUAGE-001`, `LANGUAGE-002`, `RECS-001`, `UX-001`, `UX-002`) on VM2.  
**Run status:** Deploy + server smoke + browser acceptance complete.

---

## 1) Objective

Validate B5 outcomes from reduce-phase review:

- `LANGUAGE-001`: Geo mismatch must be visible on creative triage surfaces.
- `LANGUAGE-002`: Currency mismatch decision must be explicitly resolved before schema work.
- `RECS-001`: Recommendation cards must support staged apply flow with safety controls.
- `UX-001`: Home dashboard must show clear global data freshness context.
- `UX-002`: Campaign sort/filter/view state must persist via URL query params.

---

## 2) Deployment Verification (Completed)

- [x] VM2 host: `catscan-production-sg2` (behind `vm2.scan.rtb.cat`)
- [x] Branch fast-forwarded on VM2: `b3f599c -> b84af6e`
- [x] Containers rebuilt and restarted with `sha-b84af6e`
- [x] Health endpoint reports new SHA:
  - `https://vm2.scan.rtb.cat/api/health` -> `{"version":"sha-b84af6e", ...}`

### Evidence

- VM2 `docker compose ps`:
  - `catscan-api:sha-b84af6e` (healthy)
  - `catscan-dashboard:sha-b84af6e`
- API log smoke (`--since 20m`) showed no `Traceback|NameError|Exception|ERROR` matches.

---

## 3) Code-Level Evidence (Completed)

### UX-001: Global "Data as of" banner

- [x] `dashboard/src/app/page.tsx:330` computes normalized data freshness dates.
- [x] `dashboard/src/app/page.tsx:344` renders `Data as of <date>`.
- [x] `dashboard/src/app/page.tsx:346` renders drift detail when sources differ.

### UX-002: Campaign state URL persistence

- [x] `dashboard/src/app/campaigns/page.tsx:56` parse helpers for query params.
- [x] `dashboard/src/app/campaigns/page.tsx:121` `syncQueryState(...)` writes URL params.
- [x] `dashboard/src/app/campaigns/page.tsx:163` sort changes sync to URL.
- [x] `dashboard/src/app/campaigns/page.tsx:169` country filter syncs to URL.
- [x] `dashboard/src/app/campaigns/page.tsx:174` issues-only toggle syncs to URL.

### RECS-001: Recommendation apply flow with safety

- [x] `dashboard/src/components/recommendations/recommendations-panel.tsx:113` maps only actionable recommendation actions.
- [x] `dashboard/src/components/recommendations/recommendations-panel.tsx:165` blocks apply when no compatible mappings exist.
- [x] `dashboard/src/components/recommendations/recommendation-card.tsx:263` shows staged apply UI only when actionable and config is selected.

### LANGUAGE-001: Geo mismatch surfaced in triage cards

- [x] `dashboard/src/components/creative-card.tsx:225` computes mismatch.
- [x] `dashboard/src/components/creative-card.tsx:317` renders `Mismatch` badge in card metadata row.

### LANGUAGE-002: Currency mismatch (decision gate)

- [x] Confirmed no `currency_code` on creative model (`storage/models.py`).
- [ ] Product decision for currency mismatch implementation is still required (see section 6).

---

## 4) Build Verification (Completed)

- [x] Local production build succeeds:
  - `dashboard`: `npm run build` passed with no TypeScript errors.

---

## 5) Browser Acceptance Checklist (Completed)

Run on authenticated VM2 session (`https://vm2.scan.rtb.cat/1487810529`) via Chrome DevTools MCP.

- [x] **B5-1 Version check: PASS** — Footer shows `sha-b84af6e` (a11y uid=56_24).
- [x] **B5-2 UX-001: PASS** — Home top bar displays `Data as of 2026-02-12` (uid=56_30/31). Drift detail visible: delivery data through 2026-02-12, requested through 2026-02-18.
- [x] **B5-3 UX-002: PASS** — On Creative Clusters (`/campaigns`):
  - Clicked List view, sort=Name, Issues toggle ON.
  - URL updated to `?view=list&sort=name&issues=1`.
  - Page reload preserved all three params; page rendered in list view, sorted by name, showing only clusters with issues (Meetcleo Cleo, Einnovation Temu, Blockpuzzle).
  - Note: `country` filter not rendered in current UI; `dir` param implicit (default asc for name sort).
- [x] **B5-4 LANGUAGE-001: Code PASS, runtime N/A** — Mismatch badge code verified at `creative-card.tsx:311-322` (conditional render when `hasMismatch` is true via `isLanguageCountryMismatch()`). However, 0 of 300 creatives in the test buyer dataset have `country` or `detected_language_code` populated. Badge cannot be exercised without geo/language data. No code defect.
- [x] **B5-5 RECS-001: N/A (not wired)** — `RecommendationsPanel` and `RecommendationCard` in `dashboard/src/components/recommendations/` are not imported by any page route component. Grep for `import.*Recommend` across `dashboard/src/` confirms no page-level imports. Components exist as standalone code but are unreachable via any active route. No false apply UI shown anywhere.
- [x] **B5-6 Regression: PASS** — Zero app-generated console errors across home, campaigns, creatives, and pretargeting config pages. One 404 from manual API probe (`/api/creatives/1487810529?limit=5`) — not app-generated.

---

## 6) LANGUAGE-002 Decision Gate

**Decision: `DEFER`**

Rationale:

- Creative model has no `currency_code` field (`storage/models.py` confirmed).
- Import and analytics pipelines treat spend in normalized USD/micros terms.
- No schema edits were included in this B5 code deploy.
- Adding currency end-to-end (model + migration + importer + API + UI) is a dedicated batch scope.
- Track as follow-up with source-of-truth requirements for multi-currency support.

---

## 7) Final Go/No-Go

- Server-side deploy and code-level checks: **PASS**
- Browser acceptance: **PASS** (4/4 exercisable checks pass; 2 checks N/A due to data/wiring)
- LANGUAGE-002 decision: **DEFER** (explicit, no schema changes this release)

**Verdict: GO**

Notes:
- LANGUAGE-001 mismatch badge: code correct but untestable without geo/language data on creatives. Will be exercisable once creative geo detection pipeline populates these fields.
- RECS-001 staged apply: components implemented but not wired to any route. Will be exercisable once a page imports `RecommendationsPanel`.

