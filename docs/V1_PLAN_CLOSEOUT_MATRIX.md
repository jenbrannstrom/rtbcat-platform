# V1 Plan Closeout Matrix

**Last updated:** 2026-03-01 21:45:00 UTC  
**Branch checkpoint:** `unified-platform` (rolling checkpoint)

## CI Status & Report Links

[![v1 Closeout Quick](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-quick.yml/badge.svg?branch=unified-platform)](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-quick.yml)
[![v1 Closeout Deployed](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-deployed.yml/badge.svg)](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-deployed.yml)
[![v1 BYOM API Regression](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-byom-api-regression.yml/badge.svg?branch=unified-platform)](https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-byom-api-regression.yml)

Latest workflow/report entry points:

1. Quick closeout runs + artifacts: `https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-quick.yml`
2. Deployed closeout dispatch + artifacts: `https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-deployed.yml`
3. BYOM API/e2e regression runs: `https://github.com/jenbrannstrom/rtbcat-platform/actions/workflows/v1-byom-api-regression.yml`

## Status Legend

- `Complete`: implemented and verified with passing local gates/tests.
- `Operational Pending`: implemented in code, but final sign-off requires production/customer rollout evidence.
- `Blocked (Env)`: cannot be closed from local workspace; needs deployed environment access/data.

## Verification Evidence (this session)

1. `make v1-closeout-local` (new consolidated local closeout runner)
   - includes `v1-gate`, Phase 4 targeted suites, BYOM service suites, optimizer syntax compile checks
   - result: passed
   - latest artifact report: `/tmp/v1_closeout_last_run.md`
   - quick profile also validated: `CATSCAN_CLOSEOUT_PROFILE=quick make v1-closeout-local` (passed)
2. `make v1-gate` (latest rerun after blocked-exit handling update)
   - `phase0-regression`: `29 passed, 1 skipped`
   - dashboard production build (`webpack`): passed
   - `v1-conversion-regression`: `42 passed, 1 skipped`
3. Targeted Phase 4 suites:
   - `pytest -q tests/test_system_ui_metrics_api.py tests/test_pretargeting_repo_query_shapes.py tests/test_pretargeting_service_cache.py tests/test_endpoints_service_cache.py tests/test_analytics_service_cache.py`
   - result: `30 passed, 1 skipped`
4. BYOM/optimizer service-level suites:
   - `pytest -q tests/test_optimizer_models_service.py tests/test_optimizer_scoring_service.py tests/test_optimizer_proposals_service.py tests/test_optimizer_economics_service.py tests/test_response_model_regressions.py`
   - result: `44 passed`
5. Canary execution attempts (environment evidence):
   - `make v1-canary-go-no-go` -> exits with code `2` (`Blocked`) in this sandbox with explicit reachability preflight: `API health -> outbound network blocked (Operation not permitted)`.
   - `make v1-canary-qps-page-slo-strict` -> same environment blocker applies in this sandbox.
   - verified in closeout runner mode (`CATSCAN_CLOSEOUT_RUN_DEPLOYED=1`, `CATSCAN_CLOSEOUT_ALLOW_DEPLOYED_BLOCKED=1`): both deployed canary steps are recorded as `BLOCKED` and report output still completes.
6. Optimizer API/e2e test attempt:
   - target API suites skip in this environment because `fastapi` is unavailable; installing dependencies is network-blocked.
7. Optimizer API syntax checks:
   - `python3 -m py_compile api/routers/optimizer_models.py api/routers/optimizer_scoring.py api/routers/optimizer_proposals.py api/routers/optimizer_workflows.py api/routers/optimizer_economics.py services/optimizer_models_service.py services/optimizer_scoring_service.py services/optimizer_proposals_service.py services/optimizer_economics_service.py`
   - result: passed
8. CI automation:
   - `.github/workflows/v1-closeout-quick.yml` runs `CATSCAN_CLOSEOUT_PROFILE=quick make v1-closeout-local`, publishes a GitHub job summary from `/tmp/v1_closeout_last_run.json`, and uploads both `/tmp/v1_closeout_last_run.md` and `/tmp/v1_closeout_last_run.json` as artifacts on matching push/PR changes.
   - `.github/workflows/v1-closeout-deployed.yml` adds manual (`workflow_dispatch`) deployed closeout execution using `make v1-closeout-deployed-only`, with summary + md/json artifacts for attachable canary evidence (repo secrets: `CATSCAN_CANARY_BEARER_TOKEN` and/or `CATSCAN_CANARY_SESSION_COOKIE`).
   - both closeout workflows render their summary via shared helper `scripts/render_v1_closeout_summary.py` to keep report formatting consistent.
   - `.github/workflows/v1-byom-api-regression.yml` runs `make v1-byom-api-regression` on optimizer API/service/test changes so BYOM API/e2e coverage is validated in a dependency-provisioned CI runner, and now also supports manual `workflow_dispatch`.
9. Latest deployed/BYOM evidence runs (buyer `1487810529`):
   - deployed strict run `22553179141` failed with `Deployed canary go/no-go: FAIL (exit 1)` due to auth failures (`401 Session expired or invalid`), not code-level assertion regressions.
   - deployed evidence-mode run `22553342553` (`allow_blocked=true`) showed the same auth-expired failure pattern; at that point auth failures still exited as hard fail.
   - BYOM regression run `22553379186` passed (`27 passed`, workflow conclusion `success`).

## Closeout Matrix

| Area | Plan Status | Closeout Status | Evidence | Remaining for Final Closure |
|---|---|---|---|---|
| Phase 0 Foundation Hardening | Completed | Complete | `v1-gate` + existing Phase 0 tests/API/UI coverage | None |
| Phase 1 Conversion Schema | Implemented baseline | Operational Pending | Conversion schema/service/API tests pass in `v1-gate` | Production-volume validation, retention tuning, connector guardrail validation |
| Phase 2 Conversion Connectors | Implemented baseline, rollout in progress | Operational Pending | Connector/readiness/security code + tests are present and passing | Customer-by-customer production certification and sustained ingestion/SLO checks |
| Phase 3 BYOM Platform | Implemented in code | Operational Pending | Optimizer service/regression suites pass locally (`44 passed`); optimizer routers/services compile cleanly; API/e2e suites are env-blocked in this workspace (missing `fastapi` with network-restricted install), with CI regression path now available via `.github/workflows/v1-byom-api-regression.yml` | Production model onboarding + runbook-driven operator acceptance + successful BYOM API/e2e CI evidence for target environments |
| Phase 4 QPS Performance | In progress | Operational Pending | Extensive query/cache/render improvements committed; local QPS contract/cache suites pass | Deployed canary SLO attainment (`p95 first row <= 6s`, `p95 hydrated <= 8s`) and strict rollup gate pass |
| QA/Canary Tooling | Implemented | Blocked (Env/Auth) for deployed execution | Canary scripts/targets exist; latest deployed CI failures were caused by expired `CATSCAN_SESSION_COOKIE` secret (`401 Session expired or invalid`) | Refresh deployed canary auth secret(s), rerun deployed closeout, and attach passing artifacts |

## Is The Plan Finished?

**Not fully finished yet.**  
Implementation is largely complete across Phases 0-4, but final plan closure requires operational sign-off items that are environment-dependent (production canary/SLO outcomes and customer rollout certification).

## Immediate Final-Close Actions (Ops)

1. Ensure deployed canary auth is configured and fresh (`CATSCAN_CANARY_BEARER_TOKEN` and/or `CATSCAN_CANARY_SESSION_COOKIE`), then run deployed canary profile: `make v1-canary-go-no-go` (from network-enabled runner) or dispatch `.github/workflows/v1-closeout-deployed.yml`.
2. Run deployed strict QPS SLO gate: `make v1-canary-qps-page-slo-strict` (or via the same deployed closeout workflow).
3. Run BYOM API/e2e suites in provisioned test env with API deps installed (or confirm pass in `.github/workflows/v1-byom-api-regression.yml`).
4. Record buyer-scoped SLO outcomes for the agreed lookback window.
5. Mark remaining `Operational Pending` rows as `Complete` once evidence is attached.

Execution template:

1. Use [V1_CLOSEOUT_EXECUTION_CHECKLIST.md](/home/x1-7/Documents/rtbcat-platform/docs/V1_CLOSEOUT_EXECUTION_CHECKLIST.md) for copy/paste dispatch payloads, run capture, and sign-off fields.

## Closeout Runner Notes

- `make v1-closeout-local` runs all non-env-blocked checks.
- convenience targets: `make v1-closeout-quick` (quick profile), `make v1-closeout-deployed` (full/quick + deployed canary gates), `make v1-closeout-deployed-only` (deployed canary gates only), `make v1-closeout-dispatch` (GitHub dispatch/watch helper), and `make v1-closeout-summary` (render latest JSON report as markdown).
- Profiles: `CATSCAN_CLOSEOUT_PROFILE=full|quick|deployed_only` (`full` includes dashboard production build via `v1-gate`; `quick` skips build and runs regression suites only; `deployed_only` skips local suites and runs network canary gates).
- It writes structured reports to `/tmp/v1_closeout_last_run.md` and `/tmp/v1_closeout_last_run.json` by default (`CATSCAN_CLOSEOUT_REPORT_PATH` and `CATSCAN_CLOSEOUT_REPORT_JSON_PATH` override).
- Summary rendering helper (`scripts/render_v1_closeout_summary.py`) can print to stdout or append to `CATSCAN_CLOSEOUT_SUMMARY_PATH`.
- GitHub dispatch helper script: `scripts/run_v1_closeout_deployed_dispatch.sh` (dispatch + run detection + watch + artifact download, optional BYOM dispatch).
- For deployed gates: set `CATSCAN_CLOSEOUT_RUN_DEPLOYED=1`.
- If running from a restricted environment, keep `CATSCAN_CLOSEOUT_ALLOW_DEPLOYED_BLOCKED=1` so deployed canary exit code `2` is recorded as `Blocked (Env)` instead of hard-failing local closeout runs.
