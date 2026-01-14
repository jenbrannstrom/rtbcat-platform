# Deploy Cat-Scan to Production

Use this prompt with Claude CLI to deploy Cat-Scan to the production GCP VM.

## VM Access Details

| Property | Value |
|----------|-------|
| **Project** | `catscan-prod-202601` |
| **VM Name** | `catscan-production` |
| **Zone** | `europe-west1-b` |
| **SSH Command** | `gcloud compute ssh catscan-production --zone=europe-west1-b` |
| **SSH (via IAP)** | `gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap` |
| **External IP** | `35.205.211.184` |
| **Domain** | `scan.rtb.cat` |
| **App User** | `catscan` |
| **Code Location** | `/opt/catscan` |
| **Data Location** | `/home/catscan/.catscan` |

---

## Task: Deploy Latest Images (Fast)

Deploy the latest Docker images to the production VM:

```bash
# 1. Pull latest images
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml pull"

# 2. Restart containers
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml up -d"

# 3. Verify
curl -s https://scan.rtb.cat/api/health
```

**Rollback (deploy a specific image tag):**
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && IMAGE_TAG=sha-<gitsha> sudo docker-compose -f docker-compose.gcp.yml pull"

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && IMAGE_TAG=sha-<gitsha> sudo docker-compose -f docker-compose.gcp.yml up -d"
```

---

## Task: First-Time Credential Setup (ONE TIME ONLY)

### Step 1: Check if credentials exist in Secret Manager

```bash
gcloud secrets versions list catscan-gmail-oauth-client --limit=1 2>/dev/null && echo "EXISTS" || echo "MISSING"
gcloud secrets versions list catscan-ab-service-account --limit=1 2>/dev/null && echo "EXISTS" || echo "MISSING"
gcloud secrets versions list catscan-gmail-token --limit=1 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

### Step 2: Find credential files locally

```bash
# Check common locations
ls -la ~/Downloads/client_secret*.json 2>/dev/null
ls -la ~/.catscan/credentials/*.json 2>/dev/null
ls -la ~/Documents/*.json 2>/dev/null
```

### Step 3: Upload to Secret Manager (if missing)

```bash
# Gmail OAuth Client (from GCP Console download)
gcloud secrets versions add catscan-gmail-oauth-client \
  --data-file=<path-to-gmail-oauth-client.json>

# Service Account (from GCP Console download)
gcloud secrets versions add catscan-ab-service-account \
  --data-file=<path-to-service-account.json>

# Gmail Token (created by running scripts/gmail_auth.py locally)
gcloud secrets versions add catscan-gmail-token \
  --data-file=~/.catscan/credentials/gmail-token.json
```

### Step 4: Restart VM to pull credentials

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- "sudo reboot"
# Wait 2 minutes, then verify
curl -s https://scan.rtb.cat/api/health
```

---

## Task: Check Logs

```bash
# API logs (Docker)
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo docker logs -f catscan-api"

# Startup script log
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo tail -f /var/log/catscan-setup.log"

# Nginx logs
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo tail -f /var/log/nginx/error.log"

---

## Task: Rebuild Dashboard Only (Fast)

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml pull dashboard"

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml up -d --no-deps dashboard"
```

---

## Task: Clean Failed Build Containers

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo docker ps -a --filter 'status=exited' --filter 'ancestor=catscan_dashboard:latest' -q | xargs -r sudo docker rm -f"
```
```

---

## Task: Run Gmail Import

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo -u catscan python scripts/gmail_import.py"
```

---

## Task: Database Backup

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo /usr/local/bin/catscan-backup --gcs"
```

---

## Important Paths on VM

| Path | Purpose |
|------|---------|
| `/opt/catscan` | Application code |
| `/home/catscan/.catscan/catscan.db` | SQLite database |
| `/home/catscan/.catscan/credentials/` | API credentials |
| `/home/catscan/.catscan/imports/` | Downloaded CSV files |
| `/var/log/catscan-setup.log` | Startup script log |

---

## Quick One-Liners for Claude CLI

**Deploy latest code:**
```
claude "SSH to catscan-production VM, pull latest code from git, restart catscan-api service, and verify with curl to https://scan.rtb.cat/api/health"
```

**Check credentials:**
```
claude "Check if credentials exist in GCP Secret Manager: catscan-gmail-oauth-client, catscan-ab-service-account, catscan-gmail-token. Report which are missing."
```

**Run import:**
```
claude "SSH to catscan-production and run the Gmail import script: sudo -u catscan python /opt/catscan/scripts/gmail_import.py"
```

**View logs:**
```
claude "SSH to catscan-production and show the last 50 lines of catscan-api logs"
```
