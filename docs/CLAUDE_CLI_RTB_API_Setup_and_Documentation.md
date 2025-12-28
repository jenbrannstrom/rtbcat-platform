# Claude CLI Prompt: RTB API Setup & Documentation

## Context

Jen has Google Authorized Buyers API access configured but needs:
1. To verify the current setup works
2. To understand how authentication is configured
3. To update the README with clear documentation
4. To test pulling RTB Troubleshooting metrics

---

## Your Task

### Part 1: Discover Current API Configuration

First, find how the API is currently set up:

```bash
# Look for Google Cloud credentials
ls -la ~/.config/gcloud/
ls -la /home/jen/.config/gcloud/

# Look for service account JSON files
find /home/jen -name "*.json" -path "*google*" 2>/dev/null
find /home/jen -name "*credentials*" -o -name "*service*account*" 2>/dev/null

# Check environment variables
env | grep -i google
env | grep -i gcloud

# Check if gcloud CLI is installed
which gcloud
gcloud --version

# Check current project/auth
gcloud config list
gcloud auth list
```

### Part 2: Verify API Access

Test that we can actually call the APIs:

```bash
# Install Google API client if needed
pip install google-api-python-client google-auth --break-system-packages

# Test script to verify access
python3 << 'EOF'
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Try to find credentials
possible_paths = [
    os.path.expanduser('~/.config/gcloud/application_default_credentials.json'),
    os.path.expanduser('~/google-credentials.json'),
    os.path.expanduser('~/Documents/rtbcat-platform/credentials.json'),
    os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', ''),
]

creds_path = None
for path in possible_paths:
    if path and os.path.exists(path):
        creds_path = path
        print(f"Found credentials at: {path}")
        break

if not creds_path:
    print("No credentials file found. Checking for default credentials...")
    try:
        import google.auth
        credentials, project = google.auth.default()
        print(f"Default credentials found for project: {project}")
    except Exception as e:
        print(f"No default credentials: {e}")
        exit(1)
else:
    # Load service account credentials
    SCOPES = ['https://www.googleapis.com/auth/realtime-bidding']
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )

# Try to build the Real-time Bidding API client
try:
    rtb_service = build('realtimebidding', 'v1', credentials=credentials)
    print("✅ Real-time Bidding API client created successfully")
    
    # Try to list bidders (this will verify access)
    # Note: Replace with actual bidder ID if known
    result = rtb_service.bidders().list().execute()
    print(f"✅ Bidders found: {result}")
except Exception as e:
    print(f"❌ Error with RTB API: {e}")

# Try Ad Exchange Buyer API II (for troubleshooting)
try:
    adx_service = build('adexchangebuyer2', 'v2beta1', credentials=credentials)
    print("✅ Ad Exchange Buyer II API client created successfully")
except Exception as e:
    print(f"❌ Error with AdX Buyer II API: {e}")

EOF
```

### Part 3: Document the Bidder/Account IDs

From the CSV, I can see:
- Buyer account ID: `299038253`
- Buyer account name: `Tuky Data Research Ltd.`
- Billing ID: `72245759413` (one of the 10 pretargeting configs)

Verify these and find all billing IDs:

```bash
# Check the CSV for all unique Billing IDs (pretargeting configs)
cat /path/to/uploaded/csv | cut -d',' -f14 | sort -u | head -20
```

### Part 4: Create API Access Documentation

Create or update the README with clear documentation:

```markdown
## Google API Access

### APIs Used

1. **Real-time Bidding API** (`realtimebidding.googleapis.com`)
   - Manage creatives, pretargeting configs, endpoints
   - Scope: `https://www.googleapis.com/auth/realtime-bidding`

2. **Ad Exchange Buyer API II** (`adexchangebuyer.googleapis.com`)
   - RTB Troubleshooting metrics (bid metrics, filtered bids)
   - Scope: `https://www.googleapis.com/auth/adexchange.buyer`

### Authentication

Authentication uses a **Service Account** with the following setup:

1. Service account JSON file location: `[DOCUMENT THE PATH]`
2. The service account email must be added as a user in Authorized Buyers UI:
   - Settings → Account Settings → User Management → Account Users → +Service Account

### Key Identifiers

| ID Type | Value | Description |
|---------|-------|-------------|
| Bidder Account ID | `299038253` | Parent bidder account |
| Buyer Account Name | `Tuky Data Research Ltd.` | Account display name |
| Billing ID (PTGT 1) | `72245759413` | Asia geo pretargeting |
| Billing ID (PTGT 2) | `[TBD]` | [Description] |
| ... | ... | ... |

### Testing API Access

```bash
# Quick test
python3 scripts/test_api_access.py

# Expected output:
# ✅ Real-time Bidding API client created successfully
# ✅ Ad Exchange Buyer II API client created successfully
```

### Common API Calls

#### Get Bid Metrics (RTB Troubleshooting)

```python
from googleapiclient.discovery import build

# Create filter set for time range
filter_set = {
    "relativeDateRange": {
        "offsetDays": 0,
        "durationDays": 7
    },
    "timeSeriesGranularity": "DAILY"
}

# Create the filter set
service.bidders().accounts().filterSets().create(
    ownerName=f"bidders/{BIDDER_ID}/accounts/{ACCOUNT_ID}",
    body={"filterSet": filter_set, "isTransient": True}
).execute()

# Get bid metrics
metrics = service.bidders().accounts().filterSets().bidMetrics().list(
    filterSetName=f"bidders/{BIDDER_ID}/accounts/{ACCOUNT_ID}/filterSets/{FILTER_SET_NAME}"
).execute()
```

#### Key Metrics Returned

| Metric | Description |
|--------|-------------|
| `reached_queries` | QPS that reached your bidder |
| `bids` | Number of bids submitted |
| `bids_in_auction` | Bids that passed filtering |
| `impressions_won` | Auctions won |
| `billable_impressions` | What you pay for |

### Troubleshooting

**"Permission denied" errors:**
- Verify service account is added in Authorized Buyers UI
- Check scopes match the API being called

**"Quota exceeded" errors:**
- RTB Troubleshooting API has rate limits
- Use `isTransient: true` for temporary filter sets

**"Resource not found" errors:**
- Verify bidder ID and account ID are correct
- Parent bidder must be used for bidder-level calls
```

### Part 5: Create a Test Script

Create a reusable script to test API access:

**File: `/home/jen/Documents/rtbcat-platform/scripts/test_api_access.py`**

```python
#!/usr/bin/env python3
"""
Test Google Authorized Buyers API access.
Run: python3 scripts/test_api_access.py
"""

import os
import sys
from datetime import datetime, timedelta

def main():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import google.auth
    except ImportError:
        print("Installing required packages...")
        os.system("pip install google-api-python-client google-auth --break-system-packages")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import google.auth

    # Configuration - UPDATE THESE
    BIDDER_ID = "299038253"  # From CSV: Buyer account ID
    ACCOUNT_ID = "299038253"  # Usually same as bidder for parent accounts
    
    # Try to get credentials
    try:
        credentials, project = google.auth.default(
            scopes=[
                'https://www.googleapis.com/auth/realtime-bidding',
                'https://www.googleapis.com/auth/adexchange.buyer'
            ]
        )
        print(f"✅ Using default credentials (project: {project})")
    except Exception as e:
        # Try service account file
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not creds_path:
            print(f"❌ No credentials found: {e}")
            print("\nTo fix, either:")
            print("1. Run: gcloud auth application-default login")
            print("2. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            sys.exit(1)
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=[
                'https://www.googleapis.com/auth/realtime-bidding',
                'https://www.googleapis.com/auth/adexchange.buyer'
            ]
        )
        print(f"✅ Using service account from: {creds_path}")

    # Test Real-time Bidding API
    print("\n--- Testing Real-time Bidding API ---")
    try:
        rtb = build('realtimebidding', 'v1', credentials=credentials)
        
        # List pretargeting configs
        configs = rtb.bidders().pretargetingConfigs().list(
            parent=f"bidders/{BIDDER_ID}"
        ).execute()
        
        print(f"✅ Found {len(configs.get('pretargetingConfigs', []))} pretargeting configs")
        for config in configs.get('pretargetingConfigs', [])[:3]:
            print(f"   - {config.get('name')}: {config.get('displayName', 'unnamed')}")
            
    except Exception as e:
        print(f"❌ RTB API error: {e}")

    # Test Ad Exchange Buyer II API (Troubleshooting)
    print("\n--- Testing RTB Troubleshooting API ---")
    try:
        adx = build('adexchangebuyer2', 'v2beta1', credentials=credentials)
        
        # Create a transient filter set
        filter_set_name = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        result = adx.bidders().accounts().filterSets().create(
            ownerName=f"bidders/{BIDDER_ID}/accounts/{ACCOUNT_ID}",
            isTransient=True,
            body={
                "name": f"bidders/{BIDDER_ID}/accounts/{ACCOUNT_ID}/filterSets/{filter_set_name}",
                "relativeDateRange": {
                    "offsetDays": 0,
                    "durationDays": 7
                },
                "timeSeriesGranularity": "DAILY"
            }
        ).execute()
        
        print(f"✅ Created filter set: {result.get('name')}")
        
        # Get bid metrics
        metrics = adx.bidders().accounts().filterSets().bidMetrics().list(
            filterSetName=result.get('name')
        ).execute()
        
        print(f"✅ Retrieved bid metrics:")
        for row in metrics.get('bidMetricsRows', [])[:3]:
            dims = row.get('rowDimensions', {}).get('timeInterval', {})
            print(f"   - Bids: {row.get('bids', {}).get('value', 0)}, "
                  f"Won: {row.get('impressionsWon', {}).get('value', 0)}, "
                  f"Reached: {row.get('reachedQueries', {}).get('value', 0)}")
                  
    except Exception as e:
        print(f"❌ Troubleshooting API error: {e}")

    print("\n--- Summary ---")
    print("If you see errors above, check:")
    print("1. Service account is added in Authorized Buyers UI")
    print("2. APIs are enabled in Google Cloud Console")
    print("3. Bidder/Account IDs are correct")

if __name__ == "__main__":
    main()
```

---

## Success Criteria

After running this prompt:

- [ ] API credentials location is documented
- [ ] Both APIs (RTB and AdX Buyer II) are verified working
- [ ] All 10 Billing IDs (pretargeting configs) are documented
- [ ] README is updated with clear API access instructions
- [ ] Test script is created and working
- [ ] Jen can run `python3 scripts/test_api_access.py` to verify access

---

## After Completing This

Tell Jen:
```
API access verified! Here's what I found:
- Credentials location: [path]
- Bidder ID: 299038253
- Pretargeting configs found: [count]

Created:
- scripts/test_api_access.py - Run this to verify access
- Updated README with API documentation

Next: We can start pulling RTB Troubleshooting metrics to analyze QPS waste.
```

---

## DO NOT

- ❌ Modify or delete any credential files
- ❌ Commit credentials to git
- ❌ Share API keys or service account details in logs
- ❌ Make API calls that could affect live bidding

---

**Priority:** MEDIUM (enables future analysis)
**Estimated time:** 30-45 minutes
**Risk:** Low (read-only operations)
