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
   - Download JSON key
5. Authorize in [Authorized Buyers](https://authorized-buyers.google.com/):
   - Settings → API Access → Add the service account email

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
# Start the API
cd creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# In another terminal, start the dashboard
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
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"

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

### Overview

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌──────────┐
│ Google Authorized│────▶│ Gmail (dedicated│────▶│ Python Script│────▶│ Cat-Scan │
│ Buyers Report    │     │ catscan@gmail)  │     │ (cron job)   │     │ Database │
└──────────────────┘     └─────────────────┘     └──────────────┘     └──────────┘
```

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

### Step 4: Install Gmail API Dependencies

```bash
cd creative-intelligence
source venv/bin/activate
pip install google-auth google-auth-oauthlib google-api-python-client
```

### Step 5: Create the Import Script

Create `scripts/gmail_import.py`:

```python
#!/usr/bin/env python3
"""
Gmail Auto-Import for Cat-Scan
Downloads scheduled reports from Google Authorized Buyers emails.
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


def extract_download_url(service, message_id):
    """Extract the GCS download URL from email body."""
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()
    
    # Get email body
    body = ''
    payload = message.get('payload', {})
    
    # Check for multipart
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    # Also check snippet as fallback
    if not body:
        body = message.get('snippet', '')
    
    # Extract GCS URL
    pattern = r'https://storage\.cloud\.google\.com/buyside-scheduled-report-export/[\w-]+'
    match = re.search(pattern, body)
    
    if match:
        return match.group(0)
    
    return None


def download_report(url, message_id):
    """Download CSV from GCS URL."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}_{message_id[:8]}.csv"
    filepath = IMPORTS_DIR / filename
    
    print(f"Downloading: {url}")
    print(f"Saving to: {filepath}")
    
    urllib.request.urlretrieve(url, filepath)
    
    # Verify it's a valid CSV
    with open(filepath, 'r') as f:
        first_line = f.readline()
        if not first_line or '\x00' in first_line:
            raise ValueError("Downloaded file doesn't appear to be a valid CSV")
    
    return filepath


def mark_as_read(service, message_id):
    """Mark email as read after processing."""
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


def import_to_catscan(filepath):
    """Import the CSV into Cat-Scan database."""
    import subprocess
    
    # Option 1: Call the API
    # requests.post('http://localhost:8000/analytics/rtb-funnel/upload', files={'file': open(filepath, 'rb')})
    
    # Option 2: Direct database import (if API not running)
    # This is a placeholder - implement based on your import logic
    print(f"TODO: Import {filepath} to database")
    print("For now, files are saved to ~/.catscan/imports/")
    print("Upload manually via the dashboard or implement API call here.")


def main():
    print("=" * 60)
    print(f"Cat-Scan Gmail Import - {datetime.now()}")
    print("=" * 60)
    
    service = get_gmail_service()
    messages = find_report_emails(service)
    
    if not messages:
        print("No new report emails found.")
        return
    
    print(f"Found {len(messages)} unread report email(s)")
    
    for msg in messages:
        message_id = msg['id']
        print(f"\nProcessing message: {message_id}")
        
        try:
            url = extract_download_url(service, message_id)
            
            if not url:
                print("  No download URL found in email (report may be attached)")
                # TODO: Handle attached CSVs for reports < 10MB
                continue
            
            filepath = download_report(url, message_id)
            print(f"  Downloaded: {filepath.name}")
            
            import_to_catscan(filepath)
            
            mark_as_read(service, message_id)
            print("  Marked as read")
            
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    print("\nDone!")


if __name__ == '__main__':
    main()
```

Make it executable:
```bash
chmod +x scripts/gmail_import.py
```

### Step 6: First-Time Authorization

Run the script once manually to authorize:

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

> **Note:** You only need to do this once. The token refreshes automatically.

### Step 7: Configure Scheduled Reports in Authorized Buyers

1. Go to [Authorized Buyers](https://authorized-buyers.google.com/)
2. Navigate to **Reporting** → **Saved Reports** (or create a new report)
3. Click **Schedule**
4. Set:
   - **Frequency:** Daily
   - **Email to:** `catscan.reports.yourcompany@gmail.com` (your dedicated Gmail)
   - **Time:** Early morning (e.g., 6:00 AM)
5. Save the schedule

### Step 8: Set Up Automatic Polling (Cron)

Add a cron job to check for new emails every 15 minutes:

```bash
crontab -e
```

Add this line:
```cron
*/15 * * * * cd /path/to/rtbcat-platform/creative-intelligence && ./venv/bin/python scripts/gmail_import.py >> ~/.catscan/logs/gmail_import.log 2>&1
```

Create the logs directory:
```bash
mkdir -p ~/.catscan/logs
```

### Step 9: Verify It's Working

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
```

**"Token has been expired or revoked"**
```bash
# Delete old token and re-authorize
rm ~/.catscan/credentials/gmail-token.json
python scripts/gmail_import.py
```

**"No download URL found in email"**
- Reports smaller than 10MB are attached directly (not via URL)
- Check if the email has a CSV attachment
- The script currently only handles URL-based downloads

**Cron not running**
```bash
# Check cron logs
grep CRON /var/log/syslog | tail -20

# Verify cron is running
systemctl status cron
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