# GCP Credentials Setup & VM Deployment

**Purpose:** How to set up Google Cloud credentials and deploy Cat-Scan to a GCP VM

**Production URL:** https://scan.rtb.cat (hosted on `catscan-production` VM)

**Infrastructure:** GCE e2-micro (~$6/month) with SQLite database

---

## ONE-TIME Credential Setup (Do This Once, Never Again)

Credentials are stored in **GCP Secret Manager** and automatically pulled on every VM deploy/restart.

### Step 1: Create Credentials (GCP Console)

1. **Gmail OAuth Client:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Desktop app)
   - Download JSON → save as `gmail-oauth-client.json`

2. **Service Account (for Authorized Buyers API):**
   - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
   - Create service account → download JSON → save as `catscan-service-account.json`

3. **Gmail Token (requires browser):**
   ```bash
   # Run locally to authorize Gmail
   python scripts/gmail_auth.py
   # Token saved to: ~/.catscan/credentials/gmail-token.json
   ```

### Step 2: Upload to Secret Manager (ONE TIME!)

```bash
# Upload Gmail OAuth client
gcloud secrets versions add catscan-gmail-oauth-client \
  --data-file=gmail-oauth-client.json

# Upload service account
gcloud secrets versions add catscan-ab-service-account \
  --data-file=catscan-service-account.json

# Upload Gmail token (after running gmail_auth.py)
gcloud secrets versions add catscan-gmail-token \
  --data-file=~/.catscan/credentials/gmail-token.json
```

### Step 3: Done!

Credentials are now stored permanently in Secret Manager.

- **Every deploy** → VM pulls credentials automatically
- **Every restart** → Credentials are there
- **Never copy manually** → It's always automatic

---

## Cost Summary

| Component | Monthly Cost |
|-----------|-------------|
| GCE e2-micro | $0-6 (free tier eligible) |
| 20GB SSD | $3.40 |
| Static IP | $0 (attached to running VM) |
| SSL | $0 (Let's Encrypt) |
| **Total** | **~$6/month** |

---

## CI/CD Pipeline

Cat-Scan uses GitHub Actions to build Docker images and push them to Artifact Registry.
The VM pulls prebuilt images — **no building on the VM**.

### Architecture

```
git push → GitHub Actions → Artifact Registry → VM pulls images
```

### Artifact Registry Setup (One-Time)

```bash
# Enable API
gcloud services enable artifactregistry.googleapis.com

# Create repository
gcloud artifacts repositories create catscan \
  --repository-format=docker \
  --location=europe-west1 \
  --description="Cat-Scan Docker images"
```

### CI Service Account Setup (One-Time)

Create a service account for GitHub Actions to push images:

```bash
# Create service account
gcloud iam service-accounts create catscan-ci \
  --display-name="Cat-Scan CI/CD"

# Grant Artifact Registry write access
gcloud projects add-iam-policy-binding catscan-prod-202601 \
  --member="serviceAccount:catscan-ci@catscan-prod-202601.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Create key and set GitHub secret
gcloud iam service-accounts keys create /tmp/key.json \
  --iam-account=catscan-ci@catscan-prod-202601.iam.gserviceaccount.com

gh secret set GCP_SA_KEY < /tmp/key.json
rm /tmp/key.json
```

### GitHub Secret: GCP_SA_KEY

| Setting | Value |
|---------|-------|
| **Secret name** | `GCP_SA_KEY` |
| **Content** | Full JSON service account key |
| **Service account** | `catscan-ci@catscan-prod-202601.iam.gserviceaccount.com` |
| **Required role** | `roles/artifactregistry.writer` |

> **WARNING:** The secret must contain the **full JSON key**, NOT an SSH key.
> An SSH key will cause: `failed to parse service account key JSON credentials`

### Workflow Details

| Setting | Value |
|---------|-------|
| **File** | `.github/workflows/build-and-push.yml` |
| **Trigger** | Push to `unified-platform` or manual dispatch |
| **Images** | `catscan-api`, `catscan-dashboard` |
| **Tags** | `latest`, `sha-<gitsha>` |
| **Registry** | `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/` |

---

## Quick Deploy (Code Updates)

**Deployment flow: Local → GitHub → CI builds images → VM pulls**

### Step 1: Push to GitHub
```bash
git add -A && git commit -m "Your message"
git push origin unified-platform
```

Wait for GitHub Actions to complete (~3 minutes).

### Step 2: Pull and restart on VM
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml pull"

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && sudo docker-compose -f docker-compose.gcp.yml up -d"
```

### Step 3: Verify

```bash
# Check containers
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"

# Check API health (internal)
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "curl -s http://localhost:8000/health"
```

### Rollback

Deploy a specific version using `IMAGE_TAG`:

```bash
# List available tags
gcloud artifacts docker tags list \
  europe-west1-docker.pkg.dev/catscan-prod-202601/catscan/catscan-api

# Deploy specific version
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "cd /opt/catscan && IMAGE_TAG=sha-abc1234 sudo docker-compose -f docker-compose.gcp.yml pull && \
   IMAGE_TAG=sha-abc1234 sudo docker-compose -f docker-compose.gcp.yml up -d"
```

### Important Notes

- **Do NOT build on VM** — The VM has limited memory. Always pull prebuilt images.
- **Do NOT use SSH keys for GCP_SA_KEY** — Must be the JSON service account key.
- **Configure Docker auth on VM** (one-time): `sudo gcloud auth configure-docker europe-west1-docker.pkg.dev`
- **If docker-compose.gcp.yml changed** — Run `git pull` on VM before deploying.

### CRITICAL RULES

- **Code MUST go through GitHub** - CI builds the images
- **Never upload directly** - No tarballs, no scp of code files
- **One deployment at a time** - Wait for docker-compose to finish before starting another

### If Deploy Fails

1. Check container logs: `sudo docker-compose -f docker-compose.gcp.yml logs`
2. Fix the issue in code locally
3. Push fix to GitHub, then SSH and pull again

---

## Overview

Cat-Scan uses ONE GCP project with:
1. **OAuth2 Proxy** - for user authentication via Google (replaces custom auth)
2. **Service Account** - for Authorized Buyers API (all AB accounts)
3. **OAuth Client (Gmail)** - for Gmail API (report import)
4. **Compute Engine VM** - to host the application
5. **Nginx** - reverse proxy with SSL termination
6. **Let's Encrypt** - free SSL certificates (auto-renewal)

**Architecture (with OAuth2 Proxy):**
```
Internet → nginx (443/HTTPS) → OAuth2 Proxy (4180) → Dashboard (3000) + API (8000)
                                    ↓
                            Google OAuth
                       (validates user login)
```

**Security:** All users must authenticate with their Google account before accessing any part of the application. No default passwords, no custom auth - Google handles everything.

Credentials are stored in `~/.catscan/credentials/` (outside git).

---

## Directory Structure

**Local development:**
```
~/.catscan/
├── catscan.db                          # SQLite database
├── credentials/
│   ├── catscan-service-account.json    # AB API access (all accounts)
│   ├── gmail-oauth-client.json         # Gmail OAuth client
│   └── gmail-token.json                # Gmail token (auto-refreshes)
├── imports/                            # Downloaded CSVs
└── gmail_import_status.json            # Import tracking
```

**Production VM (catscan-production):**
```
/home/catscan/.catscan/
├── catscan.db                          # SQLite database (~1.3GB with data)
├── credentials/
│   └── ...                             # Same structure as above
├── imports/
└── gmail_import_status.json

/opt/catscan/
├── data/catscan.db                     # Empty DB (schema only, NOT used)
└── docker-compose.gcp.yml              # Docker deployment config
```

> **Important:** On the production VM, you SSH as your user (e.g., `jen`) but the
> database is under the `catscan` user's home directory. Use `sudo` to access it:
> ```bash
> sudo sqlite3 /home/catscan/.catscan/catscan.db ".tables"
> ```

---

## Step 1: Create GCP Project

```bash
gcloud projects create YOUR-PROJECT-ID --name="Cat-Scan"
gcloud config set project YOUR-PROJECT-ID
gcloud billing projects link YOUR-PROJECT-ID --billing-account=YOUR-BILLING-ACCOUNT
```

Enable APIs:
```bash
gcloud services enable \
  compute.googleapis.com \
  authorizedbuyersmarketplace.googleapis.com \
  realtimebidding.googleapis.com \
  gmail.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

---

## Step 1b: OAuth Credentials (User Authentication)

Create OAuth credentials for OAuth2 Proxy (user login):

1. Go to https://console.cloud.google.com/apis/credentials
2. **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure OAuth consent screen first:
   - User Type: **External** (or Internal for Workspace orgs)
   - App name: `Cat-Scan`
   - Support email: your email
   - Developer contact: your email
   - Scopes: Add `email`, `profile`, `openid`
4. Create OAuth client:
   - Type: **Web application**
   - Name: `Cat-Scan User Login`
   - Authorized redirect URIs: `https://YOUR_DOMAIN/oauth2/callback`
5. Copy the **Client ID** and **Client Secret**

Add to `terraform/gcp/terraform.tfvars`:
```hcl
google_oauth_client_id     = "123456789-xxxxx.apps.googleusercontent.com"
google_oauth_client_secret = "GOCSPX-xxxxx"

# Optional: Restrict to specific domains
allowed_email_domains = []  # Empty = any Google account
# allowed_email_domains = ["company.com"]  # Restrict to company.com
```

**Note:** This is different from the Gmail OAuth client (Step 3). This one is for user login, that one is for CSV import.

---

## Step 2: Service Account (Authorized Buyers)

Create service account:
```bash
gcloud iam service-accounts create catscan-api \
  --display-name="Cat-Scan API"

gcloud iam service-accounts keys create ~/.catscan/credentials/catscan-service-account.json \
  --iam-account=catscan-api@YOUR-PROJECT-ID.iam.gserviceaccount.com
```

Add to each Authorized Buyers account:
1. Go to https://realtimebidding.google.com/
2. Select buyer account → Settings → Service Accounts
3. Add: `catscan-api@YOUR-PROJECT-ID.iam.gserviceaccount.com`
4. Repeat for each AB account

**Test:**
```bash
python3 -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build
creds = service_account.Credentials.from_service_account_file(
    '~/.catscan/credentials/catscan-service-account.json',
    scopes=['https://www.googleapis.com/auth/realtime-bidding']
)
service = build('realtimebidding', 'v1', credentials=creds)
print(service.buyers().list().execute())
"
```

---

## Step 3: Gmail OAuth (Report Import)

### 3a. Create OAuth Client

1. Go to: https://console.cloud.google.com/apis/credentials?project=YOUR-PROJECT-ID
2. **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Configure consent screen first:
   - User Type: **External**
   - App name: `Cat-Scan`
   - Scopes: Add `gmail.readonly`
   - Test users: Add your Gmail address (e.g., `reports@yourdomain.com`)
   - Publishing status: **Testing**
4. Create OAuth client:
   - Type: **Desktop app**
   - Name: `Cat-Scan Gmail Import`
5. Download JSON → save as `~/.catscan/credentials/gmail-oauth-client.json`

### 3b. Authorize Gmail

```bash
python scripts/gmail_auth.py
```

This opens a browser. Sign in with the Gmail account that receives AB reports.
Token saved to `~/.catscan/credentials/gmail-token.json`

**Test:**
```bash
python scripts/gmail_import.py --status
```

**CSV Report Types:** The Gmail importer processes 5 different CSV report types from Google Authorized Buyers (Performance Detail, RTB Funnel Geo, RTB Funnel Publisher, Bid Filtering, Quality Signals). See [DATA_MODEL.md](../DATA_MODEL.md#csv-import-reference) for complete column specifications and sample data.

---

## Step 4: Verify Setup

```bash
# Test AB API
python -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
creds = service_account.Credentials.from_service_account_file(
    os.path.expanduser('~/.catscan/credentials/catscan-service-account.json'),
    scopes=['https://www.googleapis.com/auth/realtime-bidding']
)
service = build('realtimebidding', 'v1', credentials=creds)
# Replace with your account ID
result = service.buyers().creatives().list(parent='buyers/YOUR_ACCOUNT_ID', pageSize=1).execute()
print('AB API:', len(result.get('creatives', [])), 'creatives')
"

# Test Gmail API
python -c "
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
creds = Credentials.from_authorized_user_file(
    os.path.expanduser('~/.catscan/credentials/gmail-token.json')
)
service = build('gmail', 'v1', credentials=creds)
result = service.users().messages().list(userId='me', maxResults=1).execute()
print('Gmail API: OK')
"
```

---

## OAuth2 Proxy Configuration

The production VM uses OAuth2 Proxy for authentication. Configuration file: `/etc/oauth2-proxy.cfg`

### Required Configuration
```ini
provider = "google"
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret = "GOCSPX-xxxxx"
cookie_secret = "random-32-byte-string"
cookie_secure = true
cookie_name = "_catscan_oauth"
redirect_url = "https://scan.rtb.cat/oauth2/callback"
http_address = "127.0.0.1:4180"
email_domains = ["rtb.cat", "amazingdo.com"]
cookie_expire = "168h"
cookie_refresh = "1h"
skip_auth_routes = ["/health"]
set_xauthrequest = true
pass_user_headers = true
```

### Important Notes

1. **Do NOT use `cookie_domain` or `cookie_domains`** - These can cause authentication loops. The default behavior works correctly without them.

2. **Backend requires `OAUTH2_PROXY_ENABLED=true`** - The API container must have this environment variable set to trust the `X-Email` header from OAuth2 Proxy.

3. **Restart after config changes:**
   ```bash
   sudo systemctl restart oauth2-proxy
   sudo systemctl restart nginx
   ```

### Auth Loop Troubleshooting

If users get stuck in an authentication loop (Google login succeeds but immediately redirects back to login):

1. **Check oauth2-proxy logs:**
   ```bash
   sudo journalctl -u oauth2-proxy --since "5 minutes ago" --no-pager
   ```

2. **Look for cookie issues** - If you see successful auth (202) followed by 401, check:
   - Remove any `cookie_domain` or `cookie_domains` settings
   - Ensure `OAUTH2_PROXY_ENABLED=true` is set on the API container

3. **Restart services:**
   ```bash
   sudo systemctl restart oauth2-proxy
   sudo docker restart catscan-api
   ```

4. **Clear browser cookies** for `scan.rtb.cat` and try again

---

## Troubleshooting

### "Access blocked: org_internal"
Your Gmail account is in a different Workspace org than the GCP project.
Fix: Set OAuth consent screen to **External** and add Gmail as test user.

### "invalid_request" on OAuth
The OOB flow is deprecated. Use `run_local_server()` which redirects to localhost.

### Token expired
Gmail tokens auto-refresh. If issues persist, re-run `python scripts/gmail_auth.py`

### "Invalid cross-device link" during CSV import
This means the temp upload directory is on a different filesystem than `~/.catscan/`.

Fix options:
- Upgrade to the version that uses `shutil.move()` for imports (recommended).
- Or set `TMPDIR` to a folder on the same disk as `~/.catscan/` (for example: `export TMPDIR=/home/rtbcat/.catscan/tmp`).

### "No buyer seats discovered" / 0 seats found

The service account can authenticate but doesn't have access to any Authorized Buyers accounts.

**How to fix:**

1. Go to https://authorizedbuyers.google.com
2. Select your account from the dropdown (top left)
3. Go to **Settings → User management** (or **Service accounts**)
4. Add your service account email: `catscan-api@YOUR-PROJECT.iam.gserviceaccount.com`
5. Select role: **Account Manager** or **RTB Troubleshooter** (not just Viewer)
6. Click Save
7. Wait 5-10 minutes for permissions to propagate
8. Click "Discover Buyer Seats" in Cat-Scan Setup

**Verify API access directly:**

```bash
# SSH to server and test
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap

sudo docker exec catscan-api python3 -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    '/home/rtbcat/.catscan/credentials/google-credentials.json',
    scopes=['https://www.googleapis.com/auth/realtime-bidding']
)
service = build('realtimebidding', 'v1', credentials=creds)
response = service.buyers().list().execute()
print('Buyers found:', response)
"
```

**Expected output:** A list of buyer accounts like:
```json
{'buyers': [{'name': 'buyers/123456789', 'displayName': 'Your Company', ...}]}
```

If the list is empty, the service account doesn't have access to any accounts yet

---

## Security Notes

- `~/.catscan/credentials/` is outside git (in home directory)
- Never commit credential files
- Service account key has minimal permissions
- OAuth token contains refresh token - keep secure

---

## Deploying to GCP VM

### Quick Start (Terraform)

1. **Complete Steps 1, 1b, 2, and 3** above (create OAuth credentials, service account, Gmail OAuth)

2. **Configure Terraform:**
   ```bash
   cd terraform/gcp
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values (especially OAuth credentials)
   ```

3. **Deploy:**
   ```bash
   terraform init
   terraform apply
   ```

4. **Access the app:**
   - Visit `https://your-domain.com`
   - You'll be redirected to Google login
   - After authentication, you can access the dashboard

5. **Upload Authorized Buyers credentials** via Settings → Credentials

**That's it!** No default passwords, no manual user creation. OAuth2 Proxy handles all authentication.

---

### Security Features (Automatic)

The Terraform deployment automatically configures:
- **OAuth2 Proxy** - All users must authenticate with Google
- **Nginx reverse proxy** - SSL termination, security headers
- **Fail2ban** - Brute force protection
- **Automatic updates** - Security patches applied daily
- **Firewall rules** - Only ports 80/443 exposed (no 3000/8000)
- **Let's Encrypt SSL** - Auto-renewed certificates

---

### DEPRECATED: Manual Deployment (Security Risk)

The manual steps below are **deprecated** and kept only for reference. They contain known security issues.

> **WARNING:** Manual deployment bypasses OAuth2 Proxy and may expose the app with default credentials.

### Current Production Setup (Updated January 2026)

| Property | Value |
|----------|-------|
| Project ID | `catscan-prod-202601` |
| VM Name | `catscan-production` |
| Zone | `europe-west1-b` |
| Machine Type | `e2-micro` (~$6/month) |
| RAM | 1GB |
| vCPU | 2 shared |
| Disk | 20GB SSD |
| External IP | `35.205.211.184` |
| Domain | `scan.rtb.cat` |
| SSL Certificate | Let's Encrypt (auto-renewed) |

### Quick Database Query (One-Liner)

```bash
# List tables
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo sqlite3 /home/catscan/.catscan/catscan.db '.tables'"

# Run any SQL query
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo sqlite3 /home/catscan/.catscan/catscan.db 'SELECT COUNT(*) FROM rtb_bidstream;'"

# Or via Docker container (for Python queries)
gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo docker exec catscan-api python -c \"import sqlite3; print(sqlite3.connect('/home/rtbcat/.catscan/catscan.db').execute('SELECT COUNT(*) FROM rtb_bidstream').fetchone()[0])\""
```

> **Note:** SSH as your user but DB is under `catscan` user, so use `sudo`.
> Inside Docker, the path is `/home/rtbcat/.catscan/` (volume mounted from `/home/catscan/.catscan/`).

**Upgrade if needed:**
```bash
# If slow, upgrade to e2-small (2GB RAM, ~$13/month)
gcloud compute instances set-machine-type catscan-production \
  --machine-type=e2-small --zone=europe-west1-b
```

**Note:** The old project was `augmented-vim-427407-t8` with IP `104.199.91.219`.
The new deployment uses Terraform in project `catscan-prod-202601`.

### SSH Host Key Change After VM Recreation

When the VM is recreated (via Terraform or manually), SSH host keys change. This triggers a warning:
```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
```

**This is expected after VM recreation, not a security breach.** To fix:

```bash
# Remove old host key
ssh-keygen -f ~/.ssh/known_hosts -R scan.rtb.cat
ssh-keygen -f ~/.ssh/known_hosts -R 35.205.211.184

# Add new host key
ssh-keyscan -H scan.rtb.cat >> ~/.ssh/known_hosts

# Verify connection
ssh -o StrictHostKeyChecking=accept-new catscan@scan.rtb.cat "hostname"
```

**How to verify it's not a hack:**
1. Check SSL certificate: `openssl s_client -connect scan.rtb.cat:443 | openssl x509 -noout -dates`
2. Check GCP VMs: `gcloud compute instances list --project=catscan-prod-202601`
3. Verify IP matches: `host scan.rtb.cat` should show `35.205.211.184`

### Step 1: Authenticate gcloud

After a reboot or new machine, re-authenticate:

```bash
gcloud auth login
```

This opens a browser for OAuth. Complete the flow and return to terminal.

Verify authentication:
```bash
gcloud auth list
gcloud config get-value project
```

### Step 2: Create or Check VM

**RECOMMENDED: Use Terraform instead:**
```bash
cd terraform/gcp
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID
terraform init && terraform apply
```

**Legacy manual method (NOT RECOMMENDED):**

**List existing VMs:**
```bash
gcloud compute instances list
```

**Create a new VM (if needed):**
```bash
# Use e2-micro for cost savings (~$6/month)
gcloud compute instances create catscan-prod \
  --zone=europe-west1-b \
  --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-ssd \
  --tags=http-server,https-server
```

**Create firewall rules - SECURE VERSION:**
```bash
# SECURITY: Only expose 80/443 - NEVER 3000/8000!
# The old rule (tcp:80,tcp:443,tcp:3000,tcp:8000) caused the January 2026 breach.

gcloud compute firewall-rules create allow-web \
  --allow=tcp:80,tcp:443 \
  --target-tags=http-server,https-server \
  --description="Allow HTTP/HTTPS only - ports 3000/8000 blocked"

# Allow IAP for secure SSH (no SSH port exposed)
gcloud compute firewall-rules create allow-iap-ssh \
  --allow=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=http-server,https-server \
  --description="SSH via Identity-Aware Proxy only"
```

> **WARNING:** Never create a firewall rule that includes ports 3000 or 8000.
> These ports should ONLY be accessible via localhost (nginx proxies to them).

### Step 3: SSH to VM

**Standard SSH:**
```bash
gcloud compute ssh catscan-prod --zone=europe-west1-b
```

**Direct SSH (no gcloud):**

SSH keys are auto-created by `gcloud compute ssh` on first use and stored in:
```
~/.ssh/google_compute_engine       # Private key
~/.ssh/google_compute_engine.pub   # Public key
```

Connect directly:
```bash
ssh -i ~/.ssh/google_compute_engine jen@35.205.211.184
```

Or add to `~/.ssh/config` for convenience:
```
Host catscan
    HostName 35.205.211.184
    User jen
    IdentityFile ~/.ssh/google_compute_engine
```

Then just: `ssh catscan`

**If SSH fails with "Host key verification":**
```bash
ssh-keyscan -H <EXTERNAL_IP> >> ~/.ssh/known_hosts
```

**If SSH fails with "Connection closed by remote host":**

This usually means the VM's user session service is broken. Reset the VM:
```bash
gcloud compute instances reset catscan-prod --zone=europe-west1-b
# Wait 30 seconds, then SSH again
```

**If SSH still fails, add your SSH key to VM metadata:**
```bash
# Get your public key
cat ~/.ssh/id_ed25519.pub

# Add to VM
gcloud compute instances add-metadata catscan-prod \
  --zone=europe-west1-b \
  --metadata="ssh-keys=jen:$(cat ~/.ssh/id_ed25519.pub)"
```

### Step 4: Install Cat-Scan on VM

SSH to the VM, then:

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm ffmpeg git

# Clone repository (VM)
sudo mkdir -p /opt/catscan
sudo chown -R jen:jen /opt/catscan
git clone https://github.com/jenbrannstrom/rtbcat-platform.git /opt/catscan
cd /opt/catscan
```

### Step 5: Copy Credentials to VM

From your local machine (where credentials are already set up):

```bash
# Copy service account
scp ~/.catscan/credentials/catscan-service-account.json \
  jen@<VM_EXTERNAL_IP>:~/.catscan/credentials/

# Copy Gmail OAuth client
scp ~/.catscan/credentials/gmail-oauth-client.json \
  jen@<VM_EXTERNAL_IP>:~/.catscan/credentials/

# Copy Gmail token (already authorized)
scp ~/.catscan/credentials/gmail-token.json \
  jen@<VM_EXTERNAL_IP>:~/.catscan/credentials/
```

### Step 6: Register Service Account in Database

**IMPORTANT:** The API requires service accounts to be registered in the database, not just present as files.

SSH to VM and run:

```bash
sqlite3 ~/.catscan/catscan.db "INSERT INTO service_accounts
  (id, client_email, project_id, display_name, credentials_path, is_active)
  VALUES (
    'sa-1',
    '<SERVICE_ACCOUNT_EMAIL>',
    '<GCP_PROJECT_ID>',
    'Cat-Scan API',
    '~/.catscan/credentials/catscan-service-account.json',
    1
  );"
```

Verify:
```bash
sqlite3 ~/.catscan/catscan.db "SELECT * FROM service_accounts;"
```

### Step 7: Production Services (Docker Compose)

Production uses prebuilt images from Artifact Registry. The VM pulls images and starts containers (no building on the VM).

```bash
cd /opt/catscan
sudo docker-compose -f docker-compose.gcp.yml pull
sudo docker-compose -f docker-compose.gcp.yml up -d
```

### Step 7b: Home Cache Refresh Timer (nightly)

The Home page uses precomputed tables. Install a nightly refresh:

```bash
sudo cp /opt/catscan/scripts/systemd/catscan-home-refresh.service /etc/systemd/system/
sudo cp /opt/catscan/scripts/systemd/catscan-home-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now catscan-home-refresh.timer
sudo systemctl status catscan-home-refresh.timer
```

### Step 8: Set Up Nginx Reverse Proxy

Next.js standalone mode doesn't support rewrites, so nginx handles routing `/api/*` to the backend.

**Install nginx:**
```bash
sudo apt install -y nginx
```

**Create nginx config:**
```bash
sudo tee /etc/nginx/sites-available/catscan << 'EOF'
server {
    listen 80;
    server_name scan.rtb.cat <VM_EXTERNAL_IP>;

    # Allow large CSV uploads for imports (avoid 413 errors)
    client_max_body_size 200m;

    # API routes - strip /api prefix
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
    }

    # Thumbnails
    location /thumbnails/ {
        proxy_pass http://127.0.0.1:8000/thumbnails/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Dashboard (default)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

**Enable the site:**
```bash
sudo ln -s /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### Step 9: Set Up SSL with Let's Encrypt

**Install certbot:**
```bash
sudo apt install -y certbot python3-certbot-nginx
```

**Get SSL certificate:**
```bash
sudo certbot --nginx -d scan.rtb.cat
```

Follow the prompts:
- Enter email for renewal notices
- Agree to terms
- Choose whether to redirect HTTP to HTTPS (recommended: yes)

Certbot automatically:
- Obtains the certificate
- Modifies nginx config for HTTPS
- Sets up auto-renewal via systemd timer

**Verify auto-renewal:**
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

### Step 10: Verify Deployment

**Check all services:**
```bash
sudo systemctl status nginx catscan-api catscan-dashboard
```

**Test via HTTPS:**
```bash
curl -s https://scan.rtb.cat/api/health
```

Expected response:
```json
{"status":"healthy","version":"0.9.0","configured":true,"has_credentials":true,"database_exists":true}
```

**Test dashboard:**
```bash
curl -s https://scan.rtb.cat/ | grep -o '<title>[^<]*</title>'
# Expected: <title>Cat-Scan Dashboard</title>
```

---

## After Reboot Checklist

When the GCP VM or your local machine reboots:

1. **Re-authenticate gcloud:**
   ```bash
   gcloud auth login
   ```

2. **Check VM status:**
   ```bash
   gcloud compute instances list
   ```

3. **SSH to VM (if needed):**
   ```bash
   gcloud compute ssh catscan-prod --zone=europe-west1-b
   ```

4. **If SSH fails, reset VM:**
   ```bash
   gcloud compute instances reset catscan-prod --zone=europe-west1-b
   # Wait 30 seconds, try SSH again
   ```

5. **Verify all services are running:**
   ```bash
   ssh jen@104.199.91.219 "sudo systemctl status nginx catscan-api catscan-dashboard"
   ```

6. **Check health via HTTPS:**
   ```bash
   curl -s https://scan.rtb.cat/api/health
   ```

7. **Check SSL certificate expiry:**
   ```bash
   ssh jen@104.199.91.219 "sudo certbot certificates"
   ```

---

## Common Issues

### SSH "Connection closed by remote host"

The VM's systemd user session service is failing. Fix:
```bash
gcloud compute instances reset catscan-prod --zone=europe-west1-b
```

### API shows `configured: false` despite credentials existing

Credentials must be registered in the database. Run Step 6 above.

### gcloud "Reauthentication failed"

Your auth tokens expired. Run:
```bash
gcloud auth login
```

### Services not starting after VM reboot

Check if services are enabled:
```bash
sudo systemctl is-enabled nginx catscan-api catscan-dashboard
```

If not, enable them:
```bash
sudo systemctl enable nginx catscan-api catscan-dashboard
```

### Nginx returns 502 Bad Gateway

Backend services aren't running. Check:
```bash
sudo systemctl status catscan-api catscan-dashboard
sudo journalctl -u catscan-api -n 50
```

### SSL certificate expired

Certbot auto-renewal should handle this. If not:
```bash
sudo certbot renew
sudo systemctl reload nginx
```

### Dashboard shows blank page

If multi-user mode is enabled but no users exist:
```bash
# Option A: Disable multi-user mode
sqlite3 ~/.catscan/catscan.db "UPDATE system_settings SET value='0' WHERE key='multi_user_enabled';"
sudo systemctl restart catscan-api

# Option B: Create admin user (see "Fresh Install Workaround" below)
```

---

## Debugging Session Summary (2026-01-07)

### Issue: Blank Dashboard After Fresh Install

**Symptom:** Dashboard at `http://104.199.91.219:3000` loads but shows blank content.

**Root Cause:** Multi-user authentication was enabled (`multi_user_enabled=1`) but no users existed in the database. The API returned "Authentication required" for all data endpoints.

**Diagnosis steps:**
```bash
# Check if services are running
ssh jen@104.199.91.219 "sudo systemctl status catscan-api catscan-dashboard"

# Test API authentication
curl -s http://104.199.91.219:8000/stats
# Returns: {"detail": "Authentication required. Please log in."}

# Check database settings
ssh jen@104.199.91.219 "sqlite3 ~/.catscan/catscan.db 'SELECT * FROM system_settings;'"
# Shows: multi_user_enabled|1

# Check if users exist
ssh jen@104.199.91.219 "sqlite3 ~/.catscan/catscan.db 'SELECT * FROM users;'"
# Returns empty - no users!
```

**Quick Fix (for development/testing):**
```bash
ssh jen@104.199.91.219 "sqlite3 ~/.catscan/catscan.db \"UPDATE system_settings SET value='0' WHERE key='multi_user_enabled';\""
sudo systemctl restart catscan-api
```

**Production Fix:** Ensure OAuth2 Proxy is configured and `allowed_email_domains` is set.

### Data Verification

After fixing auth, verified data pipeline is working:

```bash
# Check database has data
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM rtb_daily;"
# Result: 46,346 rows

# Check Gmail import status
cat ~/.catscan/gmail_import_status.json
# Shows: 43 files imported successfully

# Check imports folder
ls ~/.catscan/imports/ | wc -l
# Result: 1,232 CSV files
```

### SSH Connection Issues

If SSH fails with "Connection closed by remote host":
```bash
# Reset the VM (fixes systemd user session issues)
gcloud compute instances reset catscan-prod --zone=europe-west1-b
sleep 45
ssh jen@104.199.91.219 "uptime"
```

---

## First Run Setup (Production)

Cat-Scan relies on OAuth2 Proxy for authentication. There are no local
passwords or default credentials to configure. Control access via:

1. `allowed_email_domains` in Terraform
2. OAuth2 Proxy allowlist settings (optional)

*See also: [GCP_MIGRATION_PLAN.md](GCP_MIGRATION_PLAN.md)*
