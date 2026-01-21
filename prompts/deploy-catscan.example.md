# Deploy Cat-Scan to Production

Use this prompt with Claude CLI to deploy Cat-Scan to your production VM.

> **IMPORTANT:** Copy this file to `deploy-catscan.md` and fill in your values.
> The `deploy-catscan.md` file is gitignored and should contain your specific infrastructure details.

---

## CI/CD Pipeline Overview

Cat-Scan uses **GitHub Actions** to build Docker images.
Deploys pull prebuilt images — **no building on the VM**.

### How It Works

```
Push to main branch → GitHub Actions builds images → Registry → VM pulls images
```

### GitHub Actions Workflow

| Setting | Value |
|---------|-------|
| **Workflow file** | `.github/workflows/deploy.yml` |
| **Trigger** | Manual dispatch (click "Run workflow" in GitHub) |
| **Images built** | `catscan-api`, `catscan-dashboard` |

### Required GitHub Variables/Secrets

Set these in your repository: Settings > Secrets and variables > Actions

| Name | Type | Description |
|------|------|-------------|
| `GCP_PROJECT` | Variable | Your GCP project ID |
| `GCP_ZONE` | Variable | VM zone (e.g., `europe-west1-b`) |
| `VM_NAME` | Variable | Your VM name |
| `GCP_SA_KEY` | Secret | Service account JSON key |

---

## VM Access Details

| Property | Value |
|----------|-------|
| **Project** | `YOUR_PROJECT_ID` |
| **VM Name** | `YOUR_VM_NAME` |
| **Zone** | `YOUR_ZONE` |
| **SSH Command** | `gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE` |
| **SSH (via IAP)** | `gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE --tunnel-through-iap` |
| **External IP** | `YOUR_EXTERNAL_IP` |
| **Domain** | `YOUR_DOMAIN` |
| **App User** | `catscan` |
| **Code Location** | `/opt/catscan` |
| **Data Location** | `/home/catscan/.catscan` |

---

## Task: Deploy Latest Images

Deploy the latest Docker images to the production VM.

### Step 1: Pull and restart

```bash
# Pull latest images
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml pull"

# Restart containers
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
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
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"

# Check API health (internal)
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "curl -s http://localhost:8000/health"
```

**Expected API response:**
```json
{"status":"healthy","version":"0.9.0","configured":true,"has_credentials":true,"database_exists":true}
```

---

## Task: Rollback to Previous Version

Use `IMAGE_TAG=sha-<gitsha>` to deploy a specific version:

```bash
# Find available tags
docker images | grep catscan

# Deploy specific version (replace sha-abc1234 with actual tag)
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "cd /opt/catscan && IMAGE_TAG=sha-abc1234 sudo docker-compose -f docker-compose.gcp.yml up -d"
```

---

## Important Notes

1. **Do NOT build on VM** — Always use pull-based deploys
2. **Ensure Docker auth is configured on VM** — Run once: `sudo gcloud auth configure-docker`
3. **If dashboard 502 errors occur** — Use pull-based deploy. The VM has limited memory.
4. **Sync code before deploying** — If docker-compose.gcp.yml changed, run `git pull` on VM first

---

## Task: Check Logs

```bash
# API logs (Docker)
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "sudo docker logs -f catscan-api"

# Nginx logs
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE -- \
  "sudo tail -f /var/log/nginx/error.log"
```

---

## Important Paths on VM

| Path | Purpose |
|------|---------|
| `/opt/catscan` | Application code |
| `/home/catscan/.catscan/catscan.db` | SQLite database |
| `/home/catscan/.catscan/credentials/` | API credentials |
| `/home/catscan/.catscan/imports/` | Downloaded CSV files |

---

## Quick One-Liners

**Deploy latest code:**
```
claude "SSH to VM, pull latest code from git, restart services, verify with health check"
```

**View logs:**
```
claude "SSH to VM and show the last 50 lines of catscan-api logs"
```
