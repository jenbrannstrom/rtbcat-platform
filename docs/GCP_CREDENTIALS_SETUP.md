# GCP Credentials Setup & VM Deployment

**Purpose:** How to set up Google Cloud credentials and deploy Cat-Scan to a GCP VM

**Production URL:** https://scan.rtb.cat (hosted on `catscan-prod` VM)

---

## Overview

Cat-Scan uses ONE GCP project with:
1. **Service Account** - for Authorized Buyers API (all AB accounts)
2. **OAuth Client** - for Gmail API (report import)
3. **Compute Engine VM** - to host the application

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

---

## Security Notes

- `~/.catscan/credentials/` is outside git (in home directory)
- Never commit credential files
- Service account key has minimal permissions
- OAuth token contains refresh token - keep secure

---

## Deploying to GCP VM

This section covers deploying Cat-Scan to a Google Cloud Compute Engine VM.

### Current Production Setup

| Property | Value |
|----------|-------|
| Project ID | `augmented-vim-427407-t8` |
| VM Name | `catscan-prod` |
| Zone | `europe-west1-b` |
| Machine Type | `e2-medium` |
| External IP | `104.199.91.219` |
| Domain | `scan.rtb.cat` |

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

**List existing VMs:**
```bash
gcloud compute instances list
```

**Create a new VM (if needed):**
```bash
gcloud compute instances create catscan-prod \
  --zone=europe-west1-b \
  --machine-type=e2-medium \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server
```

**Create firewall rules:**
```bash
# Allow HTTP/HTTPS
gcloud compute firewall-rules create allow-http \
  --allow=tcp:80,tcp:443,tcp:3000,tcp:8000 \
  --target-tags=http-server,https-server
```

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

### Step 8: Verify Deployment

**Check service status:**
```bash
sudo systemctl status catscan-api
sudo systemctl status catscan-dashboard
```

**Test API health:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy","version":"0.9.0","configured":true,"has_credentials":true,"database_exists":true}
```

**Test external access:**
```bash
curl http://104.199.91.219:8000/health
curl http://104.199.91.219:3000
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

5. **Verify services are running:**
   ```bash
   ssh jen@104.199.91.219 "sudo systemctl status catscan-api catscan-dashboard"
   ```

6. **Check health:**
   ```bash
   curl https://scan.rtb.cat/api/health
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
sudo systemctl is-enabled catscan-api catscan-dashboard
```

If not, enable them:
```bash
sudo systemctl enable catscan-api catscan-dashboard
```

---

*See also: [GCP_MIGRATION_PLAN.md](GCP_MIGRATION_PLAN.md)*
