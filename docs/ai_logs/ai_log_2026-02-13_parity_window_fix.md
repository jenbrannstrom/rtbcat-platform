# RCA Findings (First Principles) for Billing ID 6634662463

Date: 2026-02-13
Scope: Why AB UI and CatScan looked inconsistent for MobYoung (Amazing Mingle), and what was changed.

## 1) Same label, different math
- CatScan "Win rate" on this page was computed as:
  - `impressions / reached_queries`
- AB "Win rate" is auction-funnel based (not the same denominator).
- So even with perfect data freshness, these percentages do not match 1:1.

Consequence:
- CatScan showed ~44.3% because it was a delivery ratio.
- AB can show a much lower value (for example ~17%) because auction-funnel denominators are larger/different.

## 2) Data freshness mismatch (as of 2026-02-13)
- UI requested window included dates through **2026-02-13**.
- Source tables were not equally fresh:
  - `home_seat_daily` lagged further behind
  - `rtb_bidstream` lagged behind
  - other tables had different max dates
- This means a card can appear to represent "through Feb 13" while parts of the data actually stop earlier.

Consequence:
- The screen looked internally inconsistent because different cards were effectively reading different "as-of" dates.

## 3) Off-by-one date window bug
- Previous SQL used:
  - `metric_date >= (today - days)`
- For `days=7`, this includes 8 calendar dates (today plus 7 prior days).

Consequence:
- Aggregates were inflated compared to strict 7-day expectations.
- Comparing CatScan to AB (or to ad-hoc SQL) was harder and sometimes misleading.

## What was changed in code

Commit: `3acf529`

1. Strict N-day inclusive windows everywhere relevant
- Replaced cutoff logic with exact bounds and `BETWEEN start AND end` in:
  - `storage/postgres_repositories/home_repo.py`
  - `storage/postgres_repositories/analytics_repo.py`

2. Explicit metric semantics in API response
- Endpoint efficiency payload now returns:
  - `delivery_win_rate_pct` (impressions/reached)
  - AB-style parity metrics from `rtb_bidstream`:
    - bids
    - bids_in_auction
    - auctions_won
    - filtered_bids
    - filtered_bid_rate_pct
    - auction win rates

3. Truthful data coverage metadata
- API now returns `data_coverage` with:
  - requested window
  - actual coverage (`start_date`, `end_date`, `days_with_data`) for `home_seat_daily`
  - actual coverage for `rtb_bidstream`

4. UI copy corrected to avoid falsehood
- Header/panel now show:
  - requested window
  - delivery data through date
  - auction-funnel data through date
- Old ambiguous "Win rate" wording was clarified:
  - `Delivery Win (Impr/Reached)`
- AB-parity metrics are shown separately.

## Net effect
- Users can now see both:
  - what period they asked for
  - what period the data actually covers
- CatScan no longer implies full coverage through Feb 13 when source data is stale.
- Metric disagreements with AB are now explainable by explicit formulas, not hidden assumptions.

## Verification status in this environment
- Python compile checks passed for changed backend files.
- Frontend `next` tooling is broken in this local env (module/bin issues), so full Next lint/build was not executable here.
- Deploy verification should be run on VM as normal.
