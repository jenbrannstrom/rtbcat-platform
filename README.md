# Cat-Scan Creative Intelligence

**Version:** 22.0
**Phase:** 22 - Unified Dashboard & Schema Alignment
**Last Updated:** December 6, 2025

A privacy-first QPS optimization platform for Google Authorized Buyers. Cat-Scan helps RTB bidders eliminate wasted QPS by learning which data-streams the bidder likes to bid on. Cat-Scan is a monitoring middleware between the bidder and the Ad-exchange. By looking at both what the bidder likes to buy and seeing what never gets bid on, it proposes evidence-based waste signals, enabling data-driven pretargeting decisions. All to increase QPS & bidder efficiency

> **Philosophy:** Intelligence without assumptions. Facts that drive action.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/rtbcat-platform.git
cd rtbcat-platform
./setup.sh

# 2. Start API
cd creative-intelligence && source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 3. Start dashboard (new terminal)
cd dashboard && npm run dev

# 4. Open http://localhost:3000
```

### Requirements

- Python 3.11+
- Node.js 18+
- ffmpeg (optional, for video thumbnails)

See **[INSTALL.md](INSTALL.md)** for detailed installation instructions and troubleshooting.

---

## What This Solves

**The Problem:** Google Authorized Buyers shows you creative IDs like `cr-12345`, but doesn't tell you:
- How to improve efficiency of the QPS that a bidder consumes
- What QPS is unused and what should be increased
- It does this partially by clusering creatives that belong to the same/similar campaign
- Shows the creative for easy recogition (especially for native ads)
- Which creatives are wasting your budget

**The Solution:** Cat-Scan automatically:
1. Fetches all your creatives from Authorized Buyers API
2. Extracts metadata, tracking & attribution parameters, and destination URLs
3. Stores them in a queryable SQLite database
4. Provides REST API and dashboard for exploration
5. Supports filtering by format (HTML, VIDEO, NATIVE), Spend, approval status, etc

## Features

- **Creative Collection**: Fetch all creatives from Google Authorized Buyers API with pagination
- **Metadata Extraction**: Parse UTM parameters, dimensions, approval status, advertiser names
- **Multiple Formats**: Support for HTML, VIDEO, and NATIVE creative types
- **Multi-Seat Support**: Manage multiple buyer accounts under a single bidder
- **REST API**: FastAPI-based API with Swagger documentation
- **Encrypted Config**: Secure credential storage with Fernet encryption
- **Docker Support**: Multi-stage Docker build with non-root user
- **Dashboard**: Next.js frontend for visual exploration (optional)

### Phase 11: Decision Intelligence (NEW)

- **Timeframe Context**: All endpoints support `?days=N` for time-bounded analysis
- **Campaign Metrics**: Aggregated spend, impressions, clicks, and waste_score per campaign
- **Evidence-Based Signals**: Waste detection with full evidence chain explaining WHY
- **Warning Counts**: Broken videos, zero engagement, disapproved creatives per campaign
- **Pagination**: Scalable `/v2` endpoints with metadata for large accounts
- **Fixed DnD**: Improved drag-and-drop collision detection

See [CHANGELOG.md](CHANGELOG.md) for full details.

### Multi-Seat Buyer Accounts

Enterprise customers often have multiple buyer accounts (seats) under one bidder. Cat-Scan supports:

- **Seat Discovery**: Enumerate all buyer accounts via `bidders.buyers.list()` API
- **Seat-Specific Sync**: Collect creatives for individual buyer seats
- **Filtering**: Query creatives by `buyer_id` to isolate seat-specific inventory
- **Tracking**: Monitor creative counts and last sync time per seat

## Quick Start

### Prerequisites

1. **Google Service Account** with Authorized Buyers API access
2. **Docker** and **Docker Compose** installed (or local Python 3.11+)
3. Your **Bidder Account ID** (find it in your Authorized Buyers URL)

### First Time Setup (Recommended)

1. **Start services:**
   ```bash
   sudo systemctl start rtbcat-api
   cd dashboard && npm run dev
   ```

2. **Go to** http://localhost:3000/connect

3. **Upload your Google service account JSON key** (drag & drop or click to upload)

4. **Click "Sync"** to pull your creatives from Google API

5. **Import CSV performance data** via the Import page

Need a JSON key? See [SETUP_GUIDE.md](creative-intelligence/docs/SETUP_GUIDE.md) for step-by-step instructions.

### Alternative: Docker Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/rtbcat-creative-intel.git
cd rtbcat-creative-intel

# 2. Place your Google credentials
mkdir -p ~/.rtb-cat/credentials
cp /path/to/your/service-account.json ~/.rtb-cat/credentials/google-credentials.json
chmod 644 ~/.rtb-cat/credentials/google-credentials.json

# 3. Build and start the API
docker compose build api
docker compose up -d api

# 4. Configure credentials in the container
docker exec catscan-api python -c "
from config import ConfigManager
from config.config_manager import AppConfig, AuthorizedBuyersConfig

config = AppConfig(
    authorized_buyers=AuthorizedBuyersConfig(
        service_account_path='/credentials/google-credentials.json',
        account_id='YOUR_ACCOUNT_ID'
    )
)
ConfigManager().save(config)
print('Configuration saved!')
"

# 5. Test the API
curl http://localhost:8000/health
```

### Collect Creatives

```bash
# Synchronous collection (waits for completion)
curl -X POST http://localhost:8000/collect/sync \
  -H "Content-Type: application/json" \
  -d '{"account_id": "YOUR_ACCOUNT_ID"}'

# Check stats
curl http://localhost:8000/stats
```

## Google Service Account Setup

1. **Create service account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project (or use existing)
   - Enable **Real-Time Bidding API**
   - Go to IAM & Admin → Service Accounts → Create Service Account
   - Name it `rtbcat-collector`
   - Download JSON key file

2. **Authorize in Authorized Buyers:**
   - Go to [Authorized Buyers](https://authorized-buyers.google.com/)
   - Settings → API Access
   - Add the service account email
   - Grant API access permissions

3. **Find your Account ID:**
   - Look at your Authorized Buyers URL: `https://admanager.google.com/12345#...`
   - The `12345` is your account ID

## Google API Configuration

### Current Setup (Tuky Data Research Ltd.)

| Configuration | Value |
|--------------|-------|
| **Credentials Path** | `~/.rtb-cat/credentials/google-credentials.json` |
| **Service Account** | `rtb-cat-collector@creative-intel-api.iam.gserviceaccount.com` |
| **Google Cloud Project** | `creative-intel-api` |
| **Bidder Account ID** | `299038253` |
| **Account Name** | Tuky Data Research Ltd. |

### APIs Used

| API | Service Name | Version | Scope |
|-----|-------------|---------|-------|
| **Real-time Bidding API** | `realtimebidding` | `v1` | `https://www.googleapis.com/auth/realtime-bidding` |

### API Endpoints Implemented

| Endpoint | Description | Client Class |
|----------|-------------|--------------|
| `bidders.creatives.list` | Fetch all creatives | `CreativesClient` |
| `bidders.creatives.get` | Get specific creative | `CreativesClient` |
| `bidders.buyers.list` | Discover buyer seats | `BuyerSeatsClient` |
| `buyers.get` | Get buyer details | `BuyerSeatsClient` |
| `bidders.pretargetingConfigs.list` | List pretargeting configs | `PretargetingClient` |
| `bidders.pretargetingConfigs.get` | Get specific config | `PretargetingClient` |

### Testing API Access

```bash
# Activate virtual environment
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate

# Run API test script
python scripts/test_api_access.py

# Expected output:
# [PASS] Found 652 creatives
# [PASS] Found 1 buyer seats
# [PASS] Found X pretargeting configs
```

### RTB Troubleshooting API (Not Yet Implemented)

The **Ad Exchange Buyer II API** (`adexchangebuyer2` v2beta1) provides RTB troubleshooting metrics:

- **Bid metrics**: QPS, bids submitted, impressions won
- **Filtered bid reasons**: Why bids were rejected
- **Callout metrics**: How bid requests reached your bidder

**Scope required**: `https://www.googleapis.com/auth/adexchange.buyer`

This API is NOT yet integrated into Cat-Scan. To add support:

1. Create `collectors/troubleshooting/client.py`
2. Use `build('adexchangebuyer2', 'v2beta1', credentials=credentials)`
3. Implement filter set creation and metrics retrieval

### Troubleshooting

**"PERMISSION_DENIED" errors:**
1. Verify service account is authorized in Authorized Buyers UI
   - Settings → API Access → Add service account email
2. Check Real-time Bidding API is enabled in Google Cloud Console
3. Verify account ID is correct

**"Rate limit exceeded" (HTTP 429):**
- The clients implement automatic exponential backoff (max 5 retries)
- For bulk operations, use pagination (pageSize=100 by default)

**"Credentials not found":**
- Ensure `~/.rtb-cat/credentials/google-credentials.json` exists
- Check file permissions: `chmod 644 ~/.rtb-cat/credentials/google-credentials.json`

## Installation Options

### Option A: Docker (Recommended)

```bash
# Build the API image
docker compose build api

# Start the API service
docker compose up -d api

# View logs
docker compose logs -f api

# Stop
docker compose down
```

**Services:**
- **API:** http://localhost:8000
- **Dashboard (optional):** http://localhost:3000

### Option B: Local Python (Development)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure (creates ~/.rtbcat/config.enc)
python -c "
from config import ConfigManager
from config.config_manager import AppConfig, AuthorizedBuyersConfig

config = AppConfig(
    authorized_buyers=AuthorizedBuyersConfig(
        service_account_path='/path/to/service-account.json',
        account_id='YOUR_ACCOUNT_ID'
    )
)
ConfigManager().save(config)
"

# Start API server (using systemd service - recommended)
sudo systemctl start rtbcat-api

# Or for manual development mode:
# python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker Configuration

The `docker-compose.yml` defines the following volumes:

```yaml
volumes:
  - rtbcat-data:/data                           # Persistent data storage
  - ~/.rtb-cat/credentials:/credentials:ro      # Google credentials (read-only)
  - rtbcat-config:/home/rtbcat/.rtbcat          # Encrypted config and database
```

**First-time setup:** After starting the container, you must initialize the config volume:

```bash
# Fix volume permissions for the rtbcat user (UID 999)
docker run --rm -v rtbcat-creative-intel_rtbcat-config:/config alpine chown -R 999:999 /config

# Then configure credentials inside the container (see Quick Start)
```

## REST API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with config status |
| GET | `/stats` | Database statistics |
| GET | `/creatives` | List creatives with filters |
| GET | `/creatives/{id}` | Get specific creative |
| DELETE | `/creatives/{id}` | Delete a creative |
| POST | `/creatives/cluster` | Assign creative to cluster |
| GET | `/campaigns` | List campaign clusters |
| GET | `/campaigns/{id}` | Get campaign details |
| POST | `/collect` | Start background collection |
| POST | `/collect/sync` | Synchronous collection |
| GET | `/seats` | List all buyer seats |
| GET | `/seats/{buyer_id}` | Get specific seat details |
| POST | `/seats/discover` | Discover seats from Google API |
| POST | `/seats/{buyer_id}/sync` | Sync creatives for a specific seat |

### Query Parameters for `/creatives`

- `campaign_id` - Filter by campaign
- `cluster_id` - Filter by cluster
- `buyer_id` - Filter by buyer seat
- `format` - Filter by format (HTML, VIDEO, NATIVE)
- `limit` - Max results (default: 100, max: 1000)
- `offset` - Pagination offset

### Example Responses

**GET /stats**
```json
{
  "creative_count": 652,
  "campaign_count": 0,
  "cluster_count": 0,
  "formats": {
    "HTML": 6,
    "NATIVE": 50,
    "VIDEO": 596
  },
  "db_path": "/home/rtbcat/.rtbcat/rtbcat.db"
}
```

**POST /collect/sync**
```json
{
  "status": "completed",
  "account_id": "299038253",
  "filter_query": null,
  "message": "Successfully collected 652 creatives.",
  "creatives_collected": 652
}
```

**POST /seats/discover**
```bash
curl -X POST http://localhost:8000/seats/discover \
  -H "Content-Type: application/json" \
  -d '{"bidder_id": "299038253"}'
```
```json
{
  "status": "completed",
  "bidder_id": "299038253",
  "seats_discovered": 3,
  "seats": [
    {"buyer_id": "456", "bidder_id": "299038253", "display_name": "Brand A", "active": true},
    {"buyer_id": "789", "bidder_id": "299038253", "display_name": "Brand B", "active": true}
  ]
}
```

**POST /seats/{buyer_id}/sync**
```bash
curl -X POST http://localhost:8000/seats/456/sync
```
```json
{
  "status": "completed",
  "buyer_id": "456",
  "creatives_synced": 150,
  "message": "Successfully synced 150 creatives for buyer 456."
}
```

### Interactive Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Python API

```python
import asyncio
from collectors import CreativesClient
from storage import SQLiteStore, creative_dicts_to_storage

async def main():
    # Initialize client
    client = CreativesClient(
        credentials_path="/path/to/service-account.json",
        account_id="12345"
    )

    # Fetch all creatives
    api_creatives = await client.fetch_all_creatives()
    print(f"Found {len(api_creatives)} creatives")

    # Fetch with filter (approved only)
    approved = await client.fetch_all_creatives(
        filter_query="creativeServingDecision.networkPolicyCompliance.status=APPROVED"
    )

    # Convert to storage format and save
    storage_creatives = creative_dicts_to_storage(api_creatives)

    store = SQLiteStore()
    await store.initialize()
    count = await store.save_creatives(storage_creatives)
    print(f"Saved {count} creatives")

    # Get stats
    stats = await store.get_stats()
    print(f"Total: {stats['creative_count']} creatives")
    print(f"Formats: {stats['formats']}")

asyncio.run(main())
```

### Multi-Seat Usage

```python
import asyncio
from collectors import BuyerSeatsClient, CreativesClient
from storage import SQLiteStore, creative_dicts_to_storage

async def sync_all_seats():
    bidder_id = "299038253"
    credentials = "/path/to/service-account.json"

    # Discover buyer seats
    seats_client = BuyerSeatsClient(
        credentials_path=credentials,
        account_id=bidder_id
    )
    seats = await seats_client.discover_buyer_seats()
    print(f"Found {len(seats)} buyer seats")

    # Initialize storage
    store = SQLiteStore()
    await store.initialize()

    # Save seats and sync creatives for each
    for seat in seats:
        await store.save_buyer_seat(seat)

        # Fetch creatives for this seat
        creatives_client = CreativesClient(
            credentials_path=credentials,
            account_id=bidder_id
        )
        api_creatives = await creatives_client.fetch_all_creatives(
            buyer_id=seat.buyer_id
        )

        # Save with buyer_id association
        storage_creatives = creative_dicts_to_storage(api_creatives)
        count = await store.save_creatives(storage_creatives)

        # Update seat metadata
        await store.update_seat_creative_count(seat.buyer_id)
        await store.update_seat_sync_time(seat.buyer_id)
        print(f"Synced {count} creatives for {seat.display_name}")

asyncio.run(sync_all_seats())
```

## Project Structure

```
rtbcat-platform/
├── creative-intelligence/       # Backend API and Python code
│   ├── api/
│   │   └── main.py              # FastAPI application
│   ├── collectors/              # Google API clients
│   │   ├── creatives/           # CreativesClient
│   │   ├── pretargeting/        # PretargetingClient
│   │   └── seats.py             # BuyerSeatsClient
│   ├── storage/
│   │   └── sqlite_store.py      # SQLite backend
│   ├── config/
│   │   └── config_manager.py    # Encrypted credential storage
│   ├── cli/
│   │   └── qps_analyzer.py      # CLI tools (import, thumbnails, reports)
│   ├── docs/
│   │   └── SETUP_GUIDE.md       # Comprehensive setup guide
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/                   # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── connect/         # Credential upload & sync
│   │   │   ├── creatives/       # Creative browser
│   │   │   ├── import/          # CSV performance import
│   │   │   └── ...
│   │   ├── components/          # React components
│   │   └── lib/                 # API client
│   └── package.json
└── README.md                    # This file
```

## Configuration Files

Configuration is stored in `~/.catscan/`:

```
~/.catscan/
├── config.enc    # Encrypted configuration (Fernet)
├── .key          # Encryption key (mode 0600)
├── catscan.db    # SQLite database
├── credentials/  # Service account keys
│   └── google-credentials.json
└── thumbnails/   # Generated video thumbnails
```

## Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific module
pytest tests/collectors/ -v

# Run async tests
pytest tests/api/ -v
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type checking
mypy .

# All checks
black . && isort . && ruff check . && mypy . && pytest
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Troubleshooting

### Credential Issues

**"No such file: /credentials/..." or path mismatch errors:**

This happens when Docker expects `/credentials/` but you're running locally (or vice versa).

**Fix:** Re-upload your JSON key via the `/connect` page. This stores credentials in `~/.catscan/credentials/` which works for both Docker and local setups.

### Video Cards Show Blank/No Thumbnail

Most videos don't have VAST CompanionAds with images (~91%). To generate thumbnails:

```bash
# Generate thumbnails for up to 100 videos
python cli/qps_analyzer.py generate-thumbnails --limit 100

# Force regenerate all
python cli/qps_analyzer.py generate-thumbnails --limit 500 --force
```

Requires ffmpeg: `sudo apt install ffmpeg`

### "Service account credentials not configured"

The API config hasn't been initialized. Run:

```bash
docker exec catscan-api python -c "
from config import ConfigManager
from config.config_manager import AppConfig, AuthorizedBuyersConfig
config = AppConfig(authorized_buyers=AuthorizedBuyersConfig(
    service_account_path='/credentials/google-credentials.json',
    account_id='YOUR_ACCOUNT_ID'))
ConfigManager().save(config)"
```

### "sqlite3.OperationalError: unable to open database file"

Volume permissions issue. Fix with:

```bash
docker run --rm -v rtbcat-creative-intel_rtbcat-config:/config alpine chown -R 999:999 /config
docker compose restart api
```

### "PermissionError" on credentials

Make credentials readable:

```bash
chmod 644 ~/.rtb-cat/credentials/google-credentials.json
```

### "PERMISSION_DENIED" from Google API

1. Verify service account is authorized in Authorized Buyers UI
2. Check account ID is correct
3. Ensure Real-Time Bidding API is enabled in Google Cloud Console

### Container keeps restarting

Check logs for specific error:

```bash
docker compose logs api --tail 50
```

## System Requirements

**Minimum:**
- 4GB RAM
- 10GB disk space
- Docker + Docker Compose
- Linux/Mac/Windows with WSL2

**Recommended:**
- 8GB RAM
- 50GB disk space (for creative assets)
- SSD for faster SQLite queries

## Deployment Options

| Option | Cost | Best For |
|--------|------|----------|
| Laptop/Desktop | $0/month | Testing, POC, small accounts |
| Cloud Server (t3.medium) | $30-50/month | Production, 24/7 uptime |
| Customer's AWS | ~$35/month | Privacy, zero egress costs |

## Database Schema

### Table Naming Convention (v12)

**IMPORTANT:** Phase 12 renamed tables for clarity:
- `rtb_daily` → **`rtb_daily`** (THE fact table for all CSV imports)
- `ai_campaigns` → **`campaigns`** (removed "ai_" prefix)

If you see references to old table names in documentation, they are outdated.

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `rtb_daily` | **THE fact table** - all CSV imports | `metric_date`, `creative_id`, `billing_id`, `reached_queries`, `impressions` |
| `creatives` | Creative inventory from API | `id`, `format`, `canonical_size`, `approval_status` |
| `campaigns` | User-defined campaign groupings | `id`, `name`, `seat_id` |
| `creative_campaigns` | Creative → Campaign mapping | `creative_id`, `campaign_id` |
| `buyer_seats` | Buyer accounts under a bidder | `buyer_id`, `bidder_id`, `display_name` |

### Support Tables

| Table | Purpose |
|-------|---------|
| `fraud_signals` | Detected fraud patterns for review |
| `waste_signals` | Evidence-based waste detection (Phase 11) |
| `import_history` | CSV import tracking |
| `troubleshooting_data` | RTB Troubleshooting API data (Phase 11) |
| `troubleshooting_collections` | Collection audit log |
| `thumbnail_status` | Video thumbnail generation status |

### Migration

If you have an existing database, run the migration script:

```bash
cd creative-intelligence
python scripts/migrate_schema_v12.py
```

This will:
1. Rename `rtb_daily` → `rtb_daily`
2. Rename `ai_campaigns` → `campaigns`
3. Update all indexes
4. Create automatic backup first

### buyer_seats Table

| Column | Type | Description |
|--------|------|-------------|
| `buyer_id` | TEXT PK | Buyer account ID |
| `bidder_id` | TEXT | Parent bidder account |
| `display_name` | TEXT | Human-readable name |
| `active` | INTEGER | 1=active, 0=suspended |
| `creative_count` | INTEGER | Cached count of creatives |
| `last_synced` | TIMESTAMP | Last successful sync |
| `created_at` | TIMESTAMP | First discovery time |

### Migration

Existing databases are automatically migrated on startup. To manually trigger:

```python
from storage import SQLiteStore

store = SQLiteStore()
await store.initialize()
await store.migrate_add_buyer_seats()
```

## Roadmap

### v0.1 (Completed)
- [x] Google Authorized Buyers API integration
- [x] Creative collection with pagination
- [x] SQLite storage backend
- [x] REST API with FastAPI
- [x] Encrypted credential management
- [x] Docker deployment
- [x] Multi-seat buyer account support

### v0.2 (Completed - November 2025)
- [x] Next.js dashboard structure
- [x] Campaign clustering UI
- [x] Performance metrics import (CSV upload)
- [x] Seat management UI (`/settings/seats`)
- [x] Waste Analysis dashboard (`/waste-analysis`)
- [x] Performance data visualization on creative cards

### v0.3 (Completed - November 2025)
- [x] AI-based creative clustering (`/campaigns/auto-cluster`)
- [x] Size-based campaign grouping
- [x] Seat hierarchy cleanup (Phase 8.5)
- [x] Seat display names on creative cards

### v0.4 (Completed - December 2025)
- [x] Phase 9.6: Unified Data Architecture
- [x] Phase 9.7: Onboarding Flow (`/connect` page)
- [x] Video thumbnail extraction from VAST XML
- [x] CLI thumbnail generator with ffmpeg
- [x] Native icon display on cards
- [x] Copy creative ID button on cards
- [x] Modal sizing matches ad dimensions

### v0.5 (Planned)
- [ ] Phase 10: Batch video thumbnail generation (ffmpeg)
- [ ] Phase 10.1: Multi-account support (account switcher)
- [ ] Phase 10.2: Card/modal field redesign
- [ ] Visual similarity detection
- [ ] Pretargeting recommendations

## Recent Changes (December 2025)

### Phase 22: Unified Dashboard & Schema Alignment (NEW)
- **Database schema aligned** with specification in `reset_database.py`:
  - `rtb_daily` now has 49 columns including UA/conversion fields
  - All 13 required indexes created
  - Added tables: `fraud_signals`, `waste_signals`, `troubleshooting_data`, `troubleshooting_collections`
  - Dropped legacy `performance_metrics` table
- **Avg CPM badge** in waste-analysis page header (updates with 7/14/30 day selector)
- **Config display fix**: Pretargeting configs now show "Config {id}" instead of duplicated ID
- **Size Analysis CSV instructions**: Empty state shows exactly which CSV report to generate in Google Authorized Buyers with link to /import
- **API endpoint**: `/analytics/spend-stats` for CPM calculation

### Phase 21: RTB Funnel Analysis
- Config performance section fetches from database (not file paths)
- Publisher performance with win rate categories
- Geographic performance with country-level breakdown
- Gmail auto-import for scheduled reports

### Phase 9.7: Onboarding Flow
- `/connect` page for credential management and account discovery
- JSON key upload with drag-drop support
- Smart seat UI: single-seat shows title, multi-seat shows dropdown
- Sync button conditionally appears after credentials uploaded
- Comprehensive setup guide at `docs/SETUP_GUIDE.md`

### Phase 9.6: Video & Card Improvements
- Video thumbnails extracted from VAST XML CompanionAds
- CLI thumbnail generator: `python cli/qps_analyzer.py generate-thumbnails`
- Native ad icon/logo display on cards with headline overlay
- Copy creative ID button inline next to ID on cards
- Modal sizing matches actual creative dimensions

### Phase 5: Waste Analysis Dashboard
- Added `/waste-analysis` page with size gap analysis
- Traffic pattern visualization (daily QPS charts)
- Size coverage heatmap
- Actionable recommendations (block, add creative, use flexible)

### Phase 7: Performance Data Import
- CSV performance data import (`/import` page)
- Support for impressions, clicks, spend metrics
- Performance metrics displayed on creative cards (spend, CTR, CPM, CPC)
- Color-coded CPC indicators

### Phase 8.5: Seat Hierarchy Cleanup
- Fixed sidebar seat dropdown showing "0 creatives"
- Seat display names instead of raw IDs on creative cards
- Seat management page (`/settings/seats`) for renaming
- Auto-populate buyer_seats from existing creatives on startup

### Phase 9: AI Campaign Clustering
- Auto-cluster creatives by size, format, and advertiser
- AI campaign management (`/campaigns` page)
- Campaign performance aggregation
- Daily trend charts per campaign

## Known Issues & Bugs

### Critical
1. **API Service Port Conflict**: If the systemd service fails with "Address already in use", kill old processes:
   ```bash
   sudo lsof -ti:8000 | xargs -r sudo kill -9
   sudo systemctl restart rtbcat-api
   ```

### Medium
2. **Date Serialization**: SQLite returns dates as strings; API handles both string and datetime formats
3. **Video Thumbnails**: ~91% of videos need ffmpeg generation (VAST CompanionAds rare)
   - Run: `python cli/qps_analyzer.py generate-thumbnails --limit 100`
4. **Multi-Account Support**: UI ready on /connect, backend TODO for account switching

### Low
5. **Dashboard Hot Reload**: Sometimes requires `npm run build` after backend changes
6. **Empty Seats on First Load**: Seats are auto-populated on API startup; refresh if empty

## Systemd Service

The API runs as a systemd service:

```bash
# Service file location
/etc/systemd/system/rtbcat-api.service

# Common commands
sudo systemctl status rtbcat-api
sudo systemctl restart rtbcat-api
sudo journalctl -u rtbcat-api -f

# If service fails to start (port in use)
sudo lsof -ti:8000 | xargs -r sudo kill -9
sudo systemctl restart rtbcat-api
```

### Service Configuration
```ini
[Unit]
Description=Cat-Scan Creative Intelligence API
After=network.target

[Service]
Type=simple
User=jen
WorkingDirectory=/home/jen/Documents/rtbcat-platform/creative-intelligence
ExecStart=/home/jen/Documents/rtbcat-platform/creative-intelligence/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Dashboard Service

The Next.js dashboard also runs as a systemd service:

```bash
# Service file
/etc/systemd/system/rtbcat-dashboard.service

# Commands
sudo systemctl status rtbcat-dashboard
sudo systemctl restart rtbcat-dashboard
```

## API Endpoints (Updated)

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/waste` | Get waste analysis report |
| GET | `/analytics/size-coverage` | Get size coverage data |
| POST | `/analytics/generate-mock-traffic` | Generate test traffic data |
| POST | `/performance/import-csv` | Import performance CSV |
| GET | `/performance/metrics/batch` | Get batch performance metrics |
| GET | `/campaigns` | List AI-generated campaigns |
| POST | `/campaigns/auto-cluster` | Auto-cluster creatives |
| GET | `/campaigns/{id}/performance` | Get campaign performance |
| PATCH | `/seats/{buyer_id}` | Update seat display name |
| POST | `/seats/populate` | Populate seats from creatives |
| POST | `/config/credentials` | Upload service account JSON key |
| GET | `/config/status` | Check credential configuration status |
| GET | `/thumbnails/{id}.jpg` | Serve locally-generated video thumbnail |
| GET | `/analytics/spend-stats` | Get spend/CPM stats for time period |
| GET | `/analytics/rtb-funnel/configs` | Get pretargeting config performance |

## API Data

### What You CAN Get

- Creative metadata (ID, format, size)
- Destination URLs with UTM parameters
- HTML snippets
- Native assets (headline, image, body)
- Video URLs
- Approval status
- Advertiser name

### What You CANNOT Get (Need CSV Reports)

- Impressions, clicks, spend
- Win rate
- Geographic performance
- Device breakdown

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run tests: `pytest`
5. Format code: `black . && isort .`
6. Commit: `git commit -m "Add feature"`
7. Push: `git push origin feature/my-feature`
8. Open a Pull Request

---

## Data Architecture & Waste Detection

### Data Sources Overview

Cat-Scan combines two distinct data sources. Understanding what each provides is critical for waste detection.

| Source | What It Provides | Update Frequency |
|--------|------------------|------------------|
| **Google RTB API** | Creative metadata (what the ad *is*) | On-demand sync |
| **CSV Export** | Performance data (how it *performed*) | Manual import |

**There is no Google Reporting API.** Performance metrics must be manually exported from the Authorized Buyers UI and imported via CSV.

---

### Table 1: `creatives` (from Google RTB API)

These fields describe *what the creative is* - its structure, destination, and approval state.

| Field | Type | Description | Waste Detection Use |
|-------|------|-------------|---------------------|
| `id` | TEXT PK | Unique creative ID (e.g., `cr-12345`) | Join key to rtb_daily |
| `name` | TEXT | Resource name `bidders/{id}/creatives/{id}` | - |
| `format` | TEXT | HTML, VIDEO, NATIVE, UNKNOWN | Video-specific waste analysis |
| `account_id` | TEXT | Bidder account ID | Multi-account filtering |
| `buyer_id` | TEXT | Buyer seat ID | Seat-level performance isolation |
| `approval_status` | TEXT | APPROVED, DISAPPROVED, PENDING_REVIEW | **Disapproved = 100% waste** |
| `width` | INT | Creative width (pixels) | Size mismatch detection |
| `height` | INT | Creative height (pixels) | Size mismatch detection |
| `canonical_size` | TEXT | Normalized IAB size (e.g., "300x250") | Size coverage analysis |
| `size_category` | TEXT | IAB Standard, Video, Adaptive, Non-Standard | Inventory gap detection |
| `final_url` | TEXT | Landing page URL | Broken link detection |
| `display_url` | TEXT | Displayed URL | - |
| `utm_source` | TEXT | UTM tracking parameter | Campaign grouping |
| `utm_medium` | TEXT | UTM tracking parameter | Channel analysis |
| `utm_campaign` | TEXT | UTM tracking parameter | **Auto-clustering by campaign** |
| `utm_content` | TEXT | UTM tracking parameter | A/B variant detection |
| `utm_term` | TEXT | UTM tracking parameter | Keyword analysis |
| `advertiser_name` | TEXT | Declared advertiser | Advertiser-level aggregation |
| `campaign_id` | TEXT FK | Manual cluster assignment | Campaign grouping |
| `cluster_id` | TEXT FK | AI cluster assignment | Auto-grouping |
| `raw_data` | JSON | Full API response | VAST XML, native assets, HTML snippet |

**Format-specific data in `raw_data`:**

| Format | Available Fields |
|--------|-----------------|
| HTML | `html.snippet`, `html.width`, `html.height` |
| VIDEO | `video.vastXml`, `video.videoUrl`, `video.duration`, `video.localThumbnailPath` |
| NATIVE | `native.headline`, `native.body`, `native.callToAction`, `native.image`, `native.logo` |

---

### Table 2: `rtb_daily` (from CSV Import)

These fields describe *how the creative performed* - the actual metrics that reveal waste.

**NOTE:** `buyer_id`, `bidder_id`, `billing_id` are TEXT fields because Google's API returns them as strings. Converting to INTEGER would risk data loss.

#### Essential Fields (Always export these)

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `metric_date` | DATE | Performance date | Timeframe filtering |
| `creative_id` | TEXT | Links to creatives table | Join key |
| `billing_id` | TEXT | Pretargeting config ID | **Config efficiency analysis** |
| `creative_size` | TEXT | Size from bid request | **Size mismatch detection** |
| `country` | TEXT | ISO country code | **ESSENTIAL - geo targeting efficiency** |
| `app_id` | TEXT | Mobile app bundle ID | **ESSENTIAL - where we buy inventory** |
| `advertiser` | TEXT | Advertiser name | **ESSENTIAL - detect blocked advertisers** |
| `reached_queries` | INT | Bid requests received | **THE critical waste metric** |
| `impressions` | INT | Impressions won | Win rate calculation |
| `clicks` | INT | Click count | **ESSENTIAL - major engagement signal** |
| `spend_micros` | INT | Spend in USD micros | Cost tracking |

#### Important Dimension Fields

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `creative_format` | TEXT | HTML, VIDEO, etc. | Format-specific analysis |
| `platform` | TEXT | Desktop, Mobile, Tablet | Platform waste analysis |
| `environment` | TEXT | App, Web | Environment performance |
| `app_name` | TEXT | Mobile app name | Human-readable reports |
| `publisher_id` | TEXT | Publisher ID | Publisher blocklist candidates |
| `publisher_name` | TEXT | Publisher name | Human-readable reports |
| `publisher_domain` | TEXT | Publisher website | Domain-level analysis |
| `deal_id` | TEXT | Deal identifier | Deal performance |
| `deal_name` | TEXT | Deal name | Human-readable reports |
| `transaction_type` | TEXT | Open auction, PMP, etc. | Transaction efficiency |
| `buyer_account_id` | TEXT | Buyer seat ID | Multi-seat analysis |
| `buyer_account_name` | TEXT | Buyer seat name | Human-readable reports |

#### Video Metrics

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `video_starts` | INT | Video play initiations | Video engagement analysis |
| `video_first_quartile` | INT | Reached 25% | Video completion funnel |
| `video_midpoint` | INT | Reached 50% | Video completion funnel |
| `video_third_quartile` | INT | Reached 75% | Video completion funnel |
| `video_completions` | INT | Reached 100% | **Video completion rate** |
| `vast_errors` | INT | VAST parsing errors | **Broken video detection** |
| `engaged_views` | INT | Engaged view count | Engagement quality |

#### Viewability

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `active_view_measurable` | INT | Viewability measurable | Viewability analysis |
| `active_view_viewable` | INT | Viewability viewable | **Viewability rate** |

#### Conversions (Vendor-agnostic UA data)

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `conversions` | INT | Generic conversion count | Overall conversion rate |
| `ua_installs` | INT | App installs | Install attribution |
| `ua_reinstalls` | INT | App reinstalls | Retention analysis |
| `ua_uninstalls` | INT | App uninstalls | Churn detection |
| `ua_sessions` | INT | App sessions | Engagement depth |
| `ua_in_app_events` | INT | In-app events | Post-install engagement |
| `ua_ad_revenue` | REAL | Ad revenue (USD) | ROAS calculation |
| `ua_skan_conversions` | INT | SKAdNetwork conversions (iOS) | iOS attribution |
| `ua_retargeting_reengagements` | INT | Retargeting re-engagements | Retargeting efficiency |
| `ua_retargeting_reattributions` | INT | Retargeting re-attributions | Retargeting value |
| `ua_fraud_blocked_installs` | INT | Fraud: blocked installs | Fraud signal |

#### SDK Flags

| Field | Type | Description | QPS Optimization Use |
|-------|------|-------------|---------------------|
| `gma_sdk` | BOOL | Google Mobile Ads SDK | SDK coverage |
| `buyer_sdk` | BOOL | Buyer SDK present | SDK coverage |

---

### Table 3: `thumbnail_status` (Generated)

| Field | Type | Description | Waste Detection Use |
|-------|------|-------------|---------------------|
| `creative_id` | TEXT PK | Creative ID | Join key |
| `status` | TEXT | success, failed | Thumbnail coverage |
| `error_reason` | TEXT | url_expired, timeout, etc. | **Broken video evidence** |
| `video_url` | TEXT | Attempted video URL | Debugging |
| `attempted_at` | TIMESTAMP | Last attempt time | Retry scheduling |

---

### Waste Detection: Field Combinations & Algorithms

The power of Cat-Scan is in combining fields to surface waste. Here's how:

#### 1. QPS Waste Rate (The Core Metric)

```
waste_rate = (reached_queries - impressions) / reached_queries × 100
```

| Fields Used | Insight |
|-------------|---------|
| `reached_queries`, `impressions` | **Direct waste percentage** |

*Example: 100K queries, 1K impressions = 99% waste. You're processing 99K requests for nothing.*

#### 2. Size Mismatch Detection

```sql
-- Find sizes you receive traffic for but have no creatives
SELECT p.creative_size, SUM(p.reached_queries) as wasted_qps
FROM rtb_daily p
LEFT JOIN creatives c ON c.canonical_size = p.creative_size
WHERE c.id IS NULL
GROUP BY p.creative_size
ORDER BY wasted_qps DESC
```

| Fields Used | Insight |
|-------------|---------|
| `rtb_daily.creative_size` + `creatives.canonical_size` | **Sizes you lack inventory for** |

*Action: Either add creatives for high-volume sizes OR exclude those sizes from pretargeting.*

#### 3. Broken Video Detection

```sql
-- Videos with high impressions but thumbnail generation failed
SELECT c.id, c.advertiser_name,
       SUM(p.impressions) as impressions,
       ts.error_reason
FROM creatives c
JOIN thumbnail_status ts ON c.id = ts.creative_id
JOIN rtb_daily p ON c.id = p.creative_id
WHERE c.format = 'VIDEO'
  AND ts.status = 'failed'
  AND ts.error_reason IN ('url_expired', 'timeout', 'invalid_format')
GROUP BY c.id
HAVING impressions > 1000
```

| Fields Used | Insight |
|-------------|---------|
| `creatives.format` + `thumbnail_status.error_reason` + `rtb_daily.impressions` | **Spending on unplayable videos** |

*A video that can't generate a thumbnail likely can't play for users either.*

#### 4. Zero Engagement Detection

```sql
-- Creatives with high spend but zero clicks over 7+ days
SELECT c.id, c.advertiser_name,
       SUM(p.impressions) as total_impressions,
       SUM(p.clicks) as total_clicks,
       SUM(p.spend_micros)/1000000.0 as spend_usd,
       COUNT(DISTINCT p.metric_date) as days_active
FROM creatives c
JOIN rtb_daily p ON c.id = p.creative_id
WHERE p.metric_date >= date('now', '-14 days')
GROUP BY c.id
HAVING total_impressions > 10000
   AND total_clicks = 0
   AND days_active >= 7
```

| Fields Used | Insight |
|-------------|---------|
| `impressions`, `clicks`, `spend_micros`, `metric_date` | **Money spent on creatives nobody engages with** |

*Pattern over time matters: 1 day of zero clicks is normal; 7+ days is a red flag.*

#### 5. Click Fraud Signals

```sql
-- Suspicious click patterns (clicks > impressions is impossible legitimately)
SELECT p.creative_id, p.publisher_id, p.app_id,
       p.metric_date,
       p.impressions, p.clicks,
       CAST(p.clicks AS FLOAT) / NULLIF(p.impressions, 0) as ctr
FROM rtb_daily p
WHERE p.clicks > p.impressions
   OR (p.impressions > 100 AND CAST(p.clicks AS FLOAT) / p.impressions > 0.5)
```

| Fields Used | Insight |
|-------------|---------|
| `clicks`, `impressions`, `publisher_id`, `app_id` | **Fraudulent traffic sources** |

*Flag for human review. CTR > 50% on display is almost always fraud.*

#### 6. Video Completion Funnel

```sql
-- Videos where users start but don't complete
SELECT c.id, c.advertiser_name,
       SUM(p.video_starts) as starts,
       SUM(p.video_completions) as completions,
       CAST(SUM(p.video_completions) AS FLOAT) / NULLIF(SUM(p.video_starts), 0) * 100 as vcr
FROM creatives c
JOIN rtb_daily p ON c.id = p.creative_id
WHERE c.format = 'VIDEO'
  AND p.metric_date >= date('now', '-7 days')
GROUP BY c.id
HAVING starts > 1000 AND vcr < 10
```

| Fields Used | Insight |
|-------------|---------|
| `video_starts`, `video_completions`, `format` | **Videos that annoy users** |

*Very low VCR (< 10%) suggests the video is unskippable but unwanted, or has playback issues.*

#### 7. Config Efficiency Analysis

```sql
-- Which pretargeting configs waste the most QPS?
SELECT billing_id,
       SUM(reached_queries) as total_queries,
       SUM(impressions) as total_impressions,
       100.0 * (SUM(reached_queries) - SUM(impressions)) / NULLIF(SUM(reached_queries), 0) as waste_pct
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
GROUP BY billing_id
ORDER BY waste_pct DESC
```

| Fields Used | Insight |
|-------------|---------|
| `billing_id`, `reached_queries`, `impressions` | **Which configs need tuning** |

*High waste_pct = config is too broad. Tighten targeting or add exclusions.*

#### 8. Publisher Blocklist Candidates

```sql
-- Publishers with high QPS but zero/low impressions
SELECT publisher_id, publisher_name, publisher_domain,
       SUM(reached_queries) as queries,
       SUM(impressions) as impressions,
       SUM(spend_micros)/1000000.0 as spend
FROM rtb_daily
WHERE metric_date >= date('now', '-14 days')
GROUP BY publisher_id
HAVING queries > 10000 AND (impressions = 0 OR spend/queries < 0.00001)
```

| Fields Used | Insight |
|-------------|---------|
| `publisher_id`, `publisher_domain`, `reached_queries`, `impressions` | **Publishers sending worthless traffic** |

#### 9. Disapproved Creative Waste

```sql
-- Spending on creatives that are disapproved
SELECT c.id, c.approval_status, c.advertiser_name,
       SUM(p.impressions) as impressions,
       SUM(p.spend_micros)/1000000.0 as spend
FROM creatives c
JOIN rtb_daily p ON c.id = p.creative_id
WHERE c.approval_status = 'DISAPPROVED'
GROUP BY c.id
```

| Fields Used | Insight |
|-------------|---------|
| `creatives.approval_status` + `rtb_daily.*` | **100% wasted spend on banned ads** |

*Disapproved creatives shouldn't be bidding. If they have spend, something is wrong.*

---

### AI/Algorithm Recommendations Summary

| Waste Type | Detection Method | Action |
|------------|------------------|--------|
| **Size mismatch** | `creative_size` not in `canonical_size` inventory | Add creative OR exclude size |
| **Config inefficiency** | High `reached_queries` / low `impressions` per `billing_id` | Tighten targeting |
| **Broken video** | `thumbnail_status.status = 'failed'` + high spend | Review creative quality |
| **Zero engagement** | High impressions, zero clicks over 7+ days | Review creative quality |
| **Click fraud** | `clicks > impressions` OR CTR > 50% | Block publisher/app |
| **Poor video completion** | VCR < 10% over significant volume | Review creative quality |
| **Disapproved waste** | `approval_status = 'DISAPPROVED'` with spend | Ensure it is not included in auction |
| **Publisher waste** | High queries, zero wins from `publisher_id` | Investigate, maybe add to blocklist |

---

## Actionable Controls: How to Reduce Waste

Cat-Scan identifies waste. But **what can you actually change?** There are only two levels of control available to optimize QPS efficiency:

### Control Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│  BIDDER (Not Under Your Control)                                │
│  The actual bidding logic, bid prices, creative selection       │
│  → Coordinate with bidder team for improvements                 │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 1: ENDPOINT ZONES                                        │
│  Which planetary regions receive your bid requests              │
│  → 4 zones: US-East, US-West, EU, Asia                         │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 2: PRETARGETING CONFIGS                                  │
│  Filter bid requests BEFORE they reach your bidder              │
│  → The primary lever for QPS efficiency                        │
└─────────────────────────────────────────────────────────────────┘
```

---

### Level 1: Endpoint Zone Configuration

Google Authorized Buyers routes bid requests to your bidder endpoints based on geographic zones. You can enable/disable zones and set QPS limits per zone.

| Zone | Region | Use Case |
|------|--------|----------|
| **US-East** | Eastern United States | Americas traffic |
| **US-West** | Western United States | Americas traffic |
| **EU** | Europe | European traffic (GDPR considerations) |
| **Asia** | Asia-Pacific | APAC traffic |

**How Cat-Scan helps:**
```sql
-- Find which regions waste the most QPS
SELECT country,
       SUM(reached_queries) as queries,
       SUM(impressions) as impressions,
       100.0 * (SUM(reached_queries) - SUM(impressions)) / NULLIF(SUM(reached_queries), 0) as waste_pct
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
GROUP BY country
ORDER BY queries DESC
```

**Action:** If a region has >95% waste and low volume, consider disabling that endpoint zone entirely.

---

### Level 2: Pretargeting Configuration

Pretargeting configs are the **primary lever** for QPS efficiency. They filter bid requests *before* they reach your bidder, eliminating waste at the source.

**API Reference:** [Pretargeting Configs Guide](https://developers.google.com/authorized-buyers/apis/guides/rtb-api/pretargeting-configs)

#### Core Settings

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `displayName` | string | Human-readable config name | Maps to `billing_id` in reports |
| `billingId` | string | Unique billing identifier | **Join key to `rtb_daily.billing_id`** |
| `state` | enum | ACTIVE, SUSPENDED | - |

#### Creative Filtering

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `includedFormats` | array | HTML, NATIVE, VAST | `creatives.format`, `rtb_daily.creative_format` |
| `includedCreativeDimensions` | array | Width/height pairs to accept | `creatives.canonical_size`, `rtb_daily.creative_size` |
| `minimumViewabilityDecile` | int (0-10) | Min predicted viewability (5 = 50%) | `rtb_daily.active_view_viewable` |

**CRITICAL:** Size filtering is **INCLUDE-ONLY**.
- Empty list = Accept ALL sizes (maximum QPS)
- Add ONE size = ONLY that size accepted (all others rejected)
- There is NO "exclude size" option

```sql
-- Generate recommended includedCreativeDimensions based on your actual inventory
SELECT DISTINCT canonical_size, width, height
FROM creatives
WHERE canonical_size IS NOT NULL
ORDER BY canonical_size
```

#### Geographic Targeting

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `geoTargeting.includedIds` | array | Geo region IDs to include | `rtb_daily.country` |
| `geoTargeting.excludedIds` | array | Geo region IDs to exclude | `rtb_daily.country` |
| `includedLanguages` | array | Language codes | - |

**Geo ID Reference:** [geo-table.csv](https://storage.googleapis.com/adx-rtb-dictionaries/geo-table.csv)

```sql
-- Find countries with high waste to consider excluding
SELECT country,
       SUM(reached_queries) as queries,
       SUM(impressions) as wins,
       SUM(spend_micros)/1000000.0 as spend,
       100.0 * (SUM(reached_queries) - SUM(impressions)) / NULLIF(SUM(reached_queries), 0) as waste_pct
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
  AND country IS NOT NULL
GROUP BY country
HAVING queries > 10000
ORDER BY waste_pct DESC
```

#### Platform & Environment

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `includedPlatforms` | array | PERSONAL_COMPUTER, PHONE, TABLET, CONNECTED_TV | `rtb_daily.platform` |
| `includedEnvironments` | array | APP, WEB | `rtb_daily.environment` |
| `interstitialTargeting` | enum | ONLY_INTERSTITIAL_REQUESTS, ONLY_NON_INTERSTITIAL_REQUESTS | - |

```sql
-- Platform efficiency analysis
SELECT platform, environment,
       SUM(reached_queries) as queries,
       SUM(impressions) as wins,
       100.0 * SUM(impressions) / NULLIF(SUM(reached_queries), 0) as win_rate
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
GROUP BY platform, environment
ORDER BY queries DESC
```

#### Publisher & App Targeting

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `publisherTargeting.targetingMode` | enum | INCLUSIVE or EXCLUSIVE | - |
| `publisherTargeting.values` | array | Publisher IDs from ads.txt | `rtb_daily.publisher_id` |
| `webTargeting.targetingMode` | enum | INCLUSIVE or EXCLUSIVE | - |
| `webTargeting.values` | array | Site URLs | `rtb_daily.publisher_domain` |
| `appTargeting.mobileAppTargeting` | object | App IDs to include/exclude | `rtb_daily.app_id` |
| `appTargeting.mobileAppCategoryTargeting` | object | App category IDs | - |

```sql
-- Publishers to consider blocking (high traffic, zero/low wins)
SELECT publisher_id, publisher_name, publisher_domain,
       SUM(reached_queries) as queries,
       SUM(impressions) as wins,
       SUM(clicks) as clicks
FROM rtb_daily
WHERE metric_date >= date('now', '-14 days')
GROUP BY publisher_id
HAVING queries > 50000 AND wins < 100
ORDER BY queries DESC
LIMIT 20
```

```sql
-- Apps to consider blocking (fraud signals or poor performance)
SELECT app_id, app_name,
       SUM(reached_queries) as queries,
       SUM(impressions) as impressions,
       SUM(clicks) as clicks,
       CASE WHEN SUM(impressions) > 0
            THEN CAST(SUM(clicks) AS FLOAT) / SUM(impressions)
            ELSE 0 END as ctr
FROM rtb_daily
WHERE metric_date >= date('now', '-14 days')
  AND app_id IS NOT NULL
GROUP BY app_id
HAVING queries > 10000 AND (clicks > impressions OR ctr > 0.5)
ORDER BY queries DESC
```

#### Audience Targeting

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `userListTargeting.includedIds` | array | User lists to target | - |
| `userListTargeting.excludedIds` | array | User lists to exclude | - |
| `allowedUserTargetingModes` | array | REMARKETING_ADS, INTEREST_BASED_TARGETING | - |
| `includedUserIdTypes` | array | HOSTED_MATCH_DATA, GOOGLE_COOKIE, DEVICE_ID | - |
| `excludedContentLabelIds` | array | Sensitive content categories | - |

#### Vertical/Category Targeting

| Field | Type | Description | Cat-Scan Data Link |
|-------|------|-------------|-------------------|
| `verticalTargeting.includedIds` | array | Industry category IDs to include | - |
| `verticalTargeting.excludedIds` | array | Industry category IDs to exclude | - |

**Vertical ID Reference:** [publisher-verticals.txt](https://storage.googleapis.com/adx-rtb-dictionaries/publisher-verticals.txt)

---

### Mapping Cat-Scan Insights → Pretargeting Actions

| Cat-Scan Finding | Pretargeting Field | Action |
|------------------|-------------------|--------|
| Size mismatch (traffic for sizes you lack) | `includedCreativeDimensions` | Add ONLY sizes you have creatives for |
| High waste from specific country | `geoTargeting.excludedIds` | Alert AdOps of this |
| High waste from specific platform | `includedPlatforms` | Suggest removal of underperforming platform |
| Fraud signals from publisher | `publisherTargeting` | Suggest to Set EXCLUSIVE mode, add publisher ID |
| Fraud signals from app | `appTargeting.mobileAppTargeting` | Alert user to specific app IDs |
| Poor performance on web vs app | `includedEnvironments` | use as secondary signal |
| Low viewability | `minimumViewabilityDecile` | Compareto similar and alert AdOps |

---

### Example: Full Optimization Workflow

```
1. IMPORT CSV DATA
   → python cli/qps_analyzer.py import ~/reports/weekly.csv

2. RUN ANALYSIS
   → python cli/qps_analyzer.py full-report --days 7

3. IDENTIFY WASTE SOURCES
   Cat-Scan shows:
   - 40% of QPS is for sizes you don't have (300x600, 970x250)
   - Brazil has 98% waste rate, 500K queries/day
   - Publisher "sketchy-news.com" has CTR of 85% (fraud)
   - App "com.fake.game" has clicks > impressions

4. UPDATE PRETARGETING CONFIG

   includedCreativeDimensions: [
     {width: 300, height: 250},
     {width: 728, height: 90},
     {width: 320, height: 50}
     // Only sizes you actually have creatives for
   ]

   geoTargeting: {
     excludedIds: ["2076"]  // Brazil geo ID
   }

   publisherTargeting: {
     targetingMode: "EXCLUSIVE",
     values: ["sketchy-news.com"]
   }

   appTargeting: {
     mobileAppTargeting: {
       targetingMode: "EXCLUSIVE",
       values: ["com.fake.game"]
     }
   }

5. MONITOR RESULTS
   → Wait 24-48 hours
   → Import new CSV
   → Compare waste_pct before/after
```

---

### Coordination with Bidder Team

Some optimizations require coordination with the bidder (not controllable via pretargeting):

| Issue | Who Fixes It | What to Communicate |
|-------|--------------|---------------------|
| Bid prices too low (losing auctions) | Bidder | Win rate data by segment |
| Wrong creatives selected for context | Bidder | Creative performance by publisher/app |
| Bidding on disapproved creatives | Bidder | List of disapproved creative IDs with spend |
| Slow bid response (timeouts) | Bidder or EP| Endpoint latency data or misconfig |
| Poor creative quality | Advertiser | Zero-engagement creative list |

**Cat-Scan provides the evidence.** Share reports with bidder team to coordinate improvements.

---

## License

MIT License - see [LICENSE](LICENSE) file

## Acknowledgments

- [Google Authorized Buyers RTB API](https://developers.google.com/authorized-buyers/apis)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)

---

**Built for RTB bidders who want to improve QPS efficiency.**
