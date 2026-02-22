# Claude Prompt: GCP/VM Drift RCA (Non-Code Configuration Audit)

You are acting as an SRE investigator for Cat-Scan. We have recurring incidents that may be caused by configuration drift outside the Git repo (GCP console settings, VM runtime state, scheduler, IAM, Docker env, Cloud SQL settings), not only application code.

## Objective

Determine whether recurring failures are caused by:
1. Code defects in repo, or
2. Environment/config drift outside repo (VM/GCP/Terraform mismatch), or
3. Both.

Then provide a concrete remediation plan with evidence.

## Scope

Audit and compare all of these layers:
- Repo-managed config: Terraform, deploy scripts, GitHub Actions workflows, docker-compose, `.env` templates, migration runner.
- VM2 vs VM1 runtime config: effective `.env`, container args, worker counts, systemd services/timers, cron/scheduler jobs, mounted volumes, permissions.
- GCP settings: Cloud Scheduler jobs, IAM bindings, service account roles, Secret Manager usage, firewall rules, Cloud SQL instance/flags/users/networks, DNS records, load balancer/backend health checks.
- Operational controls: restart policies, lock files, advisory locks, migration execution order, precompute/import worker concurrency.

## Critical Questions To Answer

1. Is there any drift between Terraform/state and actual GCP resources?
2. Is VM1 configured differently from VM2 in any way that affects imports, migrations, precompute, or API uptime?
3. Are there hidden manual changes in GCP/VM that are not represented in code?
4. Are duplicate or overlapping schedulers triggering concurrent jobs?
5. Are deploy scripts idempotent and safe under multi-worker startup?
6. Do we have durable data paths in production, or any accidental ephemeral behavior?

## Method

Use this sequence and capture evidence for each step:
1. Build an "expected config" matrix from repo (Terraform/workflows/deploy docs).
2. Capture "actual config" from VM2 and VM1 (read-only first).
3. Capture "actual config" from GCP (read-only first).
4. Diff expected vs actual and classify each mismatch:
   - harmless
   - risk
   - incident-causing
5. Correlate mismatches with incident timelines and commit SHAs.

## Output Format (strict)

Produce these sections:

1. **Executive Verdict**
- Primary root cause category (code, drift, or both)
- Confidence level (%)

2. **Evidence Table**
- `Finding`
- `Layer` (repo / VM / GCP)
- `Expected`
- `Actual`
- `Evidence` (exact command/log/path)
- `Severity`

3. **Incident Correlation**
- Map each recurring symptom to exact cause and triggering conditions.

4. **Fix Plan**
- Immediate containment actions
- Permanent fixes (code + infra)
- Drift-prevention controls (CI checks, startup checks, config assertions)
- Rollback plan for each risky change

5. **PR/Change List**
- Files to edit in repo (if any)
- GCP resources to change (with `gcloud`/Terraform commands)
- VM commands (exact, copy-pasteable)

## Constraints

- Do not modify production (VM1) without explicit approval.
- Prefer read-only inspection first.
- For every claim, provide concrete evidence.
- If evidence is missing, state "unknown" explicitly instead of guessing.
