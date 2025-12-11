# RTBcat Platform - Project Structure

```
rtbcat-platform/
├── cat-scan/                          # Rust-based RTB testing infrastructure
│   ├── cat_scan/                      # Core scanner
│   │   ├── src/main.rs
│   │   ├── Cargo.toml
│   │   └── Dockerfile
│   ├── fake_bidder/                   # Mock bidder for testing
│   │   ├── src/main.rs
│   │   ├── Cargo.toml
│   │   ├── Dockerfile
│   │   ├── deploy.sh
│   │   ├── buildspec.yml
│   │   ├── task-definition.json
│   │   └── DEPLOY.md
│   ├── fake_ssp/                      # Mock SSP for testing
│   │   ├── src/main.rs
│   │   ├── Cargo.toml
│   │   └── Dockerfile
│   ├── Cargo.toml
│   └── docker-compose.yml
│
├── creative-intelligence/             # Python FastAPI backend
│   ├── api/                           # API layer
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── dependencies.py
│   │   ├── campaigns_router.py
│   │   ├── routers/                   # API endpoints
│   │   │   ├── analytics.py           # QPS/spend analytics (1063 lines)
│   │   │   ├── collect.py             # Data collection
│   │   │   ├── config.py              # Config management
│   │   │   ├── creatives.py           # Creative management
│   │   │   ├── gmail.py               # Gmail integration
│   │   │   ├── performance.py         # Performance metrics import
│   │   │   ├── qps.py                 # QPS optimization
│   │   │   ├── recommendations.py     # AI recommendations
│   │   │   ├── retention.py           # Data retention
│   │   │   ├── seats.py               # Seat management
│   │   │   ├── settings.py            # Google auth & pretargeting (1416 lines)
│   │   │   ├── system.py              # System health
│   │   │   ├── troubleshooting.py     # Diagnostics
│   │   │   └── uploads.py             # File uploads
│   │   ├── schemas/                   # Pydantic models
│   │   │   ├── analytics.py
│   │   │   ├── campaigns.py
│   │   │   ├── common.py
│   │   │   ├── creatives.py
│   │   │   ├── performance.py
│   │   │   ├── qps.py
│   │   │   ├── recommendations.py
│   │   │   ├── seats.py
│   │   │   └── system.py
│   │   └── clustering/                # AI clustering
│   │       ├── ai_clusterer.py
│   │       └── rule_based.py
│   │
│   ├── analytics/                     # Analysis engines
│   │   ├── config_analyzer.py
│   │   ├── creative_analyzer.py
│   │   ├── fraud_analyzer.py
│   │   ├── geo_analyzer.py
│   │   ├── geo_waste_analyzer.py
│   │   ├── mock_traffic.py
│   │   ├── pretargeting_recommender.py
│   │   ├── recommendation_engine.py
│   │   ├── rtb_funnel_analyzer.py
│   │   ├── size_analyzer.py
│   │   ├── size_coverage_analyzer.py
│   │   ├── waste_analyzer.py
│   │   └── waste_models.py
│   │
│   ├── analysis/                      # Evaluation
│   │   └── evaluation_engine.py
│   │
│   ├── collectors/                    # Data collectors (Google RTB API)
│   │   ├── base.py
│   │   ├── csv_reports.py
│   │   ├── seats.py
│   │   ├── creatives/
│   │   │   ├── client.py
│   │   │   ├── parsers.py
│   │   │   └── schemas.py
│   │   ├── endpoints/
│   │   │   ├── client.py
│   │   │   └── schemas.py
│   │   ├── pretargeting/
│   │   │   ├── client.py
│   │   │   ├── parsers.py
│   │   │   └── schemas.py
│   │   └── troubleshooting/
│   │       └── client.py
│   │
│   ├── cli/                           # CLI tools
│   │   └── qps_analyzer.py            # (1053 lines)
│   │
│   ├── config/                        # Configuration
│   │   └── config_manager.py
│   │
│   ├── migrations/                    # SQLite migrations
│   │   ├── runner.py
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_import_tracking.sql
│   │   ├── 003_analytics_tables.sql
│   │   ├── 004_pretargeting_config.sql
│   │   ├── 005_billing_id_tracking.sql
│   │   ├── 006_pretargeting_snapshots.sql
│   │   ├── 007_multi_account_tracking.sql
│   │   └── 007_pretargeting_pending_changes.sql
│   │
│   ├── qps/                           # QPS optimization
│   │   ├── account_mapper.py
│   │   ├── config_tracker.py
│   │   ├── constants.py
│   │   ├── fraud_detector.py
│   │   ├── importer.py
│   │   ├── models.py
│   │   └── size_analyzer.py
│   │
│   ├── scripts/                       # Utility scripts
│   │   ├── fix_campaign_names.py
│   │   ├── generate_qps_report.py
│   │   ├── gmail_import.py
│   │   ├── migrate_multi_account.py
│   │   ├── migrate_schema_v12.py
│   │   ├── reset_database.py
│   │   └── test_api_access.py
│   │
│   ├── services/                      # Business logic
│   │   ├── campaign_aggregation.py
│   │   └── waste_analyzer.py
│   │
│   ├── storage/                       # Data persistence
│   │   ├── adapters.py
│   │   ├── campaign_repository.py
│   │   ├── models.py
│   │   ├── performance_repository.py
│   │   ├── retention_manager.py
│   │   ├── s3_writer.py
│   │   ├── schema.py
│   │   ├── seat_repository.py
│   │   ├── sqlite_store.py            # Legacy - to be removed (1373 lines)
│   │   ├── sqlite_store_new.py        # Refactored facade (1373 lines)
│   │   ├── migrations/
│   │   │   ├── 008_add_performance_metrics.py
│   │   │   └── 009_normalize_lookups.py
│   │   └── repositories/
│   │       ├── base.py
│   │       ├── account_repository.py
│   │       ├── creative_repository.py
│   │       ├── thumbnail_repository.py
│   │       └── traffic_repository.py
│   │
│   ├── tests/                         # Tests
│   │   ├── query_performance.py
│   │   ├── test_multi_seat.py
│   │   └── test_waste_analysis.py
│   │
│   ├── utils/                         # Utilities
│   │   ├── html_thumbnail.py
│   │   └── size_normalization.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── start.sh
│   └── venv/                          # Python virtual environment
│
├── dashboard/                         # Next.js frontend
│   ├── src/
│   │   ├── app/                       # Pages (App Router)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Home/Dashboard
│   │   │   ├── providers.tsx
│   │   │   ├── campaigns/
│   │   │   │   ├── page.tsx           # Campaign list (1088 lines)
│   │   │   │   └── [id]/page.tsx      # Campaign detail
│   │   │   ├── connect/page.tsx       # Google OAuth
│   │   │   ├── creatives/page.tsx     # Creative gallery
│   │   │   ├── import/page.tsx        # CSV import
│   │   │   ├── settings/
│   │   │   │   ├── page.tsx           # Settings
│   │   │   │   ├── retention/page.tsx
│   │   │   │   └── seats/page.tsx
│   │   │   ├── setup/page.tsx         # Initial setup wizard (1352 lines)
│   │   │   ├── uploads/page.tsx       # Upload history
│   │   │   └── waste-analysis/page.tsx # QPS Waste Optimizer (1106 lines)
│   │   │
│   │   ├── components/                # React components
│   │   │   ├── sidebar.tsx
│   │   │   ├── loading.tsx
│   │   │   ├── error.tsx
│   │   │   ├── campaign-card.tsx
│   │   │   ├── creative-card.tsx
│   │   │   ├── format-chart.tsx
│   │   │   ├── first-run-check.tsx
│   │   │   ├── import-dropzone.tsx
│   │   │   ├── import-preview.tsx
│   │   │   ├── import-progress.tsx
│   │   │   ├── preview-modal.tsx
│   │   │   ├── size-coverage-chart.tsx
│   │   │   ├── stats-card.tsx
│   │   │   ├── validation-errors.tsx
│   │   │   ├── waste-report.tsx
│   │   │   ├── campaigns/             # Campaign-specific
│   │   │   │   ├── cluster-card.tsx
│   │   │   │   ├── draggable-creative.tsx
│   │   │   │   ├── list-cluster.tsx
│   │   │   │   ├── list-item.tsx
│   │   │   │   └── unassigned-pool.tsx
│   │   │   ├── qps/                   # QPS components
│   │   │   │   ├── index.ts
│   │   │   │   ├── geo-waste-panel.tsx
│   │   │   │   ├── pretargeting-panel.tsx
│   │   │   │   └── qps-summary-card.tsx
│   │   │   ├── recommendations/       # Recommendation cards
│   │   │   │   ├── recommendation-card.tsx
│   │   │   │   └── recommendations-panel.tsx
│   │   │   └── rtb/                   # RTB/Pretargeting
│   │   │       ├── account-endpoints-header.tsx
│   │   │       ├── config-breakdown-panel.tsx
│   │   │       ├── config-performance.tsx
│   │   │       ├── pretargeting-config-card.tsx
│   │   │       ├── pretargeting-settings-editor.tsx
│   │   │       └── snapshot-comparison-panel.tsx
│   │   │
│   │   ├── contexts/                  # React contexts
│   │   │   └── account-context.tsx
│   │   │
│   │   ├── lib/                       # Utilities
│   │   │   ├── api.ts                 # API client (1382 lines)
│   │   │   ├── chunked-uploader.ts
│   │   │   ├── csv-parser.ts
│   │   │   ├── csv-validator.ts
│   │   │   ├── seat-extractor.ts
│   │   │   ├── url-utils.ts
│   │   │   ├── utils.ts
│   │   │   └── types/
│   │   │       └── import.ts
│   │   │
│   │   └── types/                     # TypeScript types
│   │       └── api.ts
│   │
│   ├── public/                        # Static assets
│   │   └── cat-scanning-stats.webp
│   │
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── package-lock.json
│
├── data/                              # Data storage
│   └── csv-reports/                   # Uploaded CSV files
│       └── README.md
│
├── docs/                              # Documentation
│   ├── HANDOVER.md                    # Current handover doc
│   ├── SETUP_GUIDE.md
│   ├── CatScan_Handover_v11.md
│   ├── CAT_SCAN_README.md
│   ├── RTB_FRAUD_SIGNALS_REFERENCE.md
│   ├── Phase26_Upload_Tracking_Features.md
│   └── phases/                        # Historical phase docs
│       └── ...
│
├── infra/                             # Infrastructure
│   └── infra/cloudformation/
│       ├── main.yaml
│       ├── cat-scan-stack.yaml
│       ├── README.md
│       └── modules/
│           ├── compute.yaml
│           ├── network.yaml
│           ├── scheduling.yaml
│           └── storage.yaml
│
├── .claude/                           # Claude Code settings
│   └── settings.local.json
│
├── docker-compose.yml                 # Full stack orchestration
├── run.sh                             # Dev startup script
├── setup.sh                           # Initial setup
├── README.md
├── INSTALL.md
├── CHANGELOG.md
├── Edgar RTB System.md
└── tree.md                            # This file
```

## Key Entry Points

| Component | Command | URL |
|-----------|---------|-----|
| Backend API | `cd creative-intelligence && source venv/bin/activate && python -m uvicorn api.main:app --reload --port 8000` | http://localhost:8000 |
| Frontend | `cd dashboard && npm run dev` | http://localhost:3000 |
| API Docs | (auto-generated) | http://localhost:8000/docs |

## Database

SQLite database: `creative-intelligence/rtbcat.db`

Migrations are in `creative-intelligence/migrations/` and run automatically on startup.

## File Counts

- Python files: ~75
- TypeScript/TSX files: ~50
- SQL migrations: 9
- Rust files: 3

*Last updated: 2025-12-10*
