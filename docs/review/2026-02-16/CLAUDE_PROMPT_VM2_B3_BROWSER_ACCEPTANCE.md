# Claude Prompt: VM2 B3 Browser Acceptance (MCP)

Use this prompt in Claude (with browser MCP enabled).

---

You are validating B3 browser acceptance on VM2 for `rtbcat-platform`.

## Objective

Complete the **manual browser validation** for:

- `docs/review/2026-02-16/VM2_ACCEPTANCE_B3.md`

Target environment:

- URL: `https://vm2.scan.rtb.cat`
- VM: `catscan-production-sg2`
- Expected deployed SHA: `sha-93e7793`

## Scope

Do browser testing only. Do not deploy, do not change runtime config, do not run migrations.
Only edit docs if needed (the acceptance file above).

## Required checks (must all be executed)

1. Open VM2 and authenticate.
2. Confirm deployed version in UI is consistent with `sha-93e7793` (footer/sidebar version text if visible).
3. Navigate to Waste Analysis page.
4. Verify visible QPS labels are explicitly **`Avg QPS`** (not ambiguous `QPS`).
5. Open browser DevTools:
   - Network tab: inspect `/api/analytics/waste` response.
   - Confirm JSON includes: `"qps_basis": "avg_daily"`.
6. Console tab:
   - Confirm no red runtime errors on dashboard home and waste-analysis pages.
7. Quick regression pass:
   - Home dashboard loads.
   - Waste Analysis page loads.
   - No obvious breakages in those two surfaces.

## Evidence requirements

For each check, record:

- timestamp (UTC),
- PASS/FAIL,
- short evidence note (actual observed text/value),
- if FAIL: root cause hypothesis and exact blocking symptom.

## File update required

Update this file with actual results:

- `docs/review/2026-02-16/VM2_ACCEPTANCE_B3.md`

Specifically:

1. Section `6) Manual Browser Validation (Pending)`:
   - mark each checklist item `[x]` or `[ ]` with real outcome.
2. Section `7) Final Go/No-Go`:
   - set final verdict `GO` only if all required checks pass.
   - otherwise `NO-GO` with blocking reason.
3. Section `8) Execution Log`:
   - append rows for this browser validation run.

## Output format (chat response)

Return:

1. One-line verdict: `GO` or `NO-GO`.
2. Table with checks, result, evidence.
3. Exact file diff summary for `VM2_ACCEPTANCE_B3.md`.
4. If NO-GO: minimal fix list ordered by severity.

## Guardrails

- Do not claim PASS without direct observed evidence.
- Do not infer `qps_basis`; verify from actual network payload.
- Keep changes limited to acceptance docs unless explicitly asked.

