# Handover

## Current Production Handover

This is the current handover as of **June 7, 2026**, with a **June 10, 2026**
language-flags RCA addendum below. It supersedes the older May/April creatives
QA notes lower in this file.

The user wants GitHub to be the source of truth. Production must be recoverable
from GitHub, Terraform, Google Secret Manager, Cloud SQL, Cloud Scheduler,
Artifact Registry, and documented scripts. The user does not want to keep an
expensive staging VM.

## Production State

- GCP project: `catscan-prod-202601`
- Production URL: `https://scan.rtb.cat`
- Current deployed commit: `983f1d9a`
- Production health: `/api/health` returns 200 with `git_sha: 983f1d9a`,
  `version: sha-983f1d9`, and `release_version: 0.9.5`
- Latest production deploy: GitHub Actions run `27075147141`, success
- Latest image build: GitHub Actions run `27075145733`, success after rerun
  from a transient Docker Hub timeout during Buildx setup
- GitHub `main` points at
  `983f1d9ab400bad5f3f70fb4258af18b0c36364a`; Gitee was not verified in this
  handover
- Production VM: `catscan-production-sg`, `RUNNING`, IP `34.143.222.60`
- Staging/old VM: `catscan-production-sg2`, `TERMINATED`, IP `34.143.231.235`
- Staging snapshot: `catscan-production-sg2-retirement-20260506-0327`
- Terraform state bucket: `gs://catscan-prod-202601-tfstate`
- Terraform backend prefix: `terraform/gcp`

Do not restart or use `catscan-production-sg2` unless explicitly asked. It is
stopped, but not deleted.

## Latest Production Commits

Already pushed to `main` and deployed where noted:

- `89aa1729` `Fix HTML language coverage evidence fallbacks`
- `b3c5516d` `Preserve Google creative preview URL evidence`
- `680a146d` `Improve HTML creative language script evidence`
- `e1bc3c6c` `Upscale small creative screenshots for OCR`
- `76c3ee02` `Ignore advertiser-only text in HTML language scans`
- `983f1d9a` `Accept English creatives serving India`
- `1247b971` `Make production recovery GitHub sourced`
- `1ed1336f` `Fix dependency audit findings`
- `9ccd4780` `Update dashboard dependencies for audit`
- `e7f4cfdf` `Fix expired v1 canary waiver tests`
- `7473f0f0` `Remove stale staging wording from Terraform`
- `71b597f4` `Handle naive precompute refresh timestamps`
- `155ed4f7` `Wire production automation API key`
- `19c2c202` `Allow secret-gated scheduler endpoints with API key`
- `bd40328b` `Fix creative ID joins and cluster creation`
- `2e2c5b58` `fix: use creative precompute for creatives page`
- `857915b2` `Fix creative live refetch for slash IDs`

## What Changed

Latest deployed language detection / market flag patch series (`983f1d9a`
latest):

- Fixed the coverage endpoint row drop caused by datetime serialization in
  `geo_linguistic_completed_at`.
- Fixed thumbnail status fallback so stored `gcs_path` is returned as
  `thumbnail_url`.
- Forced/missing language scans now best-effort refresh the live Google FULL
  creative payload before analysis.
- The collector/parser/storage path now preserves Google `previewUrl`,
  `renderUrl`, `creativeServingDecision`, and detected-language metadata.
- HTML creative evidence now uses direct image hints, safe public
  `previewUrl`/`renderUrl` screenshots, a 10 second render wait, OCR, and
  higher device-scale screenshots for small banners before sending image
  evidence to Gemini.
- The analyzer adds script heuristics for Devanagari/Hindi (`hi`) and Myanmar
  (`my`), asks the vision model for visible text, and avoids letting partial
  chrome/`AD` text override obvious non-Latin creative text.
- HTML/video language analysis no longer treats advertiser name alone as
  creative language evidence. This prevents advertisers like `Amazing Design
  Tools` from turning no-content HTML into English.
- The deterministic market flag layer now accepts English creatives serving
  India (`IN`), matching the existing behavior for other primary English
  markets.
- The reported India creative `2014265280192819202` no longer appears in the
  remaining language-market alert list after the `983f1d9a` deploy.

June 10 language-flags RCA addendum:

- User reported buyer `299038253` creative `216139` as a false positive:
  visible video copy is Vietnamese and serving Vietnam, but Language Flags shows
  `ZH mismatches VNM`.
- Production API diagnostic workflow `27271278231` confirmed this is not a
  single UI display issue. The API returned `216139 red ZH mismatches VNM
  detected=zh`, plus adjacent `216xxx` creatives with the same `zh` vs `VNM`
  pattern and a separate `zh` vs `THA` cluster.
- Revised RCA: do **not** assume Gemini misread Vietnamese. The more plausible
  fault is upstream evidence selection. For `VIDEO`, `LanguageAnalyzer` first
  extracts VAST metadata text (`AdTitle`, `Description`, `HTMLResource`) and
  sends that text to the language model. If that returns a successful language,
  the analyzer returns immediately and never reaches video-frame OCR/vision
  evidence.
- Relevant code path:
  - `api/analysis/language_analyzer.py`: `extract_text_from_creative()` reads
    VAST metadata for `VIDEO`; `analyze_creative()` returns on the first
    successful text result before rendered evidence.
  - `services/creative_evidence_service.py`: video frame extraction/OCR exists,
    but only runs later through rendered evidence fallback.
- Likely failure mode for `216139`: Gemini may have correctly classified the
  text it was given, but Cat-Scan likely gave it non-visible/stale/generated VAST
  metadata rather than the visible Vietnamese video frames. The stored `zh` then
  became authoritative for deterministic market flagging.
- Pipeline fix direction:
  - For `VIDEO`, prefer visible evidence first: video frames OCR/vision.
  - Treat VAST `AdTitle`, `Description`, and `HTMLResource` as metadata, not
    dominant creative language.
  - If visible frame evidence exists, it should override VAST metadata.
  - Store and expose the evidence source (`video_frame_ocr`,
    `video_frame_vision`, `vast_metadata`, `google_detected_language`, etc.)
    and confidence in the Language Flags page/modal.
- Important nuance: backend coverage rows already include `language_source` and
  `language_confidence` in `api/schemas/creatives.py`, but the dashboard
  `CreativeLanguageFlagCoverageRow` type and page currently do not surface them.
  This should be fixed so future RCA can see whether a row came from visible
  evidence, VAST metadata, or Google metadata.

Amazing Design Tools batch retest:

- Seat: `Amazing Design Tools LLC`, buyer ID `1487810529`
- Batch refresh workflow: run `27075424571`, success
- Status workflow: run `27075439811`, success
- Creatives returned: `350`
- Creatives analyzed: `350`
- Missing analysis: `0`
- Detected language: `143`
- Analysis errors: `207`, all currently `no content`
- `/creatives/v2` market alerts: `350` total, `25` language-market alerts,
  `325` geo-market alerts
- Coverage summary: `74` language green, `251` language orange, `25` language
  red, `350` geo orange

Current residual work:

- `25` language-market alerts remain for Amazing Design Tools in the latest
  `/creatives/v2` status run.
- `207` creatives still report language analysis error `no content`; these are
  likely creatives where no useful text/image evidence was available after the
  current best-effort render path.
- Geo alerts are still broad for this seat: `325` geo-market alerts in
  `/creatives/v2` and `350` geo orange in coverage.
- One adjacent broader test file still has unrelated route-string expectations
  for `{creative_id}` vs `{creative_id:path}` and was not part of the final
  language patch validation.

Older deployed creative live-refetch patch (`857915b2`):

- Fixed FastAPI route matching for creative IDs that contain `/`, `+`, `=`, or
  URL-encoded path characters. The frontend now uses non-ambiguous live/detail
  paths (`/creatives/live/{creative_id:path}` and
  `/creatives/detail/{creative_id:path}`), while legacy live URLs still work.
- Extended slash-safe route handling to destination diagnostics, countries,
  language, and geo-linguistic creative endpoints.
- Changed scheduled creative-cache refresh to support `background=true`, so
  Cloud Scheduler gets a quick queued response instead of timing out through
  nginx while Google metadata is fetched serially.
- Added/created the production Cloud Scheduler job
  `creative-cache-refresh`, scheduled at `45 14 * * *` UTC:
  `https://scan.rtb.cat/api/creatives/cache/refresh/scheduled?days=7&limit=1000&include_html_thumbnails=false&background=true`
- Updated `scripts/provision_gcp_runtime_config.sh` so future runtime
  provisioning keeps the creative-cache scheduler and secret header wired.

Production verification for `857915b2`:

- `CI Build and Push Images`: run `26146272312`, success.
- `CD Manual Deploy to GCP`: run `26146469928`, success.
- `/api/health`: 200,
  `{"status":"healthy","release_version":"0.9.4","version":"sha-857915b","git_sha":"857915b2","configured":true,"has_credentials":true,"database_exists":true}`.
- `creative-cache-refresh` exists, is `ENABLED`, and targets `scan.rtb.cat`.
- The new Scheduler job was triggered once manually after creation.
- Reported creative
  `u4kZtsPGIKLiMNFW/zVkMWx9n18dciKp92Q2TyoXyKc=` returned `source: live`
  from `/api/creatives/live/...`.
- That creative's cached row updated to
  `2026-05-20T13:15:12.260599+00:00` and now reports `is_stale: false`.

Local checks for `857915b2`:

- Targeted pytest suite passed: `10 passed`.
- Python compile check passed for changed routers.
- `npm --prefix dashboard run lint` passed with one pre-existing warning in
  `dashboard/src/components/preview-modal/LanguageSection.tsx`.
- `bash -n scripts/provision_gcp_runtime_config.sh` passed.
- `terraform fmt -check terraform/gcp/main.tf` passed.
- `git diff --check` passed.

Local working tree note:

- There is still unrelated pre-existing local WIP not included in `857915b2`:
  `.env.example`, `api/dependencies.py`, `api/routers/creative_language.py`,
  `api/routers/creatives.py`, `tests/test_rbac_three_tier.py`, and the
  untracked creative-audit/agent files. Do not assume those are part of the
  deployed slash-ID live-refetch patch.

Older deployed creative/RCA patch:

- Fixed auto-generated campaign cluster creation for large suggestions. The
  backend now assigns creatives with one bulk `INSERT ... SELECT FROM unnest`
  instead of one DB insert per creative.
- Fixed creative ID handling for IDs containing `+`, `/`, and URL-encoded
  characters. Google API resource paths are encoded only for the request path,
  while stored/joined creative IDs are normalized to decoded IDs.
- Changed active creative cache refresh to start from `rtb_daily` buyer-scoped
  facts instead of `performance_metrics`, so performance-only creatives can
  have metadata fetched and cached.
- Added migration `067_normalize_encoded_creative_ids.sql` to normalize safe,
  unreferenced encoded creative IDs already stored in `creatives`.
- Exposed the existing cached-row timestamp in the preview modal as
  `Cached Row Created`. No new PostgreSQL column was added for upload date.
  Example MoBoost evidence was buyer `6574658621` / `Amazing Moboost`, cached
  row created `2026-04-24 01:39:45 UTC`, raw `collectedAt`
  `2026-04-24T01:39:22.560899+00:00`.

- Removed staging as a deployment target. Production deploys are manual and
  production-only.
- Removed stale staging wording/config from Terraform and GitHub variables.
- Added `docs/PRODUCTION_RECOVERY.md`.
- Added and fixed `scripts/bootstrap_gcp_terraform_state.sh`.
- Migrated the existing Terraform state into GCS.
- Added `catscan-api-key` as a GSM-managed production API key.
- Synced GitHub `CATSCAN_CANARY_BEARER_TOKEN` from GSM `catscan-api-key`.
- Added `scripts/refresh_gcp_vm_runtime_env.sh`.
- Deploy workflow refreshes VM env files from GSM before recreating containers.
- API-key auth now attaches a sudo service-principal context for automation.
- Secret-gated scheduler/monitor endpoints bypass API-key middleware.
- Rotated scheduler secrets after one failed local `gcloud scheduler update`
  command printed an old header value.

Key changed files in the latest deployed patch:

- `services/creative_language_analyzer.py`
- `services/creative_language_flag_service.py`
- `services/creative_language_service.py`
- `services/creative_evidence_service.py`
- `services/creative_response_builder.py`
- `services/creative_preview_assets.py`
- `collectors/creatives/client.py`
- `collectors/creatives/parsers.py`
- `storage/postgres_store.py`
- `api/schemas/creatives.py`
- `api/routers/creatives.py`
- `tests/test_language_analyzer_providers.py`
- `tests/test_creative_language_flag_service.py`
- `tests/test_creative_evidence_service.py`
- `tests/test_creative_language_service.py`
- `tests/test_creatives_language_flag_coverage_api.py`
- `tests/test_postgres_store_thumbnails.py`
- `tests/test_creatives_client.py`

Key changed files from older creative live-refetch/cache patches:

- `collectors/creatives/client.py`
- `collectors/creatives/parsers.py`
- `services/creative_cache_service.py`
- `storage/postgres_repositories/campaign_repo.py`
- `storage/postgres_migrations/067_normalize_encoded_creative_ids.sql`
- `api/schemas/creatives.py`
- `services/creative_response_builder.py`
- `dashboard/src/components/preview-modal/PreviewModal.tsx`
- `tests/test_campaign_performance_repo.py`
- `tests/test_creative_cache_service.py`
- `tests/test_creatives_client.py`
- `tests/test_multi_seat.py`

Key changed files from the earlier production recovery work:

- `.github/workflows/deploy.yml`
- `api/auth.py`
- `api/session_middleware.py`
- `docs/PRODUCTION_RECOVERY.md`
- `scripts/bootstrap_gcp_terraform_state.sh`
- `scripts/provision_gcp_runtime_config.sh`
- `scripts/refresh_gcp_vm_runtime_env.sh`
- `terraform/gcp/main.tf`
- `terraform/gcp/startup.sh`
- `tests/test_api_key_service_user.py`

## Live Checks Completed

Latest production verification for `983f1d9a`:

- `CI Build and Push Images`: run `27075145733`, success after rerun from a
  transient Docker Hub timeout.
- `CD Manual Deploy to GCP`: run `27075147141`, success.
- `/api/health`: 200,
  `{"status":"healthy","release_version":"0.9.5","version":"sha-983f1d9","git_sha":"983f1d9a","configured":true,"has_credentials":true,"database_exists":true}`.
- Post-deploy contract summary:
  - `C-ING-001`: PASS, `2462` run(s), `0` stuck
  - `C-ING-002`: PASS, all `4` buyers have imports in 48h
  - `C-EPT-001`: PASS, all `13` endpoints have current observations
  - `C-PRE-002`: PASS, all ACTIVE configs have rows in `pretarg_daily`
  - `C-PRE-003`: WARN, all covered with `1` justified no-`publisher_id`
    exception: `299038253`
  - `C-WEB-001` / `C-WEB-002`: SKIP
  - Total: `4` PASS, `1` WARN, `0` FAIL, `2` SKIP

Latest local checks for the final language patch:

- Focused pytest suite passed: `47 passed, 9 warnings`:
  `tests/test_creative_language_flag_service.py`,
  `tests/test_language_analyzer_providers.py`,
  `tests/test_creative_evidence_service.py`,
  `tests/test_creative_language_service.py`, and
  `tests/test_creatives_language_flag_coverage_api.py`.

Older local checks before `bd40328b`:

- Python compile check passed for the changed backend modules.
- Targeted pytest suite passed: `12 passed`.
- `npm --prefix dashboard run lint` passed with one pre-existing warning in
  `dashboard/src/components/preview-modal/LanguageSection.tsx`.
- `git diff --check` passed.
- Migration `067_normalize_encoded_creative_ids.sql` syntax was checked against
  production PostgreSQL inside a transaction and rolled back successfully.

Older GitHub/deploy checks:

- `CI Build and Push Images`: run `25534183448`, success.
- `CD Manual Deploy to GCP`: run `25534186240`, success.
- Post-deploy contract check: success.
- `/api/health`: 200,
  `{"status":"healthy","release_version":"0.9.4","version":"sha-bd40328","git_sha":"bd40328b","configured":true,"has_credentials":true,"database_exists":true}`.

Known residual CI issue from the older May deploy:

- Separate `Security Checks` run `25534183443` failed in `Dependency Scan`
  (`pip-audit`). `tfsec` and `gitleaks` passed. This did not block the manual
  production deploy, but it still needs follow-up.

Earlier live production recovery checks for `19c2c202`:

- `/api/precompute/health` with GSM monitor secret: 200, `ok: true`.
- conversion runtime guardrail with GSM API key: pass.
- GitHub guardrail workflow using synced repo secret: run `25416559943`,
  success.
- Gmail status with production API key: 200, configured, authorized, not
  running.

Latest Gmail status observed:

- `last_success`: `2026-05-05T15:26:45.694538`
- `latest_metric_date`: `2026-05-04`
- `rows_on_latest_metric_date`: `3620458`
- `files_imported`: `20`
- `emails_processed`: `20`
- `last_unread_report_emails`: `20`

Cloud Scheduler jobs:

- `gmail-import`: `0 12 * * *`, `Etc/UTC`,
  `https://scan.rtb.cat/api/gmail/import/scheduled`
- `precompute-refresh`: `30 13 * * *`, `Etc/UTC`,
  `https://scan.rtb.cat/api/precompute/refresh/scheduled`
- `creative-cache-refresh`: `45 14 * * *`, `Etc/UTC`,
  `https://scan.rtb.cat/api/creatives/cache/refresh/scheduled?days=7&limit=1000&include_html_thumbnails=false&background=true`

All Scheduler jobs target `scan.rtb.cat`, not the staging VM IP.

## RCA Summary

### May 8 MoBoost Creative Data RCA

The MoBoost creative used for the RCA was
`LiKriOR6bAcTUIhpPq1AS+Vs1bBEOPK19zLU7BqQZGYAQEZ1SlavT9E1YnHL/4mo`.

The initial suspicion was a Gmail ingest failure because Google UI showed spend
while Cat-Scan/PostgreSQL appeared to show no spend. Production DB checks showed
that Gmail ingest had imported the spend correctly:

- `rtb_daily`, `performance_metrics`, and `config_creative_daily` all had facts
  for the decoded creative ID.
- Last-7-days facts matched the Google UI spend for billing ID `178022294840`:
  May 5 had 6,318 impressions / 75,800,000 micros, May 4 had 3,501 /
  42,000,000 micros, May 3 had 1,571 / 62,840,000 micros, and May 2 had 1,471 /
  58,840,000 micros.
- May 6 had bids but zero impressions/spend, matching the screenshot that showed
  yesterday as `$0`.
- Clicks were zero/null in the imported reports for this creative.

Root cause: creative metadata was cached under the URL-encoded creative ID
`LiKriOR6bAcTUIhpPq1AS%2BVs1bBEOPK19zLU7BqQZGYAQEZ1SlavT9E1YnHL%2F4mo`, while
Gmail/RTB facts use the decoded ID
`LiKriOR6bAcTUIhpPq1AS+Vs1bBEOPK19zLU7BqQZGYAQEZ1SlavT9E1YnHL/4mo`. The UI used
the encoded metadata ID when requesting performance, so the join returned zero
even though the facts existed under the decoded ID.

The Google live fetch also confirmed the path issue: unencoded slash-bearing
creative IDs caused the Google client to reject the `buyers.creatives.get`
resource name. The fix encodes the ID only in the Google request path and
normalizes stored IDs to decoded form.

### May 8 Auto-Generated Cluster RCA

The screenshot showed the `Servewareindia` suggestion with 845 creatives stuck
on `Creating...`. Production checks after the screenshot found no `Serveware`
campaign and all 845 suggested creatives still unassigned.

Root cause: `POST /api/campaigns` called `assign_creatives_batch`, but the
implementation inserted one row per creative. Large suggestions were too slow
and brittle from the UI flow. The fix replaced the insert loop with a single
bulk statement.

### Earlier Gmail/Precompute RCA

The recurring Gmail/precompute problem was not that emails arrived too late.
Scheduler timing is now explicit:

- Gmail import runs at `12:00 UTC`
- Precompute refresh runs at `13:30 UTC`

The better RCA was a fragile batch/import path losing its DB connection
mid-flight and leaving bad/stale state. The code fix for the discovered
precompute health failure was `71b597f4`, which treats naive DB refresh
timestamps as UTC instead of crashing on naive/aware datetime comparison.

The scheduled conversion guardrail failure was separate:

- production had a GitHub canary bearer token, but no recoverable production
  `CATSCAN_API_KEY` source in GSM
- after adding `CATSCAN_API_KEY`, API-key middleware initially blocked
  secret-gated scheduler endpoints until `19c2c202`

Both issues are fixed and deployed.

## Operational Notes

- Terraform state is now in GCS.
- Local Terraform may still use Application Default Credentials that differ
  from the active `gcloud` account.
- A Terraform apply initially failed because ADC lacked
  `secretmanager.secrets.create`.
- The active `gcloud` account was project owner and was used to create/import
  `catscan-api-key` and its IAM binding.
- Future Terraform operations should use correctly privileged ADC credentials
  or explicitly use the active gcloud access token.
- The `catscan-api-key` resource and IAM binding are now in Terraform state.

During live guardrail verification, a retention run executed and deleted old
rows:

- raw rows deleted: `88117`
- summary rows deleted: `9314`
- conversion event rows deleted: `151`

Subsequent guardrail checks were run with `--skip-retention-run` to avoid
running cleanup again.

## Local Working Tree

There are still unrelated local WIP files from earlier agent/creative-audit
access work. They were intentionally not committed during production recovery.

Do not blindly stage these:

- `.env.example`
- `api/dependencies.py`
- `api/routers/creative_language.py`
- `api/routers/creatives.py`
- `tests/test_rbac_three_tier.py`
- `.codex/`
- `.repo/`
- `docs/AGENT_INTERFACE.md`
- `docs/CREATIVE_AUDIT_AGENT_ACCESS.md`
- `docs/CREATIVE_AUDIT_AGENT_SKILL.md`
- `scripts/provision_creative_audit_agent.py`
- `storage/postgres_migrations/066_agent_read_views.sql`

## Remaining Work

1. Delete or fully retire `catscan-production-sg2` and release its static IP
   once the user confirms permanent deletion.
2. Run a full Terraform plan with correct privileged credentials and review
   any drift. Avoid destructive changes.
3. Decide whether to keep, finish, or discard the older agent/creative-audit
   local WIP files listed above.
4. Spot-check the MoBoost creative in production after browser refresh. Expected
   result: spend appears for decoded ID
   `LiKriOR6bAcTUIhpPq1AS+Vs1bBEOPK19zLU7BqQZGYAQEZ1SlavT9E1YnHL/4mo`, and the
   modal shows `Cached Row Created` from the existing cache timestamp.
5. Re-test auto-generated cluster creation in production with a large suggestion
   such as `Servewareindia`.
6. Address the `pip-audit` failure from GitHub Actions run `25534183443`.
7. Watch the next scheduled Gmail import and precompute refresh after
   `12:00 UTC` / `13:30 UTC` to confirm the rotated Scheduler secrets work
   from Cloud Scheduler.
8. Address the GitHub Actions warning about Node.js 20 actions before GitHub's
   Node 24 cutoff.

## Useful Commands

Production health:

```bash
curl -sS https://scan.rtb.cat/api/health
```

List VMs:

```bash
gcloud compute instances list \
  --project=catscan-prod-202601 \
  --format='table(name,zone,status,machineType.basename(),networkInterfaces[0].accessConfigs[0].natIP,labels)'
```

List Scheduler jobs without printing secret headers:

```bash
gcloud scheduler jobs list \
  --project=catscan-prod-202601 \
  --location=asia-southeast1 \
  --format='table(name,state,schedule,timeZone,httpTarget.uri)'
```

Refresh VM runtime env from GSM after a secret rotation:

```bash
gcloud compute ssh catscan-production-sg \
  --project=catscan-prod-202601 \
  --zone=asia-southeast1-b \
  --tunnel-through-iap \
  --command "cd /opt/catscan && sudo bash scripts/refresh_gcp_vm_runtime_env.sh --recreate-api"
```

## Archived Previous Creative QA Scope

This handover is for the **Catscan creatives QA / diagnostics** work.

Main surfaces involved:

- main creatives grid: `/[buyerId]/creatives`
- creative preview modal
- click-macro audit page: `/[buyerId]/creatives/click-macros`
- language-flags audit page: `/[buyerId]/creatives/language-flags`

Main buyer used for checks:

- `1487810529`

Representative creatives used during debugging:

- `1987702299778854923`
  English creative, `AED` currency, serving in `PH`
- `2013919535262576642`
  English native creative serving in `IND` with Spanish CTA `instalar`
- `2028723258945941508`
  English creative serving in `PHL` with Spanish CTA `instalar`
- `208416`
  Video creative that was reported as a faulty Hindi / geo-linguistic alert

## Current Status

As of **April 15, 2026**:

- branch: `main`
- production deploy source is GitHub `main`; staging/`vm2` has been retired
- `/api/health` reports `release_version: 0.9.4` and `version: sha-a63c580`
- local worktree is clean except:
  - modified `handover.md`
  - untracked `.codex`
  - untracked `.repo/`

Do not commit `.codex` or `.repo/`.

## What Shipped

These commits are already on `main`, pushed, and deployed:

1. `c09cd064` `Add Chinese creatives QA translations`
2. `31402bbc` `Improve creative card market alerts`
3. `99ea5839` `Localize preview modal language-mix reasons`
4. `505709c5` `Localize preview modal mix reasons across languages`
5. `a63c580a` `Clarify pending geo-linguistic preview states`

## User-Visible Behavior Now

- the empty modal currency panel for `No obvious market currency detected` is hidden
- creative cards can show market-alert badges next to approval status
- refreshing a creative from the modal updates the main creatives grid immediately, so `Cached` flips to `Live`
- preview-modal language-mix reasons are localized across supported non-English UI locales:
  - `es`, `pl`, `zh`, `ru`, `uk`, `da`, `fr`, `nl`, `he`, `ar`
- pending / not-run geo-linguistic states no longer render as `Needs Review` in the modal language section

## Latest Investigation: Creative `208416`

The user reported that video language detection looked faulty for `208416`.

Production inspection on April 15, 2026 showed:

- creative format: `VIDEO`
- stored language: `Hindi (hi)`
- confidence: `0.98`
- source: `claude_vision`
- last 7 days of serving: `India` only
- latest geo-linguistic run: `completed`
- latest geo-linguistic decision: `match`

The latest stored AI report for `208416` explicitly described it as a Hindi-in-India match.

Conclusion:

- the language detection itself was **not** faulty
- the misleading part was the modal UI, which could render orange geo states like `AI report pending` or `not_run` as `Needs Review`
- that display issue was fixed in `a63c580a`

If someone reports `208416` still showing the old badge, hard refresh the frontend bundle first.

## Relevant Files

Most recent frontend fix:

- `dashboard/src/components/preview-modal/LanguageSection.tsx`
- `dashboard/src/components/preview-modal/utils.ts`
- `dashboard/src/__tests__/preview-geo-linguistic-status.test.ts`

Language-mix localization work:

- `dashboard/src/components/preview-modal/reason-localization.ts`
- `dashboard/src/__tests__/preview-modal-reason-localization.test.ts`
- `dashboard/src/lib/i18n/types.ts`
- `dashboard/src/lib/i18n/translations/en/previewModal.ts`
- `dashboard/src/lib/i18n/translations/es/previewModal.ts`
- `dashboard/src/lib/i18n/translations/pl/previewModal.ts`
- `dashboard/src/lib/i18n/translations/zh/previewModal.ts`
- `dashboard/src/lib/i18n/translations/ru/previewModal.ts`
- `dashboard/src/lib/i18n/translations/uk/previewModal.ts`
- `dashboard/src/lib/i18n/translations/da/previewModal.ts`
- `dashboard/src/lib/i18n/translations/fr/previewModal.ts`
- `dashboard/src/lib/i18n/translations/nl/previewModal.ts`
- `dashboard/src/lib/i18n/translations/he/previewModal.ts`
- `dashboard/src/lib/i18n/translations/ar/previewModal.ts`

Earlier alert / card / refresh work:

- `api/routers/creatives.py`
- `api/schemas/creatives.py`
- `services/creative_response_builder.py`
- `services/creatives_service.py`
- `dashboard/src/components/creative-card.tsx`
- `dashboard/src/components/preview-modal/PreviewModal.tsx`
- `dashboard/src/app/creatives/page.tsx`
- `dashboard/src/types/api.ts`

## Validation Run

These were run and passed during this session:

```bash
.venv/bin/pytest -q tests/test_creatives_lazy_native_previews_api.py tests/test_creative_language_flag_service.py
```

```bash
cd dashboard
npx vitest run src/__tests__/preview-modal-reason-localization.test.ts
```

```bash
cd dashboard
npx vitest run src/__tests__/preview-geo-linguistic-status.test.ts src/__tests__/preview-language-geo-basis.test.ts
```

```bash
cd dashboard
npm run build
```

## Deployment Notes

Deploy flow is now production-only:

1. wait for `CI Build and Push Images`
2. deploy `production`
3. verify `https://scan.rtb.cat/api/health`

Recent deploys used:

- `.github/workflows/deploy.yml`
- `run_contract_check=false`

Reason:

- staging is retired; deploy verification runs against production health and
  post-deploy contract checks.

## Suggested Next Steps

- if the user asks for more language coverage, continue the same preview-modal localization pattern already used in `reason-localization.ts` and the locale `previewModal.ts` files
- if the user reports another geo-linguistic false alert, inspect both:
  - stored `geo_mismatch` badge state in the language section
  - latest `creative_analysis_runs` row for that creative
- if the user reports the lower AI report panel still showing internal errors for a creative that already has a completed run, inspect:
  - `dashboard/src/components/preview-modal/GeoLinguisticSection.tsx`
  - `api/routers/creative_geo_linguistic.py`
  - `services/geo_linguistic_service.py`

## Important Notes

- this file is the current creatives QA handoff; ignore older pretargeting context
- priority has been user-visible signal quality, not generic refactoring
- the user is focused on:
  - accurate creative warnings
  - localized modal reasoning
  - no misleading `Needs Review` states
  - no stale `Cached` badges after refresh
