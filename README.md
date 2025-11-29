# RTB.cat Platform

Unified platform for Creative Intelligence and RTB waste analysis.

**Status:** All 5 phases complete | **Build:** Successful

## Platform Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Creative Management | Complete |
| 2 | Size Normalization | Complete |
| 3 | Multi-Seat Support | Complete |
| 4 | Waste Analysis Engine | Complete |
| 5 | Dashboard UI Integration | Complete |

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Fake SSP    │────▶│  CAT_SCAN    │────▶│ Fake Bidder  │
│  (Testing)   │     │  (Analyzer)  │     │  (Testing)   │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Creative    │
                     │  Intelligence│
                     │  API         │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Dashboard   │
                     │  (Next.js)   │
                     └──────────────┘
```

## Components

### 1. Creative Intelligence (`/creative-intelligence`)
Python FastAPI service for creative data management.

- Fetches creatives from Google Authorized Buyers API
- SQLite storage with size normalization
- Multi-seat (buyer) support
- Waste analysis engine
- REST API for creative queries

**Key Features:**
- 2000+ raw sizes normalized to ~18 IAB standards
- VAST XML parsing for video dimensions
- Automatic canonical size computation
- RTB traffic data storage and analysis

### 2. CAT_SCAN (`/cat-scan`)
Rust RTB request analyzer.

- Sits between SSP and Bidder
- Logs and analyzes bid requests
- Detects waste patterns
- Generates format/segment reports

### 3. Dashboard (`/dashboard`)
Next.js 16 / React 19 web interface.

**Pages:**
- `/` - Home with quick actions
- `/creatives` - Creative browser with filters
- `/waste-analysis` - RTB waste visualization
- `/settings` - Configuration

**Waste Analysis Features:**
- Color-coded waste metrics (green/yellow/red)
- QPS savings calculator
- Size gap identification
- Actionable recommendations:
  - Block in pretargeting
  - Add creative
  - Use flexible HTML5
  - Monitor

## Quick Start

```bash
# Build all services
docker-compose build

# Start everything
docker-compose up

# Access:
# - Dashboard: http://localhost:3000
# - Creative API: http://localhost:8000
# - CAT_SCAN metrics: http://localhost:9090
```

### Development Setup

```bash
# Creative Intelligence API
cd creative-intelligence
pip install -r requirements.txt
python -m uvicorn api.main:app --reload

# Dashboard
cd dashboard
npm install
npm run dev
```

## API Endpoints

### Creative Intelligence API (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/creatives` | GET | List creatives with filters |
| `/api/creatives/{id}` | GET | Get single creative |
| `/api/stats` | GET | Aggregate statistics |
| `/api/seats` | GET | List buyer seats |
| `/analytics/waste` | GET | Waste analysis report |
| `/analytics/size-coverage` | GET | Size coverage data |

### Query Parameters

**Creatives:**
- `format` - HTML, VIDEO, NATIVE
- `canonical_size` - e.g., "300x250 (Medium Rectangle)"
- `size_category` - IAB Standard, Video, Adaptive, Non-Standard
- `buyer_id` - Filter by buyer seat

**Waste Analysis:**
- `buyer_id` - Required buyer account ID
- `days` - Analysis period (7, 14, 30)

## Size Normalization

Reduces 2000+ creative sizes to ~18 IAB standard categories:

**IAB Standards:**
- 300x250 (Medium Rectangle)
- 728x90 (Leaderboard)
- 320x50 (Mobile Banner)
- 160x600 (Wide Skyscraper)
- 300x600 (Half Page)
- And 10 more...

**Video Formats (by aspect ratio):**
- Video 16:9 (Horizontal)
- Video 9:16 (Vertical)
- Video 1:1 (Square)
- Video 4:5 (Portrait)

**Special Cases:**
- Adaptive/Fluid (0 dimension)
- Adaptive/Responsive (1x1)

## Documentation

- [Creative Intelligence Handover](docs/RTBcat_Project_Handover.md)
- [CAT_SCAN Handover](docs/CAT_SCAN_HANDOVER.md)
- [CAT_SCAN README](docs/CAT_SCAN_README.md)

## Development

See individual component READMEs:
- [Creative Intelligence](creative-intelligence/README.md)
- [CAT_SCAN](cat-scan/README.md)
- [Dashboard](dashboard/README.md)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | Python 3.12, FastAPI |
| Database | SQLite |
| Dashboard | Next.js 16, React 19, Tailwind CSS |
| RTB Analyzer | Rust |
| Charts | Recharts |
| Data Fetching | TanStack React Query |

## Future Phases

- **Phase 6:** Real Traffic Integration (CAT_SCAN live data)
- **Phase 7:** Pretargeting Automation (one-click blocking)
- **Phase 8:** Historical Analytics (trends over time)
- **Phase 9:** Alerting & Notifications
