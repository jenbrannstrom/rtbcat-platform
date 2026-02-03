# VM2 UI Test Results - 2026-02-03

**Target:** https://vm2.scan.rtb.cat/ (image tag `sha-bb76543`)
**Seat:** Amazing MobYoung (Buyer ID: 6634662463)
**Tester:** Claude + User (collaborative via CDP)
**Date/Time:** 2026-02-03 ~14:00-15:00 SGT (UTC+8)

---

## 0) Environment & Seat Proof ✅

- **Seat:** Amazing MobYoung (selected from dropdown)
- **Buyer ID:** 6634662463
- **Available Seats:** All Seats (1653), Amazing Design Tools LLC (304), Amazing Moboost (449), Amazing MobYoung (35), Tuky Display (865)
- **Version:** sha-bb76543

---

## A) Home Header – Funnel Math & QPS Sanity ⚠️

| Metric | Value |
|--------|-------|
| Asia QPS | 22,142 |
| Europe QPS | 4,428 |
| US East QPS | 4,428 |
| **Total QPS Allocated** | **30,998** |
| **Reached Queries** | **51.5M** |
| **Impressions** | **11.7M** |
| **Win Rate** | **22.7%** |

### Calculation
- Expected Reached (7 days): `30,998 × 3,600 × 24 × 7 = 18.75B`
- Actual Reached: 51.5M
- **Utilization: 0.27%**

### Flag
⚠️ This is expected behavior (QPS Allocated = capacity, Reached = actual matched queries), but needs documentation/tooltip.

---

## B) Period Switch Performance ⏭️ SKIPPED

---

## C) Config List & Expansion ✅ with bugs

### Configs Found (4 active)

| Config ID | Geo | Reached | Win Rate | Waste |
|-----------|-----|---------|----------|-------|
| 168508984471 | PHL | 2.8M | 10.0% | 90.0% |
| 164717596699 | PAK | 303.9K | 16.4% | 83.6% |
| 165882941410 | VNM | 24.2M | 28.6% | 71.4% |
| 168466702314 | IND | 45.7M | 40.9% | 59.1% |

### VNM Config Expanded (165882941410)
- Geos: VNM | Formats: HTML | Platforms: PHONE | Sizes: 320×50, 300×250
- Reached: 24.2M | Impressions: 6.9M | Win Rate: 28.6% | Waste: 71.4%

### Bug C-001: Publisher List Button in Header
- **Issue:** "Publisher List" button appears in config header
- **Expected:** Should only be accessible via "By Publisher" tab
- **Impact:** UX confusion - redundant navigation

---

## D) By Size Breakdown ⚠️ BUGS

### Bug D-001: Table Layout Broken
- **Issue:** Table columns stack vertically instead of horizontally
- **Expected:** Proper table grid with columns side by side
- **Actual:** Name on left, all data (Spend, Reached, Imp, Win Rate) stacked vertically on right
- **Impact:** Data hard to read/compare

### Data Captured (despite broken layout)

| Size | Spend | Reached | Imp | Win Rate |
|------|-------|---------|-----|----------|
| Video/Overlay | $376 | 13.9M | 3.3M | 23.8% |
| 320×50 | $158 | 3.3M | 1.4M | 43.4% |
| Interstitial | $128 | 2.5M | 160.8K | 6.4% |
| 360×56 | $73.65 | 1.6M | 730.6K | 44.7% |
| 384×60 | (visible) | | | |

### Drill-down Tests

**320×50 drill-down:**
- Shows: Creative | Country targeted | Preview columns
- Message: "No creatives found for this size."
- ⚠️ FLAG: Has spend/reached but no creatives linked

**Video/Overlay drill-down:**
- Shows: Same drill-down panel
- Message: "No creatives found for this size."
- ⚠️ DISCREPANCY: Expected "Drill-down is only available for dimension sizes" but got same panel

---

## E) By Geo Breakdown ✅

- **Message:** "No geo data for this config"
- **Sub-message:** "No precompute available for requested date range. Run a config refresh after imports."

Matches expected behavior.

---

## F) By Publisher (Embedded in Home) ✅

- **Mode:** "Blacklist: 0 blocked"
- **Table columns:** Publisher ID | Type | Status | Action
- **Message:** "No publishers blocked yet."
- **Add input:** "Add publisher to block:" with placeholder + button

Confirms the embedded publisher list works correctly. Bug C-001 stands - the separate "Publisher List" button in header is redundant.

---

## G) Publisher Performance Table ⏭️ SKIPPED

---

## H) Creative Preview ❌ CRITICAL BUGS

### Bug H-001: Creative Names Not Clickable
- **Location:** Home → Config → By Creative tab
- **Issue:** Clicking creative name does nothing
- **Expected:** Should open preview modal
- **Actual:** No response to click
- **Note:** No "Preview" column visible, no scroll-right option

### Bug H-002: /creatives Page Fails
- **Location:** Sidebar → Creatives
- **Error:** "Something went wrong - Cannot connect to API server. Please ensure the backend is running on port 8000."
- **Impact:** CRITICAL - entire page non-functional
- **Note:** Home page works, so API is partially up. Specific endpoint issue.

---

## I) Recommended Optimizations Panel ⚠️ BUG

### Bug I-001: Panel Visible (Should Be Disabled)
- **Issue:** Panel shows despite ROADMAP.md saying it should be disabled
- **Visible content:**
  - "2 actions" badge
  - AI Mode selector: Manual | AI | Auto-optimize
  - "Config unknown performing below threshold" (9.0% vs 21.0% avg)
  - "Config 168508984471 performing below threshold" (10.0% vs 21.0% avg)
  - Approve buttons per recommendation

---

## Summary

| Section | Status | Issues |
|---------|--------|--------|
| 0) Environment | ✅ PASS | - |
| A) Header Metrics | ⚠️ FLAG | QPS mismatch needs tooltip |
| B) Period Switch | ⏭️ SKIP | - |
| C) Config Expansion | ⚠️ BUG | C-001: Publisher List button redundant |
| D) By Size | ❌ BUG | D-001: Table layout broken |
| E) By Geo | ✅ PASS | - |
| F) By Publisher | ✅ PASS | - |
| G) Publisher Perf | ⏭️ SKIP | - |
| H) Creative Preview | ❌ CRITICAL | H-001: Click no-op, H-002: Page fails |
| I) Recommendations | ⚠️ BUG | I-001: Panel visible (should be hidden) |

### Totals
- **Passed:** 4
- **Bugs Found:** 5 (2 critical)
- **Skipped:** 3

### Top 3 Blocking Issues

1. **H-002 (CRITICAL):** /creatives page fails - "Cannot connect to API server"
2. **D-001:** By Size table layout completely broken - columns stack vertically
3. **H-001:** Creative names not clickable in By Creative tab - no preview possible

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `/tmp/00-seat-dropdown.png` | Seat selection dropdown |
| `/tmp/A-home-loaded.png` | Home page with header metrics |
| `/tmp/by-size-fullscreen.png` | By Size tab (broken layout) |
| `/tmp/size-320x50-drilldown.png` | 320×50 drill-down |
| `/tmp/size-video-drilldown.png` | Video/Overlay drill-down |
| `/tmp/by-geo.png` | By Geo tab (no data message) |
| `/tmp/by-publisher.png` | By Publisher tab (embedded list) |
| `/tmp/by-creative-click.png` | By Creative tab |
| `/tmp/creatives-page.png` | /creatives page error |
| `/tmp/home-final.png` | Final Home state |

---

## Action Items

1. **FIX D-001:** By Size table CSS - columns rendering vertically
2. **FIX H-002:** Investigate /creatives API endpoint failure
3. **FIX H-001:** Add click handler to creative names OR add Preview column
4. **FIX I-001:** Disable Recommended Optimizations panel per ROADMAP
5. **FIX C-001:** Remove redundant "Publisher List" button from config header
6. **DOC A-001:** Add tooltip explaining QPS Allocated vs Reached Queries relationship
