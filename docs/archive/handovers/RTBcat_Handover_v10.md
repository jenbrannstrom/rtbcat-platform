# RTB.cat Creative Intelligence Platform - Handover Document v10

**Date:** January 27, 2026  
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform  
**Status:** Postgres migration in progress (blocking precompute); MCP Chrome running on localhost:8765 but Codex visibility still flaky; UI precompute status bug fixed locally  
**Developer:** Jen (jen@rtb.cat)  
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI  
**Latest Updates:** Postgres serving precompute status bug fixed; MCP Chrome server running with localhost allowlist; GMail ingest attempted but failed due to schema readiness; Claude CLI can access MCP Chrome for screenshots

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence is a **comprehensive RTB (Real-Time Bidding) analytics platform** that helps media buyers optimize their programmatic advertising spend by:

1. **Collecting creatives** from Google Authorized Buyers API
2. **Importing performance data** from CSV exports (BigQuery or UI)
3. **Detecting fraud patterns** in traffic (click fraud, bot traffic)
4. **Clustering creatives into campaigns** using AI
5. **Optimizing QPS** by analyzing size coverage and pretargeting efficiency
6. **Identifying opportunities** (undervalued sizes, cheap inventory)

**Current State:**
- ✅ Postgres instance set up on Singapore VM (per report)
- ✅ MCP Chrome server listening on `localhost:8765` (required by host allowlist)
- ⚠️ Codex CLI still fails to see MCP tools reliably; Claude CLI can access MCP Chrome
- ⚠️ GMail ingest run but failed with many errors (schema not fully ready)
- ⚠️ UI shows “No precomputed data for this seat. Run a refresh after imports.” on all tables
- ✅ Bug fix applied locally: precompute status now checks Postgres table existence (not SQLite)
- 🔄 Need DSNs + verify Postgres data + run precompute refresh successfully

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What’s New in v10](#whats-new-in-v10)
3. [Postgres Migration Status](#postgres-migration-status)
4. [Precompute Status Issue](#precompute-status-issue)
5. [MCP Chrome Status](#mcp-chrome-status)
6. [Known Issues & Bugs](#known-issues--bugs)
7. [Server Management](#server-management)
8. [File Locations](#file-locations)
9. [Next Steps](#next-steps)

---

## 🚀 Quick Start

### System Status (local or VM)

```bash
# Backend service (if systemd managed)
sudo systemctl status rtbcat-api

# Backend health
curl http://localhost:8000/health

# Frontend (local dev)
cd /home/x1-7/Documents/rtbcat-platform/dashboard
npm run dev

# Access Points
Dashboard: http://localhost:3000
API Docs: http://localhost:8000/docs
```

### Postgres sanity checks (when DSNs known)

```bash
# Check schema migrations status
POSTGRES_DSN=... python scripts/postgres_migrate.py --status

# Check precompute tables
psql $POSTGRES_SERVING_DSN -c "SELECT COUNT(*), MAX(metric_date) FROM home_publisher_daily;"
psql $POSTGRES_SERVING_DSN -c "SELECT COUNT(*), MAX(metric_date) FROM rtb_publisher_daily;"

# Check precompute refresh log
psql $POSTGRES_SERVING_DSN -c "SELECT * FROM precompute_refresh_log ORDER BY completed_at DESC LIMIT 5;"
```

---

## 🆕 What’s New in v10

### 1. Postgres precompute status bug fix ✅

**Problem:** API precompute status checks always queried SQLite’s `sqlite_master`, so Postgres-backed tables were considered “missing,” resulting in UI messages:
- “No precomputed data for this seat. Run a refresh after imports.”

**Fix:** `get_precompute_status()` now uses `storage.serving_database.table_exists()` to check Postgres tables when serving DB is configured.

**File:** `api/routers/analytics/common.py`

### 2. MCP Chrome server already running ✅

- `./scripts/mcp-chromium-cdp.sh` runs:
  `playwright-mcp --cdp-endpoint ... --host localhost --port 8765 --allowed-hosts "*"`
- Host allowlist rejects `127.0.0.1`; must use `localhost`.
- `~/.codex/config.toml` should include:
  ```toml
  [mcpServers.chromium]
  url = "http://localhost:8765/mcp"
  ```
- Action: restart Codex CLI to pick up the MCP server (Codex reads config only at startup).

### 3. GMail ingest failed ⚠️

- GMail ingest was run but failed due to schema not fully ready.
- This likely means downstream precompute refresh had insufficient raw data.

---

## 🧱 Postgres Migration Status

**Runbook:** `docs/POSTGRES_MIGRATION_RUNBOOK.md`

**Reported Completed:**
- Postgres instance setup on Singapore VM

**Unknown / Needs Verification:**
- Whether Postgres migrations have run (`scripts/postgres_migrate.py --status`)
- Whether raw data successfully loaded into BigQuery
- Whether precompute refresh ran and populated Postgres tables

---

## 📉 Precompute Status Issue

**Observed:**
- UI shows “No precomputed data for this seat. Run a refresh after imports.” across tables.
- “By Publishers” nested table in Pretargeting shows no data.
- “Refresh” action does nothing.

**Likely causes (in order):**
1. **Bug fixed locally:** precompute table existence check used SQLite.
2. **Serving DSN not configured:** `serving_postgres_dsn` missing in encrypted config.
3. **Precompute tables empty:** refresh jobs ran but produced no rows.
4. **BigQuery raw tables incomplete:** GMail ingest failed and schema not ready.

**Latest verification (Jan 27, 2026):**
- `home_publisher_daily` count = 0, max(metric_date) = NULL (table empty)
- `rtb_publisher_daily` count = 0, max(metric_date) = NULL (table empty)
- `precompute_refresh_log` has two rows for `config_breakdowns` and `home_summaries` with refreshed_at `2026-01-25` covering `2025-12-27` → `2026-01-25`
- Conclusion: precompute refresh ran but produced zero rows; data upstream is likely missing

**BigQuery raw data verification (Jan 27, 2026):**
- Project: `catscan-prod-202601`, Dataset: `rtbcat_analytics`
- Tables present:
  - `rtb_daily`: 579,976 rows; date range `2026-01-07` → `2026-01-13` (only 7 days)
  - `rtb_bidstream`: 0 rows (empty)
  - `raw_facts`: 383,297 rows; date range `2026-01-11` → `2026-01-23` (13 days)
- Missing tables: `rtb_bid_filtering`, `rtb_quality`, `rtb_traffic`
- Conclusion: BigQuery source tables are incomplete/empty, which explains empty Postgres precompute tables

**Files to inspect:**
- `storage/serving_database.py`
- `api/routers/analytics/common.py`
- `services/home_precompute.py`, `services/rtb_precompute.py`, `services/config_precompute.py`

---

## 📥 GMail Ingest Operational Plan

**Constraints:**
- 200+ emails, some with GCS download links and large attachments.
- Avoid long-lived interactive terminals (prior crashes).

**Guidelines:**
1. Use a non-interactive runner (`nohup` or systemd) with log file output.
2. Add checkpointing to skip already processed messages.
3. Prefer batched downloads (size-checked) and retry with backoff.
4. Keep a single "ingest state" file with last processed message ID and summary.

**Confirmed entry points:**
- Primary: `scripts/gmail_import.py` (`run_import()`)
- Batch wrapper (new): `scripts/gmail_import_batch.py` (calls into `gmail_import.py`)
- API endpoint: `api/routers/gmail.py` (`POST /gmail/import`)

**Auth/token handling:**
- Token: `~/.catscan/credentials/gmail-token.json`
- Client secret: `~/.catscan/credentials/gmail-oauth-client.json`
- Scope: `gmail.modify` (read + mark as read)
- Tokens auto-refresh and are saved back to disk during long runs.

**GCS download behavior (current):**
- Extracts GCS URL from email body; converts `storage.cloud.google.com` → `storage.googleapis.com`.
- Signed URLs download directly; unsigned use OAuth Bearer token.
- Streams in 1MB chunks; validates first line is not HTML/binary.
- Timeout 60s, no retries (single attempt).

**Batch run commands (SG VM):**
```bash
cd /opt/catscan && git pull
nohup python3 scripts/gmail_import_batch.py --batch-size 10 >> ~/.catscan/logs/gmail_batch.log 2>&1 &
tail -f ~/.catscan/logs/gmail_batch.log
python3 scripts/gmail_import_batch.py --status
cat ~/.catscan/gmail_batch_checkpoint.json
```

**Checkpoint file:** `~/.catscan/gmail_batch_checkpoint.json` (tracks processed/failed message IDs).

**Recommended patch (GCS download retries):**
- Add exponential backoff for `download_from_url` in `scripts/gmail_import.py`.
- Increase timeout to 120s for large files.
- Retry 429/5xx up to 3 times; fail fast on other 4xx.

---

## 🧪 MCP Chrome Status

**Docs:** Use `scripts/chrome-cdp.sh` + `scripts/mcp-chromium-cdp.sh` (no dedicated doc).

**Current:**
- Server is listening on `http://localhost:8765` and attached to Chrome CDP (`http://127.0.0.1:9222/json/version`).
- Chrome is kept running by `scripts/chrome-cdp.sh` (auto-restarts Chrome with remote debugging and profile `/home/x1-7/.catscan/chrome-profile`).
- MCP process is running via `playwright-mcp` and attached to CDP.
- **Important:** Playwright browser automation is blocked by Google OAuth. We must attach to a real Chrome profile; do NOT use Playwright to launch/login.
- **Codex caveat:** MCP is tool-based; `list_mcp_resources` can be empty even when tools work.

**Deterministic bring-up sequence:**
1) CDP responds:
   - `curl -s http://127.0.0.1:9222/json/version`
2) Kill stale MCP servers:
   - `pkill -f "@playwright/mcp" || true`
   - `pkill -f "playwright-mcp" || true`
   - `pkill -f "mcp --cdp-endpoint" || true`
3) Start MCP:
   - `./scripts/mcp-chromium-cdp.sh`
4) Restart Codex CLI after MCP is running.
5) Validate via **tool usage** (e.g., screenshot), not resource listing.

**If Codex still cannot see MCP tools:**
- Use Claude CLI for browser tasks (proven working via CDP).
- Confirm Codex config uses `localhost`, not `127.0.0.1`.

---

## 🐞 Known Issues & Bugs

1. **Precompute status false-negative (fixed locally)**
   - UI says no precompute due to SQLite check; now fixed in `api/routers/analytics/common.py`.
2. **Precompute tables empty**
   - Root cause unknown until DSNs + Postgres checks.
3. **GMail ingest errors**
   - Failed due to schema readiness; likely blocking raw data completeness.
4. **MCP Chrome docs partially inaccurate**
   - Port already in use; config already present.
5. **SG API container still using SQLite (fixed in compose patch)**
   - `docker-compose.gcp.yml` forced `DATABASE_PATH`; DSNs in `/opt/catscan/.env` were ignored.
   - Patch adds `env_file: .env` and `POSTGRES_DSN`/`POSTGRES_SERVING_DSN`, removing `DATABASE_PATH`.

---

## 🖥 Server Management

- **API Startup:** `api/main.py` loads encrypted config and uses `serving_postgres_dsn` to route precompute queries to Postgres.
- **Serving DB routing:** `storage/serving_database.py` uses Postgres for precompute tables if `POSTGRES_SERVING_DSN` is configured.

### SG VM: Docker Compose patch to use Postgres

**File:** `/opt/catscan/docker-compose.gcp.yml`

**Diff (summary):**
- Add `env_file: .env` to load `/opt/catscan/.env`
- Remove `DATABASE_PATH` (forces SQLite)
- Add `POSTGRES_DSN` and `POSTGRES_SERVING_DSN` env vars

**Restart commands (SG VM):**
```bash
cd /opt/catscan
sudo docker compose -f docker-compose.gcp.yml down
sudo docker compose -f docker-compose.gcp.yml up -d
sudo docker logs -f catscan-api
```

**Verification:**
```bash
sudo docker exec catscan-api env | grep -i postgres
curl http://localhost:8000/health
```

---

## 📁 File Locations

- Postgres migration runbook: `docs/POSTGRES_MIGRATION_RUNBOOK.md`
- MCP Chrome notes: see `scripts/chrome-cdp.sh` + `scripts/mcp-chromium-cdp.sh`
- Precompute refresh script: `scripts/refresh_precompute.py`
- Precompute helpers: `services/home_precompute.py`, `services/rtb_precompute.py`, `services/config_precompute.py`
- Serving DB router: `storage/serving_database.py`
- Precompute status logic: `api/routers/analytics/common.py`

---

## ✅ Next Steps

1. Restart API to pick up precompute status fix.
2. Restart Codex CLI to attach to MCP Chrome server; validate by tool usage (screenshot) not resources.
3. Retrieve `POSTGRES_DSN` and `POSTGRES_SERVING_DSN`.
4. Run Postgres checks (counts + refresh log) to confirm whether tables are populated.
5. If tables are empty, rerun precompute refresh after confirming BigQuery raw tables and schema readiness.
