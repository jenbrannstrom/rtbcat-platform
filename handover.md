# Handover

## Current Production Handover

This is the current handover as of **July 10, 2026**. It supersedes the June
12 handover (which it extends; the June incident RCAs below are kept) and is
the companion to `retirement-notes.md` (CTO retrospective + Hetzner migration
opinion, 2026-07-09).

The user wants GitHub to be the source of truth. Production must be recoverable
from GitHub, Terraform, Google Secret Manager, Cloud SQL, Cloud Scheduler,
Artifact Registry, and documented scripts. The user does not want to keep an
expensive staging VM.

## Production State

- GCP project: `catscan-prod-202601`
- Production URL: `https://scan.rtb.cat`
- Current deployed commit: `6b3f2b19` (merge of PR #100, retirement-notes
  findings), containers on image tag `sha-6b3f2b1`
- Latest production deploy: 2026-07-09, GitHub Actions run `29045719643`,
  success with green post-deploy contract gate
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

## What Changed (July 9-10) — retirement-notes findings implemented

PR #100 (`infra/retirement-findings`, four commits) merged and deployed:

- **Daily data-trust contracts (notes §1).** `scripts/contracts_check.py`
  gained `C-DAT-001` (per-seat rtb_daily freshness, WARN >3d / FAIL >5d) and
  `C-DAT-002` (per-seat, per-report-type column completeness: fails when a
  monitored column or whole report type goes dark vs the prior window, warns
  when a column is empty everywhere). The repo's
  `catscan-contracts-check.timer` is now **installed and enabled on the
  production VM** — daily 04:00, runs inside `catscan-api`, JSON to
  `/tmp/contracts_daily.json` in the container. Expect a standing C-DAT-002
  WARN until upstream `app_name`/`app_id` emptiness is fixed (see Remaining
  Work).
- **rtb_daily partition migration kit (notes §3).** `scripts/partition_migration/`
  contains a rehearsal-gated path to monthly partitions: DDL (BIGINT `id`,
  dedup on `(metric_date, row_hash)`, 16 indexes → 7 on pg_stat evidence),
  timed loader, per-month validation, instant cutover/rollback, and
  retention-by-`DROP PARTITION` wired to `retention_config`. Importers detect
  the table shape at connect time, so no deploy needs to synchronize with the
  cutover. **Do not run against live prod without the rehearsal** — see the
  kit README. Measured while building it: rtb_daily is 327 GB / ~467M rows
  (2026-07-09), growing ~1.8 GB/day, and `rtb_daily_id_seq` is at 589.7M of
  the INTEGER column max (~16 months to exhaustion; the kit's BIGINT rebuild
  is the fix).
- **Stale workflow purge (notes §2).** The eight `v1-*` pilot workflows are
  deleted. An audit found all 34 routers mounted and real, so no code was
  deleted; `cloudsql-logical-backup.yml` is healthy and stays.
- **No-hot-patch invariant (notes §4).** CLAUDE.md now states: nothing serves
  traffic that isn't a pushed, sha-tagged image. The old "docker cp is
  acceptable" allowance is gone.

Corrections to the retirement notes discovered while verifying: Cloud SQL is
**Postgres 15.17** (not 16 — pin 15.17 for the migration) and the rtb_daily
size figures in the notes (157 GB / 227M rows) were ~2x stale.

## Latest Production Commits (June 10-12)

All pushed to `main` and deployed:

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
  --recreate-api`). Hot-patching via `docker cp` is no longer acceptable
  (CLAUDE.md invariant, July 2026): push the commit, let CI build, deploy that.
- Daily contract validation runs on the VM via systemd
  (`catscan-contracts-check.timer`, 04:00): check with
  `systemctl status catscan-contracts-check.service` or
  `journalctl -u catscan-contracts-check.service`. The unit files live in
  `scripts/systemd/`; on a redeploy of the VM they must be reinstalled
  (`cp` to `/etc/systemd/system/` + `systemctl enable --now`).
- The `gh` CLI on the production VM is authenticated as `jenbrannstrom`
  (device login, July 9). Run `gh auth logout` if credentials should not
  live on the box.
- Ad-hoc production DB access: run Python inside `catscan-api` using
  `storage.postgres_database` helpers — `pg_query` for SELECTs (it
  fetches and will roll back writes), `pg_execute` for writes.
- The deploy workflow's post-deploy contract gate updates
  `rtb_endpoints_current` and fails the run on data-freshness contract
  violations even when the deploy itself succeeded — check `/api/health`
  `git_sha` before assuming a "failed" deploy didn't ship.

## Remaining Work

0. **Upstream `app_name`/`app_id` emptiness**: both columns are 100% empty
   across all seats in rtb_daily (C-DAT-002 warns daily). The daily-spend
   feature already works around it via `rtb_buyer_spend_daily`; fixing the
   upstream mapping (or accepting and delisting the columns from
   `MONITORED_COLUMNS` in `scripts/contracts_check.py`) clears the WARN.
   Also: 2 stuck `ingestion_runs` rows keep C-ING-001 at WARN — clear with
   `contracts_check.py --fail-stale-ingestion-runs` after a look.
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
   discard deliberately. (Also seen July 9: `.env.bak.20260521003359`,
   `precompute_24h_monitor.pid`, `scripts/precompute_24h_monitor.sh` on the
   VM — same treatment.)
9. GCP → Hetzner migration: rehearse the rtb_daily restore into partitions
   on the target box per `scripts/partition_migration/README.md`, and pin
   Postgres **15.17**. Cut over onto partitions only if the rehearsal is
   clean; wire `partition_retention.py --from-config --apply` as a daily
   timer after cutover.

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
