# Deploy Cat-Scan to Production

Use this prompt with Claude CLI to deploy Cat-Scan to the production GCP VM.

---

## CI/CD Pipeline Overview

Cat-Scan uses **GitHub Actions** to build Docker images and **Artifact Registry** to store them.
Deploys pull prebuilt images from Artifact Registry — **no building on the VM**.

### How It Works

```
Push to unified-platform → GitHub Actions builds images → Artifact Registry → VM pulls images
```

### GitHub Actions Workflow

| Setting | Value |
|---------|-------|
| **Workflow file** | `.github/workflows/build-and-push.yml` |
| **Trigger** | Push to `unified-platform` branch (or manual dispatch) |
| **Images built** | `catscan-api`, `catscan-dashboard` |
| **Tags** | `latest`, `sha-<gitsha>` (for rollback) |

### Artifact Registry

| Setting | Value |
|---------|-------|
| **Project** | `catscan-prod-202601` |
| **Region** | `europe-west1` |
| **Repository** | `catscan` |
| **API image** | `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-api` |
| **Dashboard image** | `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-dashboard` |

### GitHub Secret (GCP_SA_KEY)

The workflow authenticates to GCP using a service account key stored in GitHub Secrets.

| Setting | Value |
|---------|-------|
| **Secret name** | `GCP_SA_KEY` |
| **Content** | **Full JSON service account key** (NOT an SSH key!) |
| **Service account** | `catscan-ci@catscan-prod-202601.iam.gserviceaccount.com` |
| **Required role** | `roles/artifactregistry.writer` |

**To create/rotate the key:**
```bash
# Create new key
gcloud iam service-accounts keys create /tmp/key.json \
  --iam-account=catscan-ci@catscan-prod-202601.iam.gserviceaccount.com

# Set GitHub secret
gh secret set GCP_SA_KEY < /tmp/key.json

# Delete local key
rm /tmp/key.json
```

---

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

Deploy the latest Docker images to the production VM.

### Step 1: Pull and restart

```bash
# Pull latest images
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml pull"

# Restart containers
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml up -d"
```

Or run directly on the VM:
```bash
cd /opt/catscan
sudo docker-compose -f docker-compose.gcp.yml pull
sudo docker-compose -f docker-compose.gcp.yml up -d
```

### Step 2: Verify deployment

```bash
# Check containers are running with correct images
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"

# Check API health (internal)
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "curl -s http://localhost:8000/health"
```

**Expected API response:**
```json
{"status":"healthy","version":"0.9.0","configured":true,"has_credentials":true,"database_exists":true}
```

### How to Verify (External)

| URL | Expected Result |
|-----|-----------------|
| https://scan.rtb.cat | Dashboard loads (OAuth2 login page if not authenticated) |
| https://scan.rtb.cat/api/health | OAuth2 redirect (returns 200 with login page HTML) |

> **Note:** External `/api/health` shows OAuth2 login page because all routes are protected.
> Use the internal check above for true health status.

---

## Task: Rollback to Previous Version

Use `IMAGE_TAG=sha-<gitsha>` to deploy a specific version:

```bash
# Find available tags in Artifact Registry
gcloud artifacts docker tags list \
  europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-api

# Deploy specific version (replace sha-abc1234 with actual tag)
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && IMAGE_TAG=sha-abc1234 sudo docker-compose -f docker-compose.gcp.yml pull"

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && IMAGE_TAG=sha-abc1234 sudo docker-compose -f docker-compose.gcp.yml up -d"
```

---

## Important Notes / Gotchas

1. **Do NOT build on VM** — Always use pull-based deploys from Artifact Registry
2. **Do NOT paste SSH keys into GCP_SA_KEY** — Must be the full JSON service account key
3. **Ensure Docker auth is configured on VM** — Run once: `sudo gcloud auth configure-docker europe-west1-docker.pkg.dev`
4. **If dashboard 502 errors occur** — Use pull-based deploy (not build). The VM has limited memory.
5. **Sync code before deploying** — If docker-compose.gcp.yml changed, run `git pull` on VM first

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
| Cloud SQL PostgreSQL | Serving database (via `POSTGRES_SERVING_DSN`) |
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
