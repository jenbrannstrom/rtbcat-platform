# Cat-Scan v1 Execution Plan

**Source:** `docs/QPS_AI_OPTIMIZER_PLAN.md` v0.4 (2026-02-28)  
**Execution horizon:** 14 weeks (7 two-week sprints)  
**Release target:** v1.0 GA at end of Sprint 7

---

## 1) v1 Outcome Definition

Cat-Scan v1 is complete when all of the following are true:

1. Foundation data quality issues are fixed (Phase 0), including `rtb_quality` ingestion and missingness semantics.
2. Universal conversion schema is live (Phase 1) and powering daily aggregates.
3. At least one MMP integration path is production-ready (Phase 2 primary), plus generic postback path.
4. BYOM optimization workflow is live (Phase 3) with model registry, scoring, proposal generation, and approval flow.
5. Dashboard exposes data quality, cost context, and outcome-oriented optimization metrics.

---

## 2) Scope and Non-Goals

### In scope (v1)

- Data pipeline hardening for quality/fraud/funnel fidelity.
- Conversion event platform (schema + normalization + aggregates).
- AppsFlyer + Adjust + Branch adapters (minimum one production-validated first, then the others).
- Generic postback ingestion endpoint.
- BYOM API + rules fallback + proposal/approval workflow.
- Core UX for optimizer operations and health observability.

### Out of scope (post-v1)

- Full autonomous optimization (auto-apply without human approval).
- Advanced bidder real-time streaming optimization loops for all customers.
- Deep causal/incrementality modeling.

---

## 3) Delivery Structure

## Workstream A — Data Foundation (Phase 0)

**Goal:** Trustworthy optimizer inputs.

Primary tasks:

1. Add `rtb_quality` ingestion route in `importers/unified_importer.py`.
2. Implement `import_to_rtb_quality()` with mapping + upsert + dedupe by `row_hash`.
3. Persist `platform`, `environment`, `transaction_type` in `rtb_bidstream` insert path.
4. Implement missingness semantics:
   - use `NULL` for unavailable source fields,
   - reserve `0` for measured zero.
5. Ensure report lineage fields are preserved consistently across raw facts/parquet/BQ mirrors.
6. Add data-quality checks and health endpoints for:
   - report-type completeness,
   - quality table freshness,
   - critical dimension coverage.

Acceptance criteria:

- Quality-signal CSV imports produce rows in `rtb_quality`.
- Bidstream rows retain platform/environment/transaction_type when present.
- Analyzer outputs distinguish unknown from zero.
- Data quality panel reflects freshness/coverage by buyer and report type.

## Workstream B — Conversion Platform (Phase 1)

**Goal:** Single schema for all conversion sources.

Primary tasks:

1. Create migrations for:
   - `conversion_events`,
   - `conversion_aggregates_daily`.
2. Implement canonical event taxonomy and source mapping utilities.
3. Build conversion aggregation job joining conversions with RTB tables by dimensions.
4. Add API read endpoints for conversion aggregates (buyer/config/country/publisher breakdowns).
5. Add monitoring for conversion ingestion lag and aggregation lag.

Acceptance criteria:

- Ingested conversion events from any source normalize into common schema.
- Daily aggregate tables generate CPA/CVR/value metrics correctly.
- Aggregates queryable by billing_id and major segmentation keys.

## Workstream C — Conversion Connectors (Phase 2)

**Goal:** Reliable conversion data inflow.

Primary tasks:

1. Build and secure inbound endpoints:
   - `/conversions/appsflyer/postback`,
   - `/conversions/adjust/callback`,
   - `/conversions/branch/webhook`,
   - `/conversions/generic/postback`,
   - `/conversions/csv/upload`.
2. Implement provider-specific normalizers -> `conversion_events`.
3. Add signature/auth validation per provider.
4. Add replay protection and idempotency keys.
5. Add connector-level observability:
   - accepted/rejected postbacks,
   - mapping errors,
   - schema drift alerts.
6. Optional v1 stretch: lightweight web conversion pixel endpoints.

Acceptance criteria:

- At least one MMP (AppsFlyer preferred) production-validated end-to-end.
- Remaining connectors pass integration tests with fixture payloads.
- Failed payloads are diagnosable with actionable error reasons.

## Workstream D — BYOM Optimizer (Phase 3)

**Goal:** Customer-owned model decisions over Cat-Scan data.

Primary tasks:

1. Add model management schema and APIs:
   - `optimization_models`,
   - credentials handling (encrypted),
   - schema contracts.
2. Build scoring pipeline:
   - feature extraction by segment,
   - model invocation,
   - `segment_scores` persistence.
3. Build proposal engine:
   - current vs proposed QPS,
   - confidence-aware constraints,
   - rationale and projected impact.
4. Add approval/apply workflow:
   - draft -> approved -> applied/rejected,
   - full audit trail.
5. Implement rules-based fallback model for non-ML customers.
6. Publish prompt templates and integration guide for customer AI tools.

Acceptance criteria:

- Customer can register model endpoint and receive scoring calls.
- Proposal engine generates explainable recommendations.
- Human approval required before apply in v1.
- Rules fallback produces usable recommendations without external model.

## Workstream E — UX, Productization, and Docs

**Goal:** Operable v1 product surface.

Primary tasks:

1. Add optimizer workspace UI:
   - data health,
   - scoring runs,
   - proposals,
   - approvals,
   - apply history.
2. Add v1 metric views:
   - Assumed-Value/QPS efficiency,
   - Effective CPM (using monthly hosting cost input),
   - conversion outcomes where available.
3. Add setup flow for:
   - monthly hosting cost,
   - conversion sources,
   - BYOM registration.
4. Update docs and playbooks:
   - operator runbook,
   - connector setup guides,
   - BYOM contract docs,
   - rollback procedures.

Acceptance criteria:

- v1 workflows discoverable without engineering support.
- All critical pages localized and error states actionable.
- Operator runbooks validated in staging drills.

---

## 4) Sprint Plan (14 Weeks)

## Sprint 1 (Weeks 1-2)

- Finalize v1 architecture + RFC signoff.
- Implement `rtb_quality` importer route + table write path.
- Fix bidstream persistence of platform/environment/transaction_type.
- Start missingness semantics migration plan.

Exit gate:

- Foundation fixes merged behind feature flags.
- Ingestion contract tests added for new paths.

## Sprint 2 (Weeks 3-4)

- Complete missingness semantics and lineage propagation.
- Build data quality health APIs + dashboard panel v1.
- Phase 0 hardening verification in staging.

Exit gate:

- Phase 0 complete and validated with backfill sample window.

## Sprint 3 (Weeks 5-6)

- Create conversion schema migrations.
- Implement event taxonomy + normalization core.
- Build first conversion aggregate job and APIs.

Exit gate:

- Synthetic conversion events produce correct daily aggregates.

## Sprint 4 (Weeks 7-8)

- AppsFlyer connector end-to-end.
- Generic postback endpoint.
- Connector observability and idempotency layer.

Exit gate:

- One source live in staging with stable ingestion SLO.

## Sprint 5 (Weeks 9-10)

- Add Adjust + Branch connectors.
- CSV conversion upload path.
- Start BYOM schema/APIs (`optimization_models`, `segment_scores`).

Exit gate:

- Multi-source conversion ingestion working in staging.

## Sprint 6 (Weeks 11-12)

- Complete BYOM scoring pipeline.
- Build proposal generation + approval workflow.
- Implement rules fallback model.
- Add optimizer UI pages.

Exit gate:

- End-to-end BYOM dry run in staging with proposal outputs.

## Sprint 7 (Weeks 13-14)

- Stabilization, bug bash, perf tuning.
- Security review for inbound endpoints and model credentials.
- Documentation freeze + operator training.
- Canary rollout + GA release.

Exit gate:

- v1.0 GA criteria met.

---

## 5) Milestones and Release Gates

## M1 — Phase 0 Complete

Status: Completed (2026-02-28)

Criteria:

- Data hardening tasks all green.
- No high-severity ingestion integrity defects open.

## M2 — Conversion Platform Ready

Criteria:

- Conversion schema and aggregates production-ready.
- Backfill + validation scripts available.

## M3 — External Conversion Sources Live

Criteria:

- At least one MMP integrated and validated with customer test account.
- Generic endpoint operational.

## M4 — BYOM Closed Loop Live

Criteria:

- Model registration -> scoring -> proposal -> approval -> apply flow operational.

## M5 — v1 GA

Criteria:

- SLOs met for 2 consecutive weeks in canary.
- Documentation + support handoff complete.

---

## 6) Engineering Backlog by Component

## Backend/API

- `importers/unified_importer.py`: add `rtb_quality` branch and importer.
- `importers/flexible_mapper.py`: preserve missingness metadata.
- `analytics/qps_optimizer.py`: consume improved quality inputs and unknown/zero flags.
- `api/routers/*`: conversion ingress endpoints and BYOM APIs.
- `services/*`: scoring orchestration, proposal engine, approval workflow.

## Storage/Migrations

- New migrations for conversion and optimizer control tables.
- Index and partition strategy for `conversion_events` and postback throughput.
- Retention policy and archival jobs for raw payloads.

## Dashboard

- Data quality/freshness panel.
- Conversion and cost metrics surfaces.
- Optimizer model/proposal pages.

## Security

- Signed webhook verification.
- Model credential encryption/rotation.
- Rate limiting and replay attack protection.

## QA/Test

- Importer contract tests.
- Connector integration tests with provider fixtures.
- End-to-end BYOM flow tests.
- Regression tests for existing analytics endpoints.

---

## 7) Dependencies and Critical Path

Critical path:

1. Phase 0 data integrity ->
2. Conversion schema and aggregate correctness ->
3. At least one robust conversion connector ->
4. BYOM scoring/proposal workflow ->
5. GA.

External dependencies:

- Provider credentials and sandbox accounts (AppsFlyer/Adjust/Branch).
- Customer-side callback setup and whitelisting.
- Security/compliance review turnaround.

---

## 8) Risks and Mitigations

1. **Provider payload drift**
- Mitigation: versioned normalizers + schema contract tests + dead-letter queue.

2. **False recommendations due to partial data**
- Mitigation: strict confidence gating + unknown/zero semantics + data health badges.

3. **Low customer integration completion**
- Mitigation: start with one high-leverage connector (AppsFlyer), publish simple onboarding wizard.

4. **Credential/security incidents**
- Mitigation: encrypted secrets, least privilege, request signature validation, audit logs.

5. **Scope creep (autonomous optimization too early)**
- Mitigation: v1 human-approval required, auto-apply postponed.

---

## 9) Team and Ownership Model

Recommended minimum staffing:

- 2 Backend engineers (ingestion, conversions, BYOM APIs)
- 1 Data engineer (aggregations, data quality, backfills)
- 1 Frontend engineer (optimizer and health UX)
- 1 QA engineer (integration + regression)
- 0.5 DevOps/SRE (deploy, observability, security hardening)
- 0.5 Product/PM (scope, milestones, rollout coordination)

Ownership:

- Data Foundation: Backend + Data Eng
- Conversion Connectors: Backend
- BYOM Platform: Backend + Frontend
- Release Quality: QA + SRE
- Go-to-market docs: PM + Eng

---

## 10) v1 Definition of Done

v1 is done when all are true:

1. Phase 0/1/2/3 acceptance criteria completed.
2. End-to-end customer workflow validated in production canary:
   - ingest quality + funnel data,
   - ingest conversions from at least one MMP,
   - run BYOM score,
   - generate/approve/apply proposal.
3. No Sev-1/Sev-2 defects open for v1 scope.
4. Ops playbooks and rollback procedures are tested and documented.
5. KPIs track in production dashboard with daily review cadence.

---

## 11) Immediate Next Actions (Week 0)

1. Freeze v1 scope and sign off this execution plan.
2. Open implementation epics for Workstreams A-E.
3. Create Sprint 1 tickets for the three highest-risk fixes:
   - `rtb_quality` importer path,
   - bidstream dimension persistence,
   - missingness semantics.
4. Secure AppsFlyer sandbox credentials and test postback contract.
5. Stand up v1 program dashboard (milestones, burn, risks, SLOs).
