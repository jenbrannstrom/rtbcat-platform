# VM2 Acceptance Checklist (B1 + B2)

**Date:** 2026-02-17  
**Target branch:** `unified-platform`  
**Target commit:** `b45644c`  
**Scope:** Validate B1 (crash/cache guardrails) and B2 (dashboard reliability)
**Run status:** Baseline run captured before follow-up reliability fixes; rerun required for final GO/NO-GO.

---

## 1) Test Setup

- [x] Open VM2 dashboard in Chrome. (`https://vm2.scan.rtb.cat/1487810529`)
- [x] Open DevTools -> Network. (via Chrome DevTools MCP)
- [x] Enable `Preserve log`.
- [x] Disable browser cache.
- [x] Network filter set to:
  - `qps-summary|spend-stats|settings/pretargeting|analytics/home/configs|seats`
- **Method:** Automated via Chrome DevTools MCP + fetch interceptor (initScript) for request blocking.

---

## 2) B1 Check: Buyer-Switch Cache Integrity

### Steps

- [x] Select buyer A and wait for data load.
- [x] Switch to buyer B.
- [x] Confirm request exists:
  - `/api/analytics/qps-summary?...buyer_id=<buyerB>`
- [x] Switch back to buyer A.
- [x] Confirm values and requests are buyer-specific (no cross-buyer stale data).

### Pass Criteria

- [x] QPS summary always matches current selected buyer.

---

## 3) B2 Check: Seat Init Failure + Retry UX

### Steps

- [x] In DevTools request blocking, add `/api/seats*`.
- [x] Hard refresh page.
- [ ] ~~Confirm error banner appears:~~
  - ~~`Unable to load buyer seats. Retry to continue.`~~
  - **FAIL:** Shows `"No seats connected"` / `"Go to Settings to connect"` instead of error+retry banner. Treats fetch failure as empty state.
- [ ] ~~Remove blocking rule.~~
- [ ] ~~Click `Retry`.~~
- [ ] ~~Confirm seats load and page recovers.~~

### Pass Criteria

- [ ] Seat error state is explicit and recoverable via retry. **FAIL — no error banner, no retry button.**

---

## 4) B2 Check: Config Metrics Fallback Is Not Misleading

### Steps

- [x] Block `/api/analytics/home/configs*`.
- [x] Refresh page.
- [x] Confirm warning appears:
  - Actual text: `"Config performance metrics are delayed; showing base config list."` (wording differs from spec but intent correct)
- [x] Confirm config cards show placeholders (`--` / `No data`) instead of synthetic zero performance.
- [x] Unblock request and refresh.
- [x] Confirm real values return.

### Pass Criteria

- [x] No fake zero-performance values are shown when config metrics are unavailable. **PASS** (warning text differs from spec)

---

## 5) B2 Check: Transient Retry Behavior

### Steps

- [x] Temporarily block:
  - `/api/settings/pretargeting*`
  - `/api/analytics/home/configs*`
- [x] Refresh page, then remove blocks after initial failures (8s transient block via fetch interceptor).
- [ ] ~~Confirm automatic retry attempts occur and calls recover without manual refresh.~~
  - **FAIL:** Only 1 attempt per endpoint. No automatic retry after blocks lifted. Page stuck showing "Pretargeting Configs (0 active)" / "No Pretargeting Configs" 23+ seconds after blocks removed.

### Pass Criteria

- [ ] Transient failures self-recover via retry policy. **FAIL — no retry policy observed.**

---

## 6) B1 Check: No Analyzer NameError in API Logs

Run on VM2 host:

```bash
docker compose logs api --since 30m | rg -n "NameError|LOW_WIN_RATE_THRESHOLD|HIGH_WASTE_RATE_THRESHOLD|Traceback"
```

### Pass Criteria

- [x] No NameError / threshold-related traceback appears after exercising dashboard/recommendation flows. **PASS — 0 matches via IAP tunnel.**

---

## 7) Final Go/No-Go

- [ ] All sections 2-6 pass. **2 of 5 FAILED (Checks 3, 5)**
- [ ] ~~Outcome: **GO to B3 implementation**~~
- [x] If any fail, record exact endpoint/screen/trace and keep status **NO-GO** until fixed.
- **Outcome: NO-GO**

### Failures requiring fix before B3:

1. **Check 3 — Seat error UX**: Seat fetch failure shows "No seats connected" empty state instead of error banner with retry. The `useSeats` hook (or equivalent) does not distinguish between "empty response" and "network error". Needs: error state detection + retry button UI.

2. **Check 5 — Transient retry**: Neither `settings/pretargeting` nor `analytics/home/configs` have automatic retry on failure. React Query `retry` option may not be configured, or the fetch wrappers swallow errors into empty results. Needs: `retry: 3` (or similar) with exponential backoff on these query hooks.

---

## 8) Execution Log

| Check | Tester | Start (UTC) | End (UTC) | Result | Notes |
|---|---|---|---|---|---|
| B1 Buyer-switch cache | Claude | 2026-02-17 ~04:00 | 2026-02-17 ~04:10 | **PASS** | Buyer A (1487810529) vs B (6634662463) — data always matched current buyer, no stale cross-buyer data |
| B2 Seat retry UX | Claude | 2026-02-17 ~04:10 | 2026-02-17 ~04:15 | **FAIL** | Shows "No seats connected" instead of error banner; no Retry button; 4 blocked fetches confirmed in console |
| B2 Metrics fallback | Claude | 2026-02-17 ~04:15 | 2026-02-17 ~04:20 | **PASS** | Warning banner shown ("metrics are delayed"); placeholders (`--`/`No data`) correct; wording differs from spec |
| B2 Transient retries | Claude | 2026-02-17 ~04:20 | 2026-02-17 ~04:30 | **FAIL** | 1 attempt each for pretargeting + configs; no automatic retry after 8s block lifted; page stuck in failed state 23s+ later |
| B1 Analyzer logs | Claude | 2026-02-17 ~04:30 | 2026-02-17 ~04:35 | **PASS** | 0 matches for NameError/threshold tracebacks in 30m of API logs (via IAP tunnel) |
