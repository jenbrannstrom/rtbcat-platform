# Phase 4: Release Gates + Continuous Contract Enforcement

**Date:** 2026-02-11
**Branch:** unified-platform

## Goal

Automate machine-checking of contracts C-ING-001, C-ING-002, C-EPT-001, C-PRE-002,
C-PRE-003 so that violations are caught at three stages: CI (pre-build), post-deploy,
and daily scheduled runs.

## Deliverables

### 1. Contract-check runner: `scripts/contracts_check.py`

Single script that executes all 5 contract checks against the target database.

**Features:**
- Discovers active buyers dynamically from `buyer_seats (active=true)`
- Human-readable summary table to stdout
- Machine-readable JSON output via `--json-out <path>`
- Exit codes: 0 = all pass, 1 = any FAIL (or WARN under `--strict`)
- Flags: `--days` (default 7), `--strict`, `--buyer <id>`, `--db-dsn-env <ENV_VAR>`

**Contract checks implemented:**

| Contract | Check Logic | PASS | WARN | FAIL |
|----------|------------|------|------|------|
| C-ING-001 | `ingestion_runs` has rows, no stuck runs (>1h without finished_at) | rows>0, stuck=0 | stuck>0 | rows=0 |
| C-ING-002 | All active buyers have `import_history` rows within 48h | all covered | — | any buyer missing |
| C-EPT-001 | All `rtb_endpoints` have `rtb_endpoints_current` row observed <24h | all current | no endpoints registered | any missing/stale |
| C-PRE-002 | All ACTIVE configs have rows in `home_config_daily` (N-day window) | gap=0 | — | gap>0 |
| C-PRE-003 | All buyers with `home_config_daily` have `config_publisher_daily` | all covered | justified exception (no publisher_id in source) | missing with publisher data |

**Run commands:**
```bash
# Production (inside container)
python scripts/contracts_check.py --days 7 --db-dsn-env POSTGRES_DSN

# With JSON output
python scripts/contracts_check.py --days 7 --json-out /tmp/contracts.json

# Strict mode (WARN = FAIL)
python scripts/contracts_check.py --days 7 --strict

# Single buyer
python scripts/contracts_check.py --buyer 6574658621
```

**Sample output:**
```
========================================================================
CONTRACT VALIDATION SUMMARY
========================================================================
Contract     Status Message
------------------------------------------------------------------------
C-ING-001    [+] PASS  42 run(s), 0 stuck
C-ING-002    [+] PASS  All 4 buyers have imports in 48h
C-EPT-001    [+] PASS  All 11 endpoints have current observations
C-PRE-002    [+] PASS  All ACTIVE configs have rows in home_config_daily (7d window)
C-PRE-003    [!] WARN  All covered; 1 justified exception(s) (no publisher_id in source): ['6574658621']
------------------------------------------------------------------------
Total: 4 PASS, 1 WARN, 0 FAIL
========================================================================
```

### 2. CI integration: `.github/workflows/build-and-push.yml`

Added `test` job that runs before `build-and-push`:

- Sets up Python 3.12 with pip cache
- Installs test dependencies (psycopg, pytest, pytest-asyncio)
- Runs all recovery-phase tests (28 tests across 4 files)
- Produces JUnit XML artifact
- `build-and-push` job has `needs: test` — build is blocked on test failure

**Test files executed in CI:**
- `tests/test_contracts_check.py` (8 tests) — Phase 4
- `tests/test_precompute_completeness.py` (8 tests) — Phase 3
- `tests/test_ingestion_observability.py` (7 tests) — Phase 1
- `tests/test_endpoint_feed.py` (5 tests) — Phase 2

### 3. Post-deploy gate: `deploy.yml`

Added `Post-deploy contract check` step after the existing health check.

**Blocking by default.** If `contracts_check.py` exits non-zero, the deploy
workflow fails — preventing silent release of contract-violating deployments.

**Behavior:**
- Runs `contracts_check.py` inside the deployed container via SSH
- Writes JSON to a dated path: `contracts_<sha>_<vm>_<timestamp>.json`
- Copies JSON from VM via `gcloud compute scp`. If the copy fails, a fallback
  JSON is written locally (see "Deterministic artifact" below).
- Artifact is uploaded as a GitHub Actions artifact (90-day retention).
- On contract failure:
  - **Default (`ALLOW_CONTRACT_FAILURE=false`):** step emits `::error::` and exits 1,
    failing the workflow.
  - **Bypass (`ALLOW_CONTRACT_FAILURE=true`):** step emits `::warning::` with explicit
    bypass notice but does NOT fail. The JSON artifact is still uploaded for audit.
- Artifact is always uploaded (`if: always()`), even on failure or bypass.

**Bypass mechanism:**
- Set repository variable `ALLOW_CONTRACT_FAILURE=true` in GitHub Settings >
  Secrets and variables > Actions > Variables.
- Use only for emergency/known-gap deployments.
- Remove the variable immediately after investigation.
- The bypass is auditable: the workflow log shows the warning annotation.

**Deterministic artifact upload:**

The artifact file at `${ARTIFACT_PATH}` is guaranteed to exist before the upload
step runs. Two paths:

1. **SCP succeeds:** the real contract JSON from the VM is uploaded.
2. **SCP fails:** a fallback JSON is written locally with schema:
   ```json
   {
     "timestamp": "20260211T143022Z",
     "vm": "catscan-production",
     "sha": "d8f5547",
     "check_exit": 1,
     "error": "artifact_copy_failed",
     "note": "Contract JSON could not be copied from VM. Gate status decided by check_exit and ALLOW_CONTRACT_FAILURE flag."
   }
   ```
   A `::warning::` annotation is emitted when the fallback is used.

The gate decision (block / bypass / pass) is always based on the contract check
exit code, never on whether SCP succeeded.

**Workflow snippet (post-deploy step):**
```yaml
- name: Post-deploy contract check
  id: contracts
  run: |
    set +e
    gcloud compute ssh $VM_NAME ... --command="
      sudo docker exec catscan-api python /app/scripts/contracts_check.py \
        --days 7 --db-dsn-env POSTGRES_DSN \
        --json-out /tmp/contracts_post_deploy.json
    "
    CHECK_EXIT=$?
    set -e
    # ... copy artifact from VM ...
    if [ "$CHECK_EXIT" -ne 0 ]; then
      if [ "$ALLOW_CONTRACT_FAILURE" = "true" ]; then
        echo "::warning::BYPASSED"
      else
        echo "::error::Deploy blocked."
        exit 1
      fi
    fi

- name: Upload contract check artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: contracts-${{ env.VM_NAME }}-${{ github.sha }}
    path: ${{ env.ARTIFACT_PATH }}
    retention-days: 90
```

**Artifact path format:**
`contracts_<7-char-sha>_<vm-name>_<YYYYMMDDTHHMMSSZ>.json`

Example: `contracts_d8f5547_catscan-production_20260211T143022Z.json`

### 4. Daily scheduled check: systemd timer

New files:
- `scripts/systemd/catscan-contracts-check.timer` — runs daily at 04:00
- `scripts/systemd/catscan-contracts-check.service` — docker exec contracts_check.py

**Installation:**
```bash
sudo cp scripts/systemd/catscan-contracts-check.{timer,service} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now catscan-contracts-check.timer
```

### 5. Tests: `tests/test_contracts_check.py`

8 environment-independent tests using mocked `pg_query`:

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_all_pass` | All 5 checks return PASS when DB state is healthy |
| 2 | `test_ept_001_gap_failure` | Missing endpoints detected as FAIL |
| 3 | `test_pre_002_missing_config` | ACTIVE config gap detected as FAIL |
| 4 | `test_pre_003_justified_exception_warn` | Zero publisher_id in source → WARN |
| 5 | `test_pre_003_strict_fail` | Same exception under --strict → FAIL |
| 6 | `test_no_active_buyers` | No buyer_seats → DISCOVERY FAIL |
| 7 | `test_ing_001_stuck_runs` | Stuck ingestion runs → WARN |
| 8 | `test_ing_002_missing_buyers` | Buyer missing from import_history → FAIL |

## Test Output

```
tests/test_contracts_check.py::test_all_pass PASSED
tests/test_contracts_check.py::test_ept_001_gap_failure PASSED
tests/test_contracts_check.py::test_pre_002_missing_config PASSED
tests/test_contracts_check.py::test_pre_003_justified_exception_warn PASSED
tests/test_contracts_check.py::test_pre_003_strict_fail PASSED
tests/test_contracts_check.py::test_no_active_buyers PASSED
tests/test_contracts_check.py::test_ing_001_stuck_runs PASSED
tests/test_contracts_check.py::test_ing_002_missing_buyers PASSED
8 passed in 0.24s
```

All recovery-phase tests pass (28/28):
- Phase 1 (C-ING-001/002): 7/7
- Phase 2 (C-EPT-001): 5/5
- Phase 3 (C-PRE-002/003): 8/8
- Phase 4 (contracts runner): 8/8

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `scripts/contracts_check.py` | NEW | Contract validation runner |
| `tests/test_contracts_check.py` | NEW | 8 environment-independent tests |
| `.github/workflows/build-and-push.yml` | MODIFIED | Added `test` job before `build-and-push` |
| `.github/workflows/deploy.yml` | MODIFIED | Added post-deploy contract check step |
| `scripts/systemd/catscan-contracts-check.timer` | NEW | Daily 04:00 schedule |
| `scripts/systemd/catscan-contracts-check.service` | NEW | Docker exec contract check |
| `docs/recovery/phase4_contract_enforcement_2026-02-11.md` | NEW | This document |
