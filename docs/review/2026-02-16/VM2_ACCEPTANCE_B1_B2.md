# VM2 Acceptance Checklist (B1 + B2)

**Date:** 2026-02-17  
**Target branch:** `unified-platform`  
**Target commit:** `b45644c`  
**Scope:** Validate B1 (crash/cache guardrails) and B2 (dashboard reliability)

---

## 1) Test Setup

- [ ] Open VM2 dashboard in Chrome.
- [ ] Open DevTools -> Network.
- [ ] Enable `Preserve log`.
- [ ] Disable browser cache.
- [ ] Network filter set to:
  - `qps-summary|spend-stats|settings/pretargeting|analytics/home/configs|seats`

---

## 2) B1 Check: Buyer-Switch Cache Integrity

### Steps

- [ ] Select buyer A and wait for data load.
- [ ] Switch to buyer B.
- [ ] Confirm request exists:
  - `/api/analytics/qps-summary?...buyer_id=<buyerB>`
- [ ] Switch back to buyer A.
- [ ] Confirm values and requests are buyer-specific (no cross-buyer stale data).

### Pass Criteria

- [ ] QPS summary always matches current selected buyer.

---

## 3) B2 Check: Seat Init Failure + Retry UX

### Steps

- [ ] In DevTools request blocking, add `/api/seats*`.
- [ ] Hard refresh page.
- [ ] Confirm error banner appears:
  - `Unable to load buyer seats. Retry to continue.`
- [ ] Remove blocking rule.
- [ ] Click `Retry`.
- [ ] Confirm seats load and page recovers.

### Pass Criteria

- [ ] Seat error state is explicit and recoverable via retry.

---

## 4) B2 Check: Config Metrics Fallback Is Not Misleading

### Steps

- [ ] Block `/api/analytics/home/configs*`.
- [ ] Refresh page.
- [ ] Confirm warning appears:
  - `Config performance metrics failed to load; showing config list without performance values.`
- [ ] Confirm config cards show placeholders (`--` / `No data`) instead of synthetic zero performance.
- [ ] Unblock request and refresh.
- [ ] Confirm real values return.

### Pass Criteria

- [ ] No fake zero-performance values are shown when config metrics are unavailable.

---

## 5) B2 Check: Transient Retry Behavior

### Steps

- [ ] Temporarily block:
  - `/api/settings/pretargeting*`
  - `/api/analytics/home/configs*`
- [ ] Refresh page, then remove blocks after initial failures.
- [ ] Confirm automatic retry attempts occur and calls recover without manual refresh.

### Pass Criteria

- [ ] Transient failures self-recover via retry policy.

---

## 6) B1 Check: No Analyzer NameError in API Logs

Run on VM2 host:

```bash
docker compose logs api --since 30m | rg -n "NameError|LOW_WIN_RATE_THRESHOLD|HIGH_WASTE_RATE_THRESHOLD|Traceback"
```

### Pass Criteria

- [ ] No NameError / threshold-related traceback appears after exercising dashboard/recommendation flows.

---

## 7) Final Go/No-Go

- [ ] All sections 2-6 pass.
- [ ] Outcome: **GO to B3 implementation**
- [ ] If any fail, record exact endpoint/screen/trace and keep status **NO-GO** until fixed.

---

## 8) Execution Log

| Check | Tester | Start (UTC) | End (UTC) | Result | Notes |
|---|---|---|---|---|---|
| B1 Buyer-switch cache |  |  |  |  |  |
| B2 Seat retry UX |  |  |  |  |  |
| B2 Metrics fallback |  |  |  |  |  |
| B2 Transient retries |  |  |  |  |  |
| B1 Analyzer logs |  |  |  |  |  |

