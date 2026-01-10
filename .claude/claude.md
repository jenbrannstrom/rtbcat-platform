# Cat-Scan Project Context

## ⚠️ MANDATORY: Read Before ANY Deployment or Database Operation

**CONSULT `/agent guardian` before:**
- Any deployment to production
- Any docker cleanup commands
- Any database operations
- Any commands involving `rm`, `prune`, or `delete`

---

## CRITICAL: Browser Testing with MCP

**ALWAYS USE CHROMIUM, NEVER CHROME!**

When using MCP chrome-devtools for browser interaction:
1. First launch Chromium with remote debugging:
   ```bash
   chromium-browser --remote-debugging-port=9222 --no-first-run "URL_HERE" &
   ```
2. Wait 2-3 seconds for it to start
3. Then use mcp__chrome-devtools__* tools

**DO NOT** try to connect to Chrome - it won't work. Only Chromium is configured.

---

## URLs
- Production: https://scan.rtb.cat
- Local Dashboard: http://localhost:3000
- Local API: http://localhost:8000

---

## 🚨 Deploying Updates to Production

### THE ONLY CORRECT FLOW
```
Local → git push → SSH to VM → git pull → docker-compose up
```

### Step 1: Push to GitHub FIRST (NEVER SKIP)
```bash
git add -A && git commit -m "Your message"
git push origin unified-platform
```

### Step 2: SSH to VM
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap
```

### Step 3: On the VM (run these IN ORDER, WAIT for each to complete)
```bash
cd /opt/catscan
sudo -u catscan git fetch origin
sudo -u catscan git reset --hard origin/unified-platform
sudo docker-compose -f docker-compose.gcp.yml down --remove-orphans
sudo docker-compose -f docker-compose.gcp.yml up -d --build
```

### 🛑 CRITICAL RULES - VIOLATIONS CAUSE DATA LOSS

| Rule | Why |
|------|-----|
| **Code MUST go through GitHub** | Direct uploads bypass version control and cause conflicts |
| **Never upload directly** | No tarballs, no scp of code files - EVER |
| **One deployment at a time** | Wait for docker-compose to FULLY finish |
| **NEVER interrupt docker-compose** | Interrupting mid-build can corrupt state |
| **NEVER run `docker volume prune`** | This can DELETE the database |
| **NEVER run `docker system prune -a --volumes`** | This WILL delete everything |

### If Deploy Fails
1. Check container logs: `sudo docker-compose -f docker-compose.gcp.yml logs`
2. Fix the issue in code **locally**
3. Push fix to GitHub, then SSH and pull again
4. **DO NOT** try to fix things directly on the VM

---

## 🗄️ Database Protection

### Location
- **VM:** `/home/catscan/.catscan/catscan.db`
- **Local:** `~/.catscan/catscan.db`

### Before ANY database operation
```bash
# 1. Create backup
cp ~/.catscan/catscan.db ~/.catscan/backups/catscan.db.$(date +%Y%m%d_%H%M%S)

# 2. Verify data exists
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM rtb_daily;"
```

### Data can be recovered from
- Gmail CSVs in `~/.catscan/imports/`
- Gmail import status in `~/.catscan/gmail_import_status.json`
- Google API re-sync (creatives, pretargeting)

---

## 🐳 Docker Cleanup (DANGEROUS)

### Safe cleanup (images only)
```bash
docker image prune -f
docker container prune -f
```

### ⚠️ DANGEROUS - Check database location FIRST
```bash
# Check where DB is mounted
docker inspect catscan-api | grep -A 10 Mounts

# Only if DB is NOT in a volume:
docker volume prune -f
```

### ☠️ NEVER RUN WITHOUT EXPLICIT USER CONFIRMATION
```bash
docker system prune -a --volumes  # ← WILL DELETE DATABASE
```

---

## Key Paths

| Purpose | Path |
|---------|------|
| Database | `~/.catscan/catscan.db` |
| Backups | `~/.catscan/backups/` |
| Imports | `~/.catscan/imports/` |
| Credentials | `~/.catscan/credentials/` |

---

## Agents Available

| Agent | Purpose |
|-------|---------|
| `/agent guardian` | **MANDATORY** before deployments, docker ops, DB changes |
| `/agent debugger` | Root cause analysis for errors |
| `/agent code-reviewer` | Code quality and security review |
| `/agent data-scientist` | SQL queries and data analysis |
