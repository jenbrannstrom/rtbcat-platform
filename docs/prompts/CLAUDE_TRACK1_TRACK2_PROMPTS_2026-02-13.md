# Claude Prompts: Track 1 + Track 2 (2026-02-13)

## Track 1 Prompt (Secret + Bootstrap Hardening)

You are working on **Track 1 only**: secret/bootstrap hardening for clean installs.
Do **not** work on Track 2 (pending-change/suspend 500 bugs) in this task.

### Context
- Repo: `/home/x1-7/Documents/rtbcat-platform`
- Goal: make OSS install secure-by-default for **single-tenant safety-first**.
- Current risk:
1. Sensitive values exist in local plaintext Terraform artifacts (`terraform/gcp_sg_vm2/terraform.tfvars`, `terraform/gcp_sg_vm2/terraform.tfstate`).
2. VM startup auto-fetches AB key and may pre-seed credentials on install (`terraform/gcp_sg_vm2/startup.sh`).
3. With OAuth-gated nginx + auto-provision, first Google user can become admin when user table is empty (`api/session_middleware.py`).

### Objective
Implement a secure install flow where:
1. Secrets are sourced from Google Secret Manager, not plaintext tfvars/template literals.
2. Fresh install starts with no AB key active in app unless explicitly intended.
3. First admin creation is explicit and controlled (no accidental first-Google-user admin takeover).
4. Existing deployment remains operable with clear migration/rotation steps.

### Hard guardrails
1. Never print or commit raw secret values.
2. Do not add hardcoded secrets anywhere.
3. Do not run destructive infra changes without explicit approval.
4. Do not trigger live Google pretargeting mutations as part of verification.
5. Keep changes minimal and auditable; prefer secure defaults with explicit override flags.
6. If backward compatibility is impacted, include a migration toggle and document it.

### Required implementation work
1. Refactor Terraform/VM startup secret handling.
2. Remove secret-value injection into startup template vars in `terraform/gcp_sg_vm2/main.tf`.
3. Replace secret value vars with secret **ID/name references** where needed.
4. In `terraform/gcp_sg_vm2/startup.sh`, fetch needed secrets at runtime from GSM using `gcloud secrets versions access`.
5. Ensure startup logs never echo secret contents.
6. Decide and implement AB credential boot policy:
7. Default mode should be **manual-key mode** (no automatic AB key activation on fresh install).
8. Optional explicit flag for preseed mode is acceptable, but default must be safe.

9. Harden first-admin bootstrap flow.
10. Set default behavior so unknown OAuth users are **not** auto-created unless explicitly enabled.
11. Introduce explicit bootstrap mechanism for first admin (token or CLI-assisted claim flow), one-time and auditable.
12. Ensure once first admin exists, normal controls continue (single-tenant restrictions preserved).

13. Add/update documentation.
14. Create a concise runbook with:
15. Required GSM secrets.
16. Secret rotation steps (including OAuth secret).
17. Fresh-install bootstrap sequence.
18. How to verify “empty app until key upload”.
19. Rollback path.

20. Add lightweight checks/tests where practical.
21. Add at least one automated check for bootstrap gating logic.
22. Add at least one check that startup/config path does not require plaintext secret files in repo.

### Files likely involved
- `terraform/gcp_sg_vm2/main.tf`
- `terraform/gcp_sg_vm2/variables.tf`
- `terraform/gcp_sg_vm2/startup.sh`
- `api/session_middleware.py`
- `api/auth_authing.py` (if needed)
- `api/auth_password.py` (if needed for first-admin bootstrap consistency)
- `docs/SECURITY.md`
- `docs/AUTHENTICATION.md`
- Add a new runbook doc under `docs/` for this hardening rollout.

### Acceptance criteria
1. No secret values in tracked Terraform inputs or startup template substitutions.
2. Fresh VM install does not auto-enable AB API credentials by default.
3. First admin cannot be created accidentally via first OAuth login.
4. Explicit bootstrap succeeds and is one-time.
5. Existing login/auth still works after bootstrap.
6. Documentation is complete enough for another engineer to execute safely.
7. Provide evidence commands and outputs (masked where needed).

### Verification checklist to execute
1. Static grep checks proving no plaintext secret literals in modified IaC/startup files.
2. Fresh-install simulation (or VM dry run) showing app starts without AB credentials configured.
3. Auth check showing unknown OAuth user is denied before bootstrap.
4. Bootstrap action creates first admin successfully.
5. Post-bootstrap login works and admin can reach setup pages.
6. Health/status behavior aligns with expected “not configured until key added”.

### Output format required
1. Summary of changes.
2. Security rationale (what risk each change removes).
3. Exact files changed.
4. Verification evidence.
5. Remaining risks and follow-ups.
6. Explicit note that Track 2 bugs were intentionally not touched.

---

## Track 2 Prompt (Fix Two Backend 500s)

You are working on **Track 2 only**: fix the two backend 500 errors reported after SHA `sha-4ab7628`.
Do **not** change Track 1 secret/bootstrap architecture in this task.

### Context
Repo: `/home/x1-7/Documents/rtbcat-platform`

Claude validation found:
1. `POST /settings/pretargeting/pending-change` can 500 due to `created_at` type mismatch.
2. `POST /settings/pretargeting/{billing_id}/suspend` can 500 with:
   `the JSON object must be str, bytes or bytearray, not dict`

Frontend wiring is already present and verified; backend response serialization is blocking stable behavior.

### Objective
Eliminate both 500s safely and add regression tests so they don’t return.

### Hard guardrails
1. Do not perform live Google config mutations in verification.
2. Do not broaden scope to UI rewrites or infra/security redesign.
3. Keep API contracts backward-compatible unless absolutely necessary.
4. If contract field type must change, do it deliberately and update all dependent code + tests.
5. No destructive DB operations.
6. Keep changes focused, minimal, and test-backed.

### Required implementation work

#### A) Fix pending-change response serialization
1. Inspect:
   - `api/routers/settings/models.py`
   - `api/routers/settings/changes.py`
2. Root issue: `PendingChangeResponse.created_at` currently expects `str`, but DB/repo may return `datetime`.
3. Implement one consistent approach across settings models/routes:
   - Either use `datetime` in response model and let Pydantic serialize ISO.
   - Or explicitly convert to ISO strings at route/service boundary.
4. Ensure all `PendingChangeResponse` constructors in settings routes are consistent.

#### B) Fix suspend endpoint 500 (`json.loads(dict)` class of bug)
1. Inspect:
   - `api/routers/settings/actions.py`
   - `services/actions_service.py`
   - `services/snapshots_service.py`
2. Likely fault: parsing `raw_config` as JSON string when Postgres JSONB already returns dict.
3. Implement safe JSON normalization utility for these paths:
   - If value is dict/list: use as-is.
   - If value is string: `json.loads`.
   - If null/invalid: fallback safe empty object.
4. Apply in snapshot creation and any action flow that parses config JSON.
5. Verify suspend path returns `SuspendActivateResponse` successfully.

#### C) Regression tests
Add tests covering:
1. Pending change create/list endpoints return 200 and valid `created_at` serialization.
2. Suspend endpoint does not throw serialization error when `raw_config` is dict-like JSONB.
3. (Optional but preferred) Activate endpoint symmetry test.
4. Keep tests isolated (mock external Google client calls).

### Files likely involved
- `api/routers/settings/models.py`
- `api/routers/settings/changes.py`
- `api/routers/settings/actions.py`
- `services/actions_service.py`
- `services/snapshots_service.py`
- relevant tests under `tests/` (add new settings/action tests if needed)

### Acceptance criteria
1. `POST /settings/pretargeting/pending-change` no longer 500s on `created_at` mismatch.
2. `POST /settings/pretargeting/{billing_id}/suspend` no longer 500s from JSON type parsing.
3. Tests added and passing for both bug classes.
4. No regression in existing settings routes.
5. No live Google mutation required for verification.

### Verification checklist to execute
1. Run targeted tests for settings/actions (and any touched suites).
2. Run basic API smoke (or unit-level route tests) for:
   - pending-change create/list
   - suspend/activate route response shape
3. Provide concise evidence outputs.
4. If any test is infeasible in local env, state exactly what was skipped and why.

### Output format required
1. Summary of fixes.
2. Root cause explanation for each 500.
3. Exact files changed.
4. Test evidence.
5. Any residual risk.
6. Explicit note that Track 1 secret/bootstrap hardening was intentionally not touched.
