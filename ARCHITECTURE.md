# Cat-Scan Architecture

**Version:** 1.0 | **Last Updated:** January 2026

This document describes the technical architecture of Cat-Scan, a QPS optimization platform for Google Authorized Buyers.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Google Authorized Buyers API    │    Gmail API    │    AWS S3 (Archive)    │
│  - Creatives                     │    - CSV Import │    - Data retention    │
│  - Pretargeting Configs          │    - Reports    │    - Backups           │
│  - RTB Endpoints                 │                 │                        │
│  - Buyer Seats                   │                 │                        │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                       │                    │
                    ▼                       ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                               │
│                              Port 8000                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API ROUTERS (15+)                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  system      │ creatives  │ seats      │ settings   │ config       │   │
│  │  campaigns   │ uploads    │ gmail      │ retention  │ admin        │   │
│  │  analytics/* │ qps        │ performance│ collect    │ recommendations │ │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MIDDLEWARE                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  SessionAuthMiddleware  │  APIKeyAuthMiddleware  │  CORS            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         CORE SERVICES                                │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  collectors/     │  analytics/      │  qps/           │  analysis/  │   │
│  │  - creatives     │  - efficiency    │  - optimizer    │  - waste    │   │
│  │  - pretargeting  │  - funnel        │  - importer     │  - signals  │   │
│  │  - endpoints     │  - traffic       │  - recommender  │             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         STORAGE LAYER                                │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  SQLiteStore         │  Repositories            │  S3Writer         │   │
│  │  - 41 tables         │  - repositories/         │  - Archive        │   │
│  │  - WAL mode          │    - campaign_repository │  - Backup         │   │
│  │                      │    - seat_repository     │                   │   │
│  │                      │    - performance_repository                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                              │
│                              Port 3000                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         PAGES (21+)                                  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  /              │ /creatives    │ /campaigns     │ /import          │   │
│  │  /login         │ /history      │ /uploads       │ /setup           │   │
│  │  /settings/*    │ /admin/*      │ /connect       │ /waste-analysis  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         COMPONENTS                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  sidebar        │ preview-modal │ creative-card  │ charts           │   │
│  │  data-tables    │ forms         │ filters        │ notifications    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         STATE & API                                  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  lib/api.ts     │ contexts/     │ hooks/         │ types/           │   │
│  │  (118 endpoints)│ auth-context  │ useCreatives   │ api.ts           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
rtbcat-platform/
├── api/                    # FastAPI backend
│   ├── main.py            # Application entry point
│   ├── auth.py            # API key authentication
│   ├── auth_oauth_proxy.py # Session-based authentication
│   ├── session_middleware.py
│   ├── dependencies.py    # Dependency injection
│   ├── campaigns_router.py
│   └── routers/           # API route handlers
│       ├── system.py      # Health, stats, thumbnails
│       ├── creatives.py   # Creative management
│       ├── seats.py       # Buyer seat discovery
│       ├── settings.py    # RTB endpoints, pretargeting
│       ├── config.py      # Credentials management
│       ├── uploads.py     # CSV file uploads
│       ├── gmail.py       # Gmail auto-import
│       ├── retention.py   # Data retention policies
│       ├── recommendations.py
│       ├── qps.py         # QPS analytics
│       ├── performance.py # Performance data import
│       ├── admin.py       # User management
│       └── collect.py     # Google API sync
│
├── storage/               # Data persistence layer
│   ├── sqlite_store.py    # Main database interface
│   ├── schema.py          # Table definitions (41 tables)
│   ├── models.py          # Pydantic models
│   ├── database.py        # Connection management
│   ├── repositories/
│   │   ├── campaign_repository.py
│   │   ├── seat_repository.py
│   │   ├── performance_repository.py
│   ├── retention_manager.py
│   └── s3_writer.py       # AWS S3 archival
│
├── collectors/            # Google API clients
│   ├── creatives/         # Creative sync
│   ├── pretargeting/      # Pretargeting config management
│   ├── endpoints/         # RTB endpoint discovery
│   └── troubleshooting/   # Real-time bid troubleshooting
│
├── analytics/             # RTB analytics & metrics (14 modules)
│   ├── waste_analyzer.py  # Traffic waste analysis
│   ├── rtb_bidstream_analyzer.py  # Bidstream analysis
│   ├── qps_optimizer.py   # QPS optimization
│   ├── size_analyzer.py   # Ad size analysis
│   ├── geo_analyzer.py    # Geographic analysis
│   └── fraud_analyzer.py  # Fraud detection
│
├── analysis/              # Evaluation & recommendations
│   └── evaluation_engine.py  # Decision intelligence engine
│
├── qps/                   # CSV import & QPS utilities
│   ├── smart_importer.py  # Auto-detect CSV type
│   ├── funnel_importer.py # RTB funnel data import
│   ├── importer.py        # Core CSV import
│   ├── size_analyzer.py   # Size coverage analysis
│   ├── fraud_detector.py  # Fraud signal detection
│   └── utils.py           # Shared utilities
│
├── utils/                 # Cross-cutting utilities
│   ├── size_normalization.py  # IAB size mapping
│   ├── app_parser.py      # App metadata parsing
│   └── country_codes.py   # Geographic utilities
│
├── config/                # Configuration management
│   └── config_manager.py  # ConfigManager class
│
├── dashboard/             # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components
│   │   ├── lib/           # Utilities & API client
│   │   ├── contexts/      # React contexts
│   │   ├── hooks/         # Custom hooks
│   │   └── types/         # TypeScript types
│   └── package.json
│
├── creative-intelligence/ # CLI tools & tests (legacy location)
│   ├── cli/
│   │   └── qps_analyzer.py  # CLI for imports & analysis
│   └── tests/             # Test suite
│
├── scripts/               # Utility scripts
│   ├── gmail_import.py    # Gmail CSV import
│   └── cleanup_old_data.py
│
├── migrations/            # Database migrations (20+ migrations)
├── docs/                  # Documentation
├── terraform/             # Infrastructure as code
│
├── setup.sh              # Development setup script
├── run.sh                # Start API + Dashboard
└── requirements.txt      # Python dependencies
```

---

## Data Flow

### 1. Creative Sync Flow

```
Google Authorized Buyers API
            │
            ▼
    collectors/creatives/client.py
            │
            ▼
    storage/sqlite_store.py
            │
            ▼
    creatives table (600+ records)
```

### 2. CSV Import Flow

```
Gmail (scheduled reports)          Manual Upload
            │                            │
            ▼                            ▼
    api/routers/gmail.py         api/routers/uploads.py
            │                            │
            └──────────┬─────────────────┘
                       ▼
              qps/smart_importer.py
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    rtb_daily     rtb_bidstream    rtb_quality
   (Performance)  (Bid pipeline) (Traffic quality)
```

### 3. Analysis Flow

```
    rtb_daily + rtb_bidstream + creatives
                    │
                    ▼
    ┌───────────────────────────────┐
    │      Analysis Engines         │
    │  - qps/optimizer.py           │
    │  - analysis/waste_analyzer.py │
    │  - qps/recommender.py         │
    └───────────────────────────────┘
                    │
                    ▼
    recommendations table + inefficiency_signals
                    │
                    ▼
    api/routers/recommendations.py
                    │
                    ▼
    Dashboard (Efficiency Analysis page)
```

---

## Database Schema Overview

### Core Tables (41 total)

| Category | Tables | Purpose |
|----------|--------|---------|
| **Creative Management** | creatives, clusters, thumbnail_status | Store creative metadata and thumbnails |
| **Campaign Management** | campaigns, ai_campaigns, creative_campaigns, campaign_creatives, campaign_daily_summary | Organize creatives into campaigns |
| **Service Accounts & Seats** | service_accounts, buyer_seats, seats | Multi-account/multi-seat support (4 seats across 2 accounts) |
| **RTB Performance** | rtb_daily, rtb_bidstream, rtb_bid_filtering, rtb_quality | CSV import data |
| **Pretargeting** | pretargeting_configs, pretargeting_history, pretargeting_snapshots, pretargeting_pending_changes | Pretargeting management |
| **Import Tracking** | import_history, daily_upload_summary, import_anomalies | Track CSV imports |
| **User Authentication** | users, user_sessions, audit_log | Multi-user support |
| **Lookup Tables** | apps, publishers, geographies, billing_accounts | Reference data |
| **Quality & Efficiency** | anomaly_signals, inefficiency_signals, recommendations | Analysis outputs |

See [DATA_MODEL.md](DATA_MODEL.md) for complete schema documentation.

---

## API Architecture

### Router Organization

The API is organized into domain-specific routers:

| Router | Prefix | Endpoints | Purpose |
|--------|--------|-----------|---------|
| system | `/` | 8 | Health, stats, thumbnails |
| creatives | `/creatives` | 12 | Creative CRUD, filtering |
| seats | `/seats` | 10 | Buyer seat management |
| campaigns | `/campaigns` | 15 | Campaign clustering |
| settings | `/settings` | 20 | Pretargeting, endpoints |
| config | `/config` | 8 | Credentials, service accounts |
| analytics/* | `/analytics` | 25 | Efficiency, funnel, waste |
| recommendations | `/recommendations` | 5 | AI recommendations |
| uploads | `/uploads` | 6 | CSV upload tracking |
| gmail | `/gmail` | 4 | Gmail auto-import |
| admin | `/admin` | 15 | User management |

**Total: 118+ endpoints**

### Authentication

Two authentication modes:

1. **API Key** (single-user/development):
   - Set `CATSCAN_API_KEY` environment variable
   - Pass via `X-API-Key` header

2. **Session-based** (multi-user/production):
   - Login via `/auth/login`
   - Session cookie for subsequent requests
   - Role-based access (admin, user, viewer)

---

## Frontend Architecture

### Technology Stack

- **Framework:** Next.js 14 (App Router)
- **UI:** Tailwind CSS + shadcn/ui components
- **State:** React Context + SWR for data fetching
- **Charts:** Recharts
- **i18n:** Custom type-safe internationalization system

### Internationalization (i18n)

Cat-Scan supports 11 languages with a type-safe translation system:

| Code | Language |
|------|----------|
| `en` | English (default) |
| `pl` | Polish |
| `zh` | Chinese |
| `ru` | Russian |
| `uk` | Ukrainian |
| `es` | Spanish |
| `da` | Danish |
| `fr` | French |
| `nl` | Dutch |
| `he` | Hebrew |
| `ar` | Arabic |

**Implementation:**

```
dashboard/src/lib/i18n/
├── types.ts          # TypeScript interfaces for translations
├── index.ts          # Translation provider & hooks
└── translations/
    └── en.ts         # English translations (default)
```

**Usage:**
- `useTranslation()` hook provides type-safe access to translations
- Language preference stored in localStorage
- Language selector in sidebar allows users to switch languages
- Translations are structured by feature area (common, sidebar, creatives, etc.)

### Page Structure

```
/                       # Dashboard (Waste Optimizer)
/creatives              # Creative browser with filters
/campaigns              # AI-clustered campaigns
/campaigns/[id]         # Campaign detail
/import                 # Manual CSV upload
/history                # Import history
/uploads                # Upload tracking
/waste-analysis         # Efficiency analysis
/settings               # Settings hub
/settings/seats         # Buyer seat management
/settings/retention     # Data retention policies
/settings/accounts      # Connected accounts
/settings/system        # System status
/admin                  # Admin dashboard
/admin/users            # User management
/admin/settings         # System settings
/admin/audit-log        # Audit trail
/login                  # Authentication
/setup                  # Initial setup wizard
/connect                # API credentials
```

---

## Deployment Architecture

### Production (AWS)

```
┌─────────────────────────────────────────────────────────┐
│                      AWS Cloud                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐      ┌─────────────────┐          │
│  │   EC2 Instance  │      │      S3         │          │
│  │                 │      │                 │          │
│  │  - FastAPI      │◄────►│  - CSV Archive  │          │
│  │  - Next.js      │      │  - Backups      │          │
│  │  - SQLite       │      │                 │          │
│  │  - systemd      │      └─────────────────┘          │
│  │                 │                                    │
│  └────────┬────────┘                                    │
│           │                                             │
│  ┌────────▼────────┐                                    │
│  │   Route 53      │                                    │
│  │  scan.rtb.cat   │                                    │
│  └─────────────────┘                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Local Development

```bash
./setup.sh    # Create venv, install deps, init DB
./run.sh      # Start API (8000) + Dashboard (3000)
```

---

## Key Design Decisions

### 1. SQLite with Multi-Account Support

**Why:** Cat-Scan uses SQLite with a multi-account architecture supporting multiple Google Authorized Buyers accounts and buyer seats within a single deployment. SQLite provides:
- Zero configuration
- Single-file database for easy backup
- WAL mode for concurrent reads
- Sufficient for multiple accounts with 600+ creatives each and millions of daily rows

**Multi-Account Model:**
- **Service Accounts**: Multiple Google service account credentials can be configured
- **Buyer Seats**: Each service account can access multiple buyer seats (bidder accounts)
- **Data Isolation**: All data (creatives, imports, performance metrics) is tagged with `bidder_id` for per-account querying

### 2. Modular Router Architecture

**Why:** The 118 endpoints are organized into 15+ routers for:
- Clear separation of concerns
- Easier testing and maintenance
- Independent scaling if needed

### 3. CSV-Based Data Import

**Why:** Google Authorized Buyers has no real-time reporting API:
- Scheduled CSV reports sent to Gmail
- Auto-import via Gmail API integration
- Manual upload as fallback

### 4. Pretargeting Pending Changes

**Why:** Safe pretargeting modifications:
- Changes queued in `pretargeting_pending_changes`
- Preview before applying to Google
- Rollback via snapshots

---

## Security Considerations

1. **Authentication:** Session-based with bcrypt password hashing
2. **Authorization:** Role-based access control (admin/user/viewer)
3. **API Security:** Optional API key for programmatic access
4. **Audit Logging:** All admin actions logged to `audit_log` table
5. **Credentials:** Service account JSON stored encrypted
6. **CORS:** Configurable for production deployment

---

## Performance Optimizations

1. **Database:**
   - WAL mode for concurrent access
   - Indexes on frequently queried columns
   - 90-day data retention with S3 archival

2. **API:**
   - Slim mode for creative listings (excludes VAST XML, HTML snippets)
   - Pagination for large result sets
   - Batch endpoints for bulk operations

3. **Frontend:**
   - Server-side rendering where applicable
   - SWR for data caching and revalidation
   - Lazy loading for creative previews

---

## Account & Seat Hierarchy

Cat-Scan supports multiple Google Authorized Buyers accounts with multiple buyer seats per account.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MULTI-ACCOUNT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      SERVICE ACCOUNTS                                │   │
│  │                   (Google API Credentials)                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Account A                     │  Account B                         │   │
│  │  (service-a@project.iam...)    │  (service-b@project.iam...)        │   │
│  └────────────┬───────────────────┴────────────┬───────────────────────┘   │
│               │                                │                            │
│               ▼                                ▼                            │
│  ┌────────────────────────────┐   ┌────────────────────────────┐           │
│  │       BUYER SEATS          │   │       BUYER SEATS          │           │
│  │   (bidder_id = Account A)  │   │   (bidder_id = Account B)  │           │
│  ├────────────────────────────┤   ├────────────────────────────┤           │
│  │  Seat 1 (buyer_id: 12345)  │   │  Seat 3 (buyer_id: 67890)  │           │
│  │  Seat 2 (buyer_id: 12346)  │   │  Seat 4 (buyer_id: 67891)  │           │
│  └────────────┬───────────────┘   └────────────┬───────────────┘           │
│               │                                │                            │
│               ▼                                ▼                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           DATA LAYER                                 │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  creatives (account_id, buyer_id)                                    │   │
│  │  rtb_daily (bidder_id)                                               │   │
│  │  import_history (bidder_id)                                          │   │
│  │  pretargeting_configs (bidder_id, billing_id)                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Table | Purpose |
|-----------|-------|---------|
| **Service Account** | `service_accounts` | Google API credentials (JSON key file) |
| **Buyer Seat** | `buyer_seats` | Individual bidder accounts under a service account |
| **Account Mapper** | `pretargeting_configs` | Maps `billing_id` → `bidder_id` for CSV imports |

### Implementation Files

| Purpose | File |
|---------|------|
| Account/Seat Repository | `storage/repositories/account_repository.py` |
| Billing → Bidder Mapping | `qps/account_mapper.py` |
| Frontend Context | `dashboard/src/contexts/account-context.tsx` |
| Multi-account Migration | `migrations/007_multi_account_tracking.sql` |

### Data Flow

1. **Credential Setup**: Service account JSON uploaded → stored in `service_accounts`
2. **Seat Discovery**: API sync discovers buyer seats → stored in `buyer_seats` with `bidder_id`
3. **CSV Import**: Billing ID extracted → `AccountMapper` resolves `bidder_id` → data tagged
4. **Querying**: Frontend selects buyer/account → queries filter by `bidder_id`

---

## Future Architecture Considerations

1. **Auto-Optimization Service:**
   - Background worker for automated pretargeting adjustments
   - Confidence scoring for auto-apply decisions
   - Learning from outcomes

2. **Real-Time Updates:**
   - WebSocket for live dashboard updates
   - Event-driven architecture for notifications

> **Note:** Multi-account/multi-seat support has been implemented. See "Account & Seat Hierarchy" section below.

---

*This architecture document reflects the Cat-Scan codebase as of January 2026.*
