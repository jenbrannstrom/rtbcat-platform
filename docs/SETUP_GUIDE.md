# Cat-Scan Setup Guide

Get Cat-Scan running and connected to your Google Authorized Buyers account.

**Total time:** ~30 minutes (first-time setup)

---

## Prerequisites

Before you begin, make sure you have:

- [ ] **Google Authorized Buyers account** — You're already a bidder on the RTB exchange
- [ ] **Google Cloud Console access** — Same Google account as your Authorized Buyers
- [ ] **Python 3.12+** — Check with `python3 --version`
- [ ] **Node.js 18+** — Check with `node --version`
- [ ] **30 minutes** — First-time setup; subsequent syncs take seconds

---

## Phase 1: Install Cat-Scan (5 min)

### 1.1 Download Cat-Scan

```bash
# Clone the repository
git clone https://github.com/your-org/catscan.git
cd catscan
```

Or download the ZIP from the releases page.

### 1.2 Run the Install Script

```bash
# Make the script executable and run it
chmod +x install.sh
./install.sh
```

The installer will:
- Create a Python virtual environment
- Install backend dependencies
- Install frontend dependencies
- Initialize the SQLite database at `~/.catscan/catscan.db`

### 1.3 Start the Services

```bash
# Start the API server (systemd service)
sudo systemctl start rtbcat-api

# Start the dashboard
cd dashboard
npm run dev
```

To check service status: `sudo systemctl status rtbcat-api`

### 1.4 Verify Installation

Open http://localhost:3000 in your browser.

You should see the Cat-Scan dashboard with a message: **"No seats connected"**

[SCREENSHOT: Empty Cat-Scan dashboard showing "No seats connected" message]

---

## Phase 2: Create Google Service Account (15-30 min)

This is a one-time setup. You'll create a service account in Google Cloud that Cat-Scan uses to read your creative data.

### 2.1 Create a GCP Project

1. Go to **[console.cloud.google.com](https://console.cloud.google.com)**
2. Click the project dropdown at the top of the page
3. Click **"New Project"**
4. Enter project name: `catscan` (or any name you prefer)
5. Click **"Create"**
6. Wait 30 seconds for the project to be created
7. Select your new project from the dropdown

[SCREENSHOT: GCP Console - New Project dialog with "catscan" entered as name]

### 2.2 Enable the Real-Time Bidding API

1. In the left sidebar, click **"APIs & Services"**
2. Click **"Library"** (or go to [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library))
3. In the search box, type: `Real-Time Bidding API`
4. Click on **"Real-Time Bidding API"** in the results
5. Click the blue **"Enable"** button
6. Wait for the API to be enabled (10-20 seconds)

[SCREENSHOT: GCP API Library showing Real-Time Bidding API with Enable button]

> **Note:** If you don't see this API, your Google account may not have Authorized Buyers access. Contact your account manager.

### 2.3 Create a Service Account

1. In the left sidebar, click **"IAM & Admin"**
2. Click **"Service Accounts"**
3. Click **"+ Create Service Account"** at the top
4. Fill in the details:
   - **Service account name:** `catscan-sync`
   - **Service account ID:** (auto-filled as `catscan-sync`)
   - **Description:** `Cat-Scan creative sync service`
5. Click **"Create and Continue"**
6. **Skip** the "Grant access" step — click **"Continue"**
7. **Skip** the "Grant users access" step — click **"Done"**

[SCREENSHOT: Create Service Account form with "catscan-sync" entered]

### 2.4 Download the JSON Key

1. In the Service Accounts list, click on **`catscan-sync@your-project.iam.gserviceaccount.com`**
2. Click the **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"**
4. Select **"JSON"** format
5. Click **"Create"**
6. A JSON file will download automatically — **save this securely!**

[SCREENSHOT: Service Account Keys tab with "Add Key" dropdown open]

> **Security:** This JSON file is like a password. Don't share it, commit it to git, or post it publicly. Store it in `~/.catscan/credentials/` or another secure location.

Move the key to the credentials folder:

```bash
# Create the credentials directory
mkdir -p ~/.catscan/credentials

# Move your downloaded key (adjust the filename)
mv ~/Downloads/catscan-*.json ~/.catscan/credentials/google-credentials.json

# Restrict permissions
chmod 600 ~/.catscan/credentials/google-credentials.json
```

### 2.5 Link Service Account to Authorized Buyers

This step grants Cat-Scan permission to read your creative data.

1. Go to **[authorizedbuyers.google.com](https://authorizedbuyers.google.com)**
2. Log in with your Authorized Buyers account
3. Click the **gear icon** (Settings) in the top right
4. Click **"Account settings"**
5. Scroll down to **"API access"** or **"Service accounts"** section
6. Click **"Add service account"** (or similar)
7. Paste the service account email:
   ```
   catscan-sync@your-project-id.iam.gserviceaccount.com
   ```
   (Find this in GCP → IAM & Admin → Service Accounts)
8. Select **"Read-only"** access level
9. Click **"Save"** or **"Add"**

[SCREENSHOT: Authorized Buyers Settings showing Service Account linking]

> **Note:** Changes may take 5-10 minutes to propagate. If you get permission errors, wait and try again.

---

## Phase 3: Connect Cat-Scan (2 min)

Now let's connect Cat-Scan to your Google account.

### 3.1 Configure Cat-Scan

Run the configuration command:

```bash
cd creative-intelligence
source venv/bin/activate

python -c "
from config.config_manager import ConfigManager, AppConfig, AuthorizedBuyersConfig

config = AppConfig(
    authorized_buyers=AuthorizedBuyersConfig(
        service_account_path='~/.catscan/credentials/google-credentials.json',
        account_id='YOUR_BIDDER_ID'  # Replace with your Authorized Buyers account ID
    )
)

manager = ConfigManager()
manager.save(config)
print('Configuration saved!')
"
```

> **Find your Bidder ID:** In Authorized Buyers, go to Settings → Account settings. Your Bidder ID is the number shown (e.g., `299038253`).

### 3.2 Discover and Add Seats

```bash
# Restart the API to pick up the new config
sudo systemctl restart rtbcat-api
```

Then in the dashboard:

1. Go to **http://localhost:3000/settings**
2. Click **"Discover Seats"**
3. Select the seats you want to sync
4. Click **"Add Selected"**

Or use the API directly:

```bash
# Discover available seats
curl -X POST http://localhost:8000/seats/discover \
  -H "Content-Type: application/json" \
  -d '{"bidder_id": "YOUR_BIDDER_ID"}'
```

### 3.3 Sync Your First Creatives

In the dashboard sidebar, click the **sync button** (🔄) next to your seat.

Or use the CLI:

```bash
curl -X POST http://localhost:8000/seats/YOUR_BUYER_ID/sync
```

You should see creatives appearing in the dashboard!

[SCREENSHOT: Cat-Scan dashboard showing synced creatives]

---

## Troubleshooting

### "Permission denied" or "403 Forbidden"

**Cause:** Service account not linked in Authorized Buyers, or changes haven't propagated.

**Fix:**
1. Verify the service account email is added in Authorized Buyers settings
2. Wait 10 minutes for changes to propagate
3. Double-check you're using the correct bidder ID

### "API not enabled" or "403: Access Not Configured"

**Cause:** Real-Time Bidding API not enabled in GCP.

**Fix:**
1. Go to [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library)
2. Search for "Real-Time Bidding API"
3. Click Enable
4. Wait 1 minute, then retry

### "Invalid key" or "Could not load credentials"

**Cause:** JSON key file is missing, corrupted, or wrong format.

**Fix:**
1. Verify the file exists: `ls -la ~/.catscan/credentials/google-credentials.json`
2. Check it's valid JSON: `python -m json.tool ~/.catscan/credentials/google-credentials.json`
3. Re-download the key from GCP if needed

### "No such file or directory: '/credentials/...'"

**Cause:** Config has a Docker path instead of local path.

**Fix:**
```bash
cd creative-intelligence
source venv/bin/activate

python -c "
from config.config_manager import ConfigManager, AuthorizedBuyersConfig
import os

manager = ConfigManager()
config = manager.load()
config.authorized_buyers = AuthorizedBuyersConfig(
    service_account_path=os.path.expanduser('~/.catscan/credentials/google-credentials.json'),
    account_id=config.authorized_buyers.account_id
)
manager.save(config)
print('Path fixed!')
"
```

Then restart the API.

### "Connection refused" on port 8000

**Cause:** API server not running.

**Fix:**
```bash
sudo systemctl start rtbcat-api

# Check status
sudo systemctl status rtbcat-api
```

### Dashboard shows 0 creatives after sync

**Cause:** Seats not populated in database.

**Fix:**
```bash
curl -X POST http://localhost:8000/seats/populate
```

---

## Next Steps

### Import Performance Data

Export a CSV from Google Authorized Buyers and import it:

1. Go to **http://localhost:3000/import**
2. Drag and drop your CSV file
3. Click **Import**

### Run Your First Analysis

```bash
cd creative-intelligence
source venv/bin/activate

# Get a summary of your data
python cli/qps_analyzer.py summary

# Run a full waste analysis report
python cli/qps_analyzer.py full-report --days 7
```

### Set Up Auto-Sync (Optional)

Create a cron job to sync creatives daily:

```bash
# Edit crontab
crontab -e

# Add this line to sync at 6 AM daily
0 6 * * * curl -X POST http://localhost:8000/seats/YOUR_BUYER_ID/sync
```

### Run as a System Service (Optional)

```bash
# Copy the service file
sudo cp catscan-api.service /etc/systemd/system/

# Enable and start
sudo systemctl enable catscan-api
sudo systemctl start catscan-api

# Check status
sudo systemctl status catscan-api
```

---

## Getting Help

- **GitHub Issues:** Report bugs or request features
- **Documentation:** See `/docs` folder for detailed guides
- **CLI Help:** Run `python cli/qps_analyzer.py --help`

---

*Cat-Scan is free and open source. Built for the RTB community.*
