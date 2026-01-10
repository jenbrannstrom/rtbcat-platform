# GCP Credentials Setup & VM Deployment

**Purpose:** How to set up Google Cloud credentials and deploy Cat-Scan to a GCP VM

**Production URL:** https://scan.rtb.cat (hosted on `catscan-production` VM)

---

## Quick Deploy (Code Updates)

After pushing to GitHub, deploy to production:

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap -- \
  "cd /opt/catscan && sudo -u catscan git pull && sudo docker-compose -f docker-compose.gcp.yml down && sudo docker-compose -f docker-compose.gcp.yml up -d --build"
```

Or step by step:
1. `gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap`
2. `cd /opt/catscan && sudo -u catscan git pull`
3. `sudo docker-compose -f docker-compose.gcp.yml down && sudo docker-compose -f docker-compose.gcp.yml up -d --build`

Verify deployment:
```bash
sudo docker ps  # Both containers should be running
curl -s http://localhost:8000/health  # Should return healthy status
```

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

## Troubleshooting

### "Access blocked: org_internal"
Your Gmail account is in a different Workspace org than the GCP project.
Fix: Set OAuth consent screen to **External** and add Gmail as test user.

### "invalid_request" on OAuth
The OOB flow is deprecated. Use `run_local_server()` which redirects to localhost.

### Token expired
Gmail tokens auto-refresh. If issues persist, re-run `python scripts/gmail_auth.py`

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
| Machine Type | `e2-medium` |
| External IP | `35.205.211.184` |
| Domain | `scan.rtb.cat` |
| SSL Certificate | Let's Encrypt (auto-renewed) |

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
gcloud compute instances create catscan-prod \
  --zone=europe-west1-b \
  --machine-type=e2-medium \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
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

# Clone repository
git clone https://github.com/rtbcat/rtbcat-platform.git
cd rtbcat-platform

# Run setup
./setup.sh
```

### Step 5: Copy Credentials to VM

From your local machine (where credentials are already set up):

```bash
# Copy service account
scp ~/.catscan/credentials/catscan-service-account.json \
  jen@104.199.91.219:~/.catscan/credentials/

# Copy Gmail OAuth client
scp ~/.catscan/credentials/gmail-oauth-client.json \
  jen@104.199.91.219:~/.catscan/credentials/

# Copy Gmail token (already authorized)
scp ~/.catscan/credentials/gmail-token.json \
  jen@104.199.91.219:~/.catscan/credentials/
```

### Step 6: Register Service Account in Database

**IMPORTANT:** The API requires service accounts to be registered in the database, not just present as files.

SSH to VM and run:

```bash
sqlite3 ~/.catscan/catscan.db "INSERT INTO service_accounts
  (id, client_email, project_id, display_name, credentials_path, is_active)
  VALUES (
    'sa-1',
    'catscan-api@augmented-vim-427407-t8.iam.gserviceaccount.com',
    'augmented-vim-427407-t8',
    'Cat-Scan API',
    '~/.catscan/credentials/catscan-service-account.json',
    1
  );"
```

Verify:
```bash
sqlite3 ~/.catscan/catscan.db "SELECT * FROM service_accounts;"
```

### Step 7: Create Systemd Services

**API Service:**
```bash
sudo tee /etc/systemd/system/catscan-api.service << 'EOF'
[Unit]
Description=Cat-Scan API
After=network.target

[Service]
Type=simple
User=jen
WorkingDirectory=/home/jen/rtbcat-platform
ExecStart=/home/jen/rtbcat-platform/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

**Dashboard Service:**
```bash
sudo tee /etc/systemd/system/catscan-dashboard.service << 'EOF'
[Unit]
Description=Cat-Scan Dashboard
After=network.target

[Service]
Type=simple
User=jen
WorkingDirectory=/home/jen/rtbcat-platform/dashboard
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=10
Environment=PORT=3000

[Install]
WantedBy=multi-user.target
EOF
```

**Enable and start services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable catscan-api catscan-dashboard
sudo systemctl start catscan-api catscan-dashboard
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
    server_name scan.rtb.cat 104.199.91.219;

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

**Production Fix:** Create default admin user (see "Fresh Install Workaround" below).

### Fresh Install Workaround (Until Secure First-Run is Implemented)

On fresh installs, multi-user mode is enabled but no users exist. Apply this workaround:

**Option A: Disable multi-user mode (single-user/development)**
```bash
ssh jen@104.199.91.219 "sqlite3 ~/.catscan/catscan.db \"UPDATE system_settings SET value='0' WHERE key='multi_user_enabled';\""
sudo systemctl restart catscan-api
```

**Option B: Create admin user manually (recommended for production)**
```bash
ssh jen@104.199.91.219 "~/rtbcat-platform/venv/bin/python3 -c \"
import sqlite3, uuid, os, hashlib

db_path = os.path.expanduser('~/.catscan/catscan.db')
conn = sqlite3.connect(db_path)

# Check if admin exists
if conn.execute('SELECT COUNT(*) FROM users WHERE email=?', ('admin@local',)).fetchone()[0] > 0:
    print('Admin already exists')
else:
    # Use sha256 hash (auth_v2.py fallback format)
    password_hash = 'sha256:' + hashlib.sha256('admin'.encode()).hexdigest()
    user_id = str(uuid.uuid4())
    conn.execute('INSERT INTO users (id, email, password_hash, display_name, role, is_active) VALUES (?,?,?,?,?,?)',
        (user_id, 'admin@local', password_hash, 'Administrator', 'admin', 1))
    conn.commit()
    print(f'Created: admin@local / admin')
conn.close()
\""
ssh jen@104.199.91.219 "sudo systemctl restart catscan-api"
```

After login with admin/admin, immediately change the password via the UI.

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

For new installations, Cat-Scan should use a secure first-run flow:

### Default Credentials
- **Username:** `admin`
- **Password:** `admin`

### Security Requirements
1. On first login with default credentials, user MUST change password
2. Credentials cannot be uploaded until password is changed
3. Multi-user mode is enabled by default for security

### Setup Steps (Post-Installation)

1. **Access the dashboard:** `http://YOUR_IP:3000`
2. **Login with:** `admin` / `admin`
3. **Change password immediately** (system enforces this)
4. **Only then:** Upload Google credentials via Settings → Credentials

This ensures no sensitive API keys can be added until the installation is secured.

---

## TO BE DONE: Secure First-Run Implementation

**Status:** Not yet implemented. Currently multi-user mode must be manually disabled or admin user manually created.

### Implementation Tasks

#### 1. Database Migration (014_first_run_admin.sql)
```sql
-- Add must_change_password column to users table
ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0;

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_users_must_change_password ON users(must_change_password);
```

#### 2. Default Admin Creation (api/auth_v2.py)
On startup, if no users exist:
- Create user: `admin@local` with password: `admin`
- Set `must_change_password=1`
- Set `role='admin'`

```python
async def ensure_default_admin():
    """Create default admin if no users exist."""
    repo = _get_user_repo()
    user_count = await repo.count_users()

    if user_count == 0:
        user_id = str(uuid.uuid4())
        password_hash = hash_password("admin")
        await repo.create_user(
            user_id=user_id,
            email="admin@local",
            password_hash=password_hash,
            display_name="Administrator",
            role="admin",
            must_change_password=True,
        )
```

#### 3. Update User Model (storage/repositories/user_repository.py)
- Add `must_change_password: bool = False` to `User` dataclass
- Update all SELECT queries to include `must_change_password`
- Update `create_user()` to accept `must_change_password` parameter

#### 4. Auth Flow Changes (api/auth_v2.py)
After successful login:
```python
return LoginResponse(
    status="success",
    user={...},
    must_change_password=user.must_change_password,  # NEW
    message="Login successful",
)
```

Update `change_password()` endpoint to clear the flag:
```python
await repo.update_user(user.id, password_hash=new_hash, must_change_password=False)
```

#### 5. Block Credentials Upload (api/dependencies.py)
New dependency:
```python
async def require_password_changed(user: User = Depends(get_current_user)) -> User:
    """Block sensitive operations until password is changed."""
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="Please change your default password before adding credentials.",
        )
    return user
```

Apply to `api/routers/config.py`:
```python
@router.post("/config/service-accounts", response_model=CredentialsUploadResponse)
async def add_service_account(
    request: CredentialsUploadRequest,
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(require_password_changed),  # NEW
):
```

#### 6. Frontend Changes (dashboard)
- Check `must_change_password` in login response
- If true, redirect to `/change-password` page
- Block navigation to Settings → Credentials until password changed

### Files to Modify
- `migrations/014_first_run_admin.sql` (new)
- `storage/repositories/user_repository.py`
- `api/auth_v2.py`
- `api/dependencies.py`
- `api/routers/config.py`
- `dashboard/src/app/login/page.tsx`
- `dashboard/src/components/ProtectedRoute.tsx`

### Testing Checklist
- [ ] Fresh install creates admin@local with admin/admin
- [ ] Login with admin/admin shows must_change_password=true
- [ ] Cannot access /config/service-accounts until password changed
- [ ] After password change, must_change_password=false
- [ ] Credentials upload works after password change

---

*See also: [GCP_MIGRATION_PLAN.md](GCP_MIGRATION_PLAN.md)*
