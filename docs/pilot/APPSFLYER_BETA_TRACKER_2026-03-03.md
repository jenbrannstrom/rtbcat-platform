# AppsFlyer Beta Tracker (4 Customers)

Date: March 3, 2026  
Owner: Cat-Scan Ops

## Status Legend

- `No AF`: no AppsFlyer URLs detected in sampled creatives.
- `AF no clickid`: AppsFlyer URLs found, but clickid signal not detected.
- `AF exact-ready`: AppsFlyer + clickid detected in creatives.
- `Postbacks live`: conversion events observed for the seat.
- `Exact joins live`: `exact_clickid` mode has matched rows.

## Seat Tracker

| Customer | Buyer ID | Endpoint | Creative Status | Postbacks | Exact Joins | Last Evidence | Owner | Next Action |
|---|---:|---|---|---|---|---|---|---|
| Tuky Display | `299038253` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253` | `AF exact-ready` | `Pending` | `Pending` | `sha-0336013`: click-macro summary shows non-zero AppsFlyer/clickid | Ops + Customer | Collect first test postback and run Phase A + Phase B |
| Amazing Design Tools LLC | `1487810529` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=1487810529` | `No AF` (current) | `Pending` | `Pending` | Needs customer confirmation of AppsFlyer click URL usage | Ops + Customer | Send onboarding email, ask for one test event |
| Amazing Moboost | `6574658621` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6574658621` | `No AF` (current) | `Pending` | `Pending` | Low app-install footprint in prior audit | Ops + Customer | Confirm if AppsFlyer is in use; if yes send one test event |
| Amazing MobYoung | `6634662463` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6634662463` | `No AF` (current) | `Pending` | `Pending` | Primarily non-app inventory in prior audit | Ops + Customer | Confirm AppsFlyer usage or fallback conversion path |

## Validation Commands (Run Per Seat)

Set identity once:

```bash
export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
```

1) Primary one-command live validation (recommended):

```bash
scripts/run_appsflyer_pilot_live_validation.sh --buyer-id <BUYER_ID>
```

Expected result:
- `PASS`: endpoints healthy + postbacks live + exact joins live.
- `BLOCKED`: infrastructure healthy but waiting for first postback and/or exact match.
- `FAIL`: endpoint/auth/runtime failure that needs operator action.

2) Manual step breakdown (fallback/operator debug):

2.1 Pilot readiness snapshot:

```bash
scripts/run_tuky_appsflyer_pilot_check.sh --buyer-id <BUYER_ID> --timeout 90
```

2.2 Phase A audit from ingested DB events:

```bash
scripts/run_appsflyer_phase_a_audit.sh --buyer-id <BUYER_ID> --from-db --db-since-days 30
```

2.3 Phase B attribution report:

```bash
scripts/run_conversion_attribution_phase_b_report.sh --buyer-id <BUYER_ID> --source-type appsflyer --days 14
```

3) GitHub workflow alternative (same validation, artifacted):

- Workflow: `v1-appsflyer-pilot-live-validation.yml`
- Manual dispatch inputs:
  - `buyer_id`
  - `source_type` (default `appsflyer`)
  - `days`
  - `fallback_window_days`
  - `strict_phase_b_refresh` (optional hard mode)

## Promotion Rule

Promote a seat from `Pending` to live beta when all are true:

1. `AF exact-ready` on click-macro coverage.
2. `Postbacks live` with accepted events > 0.
3. `Exact joins live` with matched rows > 0 in `exact_clickid` mode.
4. No security regressions on conversion webhook posture.

## Evidence Links (Fill As Runs Complete)

| Buyer ID | Pilot Check Report Path | Phase A Report Path | Phase B Report Path | Notes |
|---:|---|---|---|---|
| `299038253` |  |  |  |  |
| `1487810529` |  |  |  |  |
| `6574658621` |  |  |  |  |
| `6634662463` |  |  |  |  |
