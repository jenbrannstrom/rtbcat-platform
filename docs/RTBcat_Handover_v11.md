# RTB.cat Creative Intelligence Platform - Handover Document v11

**Date:** January 30, 2026
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform
**Status:** BLOCKED - SQLite→Postgres date syntax migration incomplete
**Developer:** Jen (jen@rtb.cat)
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI

---

## 🚨 CRITICAL BLOCKER

**API returns 500 errors** on breakdown endpoints due to SQLite date syntax in Postgres:
```
operator does not exist: text >= timestamp without time zone
```

### Files Needing Fix (SQLite → Postgres)

| File | Occurrences | Status |
|------|-------------|--------|
| `api/routers/analytics/rtb_bidstream.py` | 23 | ✅ Fixed (commit `b719926`) |
| `api/routers/analytics/home.py` | 6 | ❌ Needs fix |
| `api/routers/analytics/spend.py` | 3 | ❌ Needs fix |
| `api/routers/analytics/common.py` | 1 | ❌ Needs fix |
| `api/routers/creatives.py` | 5 | ❌ Needs fix |
| `api/campaigns_router.py` | 1 | ❌ Needs fix |
| `api/routers/performance.py` | 1 | ❌ Needs fix |

### The Fix
Replace:
```sql
date('now', ?)           →  (CURRENT_DATE + ?::interval)
date('now', '-7 days')   →  (CURRENT_DATE - INTERVAL '7 days')
```

---

## 🎯 Current State

**Publisher List UI (Task B):** Code complete, deployed as `sha-67e6658`
- Cannot visually test until API fix is deployed

**API:** Partially fixed, deployed as `sha-b719926`
- Breakdown tables still fail due to unfixed files

**VM:** `catscan-production-sg` (asia-southeast1-b)
- Dashboard: `sha-67e6658` ✅
- API: `sha-b719926` (partial fix)

---

## ✅ Next Steps (Priority Order)

1. **Fix remaining SQLite date syntax** in 6 API files listed above

2. **Build and deploy API:**
   ```bash
   git add -A && git commit -m "Fix SQLite to Postgres date syntax in remaining files"
   gcloud builds submit --tag europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-api:sha-NEWCOMMIT .
   ```

3. **Deploy to VM:**
   ```bash
   gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap
   cd /opt/catscan
   sudo sed -i 's/IMAGE_TAG=.*/IMAGE_TAG=sha-NEWCOMMIT/' .env
   sudo docker compose -f docker-compose.gcp.yml up -d api
   ```

4. **Verify site loads** at https://scan.rtb.cat

5. **Test Publisher List UI** - see QA checklist in AI log

---

## 📁 Key Paths

| Purpose | Path |
|---------|------|
| VM config | `/opt/catscan/.env` |
| Docker compose | `/opt/catscan/docker-compose.gcp.yml` |
| Image registry | `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/` |
| AI Log | `docs/ai_logs/ai_log_2026-01-29.md` |

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

# Build images (from repo root)
gcloud builds submit --tag europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-api:sha-XXX .
gcloud builds submit --tag europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-dashboard:sha-XXX ./dashboard
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
