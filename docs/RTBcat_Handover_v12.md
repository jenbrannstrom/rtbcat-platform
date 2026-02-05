# RTB.cat Creative Intelligence Platform - Handover Document v12

**Date:** January 30, 2026
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform
**Status:** UNBLOCKED - Postgres-only migration decision; fix login loop + remove SQLite fallback
**Developer:** Jen (jen@rtb.cat)
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI

---

## ✅ Resolved Blockers (Jan 29–30)

**Breakdown endpoints fixed:** SQLite→Postgres date syntax migration completed and deployed.  
**metric_date casts:** fixed to avoid timestamp/text compare issues.  
**Integer overflow:** precompute counters migrated to BIGINT.

Commits / actions:
- SQLite→Postgres date syntax: `5bdec2a` (deployed)
- metric_date::date cast fix: `ae0ca64` (deployed)
- BIGINT migration for precompute counters: `930840b` (applied to VM Postgres)
- Win rate >100% fix (report_type filter): `cdf140d` (deployed; verified 30.9%)

---

## 🎯 Current State

**DB & Aggregations:** Up to date through Jan 28 (see Data Status below).  
**Breakdown tabs:** Postgres-only queries are correct, but login loop/empty tables can occur if `POSTGRES_SERVING_DSN` is missing in the container.  
**Publisher List UI:** Full-page editor + layout polish committed; deploy pending CI.  
**Decision:** Migrate fully to Postgres/BQ. SQLite is legacy and will be removed from serving/analytics paths.

**Open Issues (Need Root Cause):**
1) **Login loop / empty tables / slow load**  
   Cause: analytics SQL uses Postgres syntax but falls back to SQLite when `POSTGRES_SERVING_DSN` is missing.  
   Fix: pass `POSTGRES_SERVING_DSN` into API container; enforce Postgres-only for analytics.
2) **Sizes show impressions but “No creatives found for this size.”**  
   Root cause identified: `config_creative_daily` lacked `creative_size`. Fix in `services/config_precompute.py` (commit `72213ac`) — deploy + refresh needed.
3) **/creatives page fails ("Cannot connect to API server")**  
   Root cause: API 500 due to missing `creative_thumbnails` table on VM2.  
   Fix: apply Postgres migration to add `creative_thumbnails` (new migration `033_creative_thumbnails.sql`) and redeploy.
4) **Drill‑down “No precompute” for AdMob + AdSense.**  
   Likely precompute date coverage or app_name mismatch across report types; verify after Postgres-only fix.
4) ~~**Duplicate SQLite migration numbers (018/019/021)**~~
   ✅ RESOLVED: SQLite migrations archived to `docs/archive/sqlite_legacy/migrations/`.

**VM:** `catscan-production-sg` (asia-southeast1-b)
- Dashboard: pending deploy of latest Publisher List UI commits
- API: ensure `POSTGRES_SERVING_DSN` is set; otherwise analytics routes fail

---

## ✅ Next Steps (Priority Order)

1. ~~**Enforce Postgres-only analytics**~~ ✅ DONE
   - SQLite fallback removed from all analytics queries.
   - All routers now use Router→Service→Repo pattern.

2. ~~**Finish Postgres-only migration**~~ ✅ DONE
   - SQLite modules removed from runtime code.
   - SQLite migrations archived to `docs/archive/sqlite_legacy/`.

3. **Deploy UX + size drilldown fix**
   - Deploy Publisher List full-page UI: commits `1fea149`, `dffd69a`, `50db7d6`.
   - Deploy size drilldown fix in `services/config_precompute.py` (`72213ac`), then refresh config precompute.

---

## 📁 Key Paths

| Purpose | Path |
|---------|------|
| VM config | `/opt/catscan/.env` |
| Docker compose | `/opt/catscan/docker-compose.gcp.yml` |
| Image registry | `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/` |
| AI Log | `docs/ai_logs/ai_log_2026-01-30.md` |
| MCP Chrome scripts | `scripts/chrome-cdp.sh`, `scripts/mcp-chromium-cdp.sh` |
| Primary VM | `catscan-production-sg` (asia-southeast1-b) |
| Legacy VM | `catscan-production` (europe-west1-b) — do not use for Postgres |

---

## 🔧 Key Commands

```bash
# SSH to VM
gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap

# Check containers
sudo docker ps

# Check API logs
sudo docker logs catscan-api --tail 50

# Restart services
cd /opt/catscan && sudo docker compose -f docker-compose.gcp.yml up -d

# Build images: use CI (GitHub Actions) and deploy by sha tag
```

---

## 📊 Data Status (as of Jan 28)

All summary tables populated through Jan 28:
- `home_config_daily`: 391 rows
- `home_geo_daily`: 887 rows
- `home_publisher_daily`: 103,591 rows
- `home_seat_daily`: 64 rows
- `home_size_daily`: 180,555 rows
- `rtb_publisher_daily`: 103,591 rows

## 🧩 UX Commits (Pending Deploy)
- `1fea149` — Full-page Publisher List route + button wiring
- `dffd69a` — Publisher List layout polish (mode toggle dot, sticky pending)
- `50db7d6` — Final spec polish (Pending label, ID-only rows, header cleanup)

---

## 📖 Domain Terms Glossary

| Term | Meaning |
|------|---------|
| RTB | Real-Time Bidding - auction for ad impressions |
| QPS | Queries Per Second - bid requests received |
| Pretargeting | Filters that determine which bid requests you receive |
| Billing ID | Identifier for a pretargeting config |
| Creative | An ad (image, video, native) |
| Seat | A bidding entity within a buyer account |
| VAST | Video Ad Serving Template - video ad standard |
| CPM | Cost Per Mille (per 1000 impressions) |
| CTR | Click-Through Rate |
| Reached Queries | QPS that matched pretargeting filters |
| Win Rate | Impressions / Reached Queries (successful auction wins) |

---

## 📥 GMail Ingest

See **[docs/gmail-autodownload-fix-plan.md](gmail-autodownload-fix-plan.md)** for:
- Entry points and scripts
- Auth/token file paths
- GCS download behavior
- Manual batch run commands
- Auto-download scheduler setup (Cloud Scheduler)

---

## 🧪 MCP Chrome Bring-up Sequence

**Scripts:** `scripts/chrome-cdp.sh`, `scripts/mcp-chromium-cdp.sh`

**Important:** Playwright browser automation is blocked by Google OAuth. We must attach to a real Chrome profile; do NOT use Playwright to launch/login.

**Deterministic bring-up sequence:**

1. Verify CDP responds:
   ```bash
   curl -s http://127.0.0.1:9222/json/version
   ```

2. Kill stale MCP servers:
   ```bash
   pkill -f "@playwright/mcp" || true
   pkill -f "playwright-mcp" || true
   pkill -f "mcp --cdp-endpoint" || true
   ```

3. Start MCP:
   ```bash
   ./scripts/mcp-chromium-cdp.sh
   ```

4. Restart Codex CLI after MCP is running.

5. Validate via **tool usage** (e.g., screenshot), not resource listing.

**If Codex still cannot see MCP tools:**
- Use Claude CLI for browser tasks (proven working via CDP).
- Confirm Codex config uses `localhost`, not `127.0.0.1`.
