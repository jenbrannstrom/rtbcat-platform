# Cat-Scan Roadmap

**Last Updated:** January 2026

---

## Known Bugs

- [ ] **Campaigns tab filtering** - Creative ID type mismatch causing empty campaigns view
- [ ] **Thumbnail placeholders** - Some creatives show placeholder instead of generated thumbnail (ffmpeg)
- [ ] **FFmpeg missing on install** - Creatives tab fails to render video thumbnails until ffmpeg installed
- [ ] **CSV import account mismatch** - Imports not linking to correct accounts
- [ ] **Login loop / empty analytics** - Missing `POSTGRES_SERVING_DSN` breaks analytics; enforce Postgres-only and set DSN
- [ ] **Size drill-down shows no creatives** - fix is in config_precompute (creative_size) but needs deploy + config precompute refresh
- [x] **Import Now button fails** - /import does not process queued Gmail reports
- [x] **Campaigns create action no-op** - Clicking "Create" on auto cluster does nothing
- [ ] **Creative modal missing publisher data** - "No publisher data for this config" despite migrated tables
- [x] **Duplicate migration numbers** - resolved
- [ ] ~~**CI/CD pipeline** - Build images in GitHub Actions and deploy via docker pull (Artifact Registry)~~ **(Done)**
- [ ] **BigQuery raw_facts coverage** - Data only through Jan 25; Jan 26–28 pending reprocess after pipeline fix

---

## Refactor Tracking — Services/Repositories Split (Postgres-only)

Goal: unmix business logic from data access. Routers call services; services call repos; repos hold SQL only. PostgresStore becomes a thin shim and then is removed.

| Domain | Repo | Service | Router | Owner | Status | Notes |
|--------|------|---------|--------|-------|--------|-------|
| Endpoints | ☐ | ☐ | ☑ | Codex | Router done | Uses SeatsService for SA lookups |
| Snapshots | ☐ | ☑ | ☐ | Codex | Service exists | SnapshotsService in services/ |
| Changes | ☐ | ☑ | ☐ | Codex | Service exists | ChangesService in services/ |
| Pretargeting | ☐ | ☑ | ☐ | Codex | Service exists | PretargetingService in services/ |
| Actions | ☐ | ☑ | ☑ | Claude | Done | ActionsService uses SeatsService |
| Seats Sync | ☑ | ☑ | ☑ | Claude | Done | seats_repo.py + SeatsService |
| Uploads | ☑ | ☑ | ☑ | Claude | Done | uploads_repo.py + UploadsService |
| Retention | ☑ | ☑ | ☑ | Claude | Done | retention_repo.py + RetentionService |
| System/Thumbnails | ☑ | ☑ | ☑ | Claude | Done | thumbnails_repo.py + ThumbnailsService |
| Analytics/Performance | ☐ | ☐ | ☑ | Claude | Router done | Uses db_query() directly |
| Creatives | ☐ | ☐ | ☑ | Claude | Router done | Uses db_query() directly |
| Campaigns | ☐ | ☑ | ☑ | Codex | Done | campaign_repository.py migrated |

Legend: ☐ = not started, ☑ = done, ◐ = in progress.

**Runtime Postgres migration complete** (2026-01-31). SQLite legacy has been removed from runtime paths.

---

## Features 

### Core Improvements
- [ ] **MCP Integration** - Connect AI tools via Model Context Protocol
- [ ] **Navigation restructure** - Cleaner sidebar organization with unified Settings
- [x] **Creative geo display (MVP)** - Serving countries + language mismatch alerts in UI
- [ ] **Creative language detection (AI)** - Automated OCR/Gemini language detection pipeline

  **Requirements:**
  - Gemini API detects language on first creative sync (one-time analysis)
  - "Rescan, incorrect" button for manual re-analysis
  - Language field is human-editable
  - Mismatch alert when language doesn't match serving countries
  - Show serving countries (from CSV imports) in creative modal under TARGETING/GEO
  - Surface MCP-based OCR/image understanding to flag currency/language mismatches
  - API key via `GEMINI_API_KEY` environment variable

  **Implementation:**

  1. **Database Schema** (`migrations/015_language_detection.sql`)
     - `detected_language` (TEXT) - "German", "English", etc.
     - `detected_language_code` (TEXT) - ISO 639-1: "de", "en"
     - `language_confidence` (REAL) - 0.0 to 1.0
     - `language_source` (TEXT) - "gemini" or "manual"
     - `language_analyzed_at` (TIMESTAMP)
     - `language_analysis_error` (TEXT)

  2. **Creative Model** (`storage/models.py`)
     - Add new fields to `Creative` dataclass matching the migration

  3. **Language Analyzer** (`api/analysis/language_analyzer.py` - new)
     - `GeminiLanguageAnalyzer` class following `ai_clusterer.py` pattern
     - Lazy-loaded Gemini client with `GEMINI_API_KEY` env var
     - `extract_text_from_creative()` - gets text from HTML/VAST/native
     - `detect_language()` - calls Gemini, returns structured result
     - Graceful fallback when API not configured

  4. **Language-Country Mapping** (`utils/language_country_map.py` - new)
     - Map ISO 639-1 language codes to country codes where language is official
     - `check_language_country_match()` function for mismatch detection
     - Example: "de" (German) -> ["DE", "AT", "CH"]

  5. **Repository Updates** (`storage/repositories/creative_repository.py`)
     - `update_language_detection()` - save detection results
     - `get_creatives_needing_language_analysis()` - find unanalyzed creatives

  6. **API Endpoints** (`api/routers/creatives.py`)
     - `POST /creatives/{id}/analyze-language?force=false` - trigger analysis
     - `PUT /creatives/{id}/language` - manual update
     - `GET /creatives/{id}/geo-mismatch` - check mismatch status
     - New models: `LanguageDetectionResponse`, `GeoMismatchAlert`
     - Update `CreativeResponse` to include language fields

  7. **Sync Integration** (`api/routers/seats.py`)
     - Call language analysis for new creatives after sync
     - Only analyze creatives that haven't been analyzed yet
     - Non-blocking (async background processing)

  8. **Frontend Changes**
     - Types (`dashboard/src/types/api.ts`): Add `LanguageDetectionResponse`, `GeoMismatchAlert`
     - API Client (`dashboard/src/lib/api.ts`): `analyzeCreativeLanguage()`, `updateCreativeLanguage()`, `getCreativeGeoMismatch()`
     - Preview Modal (`dashboard/src/components/preview-modal.tsx`): Add `LanguageSection` component
      - Detected language with confidence
      - Mismatch alert (amber warning) if language doesn't match serving countries
      - "Rescan, incorrect" button
      - Inline edit form for manual correction
    - Add `TARGETING/GEO` section to creative modal with served countries
    - Add alert badges on creative cards for geo/lang mismatch

  9. **Dependencies** (`requirements.txt`)
     - Add: `google-generativeai>=0.3.0`

  **Critical Files:**
  | File | Change |
  |------|--------|
  | `migrations/015_language_detection.sql` | New migration |
  | `storage/models.py` | Add 6 new fields to Creative |
  | `api/analysis/language_analyzer.py` | New Gemini analyzer module |
  | `utils/language_country_map.py` | New language-country mapping |
  | `storage/repositories/creative_repository.py` | Add update methods |
  | `api/routers/creatives.py` | 3 new endpoints, update response |
  | `api/routers/seats.py` | Add language analysis to sync |
  | `dashboard/src/types/api.ts` | Add new interfaces |
  | `dashboard/src/lib/api.ts` | Add 3 API functions |
  | `dashboard/src/components/preview-modal.tsx` | Add LanguageSection |
  | `requirements.txt` | Add google-generativeai |

  **Verification:**
  1. Set `GEMINI_API_KEY` env var, run migration, test endpoint
  2. Open creative modal, verify language section and mismatch alerts
  3. Sync creatives, verify auto-analysis populates `language_analyzed_at`

### Pretargeting Management
- [x] **Pretargeting Write API** - Push config changes to Google (patch, activate, suspend)
- [x] **Rollback functionality** - Undo changes and restore previous snapshots
- [x] **Change history tracking** - Full audit trail of all pretargeting modifications
- [x] **Publisher allow/deny editor** - In-app whitelist/blacklist editing with per-config history and rollback
- [x] **Bulk edit UX** - Inline add/remove rows with validation and diff preview before save
- [x] **Publisher List UI layout** - Full-page editor + spec-aligned layout (pending deploy)

  **Publisher Targeting UX (per pretargeting config):**
  - Add a `Publishers` section under each config with mode toggle:
    - Whitelist (only these)
    - Blacklist (block these)
  - Mode is mutually exclusive; UI and actions adapt:
    - If Whitelist: show `Add` actions
    - If Blacklist: show `Block` actions
  - Inline add/remove with search and manual entry
  - Bulk Import + Export CSV actions
  - Pending changes panel with per-item undo and Apply/Discard
  - Apply changes triggers Google API update (batch)

  **Publisher Table Integration:**
  - Add column: `Add` or `Block` (depends on current mode)
  - Staged changes show yellow `pending` indicator
  - Apply changes pushes to Google and writes audit log

  **History + Rollback:**
  - Per-config history with timestamp + user
  - Each entry: summary + list of changes (added/removed/mode change)
  - Rollback action restores the list + mode to that snapshot
  - Rollback confirmation modal shows diff impact and warns about newer changes

### Creatives Tab UX
- [x] **Approval filter** - Approved count vs not approved count (red)
- [x] **Display subtype filter** - "Display image" and "Display HTML" split
- [x] **Card data** - Show GEO target, language, mismatch alert on card
- [x] **Display thumbnails** - Image thumbnails for display creatives on list view
- [x] **HTML copy** - Add "HTML" button to copy creative code
- [x] **Card layout density** - Reduce empty whitespace, improve compact layout
- [x] **Modal destination truncation** - Shorten long URLs with copy-to-clipboard
- [x] **Performance data sourcing** - Resolve "No performance data available" in modal

### Import Page
- [x] **Import Now reliability** - Fix Gmail import trigger and queue processing
- [x] **Remove redundant section** - Drop "5 Reports to Schedule in Authorized Buyers"

### Creative Clusters (Campaigns)
- [ ] **Rename Campaigns → Creative Clusters** (UI + routes)
- [x] **Cluster create action** - "Create" in auto cluster should persist
- [x] **Thumbnail modal** - Clicking cluster thumbnail opens creative modal

### Cosmetic Cleanup
- [ ] Remove "Go To WASTE optimizer" link from `/settings/accounts`

---

## Home Page Finalization (Seat-Scoped)

**Goal:** Home page shows only data for the selected seat (buyer_id). Admins can switch seats; users only see assigned seats.

### Phase 0 — Audit & Baseline
- [ ] **Data source audit** - For each Home section, list data tables used and % of rows missing `bidder_id`/`billing_id`
- [ ] **Seat scope verification** - Confirm all Home endpoints enforce `buyer_id` and user permissions

### Phase 1 — Import & Data Model Fixes
- [x] **Postgres schema alignment** - Raw fact tables + BIGINT upgrades + pretargeting_publishers table
- [x] **Backfill raw fact tables** - Load `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality` into Postgres (through 2026-01-25)
- [ ] **Persist seat identity** - Ensure `bidder_id` stored for all imports (`rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`)
- [ ] **Billing ID guarantees** - Enforce `billing_id` for per-config reports; exclude rows missing it from config breakdowns
- [ ] **Join-safe keys** - Geo/publisher joins must include seat identity (`bidder_id` or `buyer_account_id`)

### Phase 2 — Precompute & Caching
- [ ] **Materialized aggregates** - Precompute seat-wide and billing_id-level metrics (size/geo/publisher/config)
- [ ] **Refresh strategy** - Recompute on import + nightly full refresh

### Phase 3 — API Refactor
- [ ] **Seat-scoped endpoints** - `/analytics/home/*` endpoints that return precomputed data for a buyer_id
- [ ] **Correctness flags** - API returns data_source + missing-data warnings for UI banners

### Phase 4 — UI Refactor & Features
- [ ] **Pretargeting configs** - “No data” state when performance missing; seat-only list (10 active)
- [ ] **By Size** - Billing ID scoped; add size drill-down to list creatives + modal icon per creative (backend fix staged; deploy + refresh pending)
- [ ] **By Geo / By Publisher** - Re-enable once join-safe keys are available; seat-only
- [ ] **By Creative** - Confirm billing_id scoping; add creative modal icon; move country targeting near top
- [ ] **Publisher Performance** - Title “overall for {seat}”; fix blank publisher name fallback
- [ ] **Size Analysis** - Seat-wide only; two-column layout with “No Creatives” and wasted QPS
- [ ] **Geographic Performance** - Title “overall for {seat}”; sortable columns; fix totals + bids/reached mismatch; replace blocks with table icons (trophy/!)

### Phase 5 — Validation
- [ ] **Data correctness checks** - Assert `bids <= reached` where applicable; warn on inconsistent source data
- [ ] **Performance checks** - Home page loads in sections with independent loading states

---

## Features - Optimization Engine

- [ ] **QPS Adjudication Engine** - Auto-calculate optimal pretargeting based on performance data:

  the most crucial part of the app: QPS optimisation. So far we just built the framework.

  QPS optim is two parts:
  1. having the right data to hand to evaluate what is needed (we are 60% there with the current UI, there are some very confusing elements in the ui and missing data)
  2. the logic to figure out the best pretargeting config to apply. 

  Operationally we also need to WRITE the findings to the AB seat. AND crucially record those changes so we can roll them back in case it goes wrong.

  

  How do we use game theory to determine the best optimisation to the QPS problem?
  The factors are:
  1. the settings inside a pretargeting setting
  2. there are 10 pretargeting settings available
  3. the creatives uploaded to the AB seat contain targeting or the CSV's show what the bidder and media buyer is trying to do. A creative will always have at least one country targeting. 


  /home/jen/Documents/rtbcat-platform/DATA_SCIENCE_EVALUATION.md was an attempt at compiling what we have available. 

  We need to consult /home/jen/Documents/rtbcat-platform/DATA_SCIENCE_EVALUATION.md to see if we are actually using all data available to use to make those decisions. 
- [ ] **Creative change monitoring** - Detect new creatives and trigger optimization workflows
- [ ] **AI/MCP optimization** - Let AI agents analyze and optimize via MCP tools
- [ ] **Learning from outcomes** - Track before/after results to improve recommendation confidence



---

## Integrations

- [ ] **Robyn MMM integration** - Marketing mix modeling data export and visualization
- [ ] **Clerk auth for Terraform** - Secure credential handling during deployment

---

## Technical Debt

### Naming Standardization (Pre-OSS)
- [ ] **Rename `rtbcat` → `catscan` in Docker** - Container user is `rtbcat`, VM user is `catscan`. Causes confusion when debugging paths (see `docs/GCP_CREDENTIALS_SETUP.md` for current paths).

### Large File Refactoring
- [ ] `dashboard/src/lib/api.ts` - Still has ~30 legacy functions to extract
- [x] **Postgres-only migration** - Replace SQLiteStore with PostgresStore + repositories; SQLite legacy removed
- [ ] `storage/repositories/user_repository.py` (1,188 lines) - Split into auth, permissions, audit repos
- [ ] `api/routers/creatives.py` (1,181 lines) - Extract language detection, preview generation
- [ ] `cli/qps_analyzer.py` (1,053 lines) - Split into separate command modules under `cli/commands/`

### Security
- [ ] XSS via `dangerouslySetInnerHTML` in preview-modal - Sanitize HTML, use sandboxed iframe
- [ ] API keys logged in plaintext - Mask sensitive data in logs

### Code Quality
- [ ] Overly broad exception handling (`except Exception`) - Use specific exceptions
- [ ] Missing type annotations in several Python files
- [ ] Code duplication in frontend API response handling
- [ ] Inconsistent patterns (mix of sync/async, different logging approaches)
- [ ] **Schema gate for refactors** - Verify migrations before adding columns or ON CONFLICT targets

### Architecture
- [ ] Business logic mixed into route handlers - Extract to service layer
- [ ] Environment variables read directly throughout - Centralize config
- [ ] No structured logging or request ID tracking

### Testing
- [ ] Current coverage: <5%, target: 70%+ for critical paths
- [ ] Missing: API endpoint tests, repository tests, frontend component tests, E2E tests

---

## Completed

- [x] Multi-bidder account support with account switching
- [x] Creative sync from Google Authorized Buyers API
- [x] CSV import (CLI and UI)
- [x] Gmail auto-import
- [x] RTB bidstream visualization (renamed from rtb_funnel)
- [x] Efficiency analysis with recommendations
- [ ] Campaign clustering (faulty)
- [ ] Video thumbnail generation (failing on the new SG VM)
- [x] GCP deployment with OAuth2 authentication
- [x] **UTC timezone standardization** - All CSV reports now require UTC timezone
- [x] **Data quality flagging** - Legacy (pre-UTC) vs production data separation
- [x] **Per-billing_id funnel metrics** - JOIN strategy to reconstruct bid metrics by billing_id
- [x] **Database schema v17** - rtb_funnel → rtb_bidstream rename, data_quality column added
- [x] **CI/CD pipeline** - Build images in GitHub Actions and deploy via docker pull (Artifact Registry)
