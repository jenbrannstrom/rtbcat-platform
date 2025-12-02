# Cat-Scan Creative Intelligence

**Version:** 10.3
**Phase:** 9.7 - Onboarding Flow Complete
**Last Updated:** December 2, 2025

A Python-based system for collecting Google Authorized Buyers creatives and organizing them for analysis. This tool helps RTB bidders understand what they're actually bidding on by fetching and organizing creatives that Google leaves as opaque IDs.

## What This Solves

**The Problem:** Google Authorized Buyers shows you creative IDs like `cr-12345`, but doesn't tell you:
- Which creatives belong to the same campaign
- What the actual creative looks like (especially for native ads)
- Which creatives are wasting your budget

**The Solution:** Cat-Scan automatically:
1. Fetches all your creatives from Authorized Buyers API
2. Extracts metadata, UTM parameters, and destination URLs
3. Stores them in a queryable SQLite database
4. Provides REST API and dashboard for exploration
5. Supports filtering by format (HTML, VIDEO, NATIVE), approval status, and more

## Features

- **Creative Collection**: Fetch all creatives from Google Authorized Buyers API with pagination
- **Metadata Extraction**: Parse UTM parameters, dimensions, approval status, advertiser names
- **Multiple Formats**: Support for HTML, VIDEO, and NATIVE creative types
- **Multi-Seat Support**: Manage multiple buyer accounts under a single bidder
- **REST API**: FastAPI-based API with Swagger documentation
- **Encrypted Config**: Secure credential storage with Fernet encryption
- **Docker Support**: Multi-stage Docker build with non-root user
- **Dashboard**: Next.js frontend for visual exploration (optional)

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

Need a JSON key? See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for step-by-step instructions.

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

# Start API server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
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
rtbcat-creative-intel/
├── api/
│   ├── __init__.py
│   └── main.py                  # FastAPI application
├── collectors/
│   ├── __init__.py              # Exports CreativesClient, PretargetingClient, BuyerSeatsClient
│   ├── base.py                  # Base client with auth and retry logic
│   ├── csv_reports.py           # Gmail CSV report fetcher
│   ├── seats.py                 # BuyerSeatsClient - multi-seat discovery
│   ├── creatives/
│   │   ├── __init__.py
│   │   ├── client.py            # CreativesClient - main collector
│   │   ├── schemas.py           # TypedDict schemas (includes buyerId)
│   │   └── parsers.py           # API response parsers
│   └── pretargeting/
│       ├── __init__.py
│       ├── client.py            # PretargetingClient
│       ├── schemas.py           # Pretargeting schemas
│       └── parsers.py           # Pretargeting parsers
├── config/
│   ├── __init__.py
│   └── config_manager.py        # Encrypted credential storage
├── storage/
│   ├── __init__.py
│   ├── sqlite_store.py          # SQLite backend (Creative, Campaign, BuyerSeat)
│   ├── s3_writer.py             # S3 backup (optional)
│   └── adapters.py              # API → Storage type conversion
├── tests/
│   ├── __init__.py
│   ├── test_multi_seat.py       # Multi-seat functionality tests (23 tests)
│   └── ...                      # Additional test modules
├── dashboard/                   # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── connect/         # Credential upload & sync (NEW)
│   │   │   ├── creatives/       # Creative browser
│   │   │   ├── import/          # CSV performance import
│   │   │   └── ...              # Other pages
│   │   ├── components/          # React components
│   │   └── lib/                 # API client
│   └── package.json
├── docs/
│   └── SETUP_GUIDE.md           # Comprehensive setup guide (NEW)
├── scripts/
│   └── test_real_api.py         # Live API testing
├── cli/
│   └── qps_analyzer.py          # CLI tools (import, thumbnails, reports)
├── main.py                      # CLI entry point
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # Service definitions
├── requirements.txt             # Python dependencies
└── pyproject.toml               # Project configuration
```

## Configuration Files

Configuration is stored in `~/.rtbcat/` (or `/home/rtbcat/.rtbcat/` in Docker):

```
~/.rtbcat/
├── config.enc    # Encrypted configuration (Fernet)
├── .key          # Encryption key (mode 0600)
└── rtbcat.db     # SQLite database
```

Credentials are mounted from `~/.rtb-cat/credentials/`:

```
~/.rtb-cat/credentials/
└── google-credentials.json    # Google service account
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

### Tables

| Table | Description |
|-------|-------------|
| `creatives` | Creative metadata with `buyer_id` for multi-seat support |
| `campaigns` | Campaign clusters (manual or AI-generated) |
| `buyer_seats` | Buyer accounts under a bidder |

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
- [x] AI-based creative clustering (`/ai-campaigns/auto-cluster`)
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

### Phase 9.7: Onboarding Flow (NEW)
- `/connect` page for credential management and account discovery
- JSON key upload with drag-drop support
- Smart seat UI: single-seat shows title, multi-seat shows dropdown
- Sync button conditionally appears after credentials uploaded
- Comprehensive setup guide at `docs/SETUP_GUIDE.md`

### Phase 9.6: Video & Card Improvements (NEW)
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
| GET | `/ai-campaigns` | List AI-generated campaigns |
| POST | `/ai-campaigns/auto-cluster` | Auto-cluster creatives |
| GET | `/ai-campaigns/{id}/performance` | Get campaign performance |
| PATCH | `/seats/{buyer_id}` | Update seat display name |
| POST | `/seats/populate` | Populate seats from creatives |
| POST | `/config/credentials` | Upload service account JSON key |
| GET | `/config/status` | Check credential configuration status |
| GET | `/thumbnails/{id}.jpg` | Serve locally-generated video thumbnail |

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

## License

MIT License - see [LICENSE](LICENSE) file

## Acknowledgments

- [Google Authorized Buyers RTB API](https://developers.google.com/authorized-buyers/apis)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)

---

**Built for RTB bidders who want to understand their creative inventory.**
