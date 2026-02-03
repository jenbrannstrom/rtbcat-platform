# VM2 UI Investigation Prompt (Amazing Mobyoung Only)

**Target:** https://vm2.scan.rtb.cat/ (image tag `sha-bb76543`)  
**Seat:** **Amazing Mobyoung ONLY** (do not open or switch to any other seats)  
**Goal:** Full UI investigation with evidence so the Architect can update:
- `ARCHITECTURE.md`
- `docs/RTBcat_Handover_v12.md`
- `docs/RTBcat_Handover_Architect.md`

This is a full, non-trivial investigation. Please follow all steps and provide the requested evidence.

---

## 0) Environment & Seat Proof
1. Open https://vm2.scan.rtb.cat/
2. Select buyer seat: **Amazing Mobyoung** only.
3. Capture:
   - Screenshot with seat dropdown open showing “Amazing Mobyoung.”
   - Buyer ID used (from UI or network payload).  
   - Current local time + timezone.

**Evidence required:**
- Screenshot: `00-seat-selection.png`
- Note: buyer_id value
- Note: date/time/timezone

---

## A) Home Header – Funnel Math & QPS Sanity
1. Record “Total QPS Allocated.”
2. Record “Reached Queries”, “Impressions”, “Win Rate.”
3. Compute: `QPS allocated × 3600 × days`.
4. Compare with “Reached Queries.”

**Evidence required:**
- Screenshot: `A-header-metrics.png`
- Calculation: expected reached vs actual reached
- Absolute and % mismatch

**Flag if:** mismatch >10%.

---

## B) Period Switch Performance (7 → 14 days)
1. Switch from 7d to 14d.
2. Time how long the UI takes to update (seconds).
3. Verify values update:
   - Header Reached Queries
   - Config totals (per billing_id row)

**Evidence required:**
- Screenshot before/after: `B-before-7d.png`, `B-after-14d.png`
- Time in seconds
- Note if only a single billing_id updates (e.g., 165882941410)

---

## C) Config List & Expansion
1. Expand the top 2 configs (highest Reached).
2. Verify Reached / Win Rate / Waste columns render.
3. Check if **Publisher List button** exists on config header.

**Evidence required:**
- Screenshot per config: `C-config1-expanded.png`, `C-config2-expanded.png`
- Note if “Publisher List” button is present (should NOT be)

---

## D) By Size Breakdown
For each of the two expanded configs:
1. Open **By Size** tab.
2. Drill‑down on a standard dimension size (e.g., 300x250 or 320x50).
3. Drill‑down on **Video** or **Interstitial** row.
4. Drill‑down on a dimension size with spend/reached (e.g., 344x648).

**Evidence required:**
- Screenshots for each drill‑down:
  - `D-config1-size-standard.png`
  - `D-config1-size-video.png`
  - `D-config1-size-dimension.png`
  - `D-config2-size-standard.png`
  - `D-config2-size-video.png`
  - `D-config2-size-dimension.png`

**Flag if:**
- Message appears: “Drill‑down is only available for dimension sizes (e.g. 300x250).”
- Dimension size shows spend/reached/imps but “No creatives found for this size.”

---

## E) By Geo Breakdown
1. Open **By Geo** tab for each of the two configs.
2. If “No geo data for this config” appears, capture it.

**Evidence required:**
- Screenshot per config: `E-config1-geo.png`, `E-config2-geo.png`
- Note the full “no data” message text

---

## F) By Publisher (Embedded in Home)
1. Open **By Publisher** tab for each of the two configs.
2. Confirm the embedded publisher list appears (same UX as `/pretargeting/{billingId}/publishers`):
   - Columns: Publisher ID, Type, Status, Action
   - Add Publisher input
3. If message says “No publisher data…” capture it.

**Evidence required:**
- Screenshot per config: `F-config1-publisher.png`, `F-config2-publisher.png`
- Note if it shows “No publisher data for this config / No precompute…”
- Confirm there is **no separate Publisher List button** in the config header

---

## G) Publisher Performance Table (if present elsewhere)
1. Find any Publisher performance table (if visible on the page).
2. Verify columns: Name, Spend, Reached, Impressions, Win Rate, plus one extra.

**Evidence required:**
- Screenshot: `G-publisher-performance.png`
- If empty, capture error/empty state text

---

## H) Creative Preview
1. From **By Creative** or **By Size** drill‑down, click “View creative.”
2. Confirm preview modal opens.

**Evidence required:**
- Screenshot: `H-preview-modal.png`
- If error: request URL, response status, console error

---

## I) Recommended Optimizations Panel
1. Confirm whether “Recommended Optimizations” is visible.

**Evidence required:**
- Screenshot: `I-recommended-optimizations.png`
- If visible, mark as bug (should be disabled)

---

# Output Format (Must Use)
For each issue, provide:

**Issue ID:**  
**Section:**  
**Steps:**  
**Expected:**  
**Actual:**  
**Evidence:** (screenshot name + short description)  
**Impact:** (data correctness / UX / performance)  

At the end, include a summary:

**Summary Table**
- Total tests passed
- Total bugs found
- Top 3 blocking issues

---

# Required Artifacts for Architect Updates
Please provide:
1. Screenshots (clearly named as above)
2. Any network logs for 500s or missing data
3. Console errors (if any)
4. Exact text of all “no data” messages

These will be used to update:
- `ARCHITECTURE.md`
- `docs/RTBcat_Handover_v12.md`
- `docs/RTBcat_Handover_Architect.md`

