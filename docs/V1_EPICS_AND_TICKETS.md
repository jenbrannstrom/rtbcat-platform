# Cat-Scan v1 Epics and Ticket Breakdown

**Derived from:** [V1_EXECUTION_PLAN.md](/home/x1-7/Documents/rtbcat-platform/docs/V1_EXECUTION_PLAN.md)  
**Planning window:** 7 sprints (14 weeks)

---

## Execution Status (2026-03-01)

- Tracker checkpoint updated through commit `7bbb25d` and subsequent execution slices on 2026-03-01, including conversion readiness endpoint/UI/canary/CI gating and buyer-context hardening.

- `E0-001` completed: `rtb_quality` import route/table path is live and covered by importer contract tests.
- `E0-002` completed: bidstream persistence includes `platform`, `environment`, `transaction_type` with mapper support for transaction-type headers.
- `E0-003` completed: baseline missingness semantics implemented for bidstream/quality/daily/filtering metrics (`NULL` when source column is absent).
- `E0-004` completed: ingestion contract tests cover quality routing, optional dimensions, missingness, and source lineage propagation.
- `E0-005` completed: `/system/data-health` exposes optimizer-readiness checks for report completeness, `rtb_quality` freshness, bidstream dimension coverage, and seat/day completeness rollups (with endpoint filters).
- `E4-001` completed for Phase 0 scope: Settings System page renders an Optimizer Readiness panel from `/system/data-health`, including interactive filters (window/state/min completeness/row limit).
- `QA-001` completed: foundation regression suite is passing for import hardening and optimizer-readiness service/API contracts.
- `QA-001` started (CI automation slice): `.github/workflows/phase0-regression.yml` now runs `make v1-gate` (phase0 gate + conversion/readiness regression + dashboard production build) plus canary CLI sanity checks on push/PR for foundation/conversion paths, including `dashboard/**`.
- `E1-001` started: migration `054_conversion_platform.sql` adds `conversion_events` and `conversion_aggregates_daily` with indexes and constraints.
- `E1-002` started: canonical conversion taxonomy + source normalization helpers added in `services/conversion_taxonomy.py`, with provider-specific payload normalizers in `services/conversion_normalizers.py`.
- `E1-003` started: daily conversion aggregation service implemented (`services/conversions_service.py`) with RTB join and upsert refresh flow.
- `E1-004` started: conversion aggregate read API and lag health endpoints added under `/conversions/*` with router wiring in `api/main.py`.
- `QA-002` (Phase 1/2 slice) started: conversion taxonomy/service/API coverage plus provider fixture suite (`tests/fixtures/conversions/*`, `tests/test_conversion_connector_fixtures.py`) are passing in local regression runs.
- `QA-002` (Phase 1/2 slice) started: conversion readiness state logic is unit-tested in `tests/test_conversion_readiness.py` (ready/degraded/not_ready/unavailable paths).
- `QA-002` (Phase 1/2 slice): root `make v1-conversion-regression` target now runs conversion/readiness regression across readiness scoring, conversion aggregates service/API, ingestion service/API, provider fixtures, and canary helper coverage.
- `QA-003` started: BYOM workflow integration coverage now includes a single-flow API test (`tests/test_optimizer_e2e_api.py`) covering score-and-propose orchestration, proposal approval/apply, sync, and audit-history retrieval.
- `E2-001` started: `/conversions/appsflyer/postback` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-002` started: `/conversions/adjust/callback` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-003` started: `/conversions/branch/webhook` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-004` started: `/conversions/generic/postback` and `/conversions/csv/upload` endpoints added, feeding the universal conversion event schema.
- `E2-004` started (agency connector slice): `/conversions/redtrack/postback` and `/conversions/voluum/postback` alias routes now reuse generic ingestion/security with source defaults for lower-friction tracker onboarding.
- `E2-004` started (stretch slice): lightweight web conversion pixel endpoint `GET /conversions/pixel` added, ingesting query payloads into conversion events while returning a cache-busted 1x1 GIF and preserving DLQ capture on ingest failures.
- `E2-005` started: conversion ingestion observability + DLQ operations added (`conversion_ingestion_failures`, list/replay/discard endpoints, accepted/rejected stats, and `/conversions/ingestion/error-taxonomy` breakdowns).
- `E2-005` started (readiness slice): aggregated conversion readiness endpoint `/conversions/readiness` now combines health + ingestion stats + freshness thresholds into a single buyer-scoped readiness state with explicit reasons.
- `E3-001` started: migration `056_byom_optimizer_platform.sql` adds `optimization_models`, `segment_scores`, and `qps_allocation_proposals`; model registry APIs are available under `/optimizer/models/*` with service/test coverage, including endpoint contract validation via `/optimizer/models/{model_id}/validate` and encrypted-at-rest handling for model auth headers when `CATSCAN_OPTIMIZER_MODEL_SECRET_KEY` is configured.
- `E3-001` started: model endpoint validation now accepts optional request-body `sample_payload` for contract checks against real feature payloads (not only default ping payload).
- `E3-002` started: segment scoring orchestration supports both `rules` and external `api` model types (`services/optimizer_scoring_service.py`) with run/read APIs under `/optimizer/scoring/*`, persisting scored segments into `segment_scores`.
- `E3-003` started: QPS proposal generation service/API added (`services/optimizer_proposals_service.py`, `/optimizer/proposals/generate`) with confidence/delta guardrails and persisted draft proposals.
- `E3-004` started: proposal workflow endpoints for approve/reject/apply are available under `/optimizer/proposals/{proposal_id}/*`; apply supports `mode=queue|live`, status transitions are state-machine guarded, apply queues `set_maximum_qps` pending changes for pretargeting configs, apply metadata sync is available at `/optimizer/proposals/{proposal_id}/sync-apply-status`, and proposal audit history is queryable at `/optimizer/proposals/{proposal_id}/history`.
- `E3-005` started: rules fallback path is operational (`/optimizer/scoring/rules/run` -> `/optimizer/proposals/generate`) and a one-shot orchestrator endpoint `/optimizer/workflows/score-and-propose` runs scoring + proposal generation in one call; `model_type=csv` now routes through the same rules scoring fallback to avoid unsupported-type runtime failures.
- `E3-005` started: dashboard API client parameter mapping for score+propose now aligns with backend contract (`days`, `score_limit`, `proposal_limit`), eliminating silent no-op query params from the System control plane.
- `E3-005` started: `/optimizer/workflows/score-and-propose` now accepts legacy query aliases (`scoring_days`, `proposal_days`, `scoring_limit`) for backward compatibility while using canonical params internally.
- `E3-005` started: `/optimizer/workflows/score-and-propose` now supports optional `profile=safe|balanced|aggressive` defaults, with explicit params still able to override profile values.
- `E4-004` (security hardening slice) started: conversion webhook endpoints now support optional HMAC verification, configurable timestamp-freshness checks for replay-risk reduction, and optional per-source/IP ingress rate limiting.
- `E4-004` (security hardening slice) started: webhook auth now supports zero-downtime secret rotation windows by accepting multiple active plain/HMAC secrets per env var (comma/semicolon/newline-separated), with tests and setup/runbook guidance updated.
- `E4-004` (security hardening slice) started: webhook security posture API is available at `GET /conversions/security/status` (non-secret state + rotation counts + freshness/rate-limit toggles/thresholds) with API coverage in `tests/test_conversions_api.py`.
- `E4-005` started (frontend performance slice): QPS Home now avoids initial N+1 detail fetches by lazy-loading `/settings/pretargeting/{billing_id}/detail` only on expanded/edit paths, mounts `ConfigBreakdownPanel` only for the expanded row, and captures startup load metrics on `window.__CATSCAN_QPS_LOAD_METRICS` (first row, hydrated, and key API latencies including `/settings/endpoints`, `/settings/pretargeting`, `/analytics/home/configs`, `/analytics/home/endpoint-efficiency`).
- `E4-002` started (backend slice): optimizer setup API now supports persisted monthly hosting cost under `/settings/optimizer/setup` for effective-CPM context and setup-flow readiness.
- `E4-002` started (frontend slice): Optimizer Control Plane now includes monthly hosting cost save controls wired to `/settings/optimizer/setup` with effective-CPM enabled/disabled state feedback, one-click active-model endpoint validation, and model lifecycle controls (create/update + activate/deactivate + select).
- `E4-002` started (frontend slice): endpoint validation now supports optional custom JSON payload input in System Settings for contract checks against realistic model request bodies.
- `E4-002` started (frontend slice): score+propose controls now expose configurable runtime parameters (days, score/proposal limits, min confidence, max delta) with client-side guardrails instead of fixed constants.
- `E4-002` started (frontend slice): score+propose controls include preset profiles (`safe`, `balanced`, `aggressive`) with explicit `custom` mode when fields are manually edited.
- `E4-002` started (frontend slice): score+propose execution now forwards preset `profile` (`safe|balanced|aggressive`) to the workflow API while still sending explicit guardrail params for deterministic overrides.
- `E4-002` started (frontend setup slice): `/setup` is now a v1 checklist page with readiness progress and direct links for accounts, data-health validation, BYOM model activation, active-model endpoint validation, hosting-cost configuration, and conversion-source readiness (from `/conversions/health`).
- `E4-002` started (frontend setup slice): conversion-source readiness on `/setup` now uses both `/conversions/health` lag and `/conversions/ingestion/stats` accepted volume (14-day window), scoped to active buyer context, to avoid false-ready states from stale historical totals.
- `E4-002` started (frontend setup slice): buyer-specific setup checks now require active buyer context selection (`selectedBuyerId`) and display explicit buyer-context status to prevent global/mixed readiness false positives.
- `E4-002` started (frontend setup slice): `/setup` conversion-source step now consumes `/conversions/readiness` for centralized backend readiness logic and reason strings instead of duplicating lag/volume checks client-side.
- `E4-002` started (frontend setup slice): `/setup` conversion-source step now includes webhook security posture summary from `/conversions/security/status` (secured-source coverage + freshness/rate-limit toggles) in checklist guidance.
- `E4-002` started (frontend setup slice): account step on `/setup` now requires the selected buyer to be an active connected seat (with explicit mismatch guidance), preventing false-ready progress when only unrelated seats exist.
- `E4-001` started (backend metric slice): optimizer economics endpoints now expose `/optimizer/economics/effective-cpm` (media/infra/effective CPM), `/optimizer/economics/assumed-value` (proxy value score with weighted components), and `/optimizer/economics/efficiency` (QPS efficiency + assumed-value-per-QPS context) using core RTB fact tables.
- `E4-001` started (frontend slice): Settings System now includes an Optimizer Control Plane panel showing model inventory, recent segment scores, recent QPS proposals, proposal-history drilldown, a 14-day efficiency context block (effective CPM, QPS efficiency, assumed-value per QPS), 7-day conversion signal health telemetry, and an applied-proposal rollback modal (snapshot preview + execute) for the active buyer context.
- `E4-001` started (frontend slice): conversion telemetry in Settings System now includes `/conversions/readiness` state + primary reason alongside health and ingestion stats for faster operator triage.
- `E4-001` started (frontend slice): conversion telemetry in Settings System now includes webhook security posture from `/conversions/security/status` (secret/HMAC coverage by source, freshness/rate-limit state) for operator triage.
- `E4-001` started (frontend slice): Optimizer Control Plane now shows explicit buyer-context status with a warning when no buyer is selected, reducing unscoped-operations risk.
- `E4-001` started (frontend slice): conversion readiness UX now surfaces multiple readiness reasons (up to three in System, full summary in Setup) for faster troubleshooting without extra endpoint queries.
- `E4-003` started (audit linkage slice): optimizer-triggered rollbacks can now attach `proposal_id` + reason context to pretargeting history entries, and History UI renders this rollback context for operator traceability.
- `QA-004` started (audit coverage slice): API tests now verify rollback context passthrough (`proposal_id`/reason/user) and history rollback-context serialization from both JSON objects and JSON strings.
- `E4-003` started: operator playbook drafted in `docs/OPTIMIZER_V1_OPERATOR_RUNBOOK.md` covering preflight checks, score/propose/apply workflow, rollback procedure, and webhook security controls.
- `E4-003` started: operator playbook now includes conversion readiness gating (`/conversions/readiness`) and pixel-ingestion incident guidance for go/no-go decisions.
- `E4-003` started: operator playbook now includes `/conversions/security/status` posture checks and bundled webhook security canary command (`make v1-canary-webhook-security`) for repeatable controls validation.
- `E4-003` started: conversion connector setup guide drafted in `docs/CONVERSION_CONNECTORS_SETUP_GUIDE.md` covering AppsFlyer/Adjust/Branch/generic/CSV ingestion paths, security envs, and post-setup validation/DLQ flow.
- `E4-003` started: BYOM integration docs drafted in `docs/BYOM_MODEL_INTEGRATION_GUIDE.md` with model registry + external scoring contract details; example prompt template added at `prompts/byom-qps-optimizer.example.md`.
- `QA-004` started: canary go/no-go checklist drafted in `docs/V1_CANARY_GO_NO_GO_CHECKLIST.md` with data integrity, conversion ingestion, optimizer workflow, and rollback gates; runnable smoke script added at `scripts/v1_canary_smoke.py` with env-driven wrapper `scripts/run_v1_canary_smoke.sh`, stricter readiness assertions, root `make v1-canary-smoke` / `make phase0-gate` entrypoints, and unit coverage in `tests/test_v1_canary_smoke.py`.
- `QA-004` started (workflow depth slice): canary smoke supports optional full proposal lifecycle validation (`CATSCAN_CANARY_RUN_LIFECYCLE=1`) for approve -> apply(queue) -> sync -> history verification after score/propose.
- `QA-004` started (workflow depth slice): lifecycle canary can target either fresh workflow output or explicit existing `proposal_id` (`CATSCAN_PROPOSAL_ID`) for deterministic go/no-go validation.
- `QA-004` started (workflow depth slice): root `make` now includes convenience targets `v1-canary-workflow` and `v1-canary-lifecycle` for deeper canary execution without manual env wiring.
- `QA-004` started (workflow depth slice): root `make` now includes `v1-canary-go-no-go` strict profile target (workflow + lifecycle + healthy readiness + conversion-ready checks).
- `QA-004` started (workflow depth slice): canary workflow execution now supports env/CLI tuning for days, score/proposal limits, min confidence, and max delta guardrails.
- `QA-004` started (workflow depth slice): canary wrapper supports `CATSCAN_CANARY_PROFILE=safe|balanced|aggressive` preset mapping to workflow guardrail defaults.
- `QA-004` started (workflow depth slice): root `make` now exposes `v1-canary-safe|balanced|aggressive` targets for one-command preset execution.
- `QA-004` started (workflow depth slice): canary workflow defaults are now aligned with System UI balanced preset values (days=14, score_limit=1000, proposal_limit=200, min_confidence=0.3, max_delta=0.3).
- `QA-004` started (workflow depth slice): canary CLI/wrapper now forwards optional workflow `profile` to `/optimizer/workflows/score-and-propose` while still sending explicit guardrail params as deterministic overrides.
- `QA-004` started (connector coverage slice): canary smoke supports optional conversion pixel gate (`--run-pixel` / `CATSCAN_CANARY_RUN_PIXEL=1`) that validates GIF response + conversion status header for `/conversions/pixel`.
- `QA-004` started (connector coverage slice): canary smoke now validates `/conversions/readiness` and supports strict readiness enforcement (`--require-conversion-ready` / `CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1`).
- `QA-004` started (security coverage slice): canary smoke now supports optional webhook auth verification (`--run-webhook-auth-check` / `CATSCAN_CANARY_RUN_WEBHOOK_AUTH=1`) for generic conversion postbacks (401 without secret, 200 with secret), with `make v1-canary-webhook-auth` convenience target.
- `QA-004` started (security coverage slice): canary smoke now supports optional webhook HMAC verification (`--run-webhook-hmac-check` / `CATSCAN_CANARY_RUN_WEBHOOK_HMAC=1`) for generic conversion postbacks (200 valid signature, 401 invalid signature), with `make v1-canary-webhook-hmac` convenience target.
- `QA-004` started (security coverage slice): canary smoke now supports optional webhook freshness enforcement verification (`--run-webhook-freshness-check` / `CATSCAN_CANARY_RUN_WEBHOOK_FRESHNESS=1`) for generic conversion postbacks (200 fresh timestamp, 401 stale timestamp), with `make v1-canary-webhook-freshness` convenience target.
- `QA-004` started (security coverage slice): canary smoke now supports optional webhook rate-limit enforcement verification (`--run-webhook-rate-limit-check` / `CATSCAN_CANARY_RUN_WEBHOOK_RATE_LIMIT=1`) for generic conversion postbacks (200 until threshold, 429 after threshold), with `make v1-canary-webhook-rate-limit` convenience target.
- `QA-004` started (security coverage slice): canary smoke now supports optional webhook security-status contract verification (`--run-webhook-security-status-check` / `CATSCAN_CANARY_RUN_WEBHOOK_SECURITY_STATUS=1`) for `/conversions/security/status`, including minimum secured-source thresholds, with `make v1-canary-webhook-security-status` convenience target.
- `QA-004` started (security coverage slice): root `make` now includes bundled webhook security suite target `v1-canary-webhook-security` (auth + HMAC + freshness + rate-limit + security-status) with sane default thresholds for repeatable ops validation.
- `QA-004` started (ops hardening slice): `make phase0-gate` now runs reliably in restricted environments by building dashboard with webpack mode (`npm --prefix dashboard run build -- --webpack`), avoiding Turbopack sandbox port-binding failures.

---

## Epic E0 — Foundation Hardening (Phase 0)

**Goal:** Fix ingestion/data fidelity issues before optimizer expansion.

## E0-Story-001 (Sprint 1)

- **Title:** Add `rtb_quality` import path to unified importer
- **Owner:** Backend
- **Tasks:**
  - add `ensure_table_exists(..., "rtb_quality")`
  - add `import_to_rtb_quality(...)`
  - route `target_table == "rtb_quality"` in `unified_import`
- **Acceptance:** quality-signals CSV detected as `quality_signals` imports to `rtb_quality`.

## E0-Story-002 (Sprint 1)

- **Title:** Persist bidstream optional dimensions
- **Owner:** Backend
- **Tasks:**
  - include `platform`, `environment`, `transaction_type` in bidstream INSERT SQL + values
- **Acceptance:** imported rows retain all three fields when provided.

## E0-Story-003 (Sprint 1-2)

- **Title:** Implement missingness semantics baseline
- **Owner:** Backend + Data Eng
- **Tasks:**
  - replace default-zero behavior for absent source columns with `NULL`
  - preserve true `0` for present columns with zero values
- **Acceptance:** analytics can distinguish unknown vs true zero.

## E0-Story-004 (Sprint 2)

- **Title:** Add ingestion contract tests
- **Owner:** QA + Backend
- **Tasks:**
  - tests for quality import route
  - tests for bidstream optional field persistence
  - tests for missingness semantics
- **Acceptance:** tests fail on regression and pass on corrected behavior.

## E0-Story-005 (Sprint 2)

- **Title:** Data quality health API + dashboard indicators
- **Owner:** Backend + Frontend
- **Tasks:**
  - per-seat report completeness
  - `rtb_quality` freshness
  - dimension coverage percentages
- **Acceptance:** health status visible in UI and queriable via API.

---

## Epic E1 — Conversion Schema Platform (Phase 1)

**Goal:** Universal conversion storage/aggregation regardless of source.

## E1-Story-001 (Sprint 3)

- **Title:** Add conversion schema migrations
- **Owner:** Data Eng
- **Tasks:**
  - create `conversion_events`
  - create `conversion_aggregates_daily`
  - indexes/uniqueness/retention fields
- **Acceptance:** migrations apply idempotently in dev/staging/prod.

## E1-Story-002 (Sprint 3)

- **Title:** Build conversion taxonomy and normalization library
- **Owner:** Backend
- **Tasks:**
  - standardized event types
  - source-type normalization helpers
- **Acceptance:** same event from different sources normalizes consistently.

## E1-Story-003 (Sprint 3-4)

- **Title:** Daily conversion aggregation job
- **Owner:** Data Eng
- **Tasks:**
  - join conversion events with RTB dimensions
  - compute CPA/CVR/value totals
- **Acceptance:** aggregate metrics match fixture calculations.

## E1-Story-004 (Sprint 4)

- **Title:** Conversion aggregate API endpoints
- **Owner:** Backend
- **Tasks:**
  - query by buyer/config/country/publisher/event type/date range
- **Acceptance:** API latency and correctness targets met.

---

## Epic E2 — Conversion Connectors (Phase 2)

**Goal:** Reliable conversion inflow from external systems.

## E2-Story-001 (Sprint 4)

- **Title:** AppsFlyer postback endpoint + normalizer
- **Owner:** Backend
- **Tasks:**
  - endpoint, signature/auth validation, idempotency, mapping
- **Acceptance:** validated end-to-end with AppsFlyer sandbox payloads.

## E2-Story-002 (Sprint 5)

- **Title:** Adjust callback endpoint + normalizer
- **Owner:** Backend
- **Acceptance:** fixture and staging verification pass.

## E2-Story-003 (Sprint 5)

- **Title:** Branch webhook endpoint + normalizer
- **Owner:** Backend
- **Acceptance:** fixture and staging verification pass.

## E2-Story-004 (Sprint 4-5)

- **Title:** Generic postback + CSV conversion upload
- **Owner:** Backend
- **Acceptance:** custom trackers can ingest without source-specific code.

## E2-Story-005 (Sprint 5)

- **Title:** Connector observability and DLQ
- **Owner:** Backend + SRE
- **Tasks:**
  - accepted/rejected counters
  - payload error taxonomy
  - dead-letter queue and replay endpoint
- **Acceptance:** every rejected payload has actionable reason and replay path.

---

## Epic E3 — BYOM Optimizer Platform (Phase 3)

**Goal:** Customer-model scoring and human-approved QPS proposals.

## E3-Story-001 (Sprint 5-6)

- **Title:** Model registry schema + CRUD APIs
- **Owner:** Backend
- **Tasks:**
  - `optimization_models`
  - encrypted credential storage
  - input/output schema contracts
- **Acceptance:** model lifecycle (create/update/deactivate) works end-to-end.

## E3-Story-002 (Sprint 6)

- **Title:** Segment feature extraction + scoring orchestration
- **Owner:** Backend + Data Eng
- **Tasks:**
  - segment feature builder
  - invoke external model
  - persist `segment_scores`
- **Acceptance:** scoring run produces persisted, queryable scores with confidence.

## E3-Story-003 (Sprint 6)

- **Title:** QPS proposal engine
- **Owner:** Backend
- **Tasks:**
  - generate `qps_allocation_proposals`
  - apply guardrails (min QPS, max delta, confidence thresholds)
- **Acceptance:** proposals are explainable and constraint-compliant.

## E3-Story-004 (Sprint 6)

- **Title:** Proposal approval/apply workflow
- **Owner:** Backend + Frontend
- **Acceptance:** draft -> approved -> applied/rejected with full audit log.

## E3-Story-005 (Sprint 6)

- **Title:** Rules fallback model
- **Owner:** Backend
- **Acceptance:** recommendations generated without external model endpoint.

---

## Epic E4 — UX, Docs, and Operations

**Goal:** Make v1 operable and supportable.

## E4-Story-001 (Sprint 2/6)

- **Title:** Data quality and optimizer workspace UI
- **Owner:** Frontend
- **Acceptance:** users can inspect health, score runs, and proposals in one place.

## E4-Story-002 (Sprint 6)

- **Title:** Setup flows (hosting cost, connectors, BYOM)
- **Owner:** Frontend + Backend
- **Acceptance:** first-time setup completion under 30 minutes.

## E4-Story-003 (Sprint 7)

- **Title:** Runbooks, rollback guides, and integration docs
- **Owner:** PM + Engineering
- **Acceptance:** support can operate v1 with no tribal knowledge.

## E4-Story-004 (Sprint 7)

- **Title:** Security hardening and release readiness
- **Owner:** SRE + Backend + QA
- **Tasks:**
  - webhook signature checks
  - secrets rotation
  - replay/rate-limit verification
- **Acceptance:** no open high-severity security findings at GA.

## E4-Story-005 (Sprint 7)

- **Title:** QPS Optimizer load-performance hardening
- **Owner:** Frontend + Backend + QA
- **Tasks:**
  - instrument page timings (`navigation -> first table row -> hydrated table`) for QPS Optimizer.
  - profile/optimize initial-load API paths (`/settings/endpoints`, `/settings/pretargeting`, history/snapshot dependencies).
  - reduce client-side startup critical path with parallel fetches and non-blocking progressive rendering.
  - add canary/QA performance reporting for table readiness latency.
- **Acceptance:** `time_to_first_table_row` p95 <= 6s and `time_to_table_hydrated` p95 <= 8s for canary buyers.

---

## Cross-Cutting QA Tickets

## QA-001 (Sprint 1-2)

- regression suite for CSV import behavior across all report types.

## QA-002 (Sprint 4-5)

- provider payload fixture suite (AppsFlyer/Adjust/Branch).

## QA-003 (Sprint 6)

- end-to-end BYOM scoring/proposal approval flow tests.

## QA-004 (Sprint 7)

- production canary checklist and go/no-go script.

---

## Sprint-to-Epic Mapping

- **Sprint 1:** E0-001, E0-002, E0-003 (start), QA-001 (start)
- **Sprint 2:** E0-003 (finish), E0-004, E0-005
- **Sprint 3:** E1-001, E1-002, E1-003 (start)
- **Sprint 4:** E1-003 (finish), E1-004, E2-001, E2-004 (start)
- **Sprint 5:** E2-002, E2-003, E2-004 (finish), E2-005, E3-001 (start)
- **Sprint 6:** E3-001 (finish), E3-002, E3-003, E3-004, E3-005, E4-001/002
- **Sprint 7:** E4-003, E4-004, E4-005, QA-004, stabilization + GA

---

## Start-Now Queue (Immediate)

1. `E0-001`: `rtb_quality` import path
2. `E0-002`: bidstream optional field persistence
3. `E0-003`: missingness semantics baseline (first pass)
4. `QA-001`: importer contract tests for above
