# VM2 Acceptance Checklist (B5)

**Date:** 2026-02-18  
**Target branch:** `b4/import-quality-controls`  
**Target commits:** `cd745f3`, `b84af6e`  
**Deployed SHA:** `sha-b84af6e`  
**Scope:** Validate B5 Feature Surface and UX Polish (`LANGUAGE-001`, `LANGUAGE-002`, `RECS-001`, `UX-001`, `UX-002`) on VM2.  
**Run status:** Deploy + server smoke complete. Browser acceptance pending.

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

## 5) Browser Acceptance Checklist (Pending)

Run on authenticated VM2 session (`https://vm2.scan.rtb.cat`) and record evidence:

- [ ] **B5-1 Version check:** footer/version shows `sha-b84af6e`.
- [ ] **B5-2 UX-001:** home top bar displays `Data as of YYYY-MM-DD` (or explicit pending state).
- [ ] **B5-3 UX-002:** on Campaigns, changing view/sort/filter updates URL params; refresh preserves same state.
- [ ] **B5-4 LANGUAGE-001:** creative list/card shows geo/language mismatch badge without opening preview modal.
- [ ] **B5-5 RECS-001:** recommendation surface supports staged apply flow:
  - actionable recommendation shows config selector + `Stage Change`
  - staging creates pending changes
  - non-actionable recommendations do not present false apply UI
- [ ] **B5-6 Regression:** no console errors on home/campaigns/creatives/recommendation surfaces.

---

## 6) LANGUAGE-002 Decision Gate (Required Before Merge)

Current state:

- Creative model has no currency field.
- Import and analytics pipelines treat spend in normalized USD/micros terms.

Required B5 decision (must be explicit):

1. `DEFER`: do not add currency schema in this release; track as follow-up with source-of-truth requirements.
2. `IMPLEMENT NOW`: add `currency_code` end-to-end (model + migration + importer + API + UI) in a dedicated batch.

No schema edits were included in this B5 code deploy.

---

## 7) Current Go/No-Go

- Server-side deploy and code-level checks: **PASS**
- Browser acceptance: **PENDING**
- LANGUAGE-002 decision: **PENDING**

**Interim verdict:** **HOLD** until section 5 and section 6 are completed.

