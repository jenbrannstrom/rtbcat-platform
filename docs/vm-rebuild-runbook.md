# VM Rebuild Runbook

Complete steps to rebuild the Cat-Scan VM from scratch after a Terraform destroy/recreate.

## Prerequisites

- GCP project: `catscan-prod-202601`
- VM: `catscan-production` in `europe-west1-b`
- Artifact Registry: `europe-west1-docker.pkg.dev/catscan-prod-202601/catscan`
- Local credentials in `~/.catscan/credentials/`

## 1. Terraform Apply

```bash
cd terraform/gcp
terraform apply -replace=google_compute_instance.catscan
```

This recreates the VM with a fresh disk. The startup script handles initial setup.

## 2. Known Startup Script Issues (Fixed in 7f48a37)

### OAuth2 Proxy Cookie Secret
The cookie_secret must be exactly 16, 24, or 32 bytes. The fix:

```bash
# WRONG (produces 44 bytes base64):
COOKIE_SECRET=$(openssl rand -base64 32 | tr -d '\n')

# CORRECT (produces 32 hex chars = 16 bytes):
COOKIE_SECRET=$(openssl rand -hex 16)
```

### Docker Authentication
Docker needs auth to pull from Artifact Registry:

```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet
```

## 3. Verify Containers Running

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo docker ps
"
```

Expected: `catscan-api` and `catscan-dashboard` both running and healthy.

## 4. Fix Data Directory Permissions

The API container runs as UID 999, not 1000:

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo chown -R 999:999 /home/catscan/.catscan/
sudo chmod 755 /home/catscan/.catscan/
"
```

## 5. Upload Credentials to Secret Manager

From local machine (credentials in `~/.catscan/credentials/`):

```bash
# Service account for Authorized Buyers API
gcloud secrets versions add catscan-service-account \
  --data-file=$HOME/.catscan/credentials/catscan-service-account.json \
  --project=catscan-prod-202601

# Gmail OAuth client
gcloud secrets versions add gmail-oauth-client \
  --data-file=$HOME/.catscan/credentials/gmail-oauth-client.json \
  --project=catscan-prod-202601

# Gmail token (after OAuth flow)
gcloud secrets versions add gmail-token \
  --data-file=$HOME/.catscan/credentials/gmail-token.json \
  --project=catscan-prod-202601
```

## 6. Fetch Credentials on VM

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo bash -c '
mkdir -p /home/catscan/.catscan/credentials

# Fetch from Secret Manager
gcloud secrets versions access latest --secret=catscan-service-account > /home/catscan/.catscan/credentials/catscan-service-account.json
gcloud secrets versions access latest --secret=gmail-oauth-client > /home/catscan/.catscan/credentials/gmail-oauth-client.json
gcloud secrets versions access latest --secret=gmail-token > /home/catscan/.catscan/credentials/gmail-token.json

# Copy service account as google-credentials.json (used by API)
cp /home/catscan/.catscan/credentials/catscan-service-account.json /home/catscan/.catscan/credentials/google-credentials.json

# Fix permissions for container (UID 999)
chown -R 999:999 /home/catscan/.catscan/credentials/
chmod 644 /home/catscan/.catscan/credentials/*.json
'
"
```

## 7. Register Service Account in Database

The service account must be registered in the SQLite database:

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo docker exec catscan-api python -c '
import sqlite3
import uuid
import json
from datetime import datetime

db_path = \"/home/rtbcat/.catscan/catscan.db\"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Read service account
with open(\"/home/rtbcat/.catscan/credentials/catscan-service-account.json\") as f:
    sa = json.load(f)

sa_id = str(uuid.uuid4())
cursor.execute(\"\"\"
    INSERT OR REPLACE INTO service_accounts
    (id, name, email, credentials_json, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
\"\"\", (
    sa_id,
    \"Cat-Scan Service Account\",
    sa.get(\"client_email\", \"\"),
    json.dumps(sa),
    1,
    datetime.now().isoformat()
))
conn.commit()
print(f\"Service account registered: {sa_id}\")
'
"
```

## 8. Gmail OAuth Setup

Gmail requires TWO scopes for full functionality:
- `gmail.modify` - Read emails and mark as read
- `devstorage.read_only` - Download reports from GCS URLs

### Generate OAuth URL

```bash
python3 -c "
import urllib.parse

client_id = '449322304772-1ba125l02gpd9o4fn28spk06i0tnoiev.apps.googleusercontent.com'
redirect_uri = 'http://localhost:8080/'
scopes = 'https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/devstorage.read_only'

params = {
    'client_id': client_id,
    'redirect_uri': redirect_uri,
    'scope': scopes,
    'response_type': 'code',
    'access_type': 'offline',
    'prompt': 'consent',
    'login_hint': 'cat-scan@rtb.cat',
}

url = 'https://accounts.google.com/o/oauth2/auth?' + urllib.parse.urlencode(params)
print(url)
"
```

### Exchange Code for Token

After user completes OAuth flow and gets redirected to `http://localhost:8080/?code=...`:

```bash
python3 -c "
import json
import urllib.request
import urllib.parse

code = 'PASTE_CODE_HERE'
client_id = '449322304772-1ba125l02gpd9o4fn28spk06i0tnoiev.apps.googleusercontent.com'
client_secret = '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'
redirect_uri = 'http://localhost:8080/'

data = urllib.parse.urlencode({
    'code': code,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': redirect_uri,
    'grant_type': 'authorization_code',
}).encode()

req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
req.add_header('Content-Type', 'application/x-www-form-urlencoded')

with urllib.request.urlopen(req) as resp:
    token_data = json.loads(resp.read().decode())

token_file = {
    'token': token_data['access_token'],
    'refresh_token': token_data['refresh_token'],
    'token_uri': 'https://oauth2.googleapis.com/token',
    'client_id': client_id,
    'client_secret': client_secret,
    'scopes': ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/devstorage.read_only'],
    'universe_domain': 'googleapis.com',
    'account': '',
    'expiry': ''
}

with open('gmail-token.json', 'w') as f:
    json.dump(token_file, f, indent=2)
print('Token saved to gmail-token.json')
"
```

Then upload to Secret Manager and fetch on VM (steps 5-6).

## 9. Sync Seats and Creatives

Via dashboard: Click "Sync All" button in sidebar.

Or via API:
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo docker exec catscan-api python -c '
# This syncs all seats, creatives, endpoints, and pretargeting configs
import asyncio
from api.routers.seats import sync_all_seats
asyncio.run(sync_all_seats())
'
"
```

## 10. Run Gmail Import

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --project=catscan-prod-202601 --command="
sudo docker exec catscan-api python -c '
from scripts.gmail_import import run_import
result = run_import(verbose=True)
print(f\"Imported {result.get(\"files_imported\", 0)} files\")
'
"
```

## 11. Trigger Precompute Refresh

Via dashboard: Click "Refresh" button on home page.

Or trigger Cloud Scheduler job manually in GCP Console.

## Verification Checklist

- [ ] `docker ps` shows both containers healthy
- [ ] Dashboard loads at https://scan.rtb.cat/
- [ ] Health check: `curl https://scan.rtb.cat/api/health` returns `configured: true`
- [ ] Seats appear in sidebar dropdown
- [ ] Creatives page shows creative count
- [ ] Pretargeting configs appear on home page
- [ ] RTB endpoints show QPS allocation

## Common Issues

### "No seats connected"
- Service account not registered in database (step 7)
- Credentials file permissions wrong (step 4)

### "Session expired" on dashboard
- OAuth2 Proxy cookie_secret wrong (step 2)

### Gmail import fails with "Permission denied"
- Credentials owned by wrong UID (should be 999, not 1000)
- Run step 4 to fix permissions

### Gmail import downloads but can't authenticate to GCS
- Token missing `devstorage.read_only` scope
- Re-run OAuth flow with both scopes (step 8)

### Pretargeting shows "No data"
- Need to import quality/bidsinauction CSV reports
- These reports have a known import bug (28 values for 29 columns)

## Files Reference

| File | Purpose |
|------|---------|
| `terraform/gcp/startup.sh` | VM initialization script |
| `docker-compose.gcp.yml` | Container orchestration |
| `scripts/gmail_import.py` | Gmail report import |
| `~/.catscan/credentials/` | Local credential storage |
| `/home/catscan/.catscan/` | VM data directory |
