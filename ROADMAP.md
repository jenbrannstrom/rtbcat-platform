# Cat-Scan Roadmap

**Last Updated:** February 24, 2026

---

## Incident RCA (2026-02-22)

- [x] **Migration crash-loop recurrence**
  - Root cause: two API workers attempted schema DDL migrations at startup simultaneously, causing Postgres deadlocks and restart loops.
  - Permanent fix: advisory lock in migration runner (`scripts/postgres_migrate.py`) deployed in `a4c5c02`.
  - Guardrail: keep worker count >1 safe without race conditions on any future migration.
- [x] **Creatives page timeout / blank state (30s request timeout)**
  - Root cause: creatives list path requested large payloads (`raw_data`) and always executed expensive list-context queries for every item.
  - Fixes:
    - `storage/postgres_store.py`: support list query without `raw_data` for slim responses.
    - `api/routers/creatives.py`: fast path for `slim=true` (thumbnail context only).
    - `services/creative_preview_service.py`: thumbnail-only fallback previews when raw payload is omitted.
    - `dashboard/src/app/creatives/page.tsx`: initial fetch limit reduced (`1000 -> 300`).
- [x] **Gmail unread backlog visibility gap**
  - Root cause: status API did not expose unread report count from the last scan, so "import is behind" vs "no mail found" was opaque.
  - Fixes:
    - Persist unread count in status/history (`scripts/gmail_import.py`).
    - Expose in API (`api/routers/gmail.py`).
    - Display in UI (`dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx`).
- [x] **Import tracking coverage matrix requirement**
  - Status: implemented and live (`082ce0b`, `75b6a54`).
  - `/import` now shows account x CSV type with `pass/fail/not imported` and source (`gmail-auto`, `gmail-manual`, `manual`).

## Deploy / Contracts Follow-up (2026-02-24)

- [x] **GitHub deploy workflow defaults corrected for SG production**
  - Fixed `deploy.yml` defaults to match current production target (`catscan-production-sg`, `asia-southeast1-b`, SG Artifact Registry).
  - Related commits on `unified-platform`: `a61c998`, `5546ac5`.
- [x] **Deploy unblocked with temporary contract-gate bypass**
  - `scripts/contracts_check.py` fixed missing `::text` casts on `metric_date` comparisons (`5546ac5`) to resolve `date >= text` SQL errors.
  - Deployment proceeded with `ALLOW_CONTRACT_FAILURE=true` due pre-existing `C-EPT-001` failure (stale endpoints), unrelated to seat-access changes.
- [ ] **Remove `ALLOW_CONTRACT_FAILURE` bypass after C-EPT-001 RCA**
  - Investigate and fix stale endpoint freshness contract (`C-EPT-001: 11/11 stale endpoints`).
  - Re-enable strict contract gate in deploy path and verify clean deploy without bypass.

---

## Translation / i18n Audit (2026-02-23)

- [x] **Phase 1: audit hardcoded UI strings (dashboard frontend)**
  - Scope: `dashboard/src` only (frontend app/components/contexts/lib code that participates in dashboard i18n).
  - Result: AST-based inventory completed.
  - Findings summary:
    - `141` frontend files scanned
    - `83` files with hardcoded-string hits
    - `1459` hardcoded string inventory items
    - `103` app/components `.tsx` files, only `19` currently use `useTranslation()` (~18.4%)
    - Non-English locales are currently aliases to English in `dashboard/src/lib/i18n/index.ts`
  - Audit report: `docs/I18N_PHASE1_TRANSLATION_AUDIT_2026-02-23.md`
  - Full inventory CSV: `docs/I18N_PHASE1_HARDCODED_STRING_INVENTORY_2026-02-23.csv`
- [x] **Phase 2: convert hardcoded strings to dynamic `t.*` lookups** *(visible UI copy complete; intentional technical literals remain)*
  - Start with highest-impact hotspots from the Phase 1 report (login/auth, app shell/status/errors, import flows, RTB config panels, settings tabs).
  - Progress (2026-02-24):
    - [x] Login/auth page primary UI strings + error messages converted (`dashboard/src/app/login/page.tsx`)
    - [x] Home dashboard seat/status/error banners + pretargeting fallback messages converted (`dashboard/src/app/page.tsx`)
    - [x] Import page runtime UI/errors + import reference/troubleshooting wrapper copy converted (`dashboard/src/app/import/page.tsx`, `dashboard/src/components/import/RequiredColumnsTable.tsx`, `dashboard/src/components/import/TroubleshootingSection.tsx`)
    - [x] `ExportInstructions` import guide fully converted (prose/headings + report IDs/target tables + dimensions/metrics lists) (`dashboard/src/components/import/ExportInstructions.tsx`)
    - [x] RTB app drill-down modal UI strings/tooltips/empty states converted (`dashboard/src/components/rtb/app-drilldown-modal.tsx`)
    - [x] RTB config breakdown panel top-level UI + publisher controls copy converted (tabs/loading/error/empty states/window badges/filter/history header) (`dashboard/src/components/rtb/config-breakdown-panel.tsx`)
    - [x] RTB config breakdown panel row/editor controls copy converted (history entries, size/geo controls, table headers, row actions/statuses, suggestions, pending bar) (`dashboard/src/components/rtb/config-breakdown-panel.tsx`)
    - [x] RTB config breakdown panel confirm/undo/preview modals + pending-change descriptions/tooltips converted (`dashboard/src/components/rtb/config-breakdown-panel.tsx`)
    - [x] Admin Users page visible UI copy (placeholders, seat metadata labels, role badges, fallback errors) converted (`dashboard/src/app/admin/users/page.tsx`)
    - [x] Admin Audit Log action labels/date formatting + Admin Settings redirect copy + Admin Configuration session-duration literal converted (`dashboard/src/app/admin/audit-log/page.tsx`, `dashboard/src/app/admin/settings/page.tsx`, `dashboard/src/app/admin/configuration/page.tsx`)
    - [x] Retention settings page UI copy + local success/error/job status messages converted (`dashboard/src/app/settings/retention/page.tsx`)
    - [x] Settings Accounts top-level wrapper/status bar copy + Settings System DB-path fallback converted (`dashboard/src/app/settings/accounts/page.tsx`, `dashboard/src/app/settings/system/page.tsx`)
    - [x] `ApiConnectionTab` runtime messages + setup/instruction/account/seat section copy + seat-row status labels/tooltips converted (`dashboard/src/app/settings/accounts/components/ApiConnectionTab.tsx`)
    - [x] `ApiConnectionTab` remaining Google product/role labels moved to `t.setup.*` keys (`dashboard/src/app/settings/accounts/components/ApiConnectionTab.tsx`)
    - [x] `SystemTab` (under `/settings/accounts/components`) main status/database/thumbnail controls copy converted (`dashboard/src/app/settings/accounts/components/SystemTab.tsx`)
    - [x] `GeminiApiKeySection` UI copy + local validation/fallback error messages converted (`dashboard/src/app/settings/accounts/components/GeminiApiKeySection.tsx`)
    - [x] `GmailReportsTab` top-level/status/import runtime/disconnected-state copy + import-phase labels converted (partial; remaining deep copy pending) (`dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx`)
    - [x] Admin dashboard role display + system pages `MB` unit literals converted (`dashboard/src/app/admin/page.tsx`, `dashboard/src/app/settings/system/page.tsx`, `dashboard/src/app/settings/accounts/components/SystemTab.tsx`)
    - [x] Sidebar remaining brand/seat-error/retry strings converted (`dashboard/src/components/sidebar.tsx`)
    - [x] `PreviewModal` header/source/HTML/performance/detail/URL-tracking UI copy converted (partial; additional preview subcomponents still pending) (`dashboard/src/components/preview-modal/PreviewModal.tsx`)
    - [x] `PreviewModal` approval status badge enum labels localized (`dashboard/src/components/preview-modal/PreviewModal.tsx`)
    - [x] URL label/tooltip strings moved out of `url-utils` hardcoded defaults via translated localizer wiring in `PreviewModal` (`dashboard/src/lib/url-utils.ts`, `dashboard/src/components/preview-modal/PreviewModal.tsx`)
    - [x] `PreviewModal` language analysis/editor section copy converted (`dashboard/src/components/preview-modal/LanguageSection.tsx`)
    - [x] `PreviewModal` renderers/shared copy button strings converted (`dashboard/src/components/preview-modal/PreviewRenderers.tsx`, `dashboard/src/components/preview-modal/SharedComponents.tsx`)
    - [x] `PreviewModal` country targeting / geo mismatch section copy converted (`dashboard/src/components/preview-modal/CountrySection.tsx`)
    - [x] Import coverage matrix headings/status/source labels converted (`dashboard/src/components/import/ImportTrackingMatrixSection.tsx`)
    - [x] Import history report-type labels + localized file-size units and freshness grid CSV labels aligned to exact report names (`dashboard/src/components/import/ImportHistorySection.tsx`, `dashboard/src/components/import/DataFreshnessGrid.tsx`)
    - [x] Creative card thumbnail badges/tooltips/copy actions/stale-cache labels converted (`dashboard/src/components/creative-card.tsx`)
    - [x] Pretargeting settings editor shell copy converted (header/tabs/status/history/confirm dialogs; deeper helper sections still pending) (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Waste analyzer RTB funnel card copy + import instructions converted (`dashboard/src/components/waste-analyzer/FunnelCard.tsx`)
    - [x] Waste analyzer publisher performance section copy + empty-state report instructions converted (`dashboard/src/components/waste-analyzer/PublisherPerformanceSection.tsx`)
    - [x] Waste analyzer geographic analysis section copy + sortable table labels converted (`dashboard/src/components/waste-analyzer/GeoAnalysisSection.tsx`)
    - [x] Waste analyzer size analysis section copy + no-creative gap panel converted (`dashboard/src/components/waste-analyzer/SizeAnalysisSection.tsx`)
    - [x] Pretargeting settings editor helper controls copy converted (`ValuePill`, `PendingChangeCard`, `TargetingSection`, pending-change descriptions) (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Pretargeting publisher section shell copy converted (mode/filter/table headers/row actions/pending bar; bulk import modal/history entry copy still pending) (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Pretargeting publisher bulk-import modal + history entry labels converted (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Pretargeting size-blocking reason strings converted (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Pretargeting history/state/snapshot enum labels + locale-aware date formatting converted (`dashboard/src/components/rtb/pretargeting-settings-editor.tsx`)
    - [x] Snapshot comparison panel copy converted (cards, history dialog shell, create/restore flows) (`dashboard/src/components/rtb/snapshot-comparison-panel.tsx`)
    - [x] Pretargeting config card labels/badges/tooltips/inline controls copy converted (`dashboard/src/components/rtb/pretargeting-config-card.tsx`)
    - [x] Endpoint efficiency panel labels/tooltips/badges/funnel copy converted (`dashboard/src/components/rtb/endpoint-efficiency-panel.tsx`)
    - [x] RTB account endpoints header empty/error/sync/table/tooltip copy converted (`dashboard/src/components/rtb/account-endpoints-header.tsx`)
    - [x] Recommended optimizations panel/card/manual-mode/generated recommendation copy converted (`dashboard/src/components/rtb/recommended-optimizations-panel.tsx`)
    - [x] QPS summary card labels/error/action summaries converted (`dashboard/src/components/qps/qps-summary-card.tsx`)
    - [x] QPS pretargeting panel card/details/error/empty-state copy converted (`dashboard/src/components/qps/pretargeting-panel.tsx`)
    - [x] QPS geo waste panel labels/summary/table/action badges converted (`dashboard/src/components/qps/geo-waste-panel.tsx`)
    - [x] Waste report summary cards/empty-state/recommendations summary copy converted (`dashboard/src/components/waste-report.tsx`)
    - [x] Generic recommendations card/panel severity/type/impact/actions/empty-state copy converted (`dashboard/src/components/recommendations/recommendation-card.tsx`, `dashboard/src/components/recommendations/recommendations-panel.tsx`)
    - [x] Import result card success/failure labels/stats/actions copy converted (`dashboard/src/components/import/ImportResultCard.tsx`)
    - [x] Import column mapping/freshness/history widgets copy converted (`dashboard/src/components/import/ColumnMappingCard.tsx`, `dashboard/src/components/import/DataFreshnessGrid.tsx`, `dashboard/src/components/import/ImportHistorySection.tsx`)
    - [x] Import history report-type names now use localized CSV labels and file-size unit strings are placeholder-based for translation (`dashboard/src/components/import/ImportHistorySection.tsx`, `dashboard/src/components/import/DataFreshnessGrid.tsx`)
    - [x] Import dropzone/preview/progress widget copy converted (`dashboard/src/components/import-dropzone.tsx`, `dashboard/src/components/import-preview.tsx`, `dashboard/src/components/import-progress.tsx`)
    - [x] Required columns reference table row/bullet copy converted (`dashboard/src/components/import/RequiredColumnsTable.tsx`)
    - [x] Shared language selector fallback labels/titles converted (`dashboard/src/components/language-selector.tsx`)
    - [x] Shared first-run loading guard + format chart fallback/tooltip labels converted (`dashboard/src/components/first-run-check.tsx`, `dashboard/src/components/format-chart.tsx`)
    - [x] Route redirect wrappers + pretargeting billing route fallback/back-label copy converted (`dashboard/src/app/uploads/page.tsx`, `dashboard/src/app/setup/page.tsx`, `dashboard/src/app/connect/page.tsx`, `dashboard/src/app/bill_id/[billingId]/page.tsx`)
    - [x] AI control mode settings labels/descriptions/hints converted (`dashboard/src/components/rtb/ai-control-settings.tsx`)
    - [x] `GmailReportsTab` residual deep-copy audit completed; remaining literals are command/path examples kept intentionally (`dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx`)
    - [x] RTB config performance panel labels/error/empty-state/table/settings-chip copy converted (`dashboard/src/components/rtb/config-performance.tsx`)
    - [x] Campaign sort/issues filter control labels/tooltips + list-view unclustered label converted (`dashboard/src/components/campaigns/SortFilterControls.tsx`, `dashboard/src/app/campaigns/page.tsx`)
    - [x] History rollback modal residual copy + locale-aware history timestamps/relative time labels converted (`dashboard/src/app/history/page.tsx`)
    - [x] Creatives page fallback load-error message converted (`dashboard/src/app/creatives/page.tsx`)
    - [x] Shared error components + import validation error list copy converted (`dashboard/src/components/error.tsx`, `dashboard/src/components/validation-errors.tsx`)
    - [x] Campaign detail page core UX copy converted (errors/confirms/back navigation/edit form/period selector/empty state + basic metric labels) (`dashboard/src/app/campaigns/[id]/page.tsx`)
    - [x] Campaign detail page status badge labels + daily trend tooltip/date labels converted (`dashboard/src/app/campaigns/[id]/page.tsx`)
    - [x] Campaign card + auto-cluster button labels/tooltips/no-performance copy converted (`dashboard/src/components/campaign-card.tsx`)
    - [x] Campaign list-view cluster components labels/tooltips/empty states converted (`dashboard/src/components/campaigns/list-cluster.tsx`, `dashboard/src/components/campaigns/list-item.tsx`, `dashboard/src/components/campaigns/unassigned-pool.tsx`)
    - [x] Campaign grid-view cluster card + draggable creative tooltip/badge/sort/zoom/stats copy converted (`dashboard/src/components/campaigns/cluster-card.tsx`, `dashboard/src/components/campaigns/draggable-creative.tsx`)
    - [x] Campaign suggestions panel creative-count noun rendering fixed (translation-safe singular/plural noun keys) (`dashboard/src/components/campaigns/SuggestionsPanel.tsx`)
    - [x] Size coverage chart table/empty-state/severity/footer labels converted (`dashboard/src/components/size-coverage-chart.tsx`)
    - [x] Residual scan pass completed: remaining hardcoded UI-adjacent literals are intentional technical code examples/commands/filenames (e.g. `sudo apt install ffmpeg`, `python scripts/gmail_import.py`, sample CSV/report names) and product identifiers shown in `<code>` blocks
- [ ] **Phase 3: generate/author non-English translations**
  - Replace locale aliases (`pl`, `zh`, `ru`, `uk`, `es`, `da`, `fr`, `nl`, `he`, `ar`) with real dictionaries.
  - Progress (2026-02-24):
    - [x] Added partial-locale deep fallback to English (`dashboard/src/lib/i18n/index.ts`) so translations can ship incrementally per language
    - [x] Added initial Dutch (`nl`) dictionary priority slice (shared shell copy + core `pretargeting` UI labels/messages) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `previewModal` (source/cache states, URL labels/tooltips, approval/language/geo mismatch UI, media preview labels) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `campaigns` + `creatives` namespaces (clustering, campaign-detail, creatives page filters/status/errors/drilldown copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `recommendations` (severity/type/action/impact/staging/empty-state card/panel copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `setup` (API/Gmail/System tabs, status cards, onboarding instructions, Gemini/API key UI copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for core `import` flows (upload/preview/import states, freshness, coverage matrix, large-file/export guidance shell copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Added initial Spanish (`es`) dictionary for core shell/auth/navigation/sidebar + dashboard home summary copy (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Updated language picker native names/flags for supported locales (`dashboard/src/lib/i18n/index.ts`, `dashboard/src/components/language-selector.tsx`)
    - [x] Expanded Spanish (`es`) coverage for core `import` flows (upload/preview/result/history/freshness/matrix/export guide) and `setup` tabs (API/Gmail/System primary UI/status copy) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for core `campaigns` and `creatives` namespaces (clusters/campaign detail/creatives page labels, states, errors) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for `recommendations` card/panel severity/type/action/impact/staging/empty-state copy (`dashboard/src/lib/i18n/translations/es.ts`)
    - [ ] Expand Spanish coverage across remaining namespaces (`pretargeting`, preview modal, admin/settings deep tabs, waste-analysis helpers)
    - [ ] Add real dictionaries for remaining locales (`pl`, `zh`, `ru`, `uk`, `da`, `fr`, `nl`, `he`, `ar`)

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

## Schema Status Review (2026-02-14)

**Scope decision (pre-release):** single shared DB remains in scope; introducing a second staging DB is out of scope for now.

### Execution Priority (Locked for current phase)
- [x] **P0: Current reliability issues first (no schema renames yet)**
  - Scheduler/import freshness: fix missing dates and verify imports are landing in the active runtime path.
  - Precompute freshness parity: bring all serving/precompute tables to the same latest date and keep them in sync.
  - Pretargeting sync reliability: resolve "Sync All" failures and validate end-to-end fetch/update path.
  - Routing/URL consistency: finalize buyer-in-URL route model and remove broken/legacy route targets.
  - Data semantics cleanup in UI: clarify block/allow wording and wasted-QPS visibility so actions match user intent.
- [x] **P0 Exit criteria**
  - [x] Last 3 scheduled import runs are successful with non-zero expected ingestion or explicit "no new mail" reason logged.
  - [x] Raw fact latest date and all precompute latest dates differ by at most 1 day.
  - [x] "Sync All" succeeds for active buyer seats without manual intervention.
  - [x] No broken nav routes (`/creatives` redirect/replace behavior settled where required).
  - Verified on 2026-02-15 (UTC): latest raw/serving dates aligned at 2026-02-12, recent import windows completed successfully, and sync-all completed for active seats.

- [ ] **P1: Naming alignment only after P0 passes**
  - Keep physical table names unchanged in first step.
  - Add compatibility views/canonical aliases, then migrate reads/writes.
  - Defer hard table renames until after first-release stabilization window.

### Implemented Schema Changes (in repo)
- [x] `001_init` baseline tables include creative language fields (`detected_language`, `detected_language_code`, `language_confidence`, `language_source`, `language_analyzed_at`, `language_analysis_error`).
- [x] `027_schema_alignment` added raw fact tables (`rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality`), `pretargeting_publishers`, and BIGINT upgrades.
- [x] `030_auth_baseline_tables` added auth baseline tables for first-admin/bootstrap path.
- [x] `034_user_passwords` added password auth schema updates.
- [x] `035_audit_log` added audit log table.
- [x] `036_live_fetch_and_thumbnail_retry` added live creative fetch + thumbnail retry support tables/fields.
- [x] `037_data_reliability_foundation` added `ingestion_runs` and `source_coverage_daily`.
- [x] `038_canonical_fact_reconciliation` added `fact_delivery_daily` and `fact_dimension_gaps_daily`.
- [x] `039_ingestion_runs_extend` extended ingestion/import attribution fields.
- [x] `040_web_domain_lane` added optional `web_domain_daily`.
- [x] `041_bootstrap_tracking` added bootstrap completion setting.
- [x] `042_precompute_refresh_runs` added append-only precompute run ledger (`run_id`, table/domain status, row_count, error, host/version/sha, timing).

### Proposed Schema Changes Still Open
- [ ] Universal serving tables for fixed windows (`7/14/30`) under Phase U1 (`serve_home_*`, `serve_qps_*`, `serve_config_*`), including metadata fields (`as_of_date`, `last_refreshed_at`, `refresh_run_id`, `data_state`) and read indexes.
- [ ] Stronger seat/config integrity guarantees from Home Phase 1 TODOs (persisted seat identity and stricter billing/join-safe keys). Existing columns exist, but strict enforcement is still pending.
- [x] Precompute observability upgrade: append-only run table (per refresh run/table/status/row_count/error/host/version) to diagnose partial refreshes and stale tables quickly.
- [ ] Ingestion lineage extension: persist importer host/version + source message lineage (where available) so scheduler "200 OK but no new data" can be traced deterministically.

### Stale Schema Notes Corrected
- [x] Language-detection schema is already present in Postgres baseline; previous roadmap text referencing `migrations/015_language_detection.sql` was stale for current repo layout.

### Nomenclature Alignment (Google-centric terminology)
- [x] Introduce canonical naming in SQL layer using compatibility views first (no hard table rename in first step).
  - `home_config_daily` → `pretarg_daily`
  - `config_size_daily` → `pretarg_size_daily`
  - `config_geo_daily` → `pretarg_geo_daily`
  - `config_publisher_daily` → `pretarg_publisher_daily`
  - `config_creative_daily` → `pretarg_creative_daily`
  - `home_size_daily` → `seat_size_daily`
  - `home_geo_daily` → `seat_geo_daily`
  - `home_publisher_daily` → `seat_publisher_daily`
  - `home_seat_daily` → `seat_daily`
- [x] Migrate read paths to canonical names after views are in place.
  - [x] Precompute health read path now prefers canonical aliases with legacy fallback.
  - [x] Home analytics, endpoints QPS, data health, RTB config breakdown, and contract checks now query canonical aliases (`seat_*`, `pretarg_*`) while preserving API compatibility keys.
  - [x] Precompute validation + service/repository read SQL now use canonical aliases; legacy table names remain on write paths and compatibility responses.
- [ ] Keep backward-compatible aliases until first release stabilizes, then decide whether physical table renames are worth migration risk.
  - [x] Added canonical↔legacy fallback resolution in precompute-status paths (analytics + RTB service) so mixed migration states remain readable.
- [x] Add terminology map in API/docs/UI labels so "billing_id" is consistently presented as "pretargeting config" where users expect Google UI wording.

---

## Refactor Tracking — Services/Repositories Split (Postgres-only)

Goal: unmix business logic from data access. Routers call services; services call repos; repos hold SQL only. PostgresStore becomes a thin shim and then is removed.

| Domain | Repo | Service | Router | Owner | Status | Notes |
|--------|------|---------|--------|-------|--------|-------|
| Endpoints | ☑ | ☑ | ☑ | Codex | Done | endpoints_repo.py + EndpointsService |
| Snapshots | ☑ | ☑ | ☑ | Codex | Done | snapshots_repo.py + SnapshotsService |
| Changes | ☑ | ☑ | ☑ | Codex | Done | changes_repo.py + ChangesService |
| Pretargeting | ☑ | ☑ | ☑ | Codex | Done | pretargeting_repo.py + PretargetingService |
| Actions | — | ☑ | ☑ | Claude | Done | Orchestrates services; no repo needed |
| Seats Sync | ☑ | ☑ | ☑ | Claude | Done | seats_repo.py + SeatsService |
| Uploads | ☑ | ☑ | ☑ | Claude | Done | uploads_repo.py + UploadsService |
| Retention | ☑ | ☑ | ☑ | Claude | Done | retention_repo.py + RetentionService |
| System/Thumbnails | ☑ | ☑ | ☑ | Claude | Done | thumbnails_repo.py + ThumbnailsService |
| Analytics/Performance | ☑ | ☑ | ☑ | Claude | Done | analytics_repo.py + AnalyticsService |
| Creatives | ☑ | ☑ | ☑ | Claude | Done | creatives_repo.py + CreativesService |
| Campaigns | ☑ | ☑ | ☑ | Codex | Done | campaign_repo.py + CampaignsService |

Legend: ☐ = not started, ☑ = done, ◐ = in progress.

**Runtime Postgres migration complete** (2026-01-31). SQLite legacy has been removed from runtime paths.

---

## Features 

### Core Improvements
- [ ] **MCP Integration** - Connect AI tools via Model Context Protocol
- [ ] **Navigation restructure** - Cleaner sidebar organization with unified Settings
- [x] **Creative geo display (MVP)** - Serving countries + language mismatch alerts in UI
- [x] **Creative language detection (AI)** - Automated OCR/Gemini language detection pipeline (implemented)

  **Requirements:**
  - Gemini API detects language on first creative sync (one-time analysis)
  - "Rescan, incorrect" button for manual re-analysis
  - Language field is human-editable
  - Mismatch alert when language doesn't match serving countries
  - Show serving countries (from CSV imports) in creative modal under TARGETING/GEO
  - Surface MCP-based OCR/image understanding to flag currency/language mismatches
  - API key via `GEMINI_API_KEY` environment variable

  **Implementation:**

  1. **Database Schema** (implemented in `storage/postgres_migrations/001_init.sql`)
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
  | `storage/postgres_migrations/001_init.sql` | Creative language columns |
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
  1. Set `GEMINI_API_KEY` env var and test endpoint behavior (schema columns already present)
  2. Open creative modal, verify language section and mismatch alerts
  3. Sync creatives, verify auto-analysis populates `language_analyzed_at`

### Pretargeting Management
- [x] **Pretargeting Write API** - Push config changes to Google (patch, activate, suspend)
- [x] **Rollback functionality** - Undo changes and restore previous snapshots
- [x] **Change history tracking** - Full audit trail of all pretargeting modifications
- [x] **Publisher allow/deny editor** - In-app whitelist/blacklist editing with per-config history and rollback
- [x] **Bulk edit UX** - Inline add/remove rows with validation and diff preview before save
- [x] **Publisher List UI layout** - Full-page editor + spec-aligned layout (pending deploy)

  **Publisher List UI Spec Parity Tracking** (`docs/ui-publisher-list-management.md`)
  - [x] Core entry point + dedicated full-page editor layout (Spec §§1-2) — implemented, pending deploy verification
  - [x] Blacklist/whitelist table UX + mode-adaptive labels/actions (Spec §§3-5) — implemented, pending deploy verification
  - [x] Inline add/remove staging flow + pending changes panel + apply/discard UX (Spec §§6-11) — implemented, pending deploy verification
  - [x] Bulk list editing/import-export/history/rollback flows (Spec §§12-14) — implemented, pending deploy verification
  - [ ] Empty/error states parity audit against spec examples (Spec §§15-16) — needs explicit UI pass
  - [ ] Keyboard shortcuts + responsive behavior parity audit (Spec §§17-18) — needs explicit UI pass
  - [ ] Acceptance checks run and documented against spec (Spec §19 / Acceptance Checks) — pending post-deploy validation

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

### Feature #001 — Size block/unblock controls (Home breakdown)
- [x] Implement backend endpoints to block/unblock selected sizes from the Home > By Size table
- [x] Wire bulk actions to pretargeting updates (and persist pending changes)
- [x] Ensure audit logging + rollback support

### Phase 0 — Audit & Baseline
- [ ] **Data source audit** - For each Home section, list data tables used and % of rows missing `bidder_id`/`billing_id`
- [ ] **Seat scope verification** - Confirm all Home endpoints enforce `buyer_id` and user permissions

### Phase 1 — Import & Data Model Fixes
- [x] **Postgres schema alignment** - Raw fact tables + BIGINT upgrades + pretargeting_publishers table
- [x] **Backfill raw fact tables** - Load `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality` into Postgres (through 2026-01-25)
- [ ] **Persist seat identity** - Ensure `bidder_id` stored for all imports (`rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`)
- [ ] **Billing ID guarantees** - Enforce `billing_id` for per-config reports; exclude rows missing it from config breakdowns
- [ ] **Join-safe keys** - Geo/publisher joins must include seat identity (`bidder_id` or `buyer_account_id`)
- [ ] **Identifier integrity** - Never substitute `seat_id/buyer_id` for `billing_id`. Billing IDs scope pretargeting configs; seat IDs scope buyer seats. Keep them distinct in queries and APIs.

### Gmail Import & Pipeline (Operational)
- [ ] **Backlog ingestion** - Run `scripts/gmail_import_batch.py` with checkpointing; track progress in `~/.catscan/gmail_batch_checkpoint.json`.
- [ ] **Cloud Scheduler** - Configure `/api/gmail/import/scheduled` with `GMAIL_IMPORT_SECRET`. See `docs/gmail-autodownload-fix-plan.md`.
  - Ensure nginx has a dedicated unauthenticated `location = /api/gmail/import/scheduled` route (secret header still enforced by API).
- [ ] **Token health monitoring** - Alert on `invalid_grant` in logs and on `/gmail/status` when `authorized=false` or `last_error` contains `invalid_grant`. See `docs/gmail-autodownload-fix-plan.md`.
- [ ] **Pipeline env parity** - Ensure `CATSCAN_PIPELINE_ENABLED`, `BIGQUERY_PROJECT_ID`, `BIGQUERY_DATASET`, `RAW_PARQUET_BUCKET`, `CATSCAN_GCS_BUCKET`, and `GOOGLE_APPLICATION_CREDENTIALS` are set on VM2.
- [ ] **Ops runbook** - Link: `docs/POSTGRES_MIGRATION_RUNBOOK.md` §2b and `docs/GCP_CREDENTIALS_SETUP.md` (Gmail OAuth + Scheduler).

### Universal Precompute Program (Fresh-Only, Single-Seat Assumption)

**Principle:** user-facing analytics routes must read prepared data only.  
**Accuracy rule:** do not serve stale snapshots as current. If refresh is pending, return `refreshing` state (not old data).  
**Scope rule:** optimize for one buyer seat per user session; admin diagnostics may remain slower.

#### Phase U0 — Endpoint Inventory + Runtime Query Freeze
- [ ] Inventory all analytics endpoints used by `/`, `/qps/*`, `/settings/*` and classify each as `precomputed_read` or `runtime_aggregate`.
- [ ] Mark all non-admin `runtime_aggregate` routes as migration targets.
- [ ] Add a CI/static guard to block new multi-day fact-table aggregations in non-admin routers.

#### Phase U1 — Canonical Serving Tables
- [ ] Add universal serving tables keyed by `(window_days, buyer_account_id, dimension_key)` for windows `7/14/30`.
- [ ] Table families: `serve_home_*`, `serve_qps_*`, `serve_config_*` at seat/config/publisher/geo/size grains.
- [ ] Include metadata fields in each table: `as_of_date`, `last_refreshed_at`, `refresh_run_id`, `data_state`.
- [ ] Add indexes for read paths: `(window_days, buyer_account_id, <dimension>)`.

#### Phase U2 — Universal Refresh Orchestrator
- [ ] Build one orchestrator job that recomputes all serving tables for `7/14/30` windows.
- [ ] Trigger refresh on: scheduled cadence + post-import completion + manual admin refresh.
- [ ] Make refresh idempotent and atomic per table/window (upsert/swap pattern).
- [ ] Persist run logs and durations per domain/table/window.

#### Phase U3 — API Cutover (Read-Only Serving)
- [ ] Migrate non-admin analytics endpoints to serving-table reads only.
- [ ] Remove runtime `SUM/GROUP BY` over fact/precompute-daily tables from hot paths.
- [ ] Standardize response metadata: `data_state`, `last_refreshed_at`, `window_days`.
- [ ] Keep admin-only deep-check endpoints separate under admin/system routes.

#### Phase U4 — UI Behavior for Fresh-Only Accuracy
- [ ] Replace long loading waits with explicit status states: `refreshing`, `ready`, `unavailable`.
- [ ] Show “calculating now” banners when current window refresh is in progress.
- [ ] Avoid presenting previous-window or stale-window data as if it were current.
- [ ] Ensure core page sections render independently so one slow section does not block all.

#### Phase U5 — Performance/Correctness Gates
- [ ] SLO: non-admin analytics endpoints P95 < 500ms after warmup.
- [ ] Correctness test: serving-table values match truth-query samples within tolerance.
- [ ] Freshness test: requested window must have successful current refresh before `ready` state.
- [ ] Deployment gate: fail release if any non-admin route still uses runtime multi-day aggregation.

#### Phase U6 — Rollout Plan
- [ ] Wave 1: Home page (`/analytics/home/*`) + pretargeting/config performance feeds.
- [ ] Wave 2: QPS pages (`/qps/publisher`, `/qps/geo`, `/qps/size`) and backing APIs.
- [ ] Wave 3: Remaining user-facing analytics and recommendation inputs.
- [ ] Wave 4: remove deprecated runtime paths; keep admin diagnostic endpoints only.

### Home UI Refactor & Features
- [ ] **Pretargeting configs** - “No data” state when performance missing; seat-only list (10 active)
- [ ] **Recommended Optimizations panel (Home)** - Disabled until data correctness and optimization engine are ready
- [ ] **By Size** - Billing ID scoped; add size drill-down to list creatives + modal icon per creative (backend fix staged; deploy + refresh pending)
- [ ] **By Geo / By Publisher** - Re-enable once join-safe keys are available; seat-only
- [ ] **By Creative** - Confirm billing_id scoping; add creative modal icon; move country targeting near top
- [ ] **Publisher Performance** - Title “overall for {seat}”; fix blank publisher name fallback
- [ ] **Size Analysis** - Seat-wide only; two-column layout with “No Creatives” and wasted QPS
- [ ] **Geographic Performance** - Title “overall for {seat}”; sortable columns; fix totals + bids/reached mismatch; replace blocks with table icons (trophy/!)

### Home Validation
- [ ] **Data correctness checks** - Assert `bids <= reached` where applicable; warn on inconsistent source data
- [ ] **Performance checks** - Home page loads in sections with independent loading states
- [ ] **Deploy verification** - Follow `docs/DEPLOY_CHECKLIST.md` after UI + precompute deploys

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

### Secrets Rollout Follow-up
- [ ] Enable `SECRETS_HEALTH_STRICT=true` in production after all required feature secrets are present in the selected backend
- [ ] Add deployment health probe for `GET /api/system/secrets-health` (status-only, non-sensitive)
- [ ] Wire `CATSCAN_ENABLE_*` feature toggles explicitly in deploy templates so secret checks are deterministic

### Naming Standardization (Pre-OSS)
- [ ] **Rename `rtbcat` → `catscan` in Docker** - Container user is `rtbcat`, VM user is `catscan`. Causes confusion when debugging paths (see `docs/GCP_CREDENTIALS_SETUP.md` for current paths).

### Large File Refactoring
- [ ] `dashboard/src/lib/api.ts` - Still has ~30 legacy functions to extract
- [x] **Postgres-only migration** - Replace SQLiteStore with PostgresStore + repositories; SQLite legacy removed
- [ ] `storage/repositories/user_repository.py` (1,188 lines) - Split into auth, permissions, audit repos
- [ ] `api/routers/creatives.py` - Continue split after schema + response-builder extraction (keep route layer HTTP-only)
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
