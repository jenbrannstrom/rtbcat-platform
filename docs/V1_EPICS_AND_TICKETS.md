# Cat-Scan v1 Epics and Ticket Breakdown

**Derived from:** [V1_EXECUTION_PLAN.md](/home/x1-7/Documents/rtbcat-platform/docs/V1_EXECUTION_PLAN.md)  
**Planning window:** 7 sprints (14 weeks)

---

## Execution Status (2026-02-28)

- `E0-001` completed: `rtb_quality` import route/table path is live and covered by importer contract tests.
- `E0-002` completed: bidstream persistence includes `platform`, `environment`, `transaction_type` with mapper support for transaction-type headers.
- `E0-003` completed: baseline missingness semantics implemented for bidstream/quality/daily/filtering metrics (`NULL` when source column is absent).
- `E0-004` completed: ingestion contract tests cover quality routing, optional dimensions, missingness, and source lineage propagation.
- `E0-005` completed: `/system/data-health` exposes optimizer-readiness checks for report completeness, `rtb_quality` freshness, bidstream dimension coverage, and seat/day completeness rollups (with endpoint filters).
- `E4-001` completed for Phase 0 scope: Settings System page renders an Optimizer Readiness panel from `/system/data-health`, including interactive filters (window/state/min completeness/row limit).
- `QA-001` completed: foundation regression suite is passing for import hardening and optimizer-readiness service/API contracts.
- `QA-001` started (CI automation slice): `.github/workflows/phase0-regression.yml` runs full `make phase0-gate` (foundation regression + dashboard production build) plus canary CLI sanity checks on push/PR for foundation-related paths, including `dashboard/**`.
- `E1-001` started: migration `054_conversion_platform.sql` adds `conversion_events` and `conversion_aggregates_daily` with indexes and constraints.
- `E1-002` started: canonical conversion taxonomy + source normalization helpers added in `services/conversion_taxonomy.py`, with provider-specific payload normalizers in `services/conversion_normalizers.py`.
- `E1-003` started: daily conversion aggregation service implemented (`services/conversions_service.py`) with RTB join and upsert refresh flow.
- `E1-004` started: conversion aggregate read API and lag health endpoints added under `/conversions/*` with router wiring in `api/main.py`.
- `QA-002` (Phase 1/2 slice) started: conversion taxonomy/service/API coverage plus provider fixture suite (`tests/fixtures/conversions/*`, `tests/test_conversion_connector_fixtures.py`) are passing in local regression runs.
- `QA-003` started: BYOM workflow integration coverage now includes a single-flow API test (`tests/test_optimizer_e2e_api.py`) covering score-and-propose orchestration, proposal approval/apply, sync, and audit-history retrieval.
- `E2-001` started: `/conversions/appsflyer/postback` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-002` started: `/conversions/adjust/callback` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-003` started: `/conversions/branch/webhook` endpoint added with provider secret validation and idempotent event ingestion.
- `E2-004` started: `/conversions/generic/postback` and `/conversions/csv/upload` endpoints added, feeding the universal conversion event schema.
- `E2-005` started: conversion ingestion observability + DLQ operations added (`conversion_ingestion_failures`, list/replay/discard endpoints, accepted/rejected stats, and `/conversions/ingestion/error-taxonomy` breakdowns).
- `E3-001` started: migration `056_byom_optimizer_platform.sql` adds `optimization_models`, `segment_scores`, and `qps_allocation_proposals`; model registry APIs are available under `/optimizer/models/*` with service/test coverage, including endpoint contract validation via `/optimizer/models/{model_id}/validate` and encrypted-at-rest handling for model auth headers when `CATSCAN_OPTIMIZER_MODEL_SECRET_KEY` is configured.
- `E3-001` started: model endpoint validation now accepts optional request-body `sample_payload` for contract checks against real feature payloads (not only default ping payload).
- `E3-002` started: segment scoring orchestration supports both `rules` and external `api` model types (`services/optimizer_scoring_service.py`) with run/read APIs under `/optimizer/scoring/*`, persisting scored segments into `segment_scores`.
- `E3-003` started: QPS proposal generation service/API added (`services/optimizer_proposals_service.py`, `/optimizer/proposals/generate`) with confidence/delta guardrails and persisted draft proposals.
- `E3-004` started: proposal workflow endpoints for approve/reject/apply are available under `/optimizer/proposals/{proposal_id}/*`; apply supports `mode=queue|live`, status transitions are state-machine guarded, apply queues `set_maximum_qps` pending changes for pretargeting configs, apply metadata sync is available at `/optimizer/proposals/{proposal_id}/sync-apply-status`, and proposal audit history is queryable at `/optimizer/proposals/{proposal_id}/history`.
- `E3-005` started: rules fallback path is operational (`/optimizer/scoring/rules/run` -> `/optimizer/proposals/generate`) and a one-shot orchestrator endpoint `/optimizer/workflows/score-and-propose` runs scoring + proposal generation in one call; `model_type=csv` now routes through the same rules scoring fallback to avoid unsupported-type runtime failures.
- `E3-005` started: dashboard API client parameter mapping for score+propose now aligns with backend contract (`days`, `score_limit`, `proposal_limit`), eliminating silent no-op query params from the System control plane.
- `E3-005` started: `/optimizer/workflows/score-and-propose` now accepts legacy query aliases (`scoring_days`, `proposal_days`, `scoring_limit`) for backward compatibility while using canonical params internally.
- `E4-004` (security hardening slice) started: conversion webhook endpoints now support optional HMAC verification, configurable timestamp-freshness checks for replay-risk reduction, and optional per-source/IP ingress rate limiting.
- `E4-002` started (backend slice): optimizer setup API now supports persisted monthly hosting cost under `/settings/optimizer/setup` for effective-CPM context and setup-flow readiness.
- `E4-002` started (frontend slice): Optimizer Control Plane now includes monthly hosting cost save controls wired to `/settings/optimizer/setup` with effective-CPM enabled/disabled state feedback, one-click active-model endpoint validation, and model lifecycle controls (create/update + activate/deactivate + select).
- `E4-002` started (frontend slice): endpoint validation now supports optional custom JSON payload input in System Settings for contract checks against realistic model request bodies.
- `E4-002` started (frontend setup slice): `/setup` is now a v1 checklist page with readiness progress and direct links for accounts, data-health validation, BYOM model activation, active-model endpoint validation, hosting-cost configuration, and conversion-source readiness (from `/conversions/health`).
- `E4-001` started (backend metric slice): optimizer economics endpoints now expose `/optimizer/economics/effective-cpm` (media/infra/effective CPM), `/optimizer/economics/assumed-value` (proxy value score with weighted components), and `/optimizer/economics/efficiency` (QPS efficiency + assumed-value-per-QPS context) using core RTB fact tables.
- `E4-001` started (frontend slice): Settings System now includes an Optimizer Control Plane panel showing model inventory, recent segment scores, recent QPS proposals, proposal-history drilldown, a 14-day efficiency context block (effective CPM, QPS efficiency, assumed-value per QPS), 7-day conversion signal health telemetry, and an applied-proposal rollback modal (snapshot preview + execute) for the active buyer context.
- `E4-003` started (audit linkage slice): optimizer-triggered rollbacks can now attach `proposal_id` + reason context to pretargeting history entries, and History UI renders this rollback context for operator traceability.
- `QA-004` started (audit coverage slice): API tests now verify rollback context passthrough (`proposal_id`/reason/user) and history rollback-context serialization from both JSON objects and JSON strings.
- `E4-003` started: operator playbook drafted in `docs/OPTIMIZER_V1_OPERATOR_RUNBOOK.md` covering preflight checks, score/propose/apply workflow, rollback procedure, and webhook security controls.
- `E4-003` started: conversion connector setup guide drafted in `docs/CONVERSION_CONNECTORS_SETUP_GUIDE.md` covering AppsFlyer/Adjust/Branch/generic/CSV ingestion paths, security envs, and post-setup validation/DLQ flow.
- `E4-003` started: BYOM integration docs drafted in `docs/BYOM_MODEL_INTEGRATION_GUIDE.md` with model registry + external scoring contract details; example prompt template added at `prompts/byom-qps-optimizer.example.md`.
- `QA-004` started: canary go/no-go checklist drafted in `docs/V1_CANARY_GO_NO_GO_CHECKLIST.md` with data integrity, conversion ingestion, optimizer workflow, and rollback gates; runnable smoke script added at `scripts/v1_canary_smoke.py` with env-driven wrapper `scripts/run_v1_canary_smoke.sh`, stricter readiness assertions, root `make v1-canary-smoke` / `make phase0-gate` entrypoints, and unit coverage in `tests/test_v1_canary_smoke.py`.
- `QA-004` started (workflow depth slice): canary smoke supports optional full proposal lifecycle validation (`CATSCAN_CANARY_RUN_LIFECYCLE=1`) for approve -> apply(queue) -> sync -> history verification after score/propose.
- `QA-004` started (workflow depth slice): lifecycle canary can target either fresh workflow output or explicit existing `proposal_id` (`CATSCAN_PROPOSAL_ID`) for deterministic go/no-go validation.
- `QA-004` started (workflow depth slice): root `make` now includes convenience targets `v1-canary-workflow` and `v1-canary-lifecycle` for deeper canary execution without manual env wiring.
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
- **Sprint 7:** E4-003, E4-004, QA-004, stabilization + GA

---

## Start-Now Queue (Immediate)

1. `E0-001`: `rtb_quality` import path
2. `E0-002`: bidstream optional field persistence
3. `E0-003`: missingness semantics baseline (first pass)
4. `QA-001`: importer contract tests for above
