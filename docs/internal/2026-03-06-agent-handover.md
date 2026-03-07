# Agent Handover (2026-03-06)

Purpose: give the next agent a complete, auditable snapshot of what has been done, what is currently true, and what is still pending.

## 1) Current Truth Snapshot

### Repo + release state

- Branch: `unified-platform` (tracking `origin/unified-platform`)
- Working tree was clean before creating this handover file.
- HEAD commit: `657320b` (`docs: add Cloud SQL backup verification gate`)
- SemVer release tag exists: `v0.9.2` (points to commit `f60b96b`, dated 2026-03-05)
- Legacy deployment marker tags still exist:
  - `prod-2026-02-19-sha-2d96556`
  - `prod-2026-02-18-sha-5ad446c`
  - `prod-2026-02-18-sha-e45cad0`

### Runtime state (live checks run on 2026-03-06)

- `https://scan.rtb.cat/api/health`:
  - `status=healthy`
  - `release_version=0.9.2`
  - `version=sha-657320b`
  - `configured=true`
- `https://vm2.scan.rtb.cat/api/health`:
  - `status=healthy`
  - `release_version=0.9.2`
  - `version=sha-657320b`
  - `configured=true`
- `https://scan.rtb.cat/api/system/health` requires auth (expected).

## 2) Workstreams Completed

### A) Versioning standardization + OSS release baseline

Completed and merged in `f60b96b`:

- Clear split between release SemVer and build SHA.
- `VERSION` is canonical release value (`0.9.2`).
- CI enforces tag match (`v$(cat VERSION)`).
- Runtime/API/UI expose both release + build identity.
- Docs and release preflight added/updated.

Primary files:

- `.github/workflows/build-and-push.yml`
- `VERSION`
- `docs/VERSIONING.md`
- `docs/OSS_RELEASE_CHECKLIST.md`
- `scripts/oss_release_preflight.sh`
- `CHANGELOG.md`

### B) Terraform state import + drift closure

Completed previously (documented in reports):

- `terraform/gcp/` imported and reconciled.
- `terraform/gcp_sg_vm2/` imported and reconciled.
- Import map and drift report written.

Primary files:

- `terraform/IMPORT_MAP.md`
- `terraform/DRIFT_REPORT.md`
- `terraform/gcp/*`
- `terraform/gcp_sg_vm2/*`

### C) Secrets hardening + AB outage remediation

Completed in production:

- Scheduler/runtime secrets moved to Secret Manager pattern.
- Startup scripts hardened to fetch secrets from GSM at runtime.
- AB outage root cause identified and fixed:
  - `catscan-api@catscan-prod-202601.iam.gserviceaccount.com` was disabled.
  - Service account re-enabled; API token flow recovered.

Operational records (local/private):

- `ops/private/SECRET_ROTATION_CHECKLIST.local.md`
- `ops/private/GCP_RECOVERY_RUNBOOK.local.md`
- `ops/private/snapshots/gcp-inventory-*.txt`

### D) UI/data correctness fixes (Moboost + sorting + metrics consistency)

Merged fixes include:

- `6a186b6`: config precompute null-click handling + RCA doc.
- `9aafc90`: creative filtering/pagination false no-data fix.
- `fccf49b` + `d47461d`: numeric sort correctness in pretargeting views.
- `6ceaa2d`: pretargeting modal metric handoff fix.
- `0b4fcfe`: adds publisher spend metric in Pubs page.

RCA:

- `docs/internal/2026-03-06-moboost-ui-data-audit-rca.md`

### E) Backup hardening and automation

Completed:

- New GH workflow: daily Cloud SQL logical export.
- Deploy checklist now includes backup posture gate.
- Live Cloud SQL safety settings enabled (deletion protection, backups/PITR).
- Backup bucket created and hardened; successful export verified.

Primary files:

- `.github/workflows/cloudsql-logical-backup.yml`
- `docs/DEPLOY_CHECKLIST.md`
- `ops/private/DB_BACKUP_POLICY.local.md`

## 3) Drift Status (Updated 2026-03-06)

Initial observation on 2026-03-06:

- `terraform/gcp_sg_vm2`: `PLAN_EXIT_CODE=0` (no changes).
- `terraform/gcp`: `PLAN_EXIT_CODE=2` with **1 in-place change**:
  - `google_sql_database_instance.rtbcat_serving.settings.deletion_protection_enabled: true -> null`

Resolution completed on 2026-03-06:

- `terraform/gcp/main.tf` updated to explicitly model the hardened setting:
  - `settings.deletion_protection_enabled = var.environment == "production"`
- Post-fix verification:
  - `(cd terraform/gcp && terraform validate -no-color)` -> success
  - `(cd terraform/gcp && terraform plan -detailed-exitcode -no-color)` -> `PLAN_EXIT_CODE=0` (no changes)
  - `(cd terraform/gcp_sg_vm2 && terraform plan -detailed-exitcode -no-color)` -> `PLAN_EXIT_CODE=0` (no changes)

Execution note for Codex/sandboxed environments:

- `terraform validate/plan` may fail in sandbox due provider socket restrictions (`setsockopt: operation not permitted`).
- Re-run those Terraform commands outside sandbox when this environment-specific error appears.

## 4) Open Items / Pending Decisions

1. SG2 isolation onto a separate staging DB is **in progress**.
- Terraform codification is done and validated (see Section 8), but apply + runtime cutover are still pending.
- Hard requirement if SG2 must be safe for experiments without production DB risk.

2. OAuth client secret rotation (Google OAuth web clients) is still manual-console work.
- Migration to GSM done; full rotation still pending.

3. Terraform backend is still local state.
- Current state files are local/gitignored; remote backend (GCS) is recommended.

4. Optional infra codification gap:
- `catscan-api@...` SA (the one that was disabled) is not yet clearly under Terraform governance.

## 5) First 15 Minutes for Next Agent

Run these before making changes:

```bash
git status --short --branch
git log --oneline -n 12
git tag --list | sort

curl -sS https://scan.rtb.cat/api/health
curl -sS https://vm2.scan.rtb.cat/api/health

(cd terraform/gcp && terraform validate -no-color)
(cd terraform/gcp_sg_vm2 && terraform validate -no-color)
(cd terraform/gcp && terraform plan -detailed-exitcode -no-color)
(cd terraform/gcp_sg_vm2 && terraform plan -detailed-exitcode -no-color)
```

Then choose one priority path:

- Path A: SG2 dedicated staging DB split.
- Path B: OAuth client secret manual rotation + verification.
- Path C: Terraform remote backend (GCS) migration.

## 6) Guardrails (Do Not Skip)

- Do not run destructive Terraform operations on production without reviewed plan.
- Do not disable/delete `catscan-api@...`; this breaks AB token refresh immediately.
- Keep secret values out of git and markdown; use GSM only.
- Keep `*.tfstate` and `*.tfvars` out of commits.
- Maintain inventory snapshots after every infra/security change.

## 7) File Map for Fast Navigation

- Versioning/release:
  - `docs/VERSIONING.md`
  - `docs/OSS_RELEASE_CHECKLIST.md`
  - `CHANGELOG.md`
- Deploy/runtime gates:
  - `docs/DEPLOY_CHECKLIST.md`
  - `.github/workflows/deploy.yml`
- Backup posture:
  - `.github/workflows/cloudsql-logical-backup.yml`
  - `ops/private/DB_BACKUP_POLICY.local.md`
- Terraform provenance:
  - `terraform/DRIFT_REPORT.md`
  - `terraform/IMPORT_MAP.md`
- Data integrity RCA:
  - `docs/internal/2026-03-06-moboost-ui-data-audit-rca.md`

## 8) SG2 Dedicated DB Path Update (2026-03-06)

What is now implemented in code:

- `terraform/gcp_sg_vm2` now supports a dedicated SG2 serving DB path:
  - Creates dedicated Cloud SQL instance + DB when `enable_dedicated_serving_db=true`.
  - Creates SG2-specific DB credentials secret (`catscan-serving-db-credentials-sg2`) and IAM access for SG2 service account.
  - Startup template now accepts:
    - `serving_db_secret_id`
    - `cloudsql_instance_name`
  - SG2 production tfvars now enable dedicated mode with explicit SG2 names.

Validation/plan results after this change:

- `(cd terraform/gcp_sg_vm2 && terraform validate -no-color)` -> success
- `(cd terraform/gcp_sg_vm2 && terraform plan -detailed-exitcode -no-color)` -> `PLAN_EXIT_CODE=2`
  - Plan delta: **4 to add, 0 to change, 0 to destroy**
  - Additions:
    - `google_sql_database_instance.sg2_serving`
    - `google_sql_database.sg2_serving_db`
    - `google_secret_manager_secret.sg2_serving_db_credentials`
    - `google_secret_manager_secret_iam_member.sg2_serving_db_credentials_access`
- `(cd terraform/gcp && terraform plan -detailed-exitcode -no-color)` -> `PLAN_EXIT_CODE=0` (no changes)

Important operational note:

- Updating `google_compute_instance.metadata_startup_script` would force VM replacement in this stack.
- To avoid destructive change, `metadata_startup_script` remains in `ignore_changes`.
- Result: SG2 VM runtime will not switch DB target from Terraform metadata alone until a controlled cutover step is executed.

Remaining cutover actions (manual/ops sequencing):

1. Apply SG2 Terraform additions (create dedicated Cloud SQL + SG2 DB secret resource).
2. Create DB user/password on SG2 dedicated instance and upload matching JSON payload to `catscan-serving-db-credentials-sg2`.
3. Perform controlled VM2 runtime cutover so `cloud-sql-proxy` points to `catscan-production-sg2-serving` and app env reads SG2 secret.
4. Post-cutover verify:
- `https://vm2.scan.rtb.cat/api/health`
- VM2 app DB connectivity
- Primary SG still points to and serves from `catscan-production-serving`.
