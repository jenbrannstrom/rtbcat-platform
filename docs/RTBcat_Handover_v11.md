# RTB.cat Creative Intelligence Platform - Handover Document v11

**Date:** January 28, 2026  
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform  
**Status:** Postgres raw fact backfill complete; QPS join verified; size/config aggregations re‑enabled (pending re‑run)  
**Developer:** Jen (jen@rtb.cat)  
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI  

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence is a **QPS optimization platform** for Google Authorized Buyers.  
The critical path is: **Gmail → Parquet → BigQuery raw_facts → Postgres → Aggregations → UI/QPS**.

**Current State (as of Jan 28, 2026):**
- ✅ Postgres schema alignment applied (migration 027)
- ✅ Raw fact tables populated in Postgres:
  - `rtb_daily` 9,082,712 rows (2026‑01‑07 → 2026‑01‑25)
  - `rtb_bidstream` 3,547,431 rows (2026‑01‑07 → 2026‑01‑25)
  - `rtb_bid_filtering` 44,936 rows (2026‑01‑13 → 2026‑01‑25)
- ✅ QPS join verification query returns valid results
- ✅ `home_publisher_daily` and `rtb_publisher_daily` populated through 2026‑01‑25
- 🔄 `home_size_daily` and `home_config_daily` re‑enabled but need re‑aggregation run
- 🔄 UI needs to consume normalized publisher list (`pretargeting_publishers`)

---

## ✅ Completed Milestones

1) **Postgres schema alignment** (`027_schema_alignment.sql`)
   - Added raw fact tables + normalized publisher targeting
   - BIGINT upgrades for aggregate counters

2) **Gmail ingest reliability**
   - Batch importer + OAuth fallback for link‑only GCS downloads

3) **Raw fact backfill**
   - BigQuery → Postgres backfill completed

4) **QPS join verified**
   - `rtb_bidstream` → `rtb_daily` join returns impressions and bid metrics

---

## 📌 Active Tasks

1) **Re‑run aggregation** now that size/config logic is corrected:
   - `home_size_daily`
   - `home_config_daily`

2) **Verify UI precompute status**
   - Ensure all `home_*_daily` and `rtb_*_daily` tables show non‑zero rows.

3) **Wire UI to normalized publisher list**
   - Use `pretargeting_publishers` endpoints in the settings UI.

---

## 🔎 Key Verification Queries

Row counts + date range:
```sql
SELECT 'rtb_daily' as table_name, COUNT(*), MIN(metric_date), MAX(metric_date) FROM rtb_daily
UNION ALL
SELECT 'rtb_bidstream', COUNT(*), MIN(metric_date), MAX(metric_date) FROM rtb_bidstream
UNION ALL
SELECT 'rtb_bid_filtering', COUNT(*), MIN(metric_date), MAX(metric_date) FROM rtb_bid_filtering;
```

QPS join check:
```sql
SELECT f.metric_date, f.publisher_id,
       SUM(f.bid_requests) as bid_requests,
       SUM(f.auctions_won) as auctions_won,
       COALESCE(SUM(d.impressions), 0) as impressions_from_daily
FROM rtb_bidstream f
LEFT JOIN rtb_daily d
  ON f.metric_date = d.metric_date
 AND f.country = d.country
 AND f.publisher_id = d.publisher_id
WHERE f.metric_date >= '2026-01-20'
  AND f.publisher_id IS NOT NULL
GROUP BY f.metric_date, f.publisher_id
ORDER BY bid_requests DESC
LIMIT 10;
```

---

## 🧪 MCP Chromium Status

See `docs/MCP_CHROMIUM.md` for the unified MCP setup.  
Current MCP URL: `http://localhost:8765/mcp`

---

## ✅ Next Steps (Order)

1) Re‑run aggregation (`scripts/bq_aggregate_to_pg.py`) for 2026‑01‑07 → 2026‑01‑25.  
2) Verify `home_size_daily` and `home_config_daily` populated.  
3) Update UI to use `pretargeting_publishers`.  
4) Add automation (daily Gmail → BQ → Postgres + aggregation).

