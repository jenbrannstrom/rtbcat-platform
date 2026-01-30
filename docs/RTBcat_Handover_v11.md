# RTB.cat Creative Intelligence Platform - Handover Document v11

**Date:** January 30, 2026
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform
**Status:** UNBLOCKED - DB fixes complete; focus shifts to UX + metric correctness
**Developer:** Jen (jen@rtb.cat)
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI

---

## ✅ Resolved Blockers (Jan 29)

**Breakdown endpoints fixed:** SQLite→Postgres date syntax migration completed and deployed.  
**metric_date casts:** fixed to avoid timestamp/text compare issues.  
**Integer overflow:** precompute counters migrated to BIGINT.

Commits / actions:
- SQLite→Postgres date syntax: `5bdec2a` (deployed)
- metric_date::date cast fix: `ae0ca64` (deployed)
- BIGINT migration for precompute counters: `930840b` (applied to VM Postgres)

---

## 🎯 Current State

**DB & Aggregations:** Up to date through Jan 28 (see Data Status below).  
**Breakdown tabs:** load with data (confirmed via MCP).  
**Publisher List UI (Task B):** UX refinements committed and pushed; deploy pending CI.  

**Open Issues (Need Root Cause):**
1) **Win Rate > 100%** (e.g., Reached 33.2M, Impressions 68.4M, Win Rate 205.9%).  
   Likely mismatched data sources (rtb_daily vs rtb_bidstream) or join fan‑out.
2) **Sizes show impressions but “No creatives found for this size.”**  
   Likely size normalization mismatch or creative_id/join gaps between creatives and performance rows.
3) **Drill‑down “No precompute” for AdMob + AdSense.**  
   Likely precompute date coverage or app_name mismatch across report types.

**VM:** `catscan-production-sg` (asia-southeast1-b)
- Dashboard: `sha-67e6658` ✅
- API: `sha-b719926` (partial fix)

---

## ✅ Next Steps (Priority Order)

1. **Investigate Win Rate > 100%**
   - Identify exact endpoint/query computing win_rate.
   - Verify numerator/denominator sources and join keys.
   - Fix computation to use aligned grain (prefer single table).

2. **UX Changes**
   - Proceed with publisher list UX per `docs/ui-publisher-list-management.md`.
   - Use MCP Chrome for visual validation if available.
   - Deploy dashboard after CI: commits `b8112a6` and `fa7295b`.

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
- `b8112a6` — Add publisher list entry + tabbed editor
- `fa7295b` — Publisher list UX refinements (name+ID, Apply CTA, Sync button)
