# RTB.cat Platform

Unified platform for Creative Intelligence and RTB waste analysis.

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
- Python FastAPI service
- Fetches creatives from Google Authorized Buyers API
- Stores in SQLite
- Provides REST API for creative queries

### 2. CAT_SCAN (`/cat-scan`)
- Rust RTB request analyzer
- Sits between SSP and Bidder
- Logs and analyzes bid requests
- Detects waste patterns

### 3. Dashboard (`/dashboard`)
- Next.js UI
- Visualizes creatives
- Shows waste analysis
- Live RTB metrics

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

## Documentation

- [Creative Intelligence Handover](docs/RTBcat_Project_Handover.md)
- [CAT_SCAN Handover](docs/CAT_SCAN_HANDOVER.md)
- [CAT_SCAN README](docs/CAT_SCAN_README.md)

## Development

See individual component READMEs:
- [Creative Intelligence](creative-intelligence/README.md)
- [CAT_SCAN](cat-scan/README.md)
- [Dashboard](dashboard/README.md)
