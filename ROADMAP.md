# Cat-Scan Roadmap

**Last Updated:** March 4, 2026

## Priority Buckets (2026-02-27)

- [ ] **Now** - Objective: clear production-facing regressions and runtime blockers; Current: seat-switch determinism and operator verification path complete; automation coverage remains; Acceptance: seat-switch/operator path is fixed and validated on production traffic, and runtime blocker follow-up is tracked to closure.
- [ ] **Next** - Objective: complete Universal Precompute Epics A/B plus Home correctness/performance gates; Current: scope is defined but rollout is incomplete; Acceptance: serving-table path and validation gates are green.
- [ ] **Later** - Objective: deliver optimization engine and external integrations after core reliability; Current: backlog/design items exist; Acceptance: features ship only after stability targets hold.

---

## AppsFlyer Attribution Plan (2026-03-03)

- [ ] **Objective:** add post-click attribution signal into optimizer decisions without breaking existing buyers or requiring media buyers to know RTB-internal IDs.
- [x] **Evidence baseline captured:** production click-URL audit across 4 seats shows AppsFlyer URLs in 1/4 seats (Tuky Display), with no AppsFlyer URLs observed in the other 3 seats' sampled recent creatives.
- [x] **Measurement UX in code:** dedicated click-macro audit API/page + creative-modal macro compliance indicator implemented (pending/alongside deploy verification).

### Integration principles (locked)

- [x] **Do not require buyers to manually pass `billing_id` in AppsFlyer params.**
- [x] **Primary join key is `clickid` when available; `creative_id + time window` is fallback only.**
- [x] **Mappings must be buyer-configurable** (same `af_sub*` fields can mean different things per buyer).
- [x] **No strict optimizer automation from fuzzy attribution joins** (fuzzy can inform diagnostics, not hard auto-actions).

### Phase plan

- [ ] **Phase A - Contract + reality check**
  - [x] Freeze buyer-level mapping profile schema and API surface (`/conversions/mapping-profile`; buyer/default scopes in `system_settings`).
  - [x] Add field-coverage audit tooling for raw AppsFlyer exports (`scripts/audit_appsflyer_export_coverage.py`).
  - [x] Add one-command Phase-A orchestration script (`scripts/run_appsflyer_phase_a_audit.sh`) to produce buyer contract report artifacts.
  - [x] Add DB-export helper (`scripts/export_appsflyer_events_jsonl.py`) and `--from-db` path in the Phase-A runner for buyers where local AppsFlyer exports are not yet available.
  - [x] Publish 4-seat onboarding packet with buyer-scoped webhook URLs + customer email template (`docs/APPSFLYER_CUSTOMER_ONBOARDING_AND_ENDPOINTS_2026-03-03.md`).
  - [ ] Run coverage audit on pilot-buyer real exports/API pulls and publish per-buyer contract docs.
  - Acceptance: documented per-buyer contract + measured field coverage report.

- [ ] **Phase B - Data model and ingestion**
  - [x] Add attribution join evidence storage (`conversion_attribution_joins`) with exact/fallback mode, status, and confidence fields.
  - [x] Add attribution API surface (`/conversions/attribution/refresh|summary|joins`) for buyer-scoped observability and diagnostics.
  - [x] Add operator report script (`scripts/run_conversion_attribution_phase_b_report.sh`) to capture refresh+summary+sample joins in one artifact.
  - [x] Add one-command live pilot validator (`scripts/run_appsflyer_pilot_live_validation.sh`) to orchestrate readiness + Phase A + Phase B with consolidated PASS/BLOCKED/FAIL output.
  - [x] Add CI workflow wrapper for live pilot validation (`.github/workflows/v1-appsflyer-pilot-live-validation.yml`) with artifacts + scheduled/manual runs.
  - [x] Add AppsFlyer raw ingestion tables + normalization pipeline with buyer-specific mapping profile.
  - [x] Persist ingestion lineage and quality counters (accepted/rejected/unknown mappings).
  - Acceptance: deterministic ingest for pilot buyer with replay-safe idempotency.

- [ ] **Phase C - Join engine (exact + fallback modes)**
  - Exact mode: join by `clickid` (preferred).
  - Fallback mode: probabilistic join by `creative_id` + app/site + timestamp window.
  - Expose confidence scores and explicit join mode in API/UI.
  - Acceptance: join quality report with exact-match rate and confidence distribution.

- [ ] **Phase D - Optimizer integration**
  - Feed conversion/value outcomes into optimizer economics/recommendation scoring.
  - Gate automation: only enable hard actions where confidence and coverage thresholds are met.
  - Acceptance: recommendation deltas are explainable with attribution evidence and confidence.

- [ ] **Phase E - Customer enablement**
  - Ship setup checklist for bidder + AppsFlyer owner (PID setup, link parameter policy, export cadence, QA checklist).
  - [x] Add seat-level readiness status in UI: `No AF`, `AF present/no clickid`, `AF exact-ready` (`/creatives/attribution-readiness`).
  - Acceptance: onboarding playbook can move a new seat from `No AF` to `Exact-ready`.

### Essential dependency backlog (must stay prioritized)

- [ ] Keep runtime-health strict blockers in front of attribution rollout:
  - `/system/data-health` latency/timeout stability.
  - `/optimizer/economics/efficiency` latency/timeout stability.
  - Proposal lifecycle completeness (`billing_id` propagation and apply-path reliability).
  - QPS rollup completeness gaps.
  - Progress (2026-03-04): runtime-health strict is now green for pilot buyer `1487810529` with explicit buyer-scoped waiver + deterministic rollup emission.
    - Evidence: workflow run `22655481679` (success).
    - Waiver: bidstream dimension breakdown gap (`platform/environment/transaction_type` all 100% missing for this buyer data source).
    - Waiver expiry: `2026-06-30` (must be revisited; do not treat as permanent).
- [x] Enforce policy: attribution-driven automation is not considered production-ready until runtime-health strict gate reaches stable `exit 0` for pilot buyer windows.
  - Progress (2026-03-04): automated enforcement added.
    - Daily strict run automation: `.github/workflows/v1-runtime-health-strict.yml` now scheduled (`03:35 UTC`) with buyer/profile defaults + waiver support.
    - Stability monitor: `.github/workflows/v1-runtime-health-stability.yml` (scheduled `03:50 UTC`) validates consecutive success window using `scripts/check_v1_runtime_health_stability.sh`.
  - Evidence (2026-03-04): stability window achieved for pilot buyer `1487810529` with latest 3 strict runs all `success`:
    - `22656590137`, `22656554679`, `22656401648` (`stability=STABLE` via `scripts/check_v1_runtime_health_stability.sh --window 3`).
  - Guardrail status: enabled and continuously monitored; waiver remains explicitly scoped and expires `2026-06-30`.

---

## V1 Closeout Gate Decision (2026-03-02)

- [x] **Release decision:** proceed with deployment under current strict gate semantics.
  - Evidence: strict closeout success (`22585753222`) and BYOM regression success (`22586377963`) on `unified-platform`.
- [x] **Current strict meaning (explicit):** gate is regression-focused; canary `exit 2` (all checks blocked by environment/data) is treated as non-regression pass.
- [x] **Mandatory follow-up (do not drop):** add a separate runtime-health strict gate that fails on blocked checks.
  - Objective: restore hard production-health enforcement independent of regression signal.
  - Acceptance: blocked checks fail runtime gate until remediated.
  - Implemented (2026-03-02): added workflow `v1-runtime-health-strict.yml` backed by `scripts/run_v1_runtime_health_local.sh` (treats both `FAIL` and `BLOCKED` as gate-failing outcomes), plus dispatcher helper `scripts/run_v1_runtime_health_strict_dispatch.sh`.
- [ ] **Runtime blocker backlog to resolve before enabling runtime strict gate**
  - `/system/data-health` intermittent high latency/timeouts.
  - `/optimizer/economics/efficiency` intermittent high latency/timeouts (especially assumed-value path).
  - proposal lifecycle data completeness (`billing_id` missing in generated proposals for some buyer states).
  - QPS page rollup completeness gaps (`/analytics/home/endpoint-efficiency` missing in rollup on some windows).
  - Progress (2026-03-04): strict gate now passes for buyer `1487810529` with explicit waiver + runtime telemetry hardening.
    - Success evidence: `v1 Runtime Health Strict` run `22655481679` (`exit 0` for both strict steps).
    - Waiver rationale: Google RTB source for this buyer does not provide bidstream dimension breakdowns (`platform/environment/transaction_type`), so blocker is treated as environment-waived for this buyer only.
    - Waiver controls: buyer-scoped JSON waiver with required `note` and `expires_on`; current expiry `2026-06-30`.
  - Runtime-health strict evidence (2026-03-02, run `22599615982`): both strict canaries blocked by `rtb_quality_freshness state is unavailable (no quality data for this buyer/period)` for buyer `1487810529`.
  - Remediation helper added: `scripts/remediate_v1_quality_freshness_blocker.sh` (check data health -> trigger `/gmail/import` -> poll `/gmail/status` -> re-check readiness).
  - Progress (2026-03-02): backend mitigation patch staged on `unified-platform` (pending deploy + validation):
    - `DataHealthService`: parallelized sub-checks, fixed RTB buyer filters to `buyer_account_id`, disabled MV refresh-on-read by default (opt-in via `DATA_HEALTH_REFRESH_SEAT_DAY_MV_ON_READ`).
    - `OptimizerEconomicsService`: reuse shared `rtb_daily` aggregates across efficiency/assumed-value path; bound `rtb_quality` aggregate with statement timeout (`OPTIMIZER_QUALITY_QUERY_TIMEOUT_MS`, default `10000`).
    - DB: added migration `062_rtb_fact_query_indexes` for buyer/date composite indexes on `rtb_daily`, `rtb_quality`, `rtb_bidstream`, and `rtb_bid_filtering`.
  - [ ] Apply migration `062_rtb_fact_query_indexes` on production and rerun strict closeout to confirm timeout reduction.

---

## Next Active Workstream (2026-03-02): Seat-Switch + Operator Verification

- Progress (2026-03-02):
  - [x] Added canonical buyer-context resolver + unit coverage to prevent stale/invalid buyer IDs from bouncing scoped routes (`dashboard/src/lib/buyer-context-sync.ts`, `dashboard/src/__tests__/buyer-context-sync.test.ts`, `dashboard/src/components/buyer-route-sync.tsx`).
- [x] **Seat-switch determinism**
  - Objective: selected buyer context must stay consistent across URL, in-memory context, localStorage/cookie, and active-seat RBAC validation.
  - Acceptance: no route bounce/revert during seat switch; invalid/revoked seat IDs are corrected deterministically without cross-seat data queries.
  - Done: canonical resolver (`buyer-context-sync.ts`) + route sync component refactored; 6 unit tests pass.
- [x] **Operator verification path**
  - Objective: setup/system operator views must show seat-validity and readiness status with unambiguous pass/fail reasons.
  - Acceptance: operator can verify seat validity + readiness from one flow without manual query debugging.
  - Done: `buyer-context-state.ts` (pure derivation of 4 validity states: loading, no_active_seats, selected_buyer_invalid, selected_buyer_valid), `BuyerContextBanner` reusable component, integrated into `/setup` and `/settings/system` pages with buyer-scoped query gating (`enabled: buyerCtx.canQuery`); 8 unit tests pass.
- [x] **Automation coverage**
  - Objective: add regression tests for seat-switch precedence and buyer-scoped query behavior on key routes.
  - Acceptance: CI tests fail on seat-context regressions before deploy.
  - Progress (2026-03-02):
    - [x] Added deterministic seat-switch route-sync decision tests (`dashboard/src/__tests__/buyer-route-sync-logic.test.ts`) and extracted pure sync decision logic (`dashboard/src/lib/buyer-route-sync-logic.ts`) used by `BuyerRouteSync`.
    - [x] Added direct route-level query-gating assertions for `/setup` and `/settings/system` query enablement paths (`dashboard/src/lib/setup-query-gating.ts`, `dashboard/src/lib/system-query-gating.ts`, `dashboard/src/__tests__/setup-query-gating.test.ts`, `dashboard/src/__tests__/system-query-gating.test.ts`).

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
- [x] **Remove `ALLOW_CONTRACT_FAILURE` bypass after C-EPT-001 RCA**
  - RCA (2026-02-25): active scheduled refresh paths (`scripts/refresh_home_cache.py` via `catscan-home-refresh` and `/api/precompute/refresh/scheduled`) refreshed precompute tables but did not refresh `rtb_endpoints_current`, so `C-EPT-001` went stale (>24h) even when other refreshes ran.
  - Fix deployed in `cabab81`: scheduled refresh paths now call `EndpointsService.refresh_endpoints_current()` and log/return refreshed endpoint observation row count.
  - Verification on February 25, 2026: triggered refresh populated `rtb_endpoints_current` for all 11 endpoints across 4 bidders; contracts check passed (`5 PASS`, `0 FAIL`) including `C-EPT-001`; `ALLOW_CONTRACT_FAILURE=true` removed and deploy gate enforced with clean deploy.

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
- [ ] **Phase 3: generate/author non-English translations** - Objective: replace locale aliases with real dictionaries; Current: `nl` is broad, `es`/`zh` are substantial but incomplete; Acceptance: all supported locales resolve to non-alias dictionaries for required namespaces.
  - Progress (2026-02-24):
    - [x] Added partial-locale deep fallback to English (`dashboard/src/lib/i18n/index.ts`) so translations can ship incrementally per language
    - [x] Added initial Dutch (`nl`) dictionary priority slice (shared shell copy + core `pretargeting` UI labels/messages) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `previewModal` (source/cache states, URL labels/tooltips, approval/language/geo mismatch UI, media preview labels) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `campaigns` + `creatives` namespaces (clustering, campaign-detail, creatives page filters/status/errors/drilldown copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `recommendations` (severity/type/action/impact/staging/empty-state card/panel copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `setup` (API/Gmail/System tabs, status cards, onboarding instructions, Gemini/API key UI copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for core `import` flows (upload/preview/import states, freshness, coverage matrix, large-file/export guidance shell copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for `admin` (admin dashboard, users/local-password + seat-access UI, admin settings, audit log copy) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for waste/QPS analysis namespaces (`publishers`, `sizes`, `geo`, `aiControl`, `configPerformance`, `wasteAnalysis`) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for core shell/login/home states (`relativeTime`, `auth`, `dashboard`, `errors`) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Expanded Dutch (`nl`) coverage for ops/support namespaces (`settings`, `retentionPage`, `reports`, `history`, `connect`) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Filled Dutch (`nl`) nested `import` export-guide/report-label gaps and `common.version` fallback parity (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Completed Dutch (`nl`) `pretargeting` nested gap fill (history/source/change labels, suggestions/pending/push copy, config card labels, endpoint/recommendations/panel labels) (`dashboard/src/lib/i18n/translations/nl.ts`)
    - [x] Added initial Spanish (`es`) dictionary for core shell/auth/navigation/sidebar + dashboard home summary copy (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Updated language picker native names/flags for supported locales (`dashboard/src/lib/i18n/index.ts`, `dashboard/src/components/language-selector.tsx`)
    - [x] Expanded Spanish (`es`) coverage for core `import` flows (upload/preview/result/history/freshness/matrix/export guide) and `setup` tabs (API/Gmail/System primary UI/status copy) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for core `campaigns` and `creatives` namespaces (clusters/campaign detail/creatives page labels, states, errors) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for `recommendations` card/panel severity/type/action/impact/staging/empty-state copy (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for waste-analysis helper namespaces (`publishers`, `sizes`, `geo`, `aiControl`, `configPerformance`, `wasteAnalysis`) plus `errors`/`reports` support copy (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for ops/support namespaces (`settings`, `retentionPage`, `history`, `connect`) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Filled Spanish (`es`) nested `import` report-label and auto-detection rule gaps (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for `previewModal` (cache/live state, URL labels/tooltips, approval/language/geo mismatch UI, media preview copy) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Expanded Spanish (`es`) coverage for `admin` (admin dashboard, users/local-password + seat-access UI, admin settings, audit log copy) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [ ] Expand Spanish coverage across remaining namespaces (`pretargeting`) - Objective: close remaining `es` `pretargeting` key gaps; Current: first core chunk is landed; Acceptance: `pretargeting` namespace reaches parity with active UI paths.
      - [x] Added first Spanish (`es`) `pretargeting` core chunk (page shell, tabs, breakdown states, history badges, push/suspend dialogs) (`dashboard/src/lib/i18n/translations/es.ts`)
    - [x] Refactored English (`en`) translations into split namespace modules and added Chinese (`zh`) split dictionary scaffold (`dashboard/src/lib/i18n/translations/en/*`, `dashboard/src/lib/i18n/translations/zh/*`)
    - [x] Added first real Chinese (`zh`) split translations for core shell/auth/home namespaces (`common`, `relativeTime`, `navigation`, `qpsNav`, `settingsNav`, `adminNav`, `sidebar`, `auth`, `dashboard`, `errors`, `language`) (`dashboard/src/lib/i18n/translations/zh/*`)
    - [x] Added Chinese (`zh`) import core-flow translations (upload/preview/import states, import results, unified history table, freshness/matrix labels, troubleshooting shell copy) (`dashboard/src/lib/i18n/translations/zh/import.ts`)
    - [x] Expand Chinese (`zh`) coverage across remaining namespaces (`pretargeting`, `admin`, `setup`, `campaigns`, `creatives`, `previewModal`, `settings`, `wasteAnalysis`, `recommendations`, support namespaces)
      - [x] Added first Chinese (`zh`) `pretargeting` core chunk (page shell, tabs, breakdown states, history badges, push/suspend dialogs) (`dashboard/src/lib/i18n/translations/zh/pretargeting.ts`)
      - [x] Added second Chinese (`zh`) `pretargeting` chunk (snapshots/rollback, size+publisher editor, pending-change/history labels, config card + endpoint efficiency/header labels) (`dashboard/src/lib/i18n/translations/zh/pretargeting.ts`)
      - [x] Added third Chinese (`zh`) `pretargeting` chunk (recommendations panel + pretargeting recommendations panel labels) (`dashboard/src/lib/i18n/translations/zh/pretargeting.ts`)
      - [x] Added Chinese (`zh`) `admin` translations (admin dashboard, users/local-password + seat-access UI, admin settings, audit log labels) (`dashboard/src/lib/i18n/translations/zh/admin.ts`)
      - [x] Added Chinese (`zh`) `setup` translations (API connection, Gmail reports, system tab, onboarding/setup guidance) (`dashboard/src/lib/i18n/translations/zh/setup.ts`)
      - [x] Added Chinese (`zh`) `previewModal` translations (live/cached state, URL labels/tooltips, approval/language-geo mismatch UI, media preview labels) (`dashboard/src/lib/i18n/translations/zh/previewModal.ts`)
      - [x] Added Chinese (`zh`) `campaigns` + `creatives` translations (clustering views, campaign detail labels, creatives filters/statuses/errors/drilldown copy) (`dashboard/src/lib/i18n/translations/zh/campaigns.ts`, `dashboard/src/lib/i18n/translations/zh/creatives.ts`)
      - [x] Added Chinese (`zh`) ops/support namespace translations (`settings`, `retentionPage`, `history`, `connect`) (`dashboard/src/lib/i18n/translations/zh/*.ts`)
      - [x] Added Chinese (`zh`) remaining top-level namespace translations (`aiControl`, `configPerformance`, `geo`, `publishers`, `recommendations`, `reports`, `sizes`, `wasteAnalysis`) (`dashboard/src/lib/i18n/translations/zh/*.ts`)
      - [x] Removed hardcoded English date formatting (`en-US`) in shared/RTB UI date displays; now uses locale-aware formatting (`dashboard/src/lib/utils.ts`, `dashboard/src/components/rtb/config-breakdown-panel.tsx`)
      - [x] Added explicit CJK-capable font fallback stack for Chinese rendering consistency (kept `Inter` for Latin; added `PingFang SC` / `Microsoft YaHei` / `Noto Sans CJK SC` fallbacks) (`dashboard/src/app/layout.tsx`, `dashboard/src/app/globals.css`)
      - [x] Patched additional high-visibility number/date formatting to use selected app locale (Import History, RTB endpoints header, waste-analysis cards, pretargeting/snapshot date helpers) (`dashboard/src/components/import/ImportHistoryTable.tsx`, `dashboard/src/components/rtb/account-endpoints-header.tsx`, `dashboard/src/components/waste-analyzer/FunnelCard.tsx`, `dashboard/src/components/waste-report.tsx`, `dashboard/src/components/rtb/pretargeting-settings-editor.tsx`, `dashboard/src/components/rtb/snapshot-comparison-panel.tsx`)
    - [ ] Add real dictionaries for remaining locales (`pl`, `ru`, `uk`, `da`, `fr`, `he`, `ar`) and expand residual `es` namespaces - Objective: remove English alias fallback for supported locales; Current: locale scaffolds are partial; Acceptance: each listed locale has maintainable baseline dictionaries for active surfaces.

---

## Known Bugs

- [x] **Campaigns tab filtering** - Creative ID type mismatch causing empty campaigns view
- [x] **FFmpeg missing on install** - Container/runtime image includes ffmpeg; install blocker closed
- [ ] **Login loop / empty analytics (rescoped)** - Objective: eliminate auth/analytics loop failure mode; Current: startup now hard-fails without `POSTGRES_SERVING_DSN`, but runtime env drift and telemetry gaps remain; Acceptance: no reproducible loop in prod/VM2 and telemetry isolates failures quickly.
- [x] **Import Now button fails** - /import does not process queued Gmail reports
- [x] **Campaigns create action no-op** - Clicking "Create" on auto cluster does nothing
- [x] **Duplicate migration numbers** - resolved
- [x] **CI/CD pipeline** - Build images in GitHub Actions and deploy via docker pull (Artifact Registry)

Runtime-verified bug checks have been moved to **Runtime Verification Queue (Prod/VM2)** to keep this section code-actionable.

---

## Reopened Regressions (Code-Verified)

- [x] **Creative language persistence path regression (closed in code)** - Resolution: `PostgresStore` now exposes a compatibility shim (`self.creative_repository = self`) and implements `get_creatives_needing_language_analysis` + `update_language_detection`, restoring valid persistence routing for language-analysis paths (`api/routers/seats.py`, `services/creative_language_service.py`, `storage/postgres_store.py`). Residual risk: runtime verification still required on production traffic.

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

- [ ] **P1: Naming alignment only after P0 passes** - Objective: finish naming cleanup with low migration risk; Current: compatibility views/canonical aliases are in place and reads are mostly migrated; Acceptance: hard renames are deferred until post-stabilization decision gate.

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
- [ ] Universal serving tables for fixed windows (`7/14/30`) under Phase U1 (`serve_home_*`, `serve_qps_*`, `serve_config_*`) - Objective: precompute all user-facing windows with explicit freshness metadata/indexes; Current: architecture is defined but not fully delivered; Acceptance: tables exist with (`as_of_date`, `last_refreshed_at`, `refresh_run_id`, `data_state`) and production read-path coverage.
- [ ] Stronger seat/config integrity guarantees (rescoped) - Objective: enforce strict seat/config boundaries on all analytics paths; Current: major safeguards are in place; Acceptance: enforcement audits and regression tests cover all critical endpoints.
- [x] Precompute observability upgrade: append-only run table (per refresh run/table/status/row_count/error/host/version) to diagnose partial refreshes and stale tables quickly.
- [ ] Ingestion lineage extension - Objective: trace scheduler/import outcomes deterministically; Current: partial run metadata exists but message-level lineage is incomplete; Acceptance: importer host/version and source message lineage are persisted where available.

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
- [ ] Keep backward-compatible aliases until first release stabilizes - Objective: avoid premature physical renames; Current: canonical↔legacy fallback is active; Acceptance: rename decision is made only after stabilization metrics are met.
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
- [ ] **MCP Integration** - Objective: expose safe AI tooling via Model Context Protocol; Current: hooks exist but integration is not complete; Acceptance: approved MCP tools are wired with auth/scope controls and operator workflows.
- [ ] **Navigation restructure (rescoped)** - Objective: finalize stable information architecture and link behavior; Current: buyer-route model and grouping improved; Acceptance: nav paths are consistent, deep-linkable, and new-tab behavior is correct where expected.
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

  5. **Repository Updates** (`storage/postgres_store.py` / Postgres repository surface)
     - `update_language_detection()` - save detection results
     - `get_creatives_needing_language_analysis()` - find unanalyzed creatives
     - Note: current persistence wiring is tracked in **Reopened Regressions** due to `store.creative_repository` surface mismatch.

  6. **API Endpoints** (`api/routers/creative_language.py`)
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
  | `storage/postgres_store.py` | Language fields and persistence operations |
  | `api/routers/creative_language.py` | 3 language endpoints and response models |
  | `api/routers/seats.py` | Add language analysis to sync |
  | `dashboard/src/types/api.ts` | Add new interfaces |
  | `dashboard/src/lib/api/creatives.ts` | Add 3 language API functions |
  | `dashboard/src/components/preview-modal/LanguageSection.tsx` | Add LanguageSection |
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
  - Runtime verification items moved to **Runtime Verification Queue (Prod/VM2)**.

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
- [ ] **Rename Campaigns → Creative Clusters (rescoped)** - Objective: complete naming migration across routes/APIs/UI; Current: UI wording is mostly updated while `/campaigns` compatibility remains; Acceptance: canonical naming is consistent with controlled backward-compat windows.
- [x] **Cluster create action** - "Create" in auto cluster should persist
- [x] **Thumbnail modal** - Clicking cluster thumbnail opens creative modal

### Cosmetic Cleanup
- [x] Remove "Go To WASTE optimizer" link from `/settings/accounts`

---

## Home Page Finalization (Seat-Scoped)

**Goal:** Home page shows only data for the selected seat (buyer_id). Admins can switch seats; users only see assigned seats.

### Feature #001 — Size block/unblock controls (Home breakdown)
- [x] Implement backend endpoints to block/unblock selected sizes from the Home > By Size table
- [x] Wire bulk actions to pretargeting updates (and persist pending changes)
- [x] Ensure audit logging + rollback support

### Phase 0 — Audit & Baseline
- [x] **Data source audit** - For each Home section, list data tables used and % of rows missing `bidder_id`/`billing_id`
  - Audit snapshot captured from production on 2026-02-25 (fact tables: last 30 days by `metric_date`; dimension/current tables: all rows).
  - Result: all Home source tables had `0.0%` missing on the relevant ID columns (`bidder_id` / `billing_id`), and `seat_*` precompute tables are keyed by `buyer_account_id` (no `bidder_id`/`billing_id` columns by design).
  - Audit note: `docs/review/2026-02-25/audit/HOME_DATA_SOURCE_AUDIT.md`
- [x] **Seat scope verification** - Confirm all Home endpoints enforce `buyer_id` and user permissions
  - Verified route auth + buyer resolution in `api/routers/analytics/home.py` and `api/dependencies.py`, service/repo buyer propagation in `services/home_analytics_service.py` + `storage/postgres_repositories/home_repo.py`, and frontend Home/QPS callers passing selected seat IDs.
  - Hardening fix (2026-02-25): Home GET endpoints now require explicit resolved `buyer_id` (seat-scoped) and preserve `HTTPException` status codes instead of converting permission/access errors into generic 500s.
  - Audit note: `docs/review/2026-02-25/audit/HOME_SEAT_SCOPE_VERIFICATION_AUDIT.md`

### Phase 1 — Import & Data Model Fixes
- [x] **Postgres schema alignment** - Raw fact tables + BIGINT upgrades + pretargeting_publishers table
- [x] **Backfill raw fact tables** - Load `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality` into Postgres (through 2026-01-25)
- [x] **Persist seat identity** - Ensure `bidder_id` stored for all imports (`rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`)
  - 2026-02-25 code hardening: `importers/unified_importer.py` now backfills `bidder_id` from `buyer_account_id` via `buyer_seats` lookup when filename parsing is missing (covers `rtb_bidstream` and `rtb_bid_filtering`, plus fallback path in `rtb_daily`), and uses per-row resolved bidder IDs to avoid cross-row leakage.
  - 2026-02-25 tooling hardening: `scripts/audit_seat_identity.py` and `scripts/backfill_bidder_ids_pg.py` now treat blank/whitespace `bidder_id` as missing (not just NULL); `uploads_repo` unassigned count matches that definition.
  - 2026-02-25 production verification: dry-run backfill found 0 rows needing update; 90-day coverage snapshot confirmed 0 missing `bidder_id` across 84.7M+ ingested rows (`rtb_daily` 67.6M, `rtb_bidstream` 17.0M, `rtb_bid_filtering` 152K; `rtb_quality` had no rows in window). Note: this verifies ingested-row coverage only, not Gmail ingestion backlog completeness.
  - Verification note: `docs/review/2026-02-25/audit/HOME_SEAT_IDENTITY_PERSISTENCE_VERIFICATION.md`
- [x] **Billing ID guarantees** - Enforce `billing_id` for per-config reports; exclude rows missing it from config breakdowns
  - 2026-02-25 hardening: config-level aggregations now exclude blank/NULL `billing_id` rows in `storage/postgres_repositories/home_repo.py` (`pretarg_daily`) and `storage/postgres_repositories/rtb_bidstream_repo.py` (`pretarg_size_daily`, config geo source reads when no valid-ID allowlist is provided).
  - Billing ID lookup helpers now drop blank values from `pretargeting_configs` in `storage/postgres_repositories/analytics_repo.py` and `storage/postgres_repositories/rtb_bidstream_repo.py`.
  - Production audit snapshot (`docs/review/2026-02-25/audit/HOME_DATA_SOURCE_AUDIT.md`) also confirmed `pretarg_daily` had `0.0%` missing `billing_id` in the last 30 days.
- [x] **Join-safe keys** - Geo/publisher joins must include seat identity (`bidder_id` or `buyer_account_id`)
  - 2026-02-25 audit: no unsafe geo/publisher SQL joins found in Home/RTB serving repos; the critical config publisher attribution join in `services/config_precompute.py` joins `q` and `b` rows on `buyer_account_id` (seat identity) in addition to time/creative/country keys.
  - Fallback buyer-level geo/publisher fact paths in `services/config_precompute.py` also scope correlated `NOT EXISTS` checks by `buyer_account_id`, preventing cross-seat suppression.
  - Added an inline code guard comment at the BigQuery config publisher join to preserve the seat-identity predicate during future edits.
  - Audit note: `docs/review/2026-02-25/audit/HOME_JOIN_SAFE_KEYS_AUDIT.md`
- [x] **Identifier integrity** - Never substitute `seat_id/buyer_id` for `billing_id`. Billing IDs scope pretargeting configs; seat IDs scope buyer seats. Keep them distinct in queries and APIs.
  - 2026-02-25 audit: Home/RTB analytics routes, services, and frontend config breakdown callers keep `billing_id` and `buyer_id` as separate parameters (no direct `buyer_id -> billing_id` substitution found).
  - Added API boundary guard `validate_identifier_integrity(...)` in `api/routers/analytics/common.py` and wired it into analytics routes that accept both IDs (`/analytics/rtb-funnel/configs/{billing_id}/breakdown`, `/analytics/rtb-funnel/configs/{billing_id}/creatives`, `/analytics/size-coverage`).
  - Guard returns `400` for obvious misuse (`buyer_id == billing_id`) and route handlers now preserve `HTTPException` status codes in these paths.
  - Audit note: `docs/review/2026-02-25/audit/HOME_IDENTIFIER_INTEGRITY_AUDIT.md`

### Gmail Import & Pipeline (Operational)
- Runtime-verified operational checks moved to **Runtime Verification Queue (Prod/VM2)**.
- [x] **Ops runbook** - `docs/POSTGRES_MIGRATION_RUNBOOK.md` §2b and `docs/GCP_CREDENTIALS_SETUP.md` remain the canonical references for Gmail OAuth + scheduler operations.

### Universal Precompute Program (Fresh-Only, Single-Seat Assumption)

**Principle:** user-facing analytics routes must read prepared data only.  
**Accuracy rule:** do not serve stale snapshots as current. If refresh is pending, return `refreshing` state (not old data).  
**Scope rule:** optimize for one buyer seat per user session; admin diagnostics may remain slower.

- [ ] **Epic A — Inventory + Guardrails**
  - Objective: inventory user analytics read paths and prevent regression to hot runtime aggregation.
  - Current: endpoint inventory is partial and guardrails are not enforced in CI.
  - Acceptance: all `/`, `/qps/*`, `/settings/*` routes are classified and non-admin multi-day runtime aggregations are blocked by policy checks.

- [ ] **Epic B — Universal Serving Tables + Orchestrator**
  - Objective: provide one serving-table model plus one refresh orchestrator for all user windows.
  - Current: schema and orchestrator design exist but full implementation is pending.
  - Acceptance: `serve_home_*`, `serve_qps_*`, `serve_config_*` support `7/14/30`, include freshness metadata/indexes, and refresh via idempotent atomic runs.

- [ ] **Epic C — API/UI Cutover + Gates**
  - Objective: cut APIs/UI to serving reads with explicit freshness semantics.
  - Current: metadata/state behavior is inconsistent across routes and surfaces.
  - Acceptance: non-admin paths avoid hot `SUM/GROUP BY`, metadata is standardized (`data_state`, `last_refreshed_at`, `window_days`), and staged rollout checks pass (Home -> QPS -> remaining analytics).

### Home UI Refactor & Features
- [ ] **Pretargeting configs (rescoped)** - Objective: make config-state UX stable across delayed/fallback data; Current: “No data” and seat-only behaviors are present; Acceptance: acceptance tests cover delayed refresh and fallback modes.
- [x] **Recommended Optimizations panel (Home)** - Disabled until data correctness and optimization engine are ready
- [ ] **By Size (rescoped)** - Objective: ship consistent size drill-down behavior; Current: billing_id scoping and drill-down mostly work; Acceptance: deploy/refresh validation passes with consistent totals.
- [ ] **By Geo / By Publisher (rescoped)** - Objective: fully re-enable geo/publisher surfaces safely; Current: join-safe prerequisites are mostly in place; Acceptance: production validation confirms stable, seat-correct outputs.
- [ ] **By Creative (rescoped)** - Objective: complete creative breakdown UX and targeting context; Current: billing_id scoping path exists; Acceptance: UI completeness and country-targeting placement match spec.
- [ ] **Publisher Performance (rescoped)** - Objective: guarantee correct publisher labeling across sources; Current: title behavior is implemented; Acceptance: blank-name fallback is correct across all source variants.
- [ ] **Size Analysis (rescoped)** - Objective: finalize seat-wide/two-column analysis behavior; Current: baseline behavior exists; Acceptance: acceptance criteria and edge-case validations pass.
- [ ] **Geographic Performance (rescoped)** - Objective: finalize geo totals/sorting presentation; Current: title/sort behaviors exist; Acceptance: totals integrity and iconography match spec.

### Home Validation
- [ ] **Data correctness checks** - Objective: enforce key metric invariants; Current: checks are not uniformly codified; Acceptance: `bids <= reached` (where applicable) plus inconsistency warnings are automated.
- [ ] **Performance checks (rescoped)** - Objective: lock explicit performance gates; Current: section-level loading exists; Acceptance: measured budgets and regression gates are defined and enforced.
- Runtime deploy checks moved to **Runtime Verification Queue (Prod/VM2)**.

---

## Features - Optimization Engine

- [ ] **QPS Adjudication Engine** - Objective: calculate, apply, and track optimal pretargeting actions from seat-scoped performance/targeting data; Current: framework/UI exist but decision logic and safe writeback/rollback loop are incomplete; Acceptance: recommendations are explainable, AB write actions are reversible, and outcome deltas are measurable.
  - Decision inputs: pretargeting settings (up to 10 configs), creative and CSV targeting context (including country), and performance/funnel signals cataloged in `DATA_SCIENCE_EVALUATION.md`.
  - Method requirement: rank candidate actions with constrained optimization/game-theory-inspired scoring rather than single-metric heuristics.
  - Operational requirement: every automated action writes audit + rollback metadata before apply.
- [ ] **Creative change monitoring** - Objective: detect net-new/changed creatives as optimization triggers; Current: trigger path is manual/partial; Acceptance: monitored deltas enqueue deterministic optimization workflows.
- [ ] **AI/MCP optimization** - Objective: let AI agents run bounded optimization workflows via MCP; Current: MCP and optimizer coupling is not complete; Acceptance: approved MCP tools can analyze data and propose/apply guarded changes.
- [ ] **Learning from outcomes** - Objective: improve recommendation confidence with measured before/after results; Current: outcome feedback loop is not systematized; Acceptance: recommendation quality metrics are tracked and used for model/policy tuning.



---

## Integrations

- [ ] **Robyn MMM integration** - Objective: support MMM export/visualization workflows; Current: integration is not started; Acceptance: required data contracts and visualization outputs are available for Robyn runs.
- [ ] **Clerk auth for Terraform** - Objective: harden Terraform credential/auth handling; Current: deployment auth flow is pending; Acceptance: Clerk-backed credential handling is integrated and documented.

---

## Technical Debt

### Secrets Rollout Follow-up
- [x] Add deployment health probe for `GET /api/system/secrets-health` (status-only, non-sensitive) - Objective: make secrets readiness observable in deploy checks; Current: probe is not wired into deploy flow; Acceptance: deploy pipeline validates status endpoint before promotion.
- [x] Wire `CATSCAN_ENABLE_*` feature toggles explicitly in deploy templates so secret checks are deterministic - Objective: remove toggle drift across environments; Current: toggle wiring is implicit/incomplete; Acceptance: templates define toggles explicitly per environment.
- Runtime strict-mode enablement check moved to **Runtime Verification Queue (Prod/VM2)**.

### Naming Standardization (Pre-OSS)
- [ ] **Rename `rtbcat` → `catscan` in Docker** - Objective: align runtime naming across VM/container/docs; Current: container user is `rtbcat` while VM user is `catscan`; Acceptance: naming is unified and runbooks/path references stay correct (`docs/GCP_CREDENTIALS_SETUP.md`).

### Large File Refactoring
- [x] `dashboard/src/lib/api.ts` split completed (modular API clients under `dashboard/src/lib/api/*`)
- [x] **Postgres-only migration** - Replace SQLiteStore with PostgresStore + repositories; SQLite legacy removed
- [x] `storage/repositories/user_repository.py` split completed via Postgres repos (`auth_repo`, `permissions_repo`, `audit_repo`)
- [ ] `api/routers/creatives.py` (rescoped) - Objective: complete router/service boundary cleanup; Current: file size and complexity are reduced; Acceptance: router keeps transport concerns only and business logic lives in services.
- [x] Legacy `cli/qps_analyzer.py` split/retirement completed (legacy module no longer present)

### Security
- [x] XSS hardening in preview-modal - Objective: remove high-risk HTML injection path; Current: preview HTML is sanitized before render and isolated in strict sandboxed iframe (`srcDoc`, no same-origin/script privileges, no referrer leakage); Acceptance: sanitized content and sandboxed iframe isolation are enforced.
- Runtime log-masking verification moved to **Runtime Verification Queue (Prod/VM2)**.

### Code Quality
- [ ] **RBAC role-model migration (`sudo/admin/read`)** - Objective: enforce strict global-vs-seat-scoped permissions; Current: backend role model + seat permissions are active, seat mutation APIs now require seat-admin/sudo, and non-sudo sidebar/navigation is seat-scoped; residual audit remains for full assigned-seat coverage guarantees across all routes/pages; Acceptance: `sudo` is global-only, `admin` and `read` are assigned-seat-only, and auth/UI semantics match backend enforcement. Plan: `docs/RBAC_THREE_ROLE_IMPLEMENTATION_PLAN_2026-02-28.md`.
- [x] **Performance router RBAC sweep (2026-03-04)** — Added auth guards to previously open `/performance` import/mutation endpoints (`require_seat_admin_or_sudo`), restricted broad `/performance/metrics` listing to sudo-only (`require_admin`), and added API guard coverage tests (`tests/test_performance_rbac_api.py`).
- [x] **Retention control RBAC hardening (2026-03-04)** — Restricted `POST /retention/config` and `POST /retention/run` to sudo-only via `require_admin`, with deny/allow API guard coverage tests (`tests/test_retention_rbac_api.py`).
- [x] **Troubleshooting collector RBAC hardening (2026-03-04)** — Restricted `POST /api/troubleshooting/collect` to sudo-only via `require_admin`, with deny/allow API guard coverage tests (`tests/test_troubleshooting_rbac_api.py`).
- [x] **Collection endpoint RBAC hardening (2026-03-04)** — Restricted `/collect` and `/collect/sync` to seat-admin-or-sudo via `require_seat_admin_or_sudo`, with deny/allow API guard coverage tests (`tests/test_collect_rbac_api.py`).
- [x] **Settings mutation RBAC hardening (2026-03-04)** — Restricted settings write routes (`actions`, `changes`, `endpoints`, `pretargeting`, `snapshots`) to seat-admin-or-sudo and `PUT /settings/optimizer/setup` to sudo-only, with route guard coverage tests (`tests/test_settings_mutation_rbac_api.py`).
- [x] **Thumbnail mutation RBAC hardening (2026-03-04)** — Restricted thumbnail generation/extraction routes (`POST /thumbnails/generate`, `/thumbnails/generate-batch`, `/thumbnails/extract-html`) to seat-admin-or-sudo with route guard coverage tests (`tests/test_system_thumbnail_rbac_api.py`).
- [x] **Recommendations RBAC hardening (2026-03-04)** — Added authenticated-user requirement to recommendation read routes and seat-admin-or-sudo requirement to recommendation resolution (`POST /recommendations/{recommendation_id}/resolve`), with route guard coverage tests (`tests/test_recommendations_rbac_api.py`).
- [x] **Conversion CSV upload RBAC hardening (2026-03-04)** — Restricted `POST /conversions/csv/upload` to seat-admin-or-sudo to prevent unauthenticated manual ingestion, with route guard coverage tests (`tests/test_conversions_csv_upload_rbac_api.py`).
- [x] **Exception passthrough hardening (2026-03-04)** — Added explicit `except HTTPException: raise` passthrough in settings/recommendations/retention handlers that previously relied on broad `except Exception` blocks, with API coverage for status preservation (`tests/test_settings_exception_passthrough_api.py`).
- [x] **Critical router type annotations (2026-03-04)** — Added explicit return-type annotations on stabilized settings/recommendations/retention router handlers and helper parsers to improve static-safety/readability without behavior changes.
- [x] **Operational router type annotations (2026-03-04)** — Added explicit return-type annotations for collection/troubleshooting/system router handlers to raise static-safety/readability on active operational and telemetry endpoints without behavior changes.
- [x] **Analytics auth/scope sweep (2026-02-25)** — 14 unauthenticated analytics routes gated (`get_current_user`, `resolve_bidder_id`, or `require_admin`); 5 routes gained billing_id ownership validation via strict repo calls; 20 generic `except Exception` blocks now re-raise `HTTPException`; spend endpoint silent-fallback removed. Audit: `docs/review/2026-02-25/audit/analytics-audit.md`. Residual: 5 service methods still lack buyer/bidder scope filtering (auth-gated but unscoped at query level).
- [x] **Analytics service query-scope hardening (2026-02-25)** — Added query-level `buyer_id` scoping to `rtb-funnel/publishers`, `rtb-funnel/geos`, `app-drilldown`, and `spend-stats` across route/service/repo layers (including app bid-filtering and spend precompute status filters). Residual: legacy `GET /analytics/rtb-funnel/creatives` (`RTBFunnelAnalyzer`) remains auth-gated but not buyer-scoped.
- [x] **Analytics creative-win route scope replacement (2026-02-25)** — Replaced legacy CSV-backed `GET /analytics/rtb-funnel/creatives` analyzer path with buyer-scoped DB/precompute-backed service/repo queries (plus optional `rtb_bid_filtering` bids aggregation).
- [ ] Overly broad exception handling (`except Exception`) - Objective: reduce silent error masking; Current: broad catches remain in parts of the codebase; Acceptance: critical paths use specific exceptions and preserve status semantics.
- [ ] Missing type annotations in several Python files - Objective: raise static-safety baseline; Current: annotation coverage is incomplete; Acceptance: critical services/repos/routes have complete type hints.
- [ ] Code duplication in frontend API response handling - Objective: reduce duplicated parsing/error plumbing; Current: response handling is repeated across clients; Acceptance: shared response helpers cover common API patterns.
- [ ] Inconsistent patterns (mix of sync/async, different logging approaches) - Objective: standardize async/logging conventions; Current: style varies by module; Acceptance: agreed conventions are documented and applied to active paths.
- [ ] **Schema gate for refactors** - Objective: block unsafe schema assumptions during refactors; Current: migration checks are manual; Acceptance: migration presence/ordering is verified before new columns or `ON CONFLICT` targets are introduced.

### Architecture
- [ ] Business logic mixed into route handlers - Objective: keep routers thin and testable; Current: some business decisions still live in handlers; Acceptance: logic is moved to service layer with clear boundaries.
- [ ] Environment variables read directly throughout (rescoped) - Objective: centralize runtime config access; Current: partial normalization exists; Acceptance: env reads are routed through a unified config layer.
- [ ] No structured logging or request ID tracking - Objective: improve traceability across requests/jobs; Current: logging is mostly unstructured and uncorrelated; Acceptance: request/job IDs and structured logs are standard in core flows.

### Testing
- [ ] Current coverage targeting (rescoped) - Objective: set enforceable coverage gates on critical paths; Current: coverage is above initial floor but below target; Acceptance: baseline and target thresholds are measured and enforced.
- [ ] Missing test layers (rescoped) - Objective: close remaining API/repo/frontend/E2E gaps; Current: partial tests exist across layers; Acceptance: broader endpoint coverage and E2E suite cover critical user/admin flows.

---

## Runtime Verification Queue (Prod/VM2)

- [ ] **Thumbnail placeholders** - Some creatives still show placeholders instead of generated thumbnails (runtime verification of retry/coverage paths)
- [ ] **CSV import account mismatch** - Verify imports link to correct accounts under current production data
- [ ] **Size drill-down shows no creatives** - Validate staged fix after deploy + config precompute refresh
- [ ] **Creative modal missing publisher data** - Verify migrated publisher sources are consistently available in production
- [ ] **BigQuery raw_facts coverage** - Confirm Jan 26–28 backfill/reprocess is complete
- [ ] **Publisher List UI parity checks** - Run empty/error-state, keyboard/responsive, and acceptance-check validation (Spec §§15-19)
- [ ] **Backlog ingestion** - Continue/verify `scripts/gmail_import_batch.py` progress with checkpoint tracking (`~/.catscan/gmail_batch_checkpoint.json`)
- [ ] **Cloud Scheduler (Gmail import)** - Verify `/api/gmail/import/scheduled` behavior + VM2 parity with `GMAIL_IMPORT_SECRET`
- [ ] **Token health monitoring** - Verify alerting on `invalid_grant` and `/gmail/status` health signals
- [ ] **Pipeline env parity (VM2)** - Validate `CATSCAN_PIPELINE_ENABLED`, `BIGQUERY_PROJECT_ID`, `BIGQUERY_DATASET`, `RAW_PARQUET_BUCKET`, `CATSCAN_GCS_BUCKET`, and `GOOGLE_APPLICATION_CREDENTIALS`
- [ ] **SLO verification** - Confirm non-admin analytics endpoints meet P95 < 500ms after warmup
- [ ] **Deploy verification** - Execute `docs/DEPLOY_CHECKLIST.md` after UI + precompute rollouts
- [ ] **Secrets strict mode rollout** - Enable `SECRETS_HEALTH_STRICT=true` in production after required-key matrix is verified
- [ ] **API key masking** - Verify sensitive key/token values are masked in operational logs
- [ ] **Campaign clustering runtime stability** - Validate clustering behavior at production scale
- [ ] **Video thumbnail generation on SG VM** - Validate stability and failure rates on current SG runtime

---

## Completed

- [x] Multi-bidder account support with account switching
- [x] Creative sync from Google Authorized Buyers API
- [x] CSV import (CLI and UI)
- [x] Gmail auto-import
- [x] RTB bidstream visualization (renamed from rtb_funnel)
- [x] Efficiency analysis with recommendations
- [x] GCP deployment with OAuth2 authentication
- [x] **UTC timezone standardization** - All CSV reports now require UTC timezone
- [x] **Data quality flagging** - Legacy (pre-UTC) vs production data separation
- [x] **Per-billing_id funnel metrics** - JOIN strategy to reconstruct bid metrics by billing_id
- [x] **Database schema v17** - rtb_funnel → rtb_bidstream rename, data_quality column added
- [x] **CI/CD pipeline** - Build images in GitHub Actions and deploy via docker pull (Artifact Registry)
