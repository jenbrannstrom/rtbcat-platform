# Cat-Scan Installation Guide

## System Requirements

| Requirement | Minimum Version | Check Command | Install Command (Ubuntu/Debian) |
|-------------|----------------|---------------|--------------------------------|
| Python | 3.11+ | `python3 --version` | `sudo apt install python3.11 python3.11-venv` |
| Node.js | 18+ | `node --version` | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash - && sudo apt install nodejs` |
| npm | 9+ | `npm --version` | (included with Node.js) |
| ffmpeg | 4.0+ | `ffmpeg -version` | `sudo apt install ffmpeg` |
| SQLite | 3.35+ | `sqlite3 --version` | `sudo apt install sqlite3` |

### Optional but Recommended

| Tool | Purpose | Install Command |
|------|---------|-----------------|
| Git | Version control | `sudo apt install git` |
| curl | API testing | `sudo apt install curl` |

---

## Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/rtbcat-platform.git
cd rtbcat-platform
```

### 2. Run the Setup Script

```bash
./setup.sh
```

This will:
- Check all requirements
- Create Python virtual environment
- Install Python dependencies
- Install Node.js dependencies
- Initialize the database

### 3. Configure Google Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Real-Time Bidding API**
4. Create a Service Account:
   - IAM & Admin → Service Accounts → Create
   - Name: `catscan`
   - Go to **Keys** tab → **Add Key** → **Create new key** → **JSON**
   - Download the JSON key file
5. **Upload the JSON key in Cat-Scan:**
   - Open Cat-Scan at http://localhost:3000/setup
   - Go to the **Connect API** tab
   - Drag and drop your JSON key file (or click to browse)
   - The file is securely stored in `~/.catscan/credentials/google-credentials.json`
6. Authorize in [Authorized Buyers](https://authorized-buyers.google.com/):
   - Settings → API Access → Add the service account email (from the JSON file)

### 4. Enable WAL Mode (Important!)

Before running Cat-Scan, enable Write-Ahead Logging for better concurrent performance:

```bash
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode=WAL;"
```

Verify it worked:
```bash
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode;"
# Should return: wal
```

### 5. Start Cat-Scan

```bash
./run.sh
```

This starts both the API (port 8000) and Dashboard (port 3000).

**Manual startup (if run.sh doesn't work):**
```bash
# Terminal 1: API
cd creative-intelligence
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard
npm run dev
```

### 6. Open in Browser

Visit http://localhost:3000

---

## Manual Installation

If the setup script doesn't work for your system:

### Backend (Python)

```bash
cd creative-intelligence

# Create virtual environment
python3.11 -m venv venv

# Install dependencies (no need to activate venv)
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Initialize database
./venv/bin/python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"

# Enable WAL mode
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode=WAL;"
```

### Frontend (Node.js)

```bash
cd dashboard

# Install dependencies
npm install

# Build for production (optional)
npm run build
```

---

## Automatic Report Import (Gmail)

Cat-Scan can automatically download scheduled reports from Google Authorized Buyers. This section explains how to set up a dedicated Gmail account to receive and process reports.

### How Google Sends Reports

| Report Size | Delivery Method | How We Handle It |
|-------------|-----------------|------------------|
| **< 10 MB** | Attached as CSV | Extract attachment from email |
| **≥ 10 MB** | Download link (expires in 30 days) | Download from Google Cloud Storage URL |

The script handles both cases automatically.

### Where Does This Run?

You have two options:

**Option A: Run on Your PC**
```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────────┐
│ Google sends │────▶│ Gmail inbox     │────▶│ Your PC (manual trigger)    │
│ report email │     │                 │     │ Downloads → Imports to DB    │
└──────────────┘     └─────────────────┘     └──────────────────────────────┘
```
- ✅ Easy setup (browser available for first-time auth)
- ❌ PC must stay on
- ❌ Uses your home internet

**Option B: Run on Server (Recommended for Production)**
```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────────┐
│ Google sends │────▶│ Gmail inbox     │────▶│ Server (cron once daily)    │
│ report email │     │                 │     │ Downloads → Imports to DB    │
└──────────────┘     └─────────────────┘     └──────────────────────────────┘
```
- ✅ Runs 24/7
- ✅ Database is local (fast imports)
- ✅ UI shows last import time + "Update Now" button for manual triggers
- ⚠️ First-time auth requires extra step (see below)

### First-Time Auth for Servers (No Browser)

The Gmail API requires a one-time browser authorization. For headless servers:

1. **Run the script on your PC first** (which has a browser)
2. **Copy the token to the server:**
   ```bash
   # On your PC, after successful auth:
   scp ~/.catscan/credentials/gmail-token.json user@your-server:~/.catscan/credentials/
   ```
3. **The server uses the saved token** - no browser needed after that

The token auto-refreshes, so you only do this once.

### Step 1: Create a Dedicated Gmail Account

1. Go to [accounts.google.com](https://accounts.google.com)
2. Click **Create account** → **For myself**
3. Use a name like `catscan.reports.yourcompany@gmail.com`
4. Complete the setup (phone verification, etc.)

> **Why a dedicated account?** Keeps report emails separate, easier to manage, and the OAuth token only accesses this mailbox.

### Step 2: Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your Cat-Scan project (or create one)
3. Go to **APIs & Services** → **Library**
4. Search for **Gmail API**
5. Click **Enable**

### Step 3: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External** (or Internal if using Google Workspace)
   - App name: `Cat-Scan Report Importer`
   - User support email: your email
   - Developer contact: your email
   - Click **Save and Continue** through the scopes (no scopes needed here)
   - Add your dedicated Gmail as a **Test user**
   - Click **Save and Continue**
4. Back in Credentials, click **+ CREATE CREDENTIALS** → **OAuth client ID**
5. Application type: **Desktop app**
6. Name: `Cat-Scan Gmail Importer`
7. Click **Create**
8. Click **Download JSON**
9. Save as `~/.catscan/credentials/gmail-oauth-client.json`

### Step 4: Create the Import Script

> **Note:** Gmail API dependencies (google-auth, google-auth-oauthlib, google-api-python-client) are already included in requirements.txt and installed during the main setup.

Create `scripts/gmail_import.py`:

```python
#!/usr/bin/env python3
"""
Gmail Auto-Import for Cat-Scan
Downloads scheduled reports from Google Authorized Buyers emails.
Handles both:
  - Large reports (≥10MB): Download from GCS URL in email body
  - Small reports (<10MB): Extract CSV attachment from email
"""

import os
import re
import base64
import urllib.request
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CATSCAN_DIR = Path.home() / '.catscan'
CREDENTIALS_DIR = CATSCAN_DIR / 'credentials'
IMPORTS_DIR = CATSCAN_DIR / 'imports'
TOKEN_PATH = CREDENTIALS_DIR / 'gmail-token.json'
CLIENT_SECRET_PATH = CREDENTIALS_DIR / 'gmail-oauth-client.json'

# Create directories
IMPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    
    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"Gmail OAuth client not found at {CLIENT_SECRET_PATH}\n"
                    "Download from Google Cloud Console → APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token for next run
        TOKEN_PATH.write_text(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def find_report_emails(service):
    """Find unread emails from Google Authorized Buyers."""
    query = (
        'from:noreply-google-display-ads-managed-reports@google.com '
        'is:unread'
    )
    
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=10
    ).execute()
    
    return results.get('messages', [])


def extract_download_url(body):
    """Extract the GCS download URL from email body."""
    pattern = r'https://storage\.cloud\.google\.com/buyside-scheduled-report-export/[\w-]+'
    match = re.search(pattern, body)
    return match.group(0) if match else None


def get_email_body(payload):
    """Extract plain text body from email payload."""
    body = ''
    
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
            # Recurse into nested parts
            if 'parts' in part:
                body = get_email_body(part)
                if body:
                    break
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    return body


def extract_attachments(service, message_id, payload):
    """Extract CSV attachments from email (for reports < 10MB)."""
    attachments = []
    
    def find_attachments(parts):
        for part in parts:
            filename = part.get('filename', '')
            if filename.endswith('.csv'):
                attachment_id = part.get('body', {}).get('attachmentId')
                if attachment_id:
                    attachments.append({
                        'filename': filename,
                        'attachment_id': attachment_id
                    })
            # Recurse into nested parts
            if 'parts' in part:
                find_attachments(part['parts'])
    
    if 'parts' in payload:
        find_attachments(payload['parts'])
    
    # Download each attachment
    downloaded_files = []
    for att in attachments:
        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=att['attachment_id']
        ).execute()
        
        data = attachment.get('data', '')
        if data:
            file_data = base64.urlsafe_b64decode(data)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Use original filename but add timestamp
            safe_filename = re.sub(r'[^\w\-.]', '_', att['filename'])
            filepath = IMPORTS_DIR / f"{timestamp}_{safe_filename}"
            filepath.write_bytes(file_data)
            downloaded_files.append(filepath)
            print(f"  Extracted attachment: {filepath.name}")
    
    return downloaded_files


def download_from_url(url, message_id):
    """Download CSV from GCS URL (for reports ≥ 10MB)."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}_{message_id[:8]}.csv"
    filepath = IMPORTS_DIR / filename
    
    print(f"  Downloading from URL: {url[:60]}...")
    urllib.request.urlretrieve(url, filepath)
    
    # Verify it's a valid CSV
    with open(filepath, 'r') as f:
        first_line = f.readline()
        if not first_line or '\x00' in first_line:
            filepath.unlink()  # Delete invalid file
            raise ValueError("Downloaded file doesn't appear to be a valid CSV")
    
    print(f"  Saved: {filepath.name}")
    return [filepath]


def mark_as_read(service, message_id):
    """Mark email as read after processing."""
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


def import_to_catscan(filepath):
    """
    Import the CSV into Cat-Scan database.
    
    TODO: Implement one of these options:
    
    Option 1 - Call the API (if running):
        import requests
        with open(filepath, 'rb') as f:
            requests.post('http://localhost:8000/analytics/rtb-funnel/upload', 
                         files={'file': f})
    
    Option 2 - Direct database import:
        from analytics.rtb_funnel_analyzer import RTBFunnelAnalyzer
        analyzer = RTBFunnelAnalyzer()
        analyzer.import_csv(filepath)
    """
    print(f"  Ready for import: {filepath}")
    # For now, files are saved to ~/.catscan/imports/
    # Implement API call or direct import based on your needs


def process_message(service, message_id):
    """Process a single email - extract attachment OR download from URL."""
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()
    
    payload = message.get('payload', {})
    downloaded_files = []
    
    # First, try to extract CSV attachments (reports < 10MB)
    downloaded_files = extract_attachments(service, message_id, payload)
    
    # If no attachments, look for download URL (reports ≥ 10MB)
    if not downloaded_files:
        body = get_email_body(payload)
        # Also check snippet as fallback
        if not body:
            body = message.get('snippet', '')
        
        url = extract_download_url(body)
        if url:
            downloaded_files = download_from_url(url, message_id)
    
    return downloaded_files


def main():
    print("=" * 60)
    print(f"Cat-Scan Gmail Import - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    
    messages = find_report_emails(service)
    
    if not messages:
        print("No new report emails found.")
        return
    
    print(f"Found {len(messages)} unread report email(s)\n")
    
    total_imported = 0
    
    for msg in messages:
        message_id = msg['id']
        print(f"Processing email: {message_id}")
        
        try:
            downloaded_files = process_message(service, message_id)
            
            if not downloaded_files:
                print("  No CSV found (attachment or URL)")
                continue
            
            for filepath in downloaded_files:
                import_to_catscan(filepath)
                total_imported += 1
            
            mark_as_read(service, message_id)
            print("  ✓ Marked as read")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        
        print()
    
    print("=" * 60)
    print(f"Done! Imported {total_imported} file(s) to ~/.catscan/imports/")
    print("=" * 60)


if __name__ == '__main__':
    main()
```

Make it executable:
```bash
chmod +x scripts/gmail_import.py
```

### Step 5: First-Time Authorization

**If running on your PC (has a browser):**

```bash
cd creative-intelligence
source venv/bin/activate
python scripts/gmail_import.py
```

This will:
1. Open a browser window
2. Ask you to log in to your **dedicated Gmail account**
3. Grant permission to read/modify emails
4. Save the token to `~/.catscan/credentials/gmail-token.json`

**If deploying to a server (no browser):**

```bash
# 1. On your PC, run the script to generate the token:
python scripts/gmail_import.py
# Complete browser auth

# 2. Copy BOTH credential files to server:
scp ~/.catscan/credentials/gmail-oauth-client.json user@server:~/.catscan/credentials/
scp ~/.catscan/credentials/gmail-token.json user@server:~/.catscan/credentials/

# 3. On the server, verify it works:
python scripts/gmail_import.py
# Should run without opening a browser
```

> **Note:** The token auto-refreshes indefinitely. You only do this once unless you revoke access in Google Account settings.

### Step 6: Configure Scheduled Reports in Authorized Buyers

1. Go to [Authorized Buyers](https://authorized-buyers.google.com/)
2. Navigate to **Reporting** → **Saved Reports** (or create a new report)
3. Click **Schedule**
4. Set:
   - **Frequency:** Daily
   - **Email to:** `catscan.reports.yourcompany@gmail.com` (your dedicated Gmail)
   - **Time:** Early morning (e.g., 6:00 AM)
5. Save the schedule

### Step 7: Set Up Automatic Polling (Cron)

Add a cron job to check for new emails once daily (recommended: early morning after scheduled reports arrive).

**On Linux (server or PC):**
```bash
crontab -e
```

Add this line (runs daily at 7:00 AM, adjust the path):
```cron
0 7 * * * cd /home/ubuntu/rtbcat-platform/creative-intelligence && ./venv/bin/python scripts/gmail_import.py >> /home/ubuntu/.catscan/logs/gmail_import.log 2>&1
```

**On Mac (if running on your laptop):**
```bash
crontab -e
```

Add:
```cron
0 7 * * * cd /Users/yourname/rtbcat-platform/creative-intelligence && ./venv/bin/python scripts/gmail_import.py >> ~/.catscan/logs/gmail_import.log 2>&1
```

Create the logs directory:
```bash
mkdir -p ~/.catscan/logs
```

**Manual Import via UI:**

You can also trigger an import manually from the Cat-Scan UI:
1. Go to http://localhost:3000/setup
2. Click the **Gmail Reports** tab
3. Click **Import Now** to check for new reports immediately
4. The UI displays the last import time and results

**Verify cron is working:**
```bash
# Check the log after the scheduled time:
tail -f ~/.catscan/logs/gmail_import.log
```

### Step 8: Verify It's Working

1. Wait for a scheduled report to arrive (or trigger one manually in Authorized Buyers)
2. Check the logs:
   ```bash
   tail -f ~/.catscan/logs/gmail_import.log
   ```
3. Check for downloaded files:
   ```bash
   ls -la ~/.catscan/imports/
   ```

### Troubleshooting Gmail Import

**"Gmail OAuth client not found"**
```bash
# Verify the file exists
ls -la ~/.catscan/credentials/gmail-oauth-client.json

# If missing, download from Google Cloud Console:
# APIs & Services → Credentials → Your OAuth client → Download JSON
```

**"Token has been expired or revoked"**
```bash
# Delete old token and re-authorize
rm ~/.catscan/credentials/gmail-token.json
python scripts/gmail_import.py
# This will open a browser - log in again
```

**"No CSV found (attachment or URL)"**

The script looks for:
1. CSV attachments (reports < 10MB)
2. Download URL in email body (reports ≥ 10MB)

If neither is found, check:
- Is the email actually a report? (Check sender address)
- Did Google change their email format?

**Running on a headless server (no browser)**

First-time auth requires a browser. Workaround:
```bash
# 1. On your PC (has browser), run:
python scripts/gmail_import.py
# Complete the browser auth

# 2. Copy the token to your server:
scp ~/.catscan/credentials/gmail-token.json user@server:~/.catscan/credentials/

# 3. On the server, the script now works without browser
```

**Cron not running**
```bash
# Check if cron service is running
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Test the script manually first
cd /path/to/creative-intelligence
./venv/bin/python scripts/gmail_import.py
```

**Permission errors on server**
```bash
chmod 600 ~/.catscan/credentials/gmail-token.json
chmod 600 ~/.catscan/credentials/gmail-oauth-client.json
```

---

## Running as a Service (Linux)

### Create systemd service for API

```bash
sudo tee /etc/systemd/system/catscan-api.service << EOF
[Unit]
Description=Cat-Scan API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/creative-intelligence
Environment=PATH=$(pwd)/creative-intelligence/venv/bin
ExecStart=$(pwd)/creative-intelligence/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable catscan-api
sudo systemctl start catscan-api
```

### Check status

```bash
sudo systemctl status catscan-api
```

---

## Database Maintenance

### Monthly Maintenance

```bash
# Reclaim space from deleted rows
sqlite3 ~/.catscan/catscan.db "VACUUM;"

# Check database health
sqlite3 ~/.catscan/catscan.db "PRAGMA integrity_check;"

# Check size
ls -lh ~/.catscan/catscan.db
```

### Data Retention (Optional)

Keep only the last 90 days of data:
```bash
sqlite3 ~/.catscan/catscan.db "DELETE FROM rtb_daily WHERE day < date('now', '-90 days'); VACUUM;"
```

### Backups

```bash
# Simple backup (safe with WAL mode)
cp ~/.catscan/catscan.db ~/backups/catscan_$(date +%Y%m%d).db

# Or use SQLite's backup command
sqlite3 ~/.catscan/catscan.db ".backup ~/backups/catscan_$(date +%Y%m%d).db"
```

---

## Troubleshooting

### "Python not found"

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Or use pyenv for version management
curl https://pyenv.run | bash
pyenv install 3.11.0
pyenv global 3.11.0
```

### "Node.js not found"

```bash
# Using NodeSource (recommended)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Or use nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 20
nvm use 20
```

### "ffmpeg not found"

```bash
sudo apt install ffmpeg
```

Video thumbnail generation won't work without ffmpeg, but all other features will.

### "Permission denied" on credentials

```bash
chmod 600 ~/.catscan/credentials/google-credentials.json
chmod 600 ~/.catscan/credentials/gmail-token.json
```

### "PERMISSION_DENIED" from Google API

1. Verify Real-Time Bidding API is enabled in Cloud Console
2. Verify service account email is added in Authorized Buyers UI
3. Check the account ID matches your Authorized Buyers account

### Database errors

```bash
# Check WAL mode is enabled
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode;"

# Reset database (WARNING: deletes all data)
rm ~/.catscan/catscan.db
python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode=WAL;"
```

---

## Verify Installation

Run the health check:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "configured": true,
  "has_credentials": true,
  "database_exists": true
}
```

---

## Directory Structure

After installation, Cat-Scan uses these directories:

```
~/.catscan/
├── catscan.db              # SQLite database
├── catscan.db-wal          # Write-ahead log (normal)
├── catscan.db-shm          # Shared memory (normal)
├── thumbnails/             # Generated video thumbnails
├── imports/                # Downloaded CSV reports
├── logs/                   # Import logs
└── credentials/
    ├── google-credentials.json    # RTB API service account
    ├── gmail-oauth-client.json    # Gmail API OAuth client
    └── gmail-token.json           # Gmail API token (auto-generated)
```

---

## Next Steps

1. Visit http://localhost:3000/connect to configure credentials
2. Discover and sync your buyer seats
3. Set up automatic report import (see [Gmail Import](#automatic-report-import-gmail))
4. Start analyzing QPS waste!

---

## Getting Help

- Check the [Troubleshooting](#troubleshooting) section above
- Open an issue on GitHub
- See [docs/](docs/) for detailed documentation