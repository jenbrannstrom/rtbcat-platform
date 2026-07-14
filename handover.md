# Handover

## Current Production Handover (July 14, 2026)

Supersedes the June 12 notes (kept below). Author: incident session of July
13-14, 2026 (MobYoung daily-spend RCA). Full evidence-backed RCA:
`investigations/RCA-mobyoung-daily-spend-2026-07-13.md`.

### Incident summary — MobYoung `/api/agent/v1/daily-spend` (buyer 6634662463)

Client reported 2 missing days (2026-07-05, 2026-07-12) for July 1-12. Actual
findings were three distinct defects:

- **07-01 published DOUBLED** (18,211.82 vs true 9,105.909962): an out-of-band
  replay of the spend CSV on 07-11 appended a duplicate batch (`583a4d26`, no
  import_history row) to BigQuery `rtb_daily`, and a manual precompute refresh
  materialized the sum. Fixed 07-13: batch backed up to
  `rtbcat_analytics.rtb_daily_dupbatch_583a4d26_bak_20260713`, deleted,
  day re-materialized. Verified.
- **07-05 missing because Google never delivered** the
  `catscan-bidsinauction-6634662463` email on 07-06 (mailbox searched incl.
  spam/trash; 4 of 5 report kinds arrived; that delivery weekend was visibly
  degraded). Not an importer bug. Recovery in flight — see below.
- **07-12 was plain D+1 latency** (email arrived 07-13 10:00 UTC, after the
  client checked). Ingested 07-13 (batch `d645c3b8`, 4,991,479,984 micros).
  On 07-14 a mis-scoped owner re-run (named `12JULY`, contained metric 07-12,
  display-formatted) was auto-ingested and the inline publisher DOUBLED the
  day for ~1h. Fixed same hour: backup
  `rtb_daily_dupbatch_adc8623e_bak_20260714`, deleted from BQ + PG,
  republished. That AB schedule is deleted.

Client-facing arithmetic: the 11 verified days total 123,084,809,581 micros.
The client's UI figure (141,613.90) is ~1,954 over-scoped (likely included a
July-13 partial or timezone slice); with 07-05 (~16,575) the true range total
lands ≈139,660. Ask them to re-pull the UI for exactly Jul 1-12 UTC and
compare per-day values.

### In flight (2026-07-15 morning)

Owner scheduled a `5JULY` AB query re-run: delivers ~10:00 UTC 07-15, the
10:15 UTC import ingests it, and the inline publisher (#108
`publish_buyer_spend_range`) publishes metric 07-05 automatically. One-shot
`catscan-postwave-dupcheck` (10:50 UTC, systemd transient on the VM) runs the
delivery watchdog early in case that query is mis-scoped onto an existing day
(which the inline publisher would double). Afterwards verify 12/12 days:
`SELECT metric_date, spend_micros FROM rtb_buyer_spend_daily WHERE
buyer_account_id='6634662463' AND metric_date BETWEEN '2026-07-01' AND
'2026-07-12'`.

### Live production changes made this week (already applied)

- Cloud Scheduler `gmail-import` schedule changed `0 12,15,18 * * *` →
  `15 10,12,15,18 * * *` (report wave lands 10:00-10:07 UTC; the 12:00 first
  run left spend ~2h stale daily). Mirrored in terraform + provision config on
  the PR branch (terraform had drifted to the single pre-#109 run).
- New systemd timer on the VM: `catscan-report-delivery-check.timer`
  (13:45 + 19:15 UTC daily) → runs `scripts/check_report_delivery.py` inside
  `catscan-api` (state-dir fallback copy at
  `/home/catscan/.catscan/check_report_delivery.py`). Per seat it checks:
  report emails arrived on their normal day (expected set learned from a
  14-day lookback), canonical spend-lane rows present, and a **trailing
  14-day duplicate-batch sweep**. Status JSON:
  `/home/catscan/.catscan/report_delivery_status.json`; journal:
  `journalctl -u catscan-report-delivery-check.service`. Validated against
  the real 07-05 signature and a healthy control day.
- BigQuery backup tables `rtb_daily_dupbatch_*_bak_*` hold the two deleted
  duplicate batches; drop them once the client confirms reconciliation.

### Pending review: PR #110 (draft, branch `fix/daily-spend-completeness`)

Five commits, 918 tests passing: (1) `/api/agent/v1/daily-spend` summary gains
`complete` / `missing_dates[]` / `latest_complete_date` (additive — until
deployed, the API signals gaps only via warnings/per-day source_status);
(2) Gmail discovery becomes unread-independent (rolling `newer_than:` window +
`gmail_processed_messages` ledger, **migration 070 applies at deploy**);
(3) per-seat D+1 missing-spend alerting in status JSON/API + canary;
(4) the delivery watchdog script; (5) the scheduler mirror.

### Operational gotchas learned the hard way (do not relearn)

- **The BQ lane is append-only with no idempotency**: re-running any spend CSV
  through the pipeline appends a new batch and the inline publisher multiplies
  the published day within minutes. Before ANY historical refresh, scan for
  multi-batch days (`COUNT(DISTINCT import_batch_id) > 1` per buyer/date,
  `report_type='buyer_spend'`). Three double-count incidents in one week trace
  to this; making the lane idempotent is the top follow-up.
- **Never race Gmail labels to block an import**: `is:unread` search results
  lag just-changed labels by minutes (a read-quarantine 8 minutes before a run
  failed). Take `~/.catscan/gmail_import.lock` or pause the scheduler job.
- **Newly created AB saved queries export display-formatted data** ($ prefixes,
  2dp, `m/d/yy`) even when email-delivered; only the original scheduled
  reports carry machine 6dp. The importer parses the display format correctly,
  and the 2dp cost is only ~±0.3/day — but don't expect 6dp equality.
- **The 22:30 precompute window is 2 days**; any metric date landing in BQ
  later than D+1 is never re-materialized without a manual/inline refresh.
- `docker exec` survives SSH-session death: never re-run a "timed-out"
  refresh — check `/proc/*/cmdline` in the container first (two concurrent
  refreshes contended for ~45 min on 07-13). For long jobs use
  `docker exec -d ... > logfile`.

### Open issues for the next engineer

- **Seat 299038253 has ZERO `buyer_spend`-lane rows in BigQuery** despite
  daily `catscan-bidsinauction` emails that import successfully — its file
  shape must be classifying to a different report_type. The watchdog alerts
  on it daily by design. Pre-existing; uninvestigated.
- Parquet→BQ idempotency (see gotchas — top priority).
- On-VM/state-dir pipeline scripts have drifted from the repo
  (`export_csv_to_parquet.py`, `load_parquet_to_bigquery.py`,
  `bq_aggregate_to_pg.py` live in `/home/rtbcat/.catscan/`); reconcile them
  into git.
- Local checkout note: this working tree sits on `codex/live-major-smoke`
  with local changes; deployed code == `origin/main`. Compare against
  `origin/main`, not the working tree.

## Previous Handover (June 12, 2026)

This is the previous handover as of **June 12, 2026**. It supersedes the June
7/June 10 language-flags notes and removes the archived April/May creative QA
scope (see git history for those).

The user wants GitHub to be the source of truth. Production must be recoverable
from GitHub, Terraform, Google Secret Manager, Cloud SQL, Cloud Scheduler,
Artifact Registry, and documented scripts. The user does not want to keep an
expensive staging VM.

## Production State

- GCP project: `catscan-prod-202601`
- Production URL: `https://scan.rtb.cat`
- Current deployed commit: `7d06facb`
- Production health: `/api/health` returns 200 with `git_sha: 7d06facb`,
  `version: sha-7d06fac`, and `release_version: 0.9.5`
- Latest production deploy: GitHub Actions run `27403711752`, success — first
  fully green contract gate in the June 11-12 sequence (no
  `ALLOW_CONTRACT_FAILURE` bypass)
- Production VM: `catscan-production-sg`, `RUNNING`, IP `34.143.222.60`
- Staging/old VM: `catscan-production-sg2`, `TERMINATED` (retired May 2026,
  snapshot `catscan-production-sg2-retirement-20260506-0327` kept). The deploy
  workflow only supports `production`.
- Terraform state bucket: `gs://catscan-prod-202601-tfstate`, prefix
  `terraform/gcp`
- Production access from a workstation: `gcloud --account=billing@amazingdo.com`
  with `--tunnel-through-iap` (plain SSH times out)

Do not restart or use `catscan-production-sg2` unless explicitly asked. It is
stopped, but not deleted.

## Latest Production Commits (June 10-12)

All pushed to `main` and deployed (`7d06facb` is live):

- `7d06facb` `Stop marking allowlist-skipped Gmail reports as read`
- `7f605551` `Coalesce null aggregates in config precompute`
- `e93e1242` `Fix observed QPS to use bid_requests instead of reached_queries`
- `01c9820d` `Update CLAUDE.md deploy notes: staging retired, production-only`
- `f8fe443c` `Add buyer data purge script for decommissioned seats`
- `d0f9c129` `Update handover and add language flags redesign spec`
- `9da8b58f` `Warn when bids-in-auction data is missing for win rate`
- `4b275db3` `Fix diagnostic findings: auth, metrics, hot-path queries, dead code, i18n`

## What Changed (June 11-12)

### Full-codebase diagnostic fixes (`4b275db3`, `9da8b58f`)

- Adjust (`/conversions/adjust/callback`) and Branch
  (`/conversions/branch/webhook`) webhooks added to `PUBLIC_PREFIXES`; they were
  being 401'd by auth middleware before their HMAC checks could run.
- Agent stats `win_rate_pct` now computes `auctions_won / bids_in_auction`
  (per METRICS_GUIDE) from `home_config_daily`; the old impressions/reached
  number is preserved as `efficiency_rate_pct`. A payload warning fires when a
  buyer has impressions but no bids-in-auction data.
- Creatives list waste-flags path is precompute-first (no more batch
  `rtb_daily` aggregation per page load; clicks fetched from `rtb_daily` only
  for the small zero-engagement candidate subset).
- Removed dead code: unregistered QPS router stack (`api/routers/qps.py`,
  `services/qps_service.py`, `api/schemas/qps.py`) and the superseded in-app
  docs router (docs live at docs.rtb.cat).
- Nine silent no-op `PostgresStore` stubs now raise `NotImplementedError`;
  `/performance/import` and `/performance/metrics` return HTTP 501 instead of
  fake success.
- Language-flags page fully translated in all 11 locales (was English/Chinese
  only; the other 9 had zero keys).

### Observed QPS equation fix (`e93e1242`)

`rtb_endpoints_current.current_qps` was derived from `reached_queries`, which
is a post-bid funnel stage — it understated endpoint traffic ~1800x (showed
21.5 QPS against a 46,500 allocation; reality is ~39,000 QPS, ~84%
utilization). Now derived from `bid_requests`. Verified semantics (production
seat `1487810529`, 7d averages): `bid_requests` 39,074/s ≈
`successful_responses` 38,029/s = endpoint traffic; `bids` 53/s;
`reached_queries` 21.5/s; `auctions_won` 19.6/s. See METRICS_GUIDE.md funnel
section (corrected June 2026).

### Gmail importer silent skip RCA + fix (`7d06facb`)

- Root cause: emails whose seat ID was not in `CATSCAN_GMAIL_SEAT_IDS` were
  skipped AND marked read, while the importer only searches `is:unread` —
  silently destroying reports with zero trace in `ingestion_runs`,
  `import_history`, or the status file.
- Impact: seat `7942355670` (Amazing Start) was never in the allowlist; ~3.5
  weeks of its reports (May 19 - June 10) were lost this way.
- Recovery: one-off `CATSCAN_GMAIL_QUERY` run re-imported the read backlog —
  110 files, 307,671 `rtb_daily` rows. Home/config precompute backfilled for
  May 19 - June 10.
- Fix: allowlist-skipped emails now stay unread (self-healing backlog once the
  seat is allowlisted) and skip counts/seat IDs persist in the import status
  (`last_emails_skipped`, `last_skipped_seat_ids`).
- `CATSCAN_GMAIL_SEAT_IDS` now contains all six seats:
  `1487810529,299038253,6574658621,6634662463,8087233591,7942355670`.

### Precompute null crash fix (`7f605551`)

`SUM(spend_micros)` over all-null rows returned NULL and violated the
`fact_delivery_daily` NOT NULL constraint, rolling back entire
config-breakdown refresh transactions. All precompute aggregates are now
COALESCEd to 0.

### Seat / account changes (DB state, June 11)

- `8087233591` "Tuky internet" (replaces decommissioned Tuky Display):
  discovered, active, full report coverage, precompute backfilled
  May 21 - June 9. `dea@rtb.cat` re-pointed to it in
  `user_buyer_seat_permissions` (old `299038253` grant removed).
- `299038253` "Tuky Display": seat deactivated (row kept). Its ~41.8M Postgres
  rows are archived in place until **2026-09-11**, then purged via
  `scripts/purge_buyer_data.py` (date-gated `--execute`). Schedule marker:
  `system_settings` key `data_deletion.299038253`. A one-time cloud routine
  (`trig_015RcrCDKnJHdhUcDuCLUJCw`) fires 2026-09-11 06:00 UTC with the
  runbook. Gmail source emails are kept.
- `7942355670` "Amazing Start": active, data recovered (see above).
- RBAC reminder: only `sudo` users (`cat-scan@rtb.cat`) see all seats; other
  users see exactly one seat via `user_buyer_seat_permissions` (single-seat
  policy in `api/dependencies.py`). "Discover seats" saves to `buyer_seats`
  but does not grant the clicking user visibility.

## Carried-over: VIDEO language evidence RCA (from June 10)

Buyer `299038253` creative `216139` and an adjacent `216xxx` cluster showed
`ZH mismatches VNM` on visibly Vietnamese videos. RCA: for `VIDEO`,
`LanguageAnalyzer.extract_text_from_creative()` sends VAST metadata
(`AdTitle`/`Description`/`HTMLResource`) to the language model and returns on
first success, never reaching video-frame OCR/vision. Fix direction (not yet
implemented):

- Prefer visible evidence (video frame OCR/vision) for `VIDEO`; treat VAST
  fields as metadata, not dominant creative language.
- Surface `language_source` and `language_confidence` (already in
  `api/schemas/creatives.py` coverage rows) in the dashboard Language Flags
  page/modal so future RCA can distinguish evidence sources.

Note: `299038253` is now decommissioned, but the same pipeline behavior
applies to all seats.

## Operational Notes

- Terraform state is in GCS; future Terraform operations need correctly
  privileged ADC credentials (an early apply failed on
  `secretmanager.secrets.create`).
- `docker restart` does NOT re-read `/opt/catscan/.env` — container env only
  updates on recreation (deploy or `refresh_gcp_vm_runtime_env.sh
  --recreate-api`). Hot-patched files via `docker cp` DO survive restarts but
  not recreation.
- Ad-hoc production DB access: run Python inside `catscan-api` using
  `storage.postgres_database` helpers — `pg_query` for SELECTs (it
  fetches and will roll back writes), `pg_execute` for writes.
- The deploy workflow's post-deploy contract gate updates
  `rtb_endpoints_current` and fails the run on data-freshness contract
  violations even when the deploy itself succeeded — check `/api/health`
  `git_sha` before assuming a "failed" deploy didn't ship.

## Remaining Work

1. Implement the VIDEO evidence-priority fix and surface
   `language_source`/`language_confidence` in the Language Flags UI (see
   carried-over RCA above).
2. Execute the `299038253` purge on/after **2026-09-11** (cloud routine will
   open the runbook; one command on the production VM).
3. Per-config win rates in agent stats: `bids_in_auction` arrives without
   `Billing ID` (Google blocks the combination), so config-level rows may
   under-report. DATA_MODEL.md documents a CSV1+CSV2 join on
   (day, creative_id) that `home_precompute.py` does not implement yet.
   Buyer-level totals are correct.
4. Residual language-flags QA for Amazing Design Tools (`1487810529`): 25
   language-market alerts, 207 `no content` analysis errors, broad geo alerts.
5. Delete or fully retire `catscan-production-sg2` and release its static IP
   once permanent deletion is confirmed.
6. Run a full Terraform plan with privileged credentials and review drift.
7. Address the GitHub Actions Node.js 20 deprecation warnings before GitHub's
   Node 24 default cutoff (June 16, 2026 per run annotations).
8. Untracked local files not from this work: `manual/explainers/`,
   `manual/index.md` (modified), and
   `.github/workflows/trigger-docs-freshness.yml` — review and commit or
   discard deliberately.

## Useful Commands

Production health:

```bash
curl -sS https://scan.rtb.cat/api/health
```

SSH to production (IAP required):

```bash
gcloud compute ssh catscan-production-sg \
  --project=catscan-prod-202601 \
  --zone=asia-southeast1-b \
  --account=billing@amazingdo.com \
  --tunnel-through-iap
```

List Scheduler jobs without printing secret headers:

```bash
gcloud scheduler jobs list \
  --project=catscan-prod-202601 \
  --location=asia-southeast1 \
  --format='table(name,state,schedule,timeZone,httpTarget.uri)'
```

Refresh VM runtime env from GSM after a secret rotation (recreates the API
container, picking up `.env` changes):

```bash
gcloud compute ssh catscan-production-sg \
  --project=catscan-prod-202601 \
  --zone=asia-southeast1-b \
  --tunnel-through-iap \
  --command "cd /opt/catscan && sudo bash scripts/refresh_gcp_vm_runtime_env.sh --recreate-api"
```

Gmail import status (inside the API container):

```bash
sudo docker exec catscan-api python3 scripts/gmail_import.py --status
```

Decommissioned-buyer purge dry run (date-gated execute):

```bash
sudo docker exec catscan-api python3 scripts/purge_buyer_data.py --buyer 299038253
```
