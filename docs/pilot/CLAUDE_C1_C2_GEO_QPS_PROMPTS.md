# Claude Agent Prompts: Geo QPS Incident Set (Totals/% + Empty Observed QPS)

Use these exactly as written. Assign `C1` to Claude 1 and `C2` to Claude 2.

---

## C1 — Implement + Deploy Fix

```text
You are Claude 1. Work in a dedicated worktree to avoid conflicts.

Repository:
- /home/x1-7/Documents/rtbcat-platform
- Branch target: unified-platform

Incident:
- Geo QPS page shows incorrect values (example: Reached/Wins like e+62B, many rows at 100.0%).
- New production symptom (screenshot 2026-03-04 18:02:17): top RTB Endpoints card shows empty `Observed QPS` (`—`) while other data is present.
- Known suspect files:
  - dashboard/src/components/waste-analyzer/GeoAnalysisSection.tsx
  - home/QPS endpoint card + endpoint efficiency data path

Goal:
- Fix both:
  1) Geo totals/% correctness
  2) Empty `Observed QPS` regression in top RTB Endpoints card
- Add regression tests, push, deploy, and verify production.

Hard constraints:
1) Do NOT run destructive git commands.
2) Do NOT change DB schema/migrations.
3) Keep scope limited to this bug unless CI forces a directly related fix.
4) Use one cohesive commit for code/tests (plus a second only if absolutely required).

Execution steps:
1. Create/switch to a dedicated worktree branch from unified-platform.
2. Reproduce and inspect GeoAnalysisSection math path:
   - Sorting
   - totalReached and totalWins reduce
   - per-row wins + win_rate display
   - formatNumber inputs
3. Apply strict numeric coercion using shared util:
   - import { asNumber } from "@/lib/utils"
   - Coerce all geo numeric fields before compare/sum/format:
     reached_queries, bids, auctions_won, impressions, win_rate.
4. Ensure win-rate behavior is mathematically consistent and safe:
   - No string concatenation.
   - No NaN/Infinity.
   - Clamp only after valid numeric calc.
   - Handle zero denominator safely.
5. Add regression tests:
   - Numeric strings in API payload.
   - null/undefined/"N/A".
   - Large values.
   - Assert totals are finite and formatted correctly (no exponential garbage from concat issues).
6. Reproduce and fix `Observed QPS` empty regression:
   - Identify API source(s) used by RTB Endpoints card (`/analytics/home/endpoint-efficiency`, endpoint current feed, related frontend mapping).
   - Determine why UI gets/render `—` (null/undefined/missing path/stale mapping).
   - Implement minimal fix so:
     - valid observed QPS values render numerically,
     - unavailable state is explicit and reasoned (not silent empty),
     - total observed QPS is consistent with row-level values.
   - Add regression coverage for this path (data present vs unavailable).
7. Run:
   - dashboard tests relevant to this component
   - full dashboard test command (if practical)
   - dashboard build
8. Commit with message:
   - fix(qps-geo): coerce numeric fields before sorting/aggregation/render
9. Push to origin/unified-platform.
10. Monitor CI and deployment to completion.
11. Verify production on:
   - /1487810529/qps/geo
   - Confirm corrected totals and realistic % behavior
   - /1487810529 (QPS home)
   - Confirm top RTB Endpoints `Observed QPS` row values + total are populated or explicitly explained when unavailable
   - Confirm no console errors

Deliverable format:
A) Executive summary
B) Root cause (exact code-level)
C) Files changed
D) Test evidence (commands + pass/fail)
E) Build/deploy URLs
F) Before/after values from production
G) GO/NO-GO verdict
```

---

## C2 — Independent Verification + RCA Guardrail

```text
You are Claude 2. Work in a separate dedicated worktree from Claude 1.

Repository:
- /home/x1-7/Documents/rtbcat-platform
- Branch target: unified-platform

Mission:
- Independently verify whether the Geo QPS anomaly is frontend-only or also backend payload-related.
- Independently verify why top RTB Endpoints `Observed QPS` is empty (`—`) in production.
- Provide audit-grade evidence and a follow-up recommendation set.

Context:
- Symptom observed on production: /1487810529/qps/geo shows impossible totals/percentages.
- Additional symptom: /1487810529 top RTB Endpoints card shows empty Observed QPS (`—`) despite allocated QPS and active configs.
- Recent commits fixed toFixed crash but not necessarily aggregate math correctness.

Required analysis:
1. Inspect frontend code path:
   - dashboard/src/components/waste-analyzer/GeoAnalysisSection.tsx
   - Any related formatter/util usage
2. Inspect API contract/type expectations:
   - dashboard/src/lib/api/analytics.ts (GeoPerformance / RTBFunnel response types)
3. Pull actual runtime payload samples for buyer 1487810529 from API endpoints used by Geo QPS.
4. Pull payload samples for endpoint-efficiency/RTB-endpoints card data path and compare API vs rendered UI.
5. Determine:
   - Are numeric fields arriving as strings?
   - Are win_rate values already malformed upstream?
   - Is frontend reduction/sort/render logic causing corruption?
   - Is there any backend endpoint returning non-numeric values where numeric expected?
   - Is `Observed QPS` empty due to missing telemetry rows, stale endpoint mapping, frontend null handling, or API contract drift?

Parallel output requirement:
- Produce an RCA matrix with 3 columns:
  1) Evidence
  2) Interpretation
  3) Action required (frontend fix / backend fix / data contract fix / monitoring only)

If backend issue exists:
- Propose a minimal backend hardening patch (do NOT deploy unless asked).
- Include exact file/function candidates and acceptance criteria.

If frontend-only:
- State clearly that DB and backend are not the root cause for this incident.
- Recommend API response validation + typed coercion boundary tests.

Also add guardrail recommendations:
1) Contract test ensuring GeoPerformance numeric fields are finite numbers.
2) UI regression test for string/null numeric payloads.
3) Runtime telemetry warning when non-numeric values are detected.

Deliverable format:
A) Executive summary
B) Evidence table (endpoint payload excerpts + code refs)
C) Root cause decision: frontend-only / backend-only / both
D) Risk to users until fix live
E) Recommended immediate actions (P0/P1/P2)
F) GO/NO-GO for relying on current Geo table in production
G) GO/NO-GO for relying on current RTB Endpoints `Observed QPS` values
```
