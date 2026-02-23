# Claude Prompt: VM2 B5 Browser Acceptance

Use this prompt in Claude Code (browser/MCP enabled) to run B5 UI validation on VM2 and update the acceptance doc.

---

You are validating B5 on staging (VM2) for RTBcat.

## Context

- Repo: `rtbcat-platform`
- Branch: `b4/import-quality-controls`
- Expected deployed SHA: `sha-b84af6e`
- Target URL: `https://vm2.scan.rtb.cat`
- VM host behind URL: `catscan-production-sg2`
- Acceptance doc to update: `docs/review/2026-02-16/VM2_ACCEPTANCE_B5.md`

## Hard constraints

- Do browser testing only.
- Do not deploy.
- Do not modify runtime config.
- Do not run migrations.
- Do not change production (VM1).

## Required checks

1. Version verification
- Log in to VM2.
- Confirm UI/footer version is `sha-b84af6e`.

2. UX-001: Data freshness banner
- On home dashboard, verify top bar shows:
  - `Data as of YYYY-MM-DD`, or
  - explicit pending state text.
- Record exact text and location.

3. UX-002: Campaign state persistence
- Open Campaigns page.
- Change:
  - view mode (`grid/list`)
  - sort field + direction
  - country filter
  - issues-only toggle
- Confirm URL query params update (`view`, `sort`, `dir`, `country`, `issues`).
- Refresh the page and confirm same state is preserved.

4. LANGUAGE-001: Geo mismatch visibility
- Open creatives triage surface (card/list, not preview modal first).
- Confirm mismatch badge is visible when mismatch exists.
- Capture one concrete example (creative id or card snippet).

5. RECS-001: Recommendation staged apply flow
- Find recommendation UI surface in current app.
- For at least one actionable recommendation:
  - verify config selector appears
  - click `Stage Change`
  - confirm success feedback or pending-change evidence
- For a non-actionable recommendation:
  - verify apply controls are not incorrectly shown.
- If this recommendation component is not wired in the active route, explicitly mark as `N/A (not wired)` with evidence (route/component behavior).

6. Regression checks
- Confirm no console errors across pages used above.

## Documentation + commit requirements

1. Update `docs/review/2026-02-16/VM2_ACCEPTANCE_B5.md`:
- Fill section 5 checklist with PASS/FAIL and evidence.
- Update section 7 verdict (`GO` or `NO-GO`) based on findings.
- In section 6, explicitly record LANGUAGE-002 decision:
  - `DEFER` or `IMPLEMENT NOW` (no schema changes in this run).

2. Commit and push doc update:
- Commit message: `docs(b5): record VM2 browser acceptance results`
- Push to branch: `b4/import-quality-controls`

## Required output format back to me

- Verdict: `GO` or `NO-GO`
- SHA validated in UI
- Table: check -> PASS/FAIL -> evidence
- Files changed + commit SHA
- Any blockers with exact file/route references

