# RTB.cat Creative Intelligence Platform - Handover Document v11

**Date:** January 30, 2026
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform
**Status:** Publisher list UI wired; aggregations fixed and current through Jan 28; MCP testing pending
**Developer:** Jen (jen@rtb.cat)
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence is a **QPS optimization platform** for Google Authorized Buyers.
The critical path is: **Gmail → Parquet → BigQuery → Postgres → Aggregations → UI/QPS**.

**Current State (as of Jan 30, 2026):**
- ✅ Publisher list UI wired to `/settings/pretargeting/{billing_id}/publishers` endpoint (commit `11cb55f`)
- ✅ All aggregations fixed - switched from `raw_facts` to `rtb_daily`/`rtb_bidstream`
- ✅ BigQuery data current through Jan 28 (rtb_daily: 1.4M rows for Jan 28)
- ✅ Postgres summary tables populated through Jan 28
- ✅ Gmail import fix deployed (timeouts for parquet pipeline)
- 🔄 UI changes need deployment to VM for testing
- 🔄 MCP Chrome testing pending (need to restart Claude with MCP tools)

---

## ✅ Completed Milestones (Jan 29-30)

1. **Gmail Import Fix** (commit `f2be2fc`)
   - Added timeouts to GCS upload (5min) and BigQuery load (10min)
   - Fixed hanging on large parquet files

2. **Aggregation Fixes** (commits `8fc2c5c`, `a9ddb6a`)
   - Switched `home_size_daily` and `home_config_daily` from `raw_facts` to `rtb_daily`
   - Switched `home_geo_daily`, `home_seat_daily`, `home_publisher_daily`, `rtb_publisher_daily` from `raw_facts` to `rtb_bidstream`
   - Removed obsolete `report_type` filters

3. **Publisher List UI Wiring** (commit `11cb55f`)
   - Added API functions: `getPretargetingPublishers`, `addPretargetingPublisher`, `removePretargetingPublisher`
   - Status chips: Active (green), Pending Add (yellow), Pending Remove (red)
   - Source chips: API (blue), User (purple)
   - Counts by status in section header
   - Pending changes bar directing to "Push to Google" button

4. **BigQuery Schema Fix**
   - Added `report_type` STRING column to `rtb_daily` table (was blocking parquet loads)

---

## 📊 Current Data Status

**BigQuery (Jan 28 data):**
| Table | Jan 28 Rows |
|-------|-------------|
| rtb_daily | 1,385,922 |
| rtb_bidstream | 979,360 |
| rtb_bid_filtering | 18,025 |

**Postgres Summary Tables:**
| Table | Rows | Date Range |
|-------|------|------------|
| home_config_daily | 391 | Jan 7-28 |
| home_geo_daily | 887 | Jan 7-28 |
| home_publisher_daily | 103,591 | Jan 13-28 |
| home_seat_daily | 64 | Jan 7-28 |
| home_size_daily | 180,555 | Jan 7-28 |
| rtb_publisher_daily | 103,591 | Jan 13-28 |

---

## 📌 Active Tasks

1. **Deploy UI changes to VM**
   - Commit `11cb55f` not yet deployed
   - VM running older dashboard image

2. **MCP Chrome Testing**
   - Need to restart Claude with MCP tools configured
   - Launch Chrome with: `google-chrome --remote-debugging-port=9222`
   - Test publisher list UI at scan.rtb.cat

3. **TypeScript Verification**
   - Dashboard `node_modules` missing locally
   - Run `npm install` before next Claude session (memory intensive)

---

## 🧪 MCP Chromium Setup

**Before starting Claude session:**
```bash
# 1. Launch Chrome with debugging
google-chrome --remote-debugging-port=9222

# 2. Start MCP server (from repo root)
./scripts/mcp-chromium-cdp.sh

# 3. Verify
curl http://127.0.0.1:9222/json/version
curl http://localhost:8765/health
```

See `docs/MCP_CHROMIUM.md` for full setup.

---

## 🖥️ VM Status

**SG VM (`catscan-production-sg`):**
```
catscan-dashboard   Up (port 3000, localhost only)
catscan-api         Up (port 8000, localhost only)
```

**Access via SSH tunnel:**
```bash
gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b \
  --tunnel-through-iap -- -L 3000:localhost:3000 -N
```

---

## ✅ Next Steps (Order)

1. **Before next Claude session:**
   - Run `cd dashboard && npm install` locally
   - Launch Chrome with `--remote-debugging-port=9222`

2. **In next Claude session:**
   - Deploy commit `11cb55f` to VM
   - Test publisher list UI with MCP Chrome
   - Verify status/source chips render correctly

3. **Future:**
   - Add automation (daily Gmail → BQ → Postgres + aggregation)
   - Publisher name enrichment in UI

---

## 🔗 Key Files

| Purpose | File |
|---------|------|
| Publisher list UI | `dashboard/src/components/rtb/pretargeting-settings-editor.tsx` |
| Publisher API | `dashboard/src/lib/api/settings.ts` |
| UI Spec | `docs/ui-publisher-list-management.md` |
| AI Log | `docs/ai_logs/ai_log_2026-01-29.md` |
| MCP Setup | `docs/MCP_CHROMIUM.md` |
