# Browser Testing 1 (Mobyoung Only)

**Account:** Use **Mobyoung** only. Do not test on other seats/accounts to avoid accidental edits in Google.

## A) Home + Funnel Metrics (UI)

1) **Reached Queries label + value**
- Verify label is **Reached Queries**.
- Note value at 7 days, then switch to 14 days and confirm it changes if data exists.

2) **Win Rate**
- Confirm win rate <= 100% and consistent with impressions/reached.

3) **QPS Allocation**
- Total QPS allocated renders.
- Endpoint list shows per‑endpoint QPS.

## B) Range Change Behavior (7 → 14 days)

4) Switch to 14 days
- Reached Queries value changes for Mobyoung if data exists.
- Config list metrics update.
- Note any section that remains unchanged.

## C) By Size

5) Non‑dimension sizes (Interstitial / Video / Overlay)
- Expand a size row.
- Expect message: “Drill‑down is only available for dimension sizes (e.g. 300x250).”
- No API error should appear.

6) Dimension sizes (e.g. 300x250)
- Expand a size row.
- If “No creatives found”, capture screenshot + console errors (if any).

6.1) Size bulk toolbar placeholder
- Verify the label **“Feature #001 ROADMAP.md”** is visible next to Block/Unblock.
- Block/Unblock are placeholders (no backend yet).

## D) By Geo

7) Geo breakdown
- Check for data or accurate no‑data messaging.
- If “No geo data for this config”, confirm if API is returning data or not.

## E) By Publisher (Embedded in Home)

8) Publisher list
- Verify embedded list appears inside Home breakdown.
- Message should NOT be “No precompute available...” if data exists.
- Confirm columns display (Name, Spend, Reached, Impressions, Win Rate, plus any extra).

## F) Config Expansion

9) Expand a config
- Breakdown tabs load with no 404s.
- By Creative table layout is aligned (no broken grid).
- Creative icon click opens preview (or shows loading/error if missing).

## G) Regression Check

10) DevTools console
- No 500/400 errors during Home load.
- Watch /analytics/home/funnel, /analytics/home/configs, /settings/* requests.

---

# API cURL checks (use session cookie)

**Tip:** Use DevTools → Network → Copy as cURL for authenticated endpoints.

1) Health (no auth)
```
curl -s https://vm2.scan.rtb.cat/health | jq
```

2) Home funnel (auth)
```
curl -s "https://vm2.scan.rtb.cat/analytics/home/funnel?days=7&buyer_id=<BUYER_ID>" | jq
```
Validate:
- funnel.total_reached_queries > 0
- win_rate <= 100

Repeat with days=14 and compare.

3) Home configs (auth)
```
curl -s "https://vm2.scan.rtb.cat/analytics/home/configs?days=7&buyer_id=<BUYER_ID>" | jq
```

4) Publishers list (auth)
```
curl -s "https://vm2.scan.rtb.cat/api/settings/pretargeting/<BILLING_ID>/publishers" | jq
```

---

# DB validation (Postgres)

Run on VM2:
```
psql $POSTGRES_SERVING_DSN
```

1) Precompute tables row counts
```sql
SELECT 'home_seat_daily' as tbl, COUNT(*) cnt, MIN(metric_date), MAX(metric_date)
FROM home_seat_daily;

SELECT 'home_publisher_daily' as tbl, COUNT(*) cnt, MIN(metric_date), MAX(metric_date)
FROM home_publisher_daily;

SELECT 'home_geo_daily' as tbl, COUNT(*) cnt, MIN(metric_date), MAX(metric_date)
FROM home_geo_daily;

SELECT 'home_config_daily' as tbl, COUNT(*) cnt, MIN(metric_date), MAX(metric_date)
FROM home_config_daily;

SELECT 'home_size_daily' as tbl, COUNT(*) cnt, MIN(metric_date), MAX(metric_date)
FROM home_size_daily;
```

2) Reached vs bid requests sanity
```sql
SELECT
  SUM(reached_queries) AS reached,
  SUM(bid_requests) AS bid_requests,
  SUM(impressions) AS impressions
FROM home_seat_daily
WHERE buyer_account_id = '<BUYER_ID>'
  AND metric_date::date >= CURRENT_DATE - INTERVAL '7 days';
```
Expect: reached <= bid_requests, impressions <= reached.

3) 7d vs 14d change
```sql
SELECT
  '7d' AS window,
  SUM(reached_queries) AS reached
FROM home_seat_daily
WHERE buyer_account_id = '<BUYER_ID>'
  AND metric_date::date >= CURRENT_DATE - INTERVAL '7 days'
UNION ALL
SELECT
  '14d',
  SUM(reached_queries)
FROM home_seat_daily
WHERE buyer_account_id = '<BUYER_ID>'
  AND metric_date::date >= CURRENT_DATE - INTERVAL '14 days';
```

4) Size coverage sample
```sql
SELECT creative_size, SUM(reached_queries) AS reached
FROM home_size_daily
WHERE buyer_account_id = '<BUYER_ID>'
  AND metric_date::date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY creative_size
ORDER BY reached DESC
LIMIT 10;
```
