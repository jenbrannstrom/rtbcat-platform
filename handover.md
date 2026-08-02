# Handover

## CUTOVER COMPLETE — HETZNER AUTHORITATIVE, 2026-08-02 10:45 UTC

**This section is current and overrides every historical cutover state below.**
Production DNS now points at Hetzner, the Hetzner application and PostgreSQL
database are writable, and the three production scheduler jobs target the
Hetzner-backed `https://scan.rtb.cat/` endpoints. Gate 11 ran, the controlled
post-cutover cycle passed, and the source replication slot has been dropped.
The migration is therefore past the point of no return: do not resume logical
replication or treat the old GCP database as an automatic failback target.

### Accepted production state

- Public TLS, `/api/health`, `/login`, anonymous-access rejection and the
  authenticated agent API checks passed. Health reports the accepted
  `10c45949d08f671c69743e9fc557cb9956921487` release and a reachable database.
- The Hetzner API and dashboard containers are healthy. The API is writable
  (`CATSCAN_READ_ONLY_SHADOW=false`) and all three scheduler endpoint guards
  are enabled.
- The `precompute-refresh`, `creative-cache-refresh` and `gmail-import` Cloud
  Scheduler jobs are `ENABLED` on their recorded schedules and all target
  `https://scan.rtb.cat/`.
- The controlled Gmail cycle completed exactly once with `no_new_mail`: no
  imported rows, no duplicate import history, and no BigQuery/GCS write. The
  idempotency check passed.
- Post-cycle reconciliation passed 10/10 public checks and 7/7 finance checks
  with exact source/target results. Six data contracts passed; the sole
  warning is the already-recorded empty application-name/application-id
  source-data condition, not a cutover regression.
- The final application-data sync transferred 579 files (about 6.8 GB) with
  no target deletes, no source mutation and no credential-file replacement.
- The target logical subscriptions are disabled and detached from a slot.
  The source has zero logical replication slots. The Hetzner replication
  proxy and migration monitor are disabled and inactive; target PostgreSQL
  remains enabled and active.
- The old GCP application is deliberately frozen: its application service is
  inactive, it has zero application containers, the maintenance site remains
  enabled, writer timers are inactive, and cleanup cron remains absent. Its
  host Cloud SQL proxy is deliberately still active so the frozen source can
  be inspected if required.

### Authentication deviation accepted by the operator

Email/password login is the only enabled public login method and was verified
successfully by the operator. Google and Authing login are currently disabled.
The expected Authing secrets do not exist in the project, and the target does
not run the source's oauth2-proxy arrangement. The operator explicitly
approved completing the migration with password login and repairing Google
login as a separate follow-up. No failed Authing lookup changed IAM policy.

The Hetzner runtime identity now has Secret Accessor on exactly the four
scheduler endpoint secrets needed by the production API. Those narrowly
scoped grants are part of the accepted production configuration; do not
remove them while these scheduler endpoints are in service.

### Cleanup completed and one manual action outstanding

- The one-use file-copy SSH key was destroyed, the host `authorized_keys`
  file was restored exactly, the temporary host firewall rule was removed,
  normal operator SSH still works, and source-to-target TCP/22 is blocked by
  the host firewall.
- The local API token, the one-window database-admin password copies and the
  source admin pgpass were securely erased. The temporary authenticated API
  tunnel is closed and its local port is no longer listening.
- The migration monitor, target-to-source Cloud SQL proxy and stale rehearsal
  unit are stopped/disabled or cleared. The earlier temporary GCP control-path
  IAM and firewall changes were already removed during the first-window
  rollback.
- **Manual closeout still required:** remove only the temporary inbound
  TCP/22 rule added to the Hetzner Cloud Firewall for Gate 8. Keep the normal
  operator SSH rule. This provider-console action cannot be proven from the
  host and is the only remaining cutover cleanup item.

### Operating and recovery rules from here

- Keep GCP application writers, timers and schedulers stopped. The scheduler
  jobs themselves are production jobs now owned by the Hetzner deployment;
  pausing them is an incident action, not a migration rollback step.
- Do not re-enable either target subscription. Because Hetzner has accepted
  writes and the source slot is gone, returning to GCP requires a deliberate
  restore/re-copy plan followed by a new authority change.
- Keep the frozen Cloud SQL source intact until the post-migration retention
  decision is approved. Do not delete the source instance as routine cleanup.
- Repair Google login separately and verify `/api/auth/providers` plus an
  end-to-end Google sign-in before making it the default method.
- The production TLS certificate was issued through the workstation DNS-01
  path and must be renewed from that path before its recorded expiry window.

### Evidence for the completed cutover

Private mode-0600 evidence is under the attempt-2 cutover evidence directory.
The key final receipts are the G11 activation, G12 DNS/public checks, G13
scheduler and controlled-cycle records, post-cycle public/finance
reconciliations, slot-retirement record, final source-freeze and target-runtime
checks, and the monitor/proxy/tunnel cleanup receipts. The private command card
remains authoritative for the exact gate commands; its Guardian, prep and
retry amendment sections override its original body.

## HISTORICAL — FIRST WINDOW ROLLBACK CHECKPOINT, 2026-08-02 06:26 UTC

**Historical record only; the completed-cutover section above is current.**
At this checkpoint the public site was no longer frozen. The 2026-08-01 cutover was
rolled back before Gate 5 because the operator needed to end the window.
Gate 11 never ran, Hetzner never became writable, DNS never changed, and GCP
is again the sole production authority.

### Accepted state at that checkpoint

- Public `scan.rtb.cat` is healthy on GCP on the exact pre-freeze release
  `10c45949d08f671c69743e9fc557cb9956921487`; API health reports
  `sha-10c4594`, the database exists, and `/login` returns 200.
- The final read-only preflight generated at `2026-08-02T06:06:30Z` passed
  all 12/12 checks with `ready_for_freeze=true`, `mode=read-only` and
  `authority_changed=false`.
- The three Cloud Scheduler jobs are `ENABLED` on their recorded schedules
  and still target `https://scan.rtb.cat/`.
- On the GCP VM, `catscan-api`, `catscan-dashboard` and
  `catscan-cloudsql-proxy` are running; the API is healthy. The report,
  contracts and `certbot` timers are active, and docker-cleanup cron is back
  at `/etc/cron.d/docker-cleanup`. The card's suspected
  `catscan-precompute-refresh.timer` does not exist on the live VM; the
  precompute writer is the Cloud Scheduler job.
- All three source application roles remained `LOGIN`; the interrupted G4
  command did not commit. `rtbcat_migration_repl` also remains `LOGIN`.
- Hetzner remains sealed with zero application containers. Its subscription
  is enabled, all 98 tables are ready, the monitor is healthy, and the final
  preflight accepted the database services, backup and sealed app.
- The temporary direct-SSH firewall rule and the temporary
  `roles/compute.securityAdmin` grant to the operator identity have both
  been removed and independently re-read as absent.
- The one-window Cloud SQL `postgres` password copies were shredded on the
  workstation and database host. That password was randomized during G4
  preparation and is now intentionally unknown; reset it through GCP before
  the next G4 attempt. The temporary sensitive VM env backup was also
  shredded.

### Rollback incident that must be reviewed before the retry

The documented `systemctl start catscan.service` rollback command exposed a
pre-existing release-pin defect. `/opt/catscan` was checked out at the
accepted `10c4594` commit, but `/opt/catscan/.env` still said
`IMAGE_TAG=sha-0d2b83e`. Because the stopped images had to be rebuilt, the
service initially built and served that older March release. Legacy
`docker-compose` also hit its `ContainerConfig` stale-container error; only
the already-stopped containers belonging to compose project `catscan` were
removed, with no image or application-data deletion, and the service then
recreated them.

The stale release was publicly healthy from roughly 20:33 UTC on August 1
until the exact-release correction began around 05:54 UTC on August 2.
During that interval the 22:30 UTC `precompute-refresh` job made four
attempts; Cloud Scheduler recorded four 504 results. The immutable database
ledger shows old-release writes only to derived precompute caches:

- `home_summaries`: 20 successful ledger rows across four run IDs;
- `config_breakdowns`: 8 successful rows across two run IDs and one failed
  row from one additional run ID;
- no `rtb_summaries` ledger rows in the audited start window.

The retries continued backend work after the scheduler's HTTP timeout; some
config work completed after midnight. Replacing the containers ended any
remaining old-release process. Raw source data stayed on Cloud SQL and no
Hetzner write occurred, but review the derived-cache results (or require a
clean accepted-release precompute cycle plus contracts check) before opening
the next cutover window.

The correction was to set only the persisted GCP `IMAGE_TAG` to
`sha-10c4594`, rebuild from the matching checked-out source, and require both
private and public health to report `sha-10c4594`. Do not use the plain
rollback `systemctl start` again without first asserting the persisted image
tag equals the receipt's release. Keep that assertion in the next command
card amendment.

### Private rollback evidence

All files below are mode 0600 under
`/home/jen/private/rtbcat-cutover-20260801/`:

- `g4-precheck.txt` — all four relevant roles were still login-enabled and
  the unexpected-session array was empty before the interrupted G4 command;
- `rb-schedulers-final.json` — final three-job enabled state;
- `rb-preflight.json` and `rb-preflight.log` — accepted 12/12 final state;
- `rb-precompute-scheduler-logs.json` — four overnight precompute attempts
  and their 504 results;
- `rb-controlpath-firewall-before.json`,
  `rb-controlpath-iam-before.json` and `rb-controlpath-iam-remove.txt` —
  before-state and removal receipts for the two temporary access changes.

### Next attempt starts from G0/G1, not G5

1. Review the derived precompute cache incident above and record acceptance.
2. Reauthenticate an account with Cloud SQL admin, generate a new one-window
   `postgres` password, reset it through GCP, and stage a root-only pgpass on
   the database host.
3. Amend the rollback card to assert the exact persisted GCP `IMAGE_TAG`
   before starting `catscan.service`; preferably use the accepted immutable
   images instead of an on-VM build.
4. Run a fresh G0 and require 12/12. IAP worked with the refreshed billing
   identity during the final preflight, so do not recreate direct SSH access
   unless it fails again.
5. Open a new freeze at G1 and follow the Guardian Amendments. None of the
   aborted window's G5-G13 receipts may be reused.

## HISTORICAL — LIVE WINDOW HALTED MID-FREEZE, 2026-08-01 ~20:10 UTC

**Historical record only; the rollback checkpoint above is current. At this
point in the window, source writers were frozen and `scan.rtb.cat` was
serving a maintenance 503 to the public.** GCP was still authoritative, no
Hetzner write had occurred, and the cutover was fully reversible. The system
could not be left in that state: the remaining gates or the rollback below
had to run.

Operator/verifier/rollback owner for this window: Jen (solo, recorded
deviation from the two-person rule). Window opened 19:00 UTC against a
60-minute reservation.

### What is true right now

- Public: `scan.rtb.cat` → 503 maintenance page (GCP host nginx). DNS still
  points at the GCP IPv4; DNS has **not** been touched.
- GCP writers frozen: three Cloud Scheduler jobs `PAUSED`; `catscan.service`
  stopped so `catscan-api`, `catscan-dashboard` and `catscan-cloudsql-proxy`
  are all down (0 containers); report-delivery, contracts, precompute and
  `certbot` timers stopped; `/etc/cron.d/docker-cleanup` moved aside to
  `/root/docker-cleanup.cron.disabled`.
- Host `cloud-sql-proxy.service` on the VM is deliberately still `active`.
- Cloud SQL: **zero sessions other than the replication login** (verified).
  The role block was NOT applied — see the blocker below.
- Hetzner: replication healthy, 98/98 tables `ready`, monitor `ok`, retained
  WAL in the tens of KB. Application still sealed, 0 containers.
- Nothing has been written to the Hetzner database or app data by this
  window.

### Why it halted

Gate 4 (block the application database login roles) needs Cloud SQL admin.
`cat-scan@rtb.cat` has neither `cloudsql.admin` nor Secret Manager access,
and the `billing@amazingdo.com` credential had expired. Resolve by
re-authenticating `billing@amazingdo.com` (`gcloud auth login`), or accept
the documented deviation: every writer process is already stopped and
sessions are verified empty, so the practical freeze holds without the
`NOLOGIN` step. If you skip it, record that decision — and note that
applying `NOLOGIN` to `rtbcat_serving` without a second working admin login
would strand the rollback, which is exactly why it was not forced through.

### Unplanned changes made during the window — revert these at close

IAP tunnelling to the production VM failed repeatedly mid-freeze
(`4033: not authorized`), which removed the only control path to a frozen
production host. To restore control:

1. `roles/compute.securityAdmin` was granted to `cat-scan@rtb.cat` on
   project `catscan-prod-202601`.
2. Firewall rule `catscan-cutover-operator-ssh` was created: ingress
   TCP/22 from the approved operator `/32` to tag `catscan-server`.

Both are outside the approved gate list, both are reversible, and both must
be removed at window close. Direct SSH to the VM as the operator account
currently works and is the control path in use; if IAP recovers, prefer it.

### Remaining gates (command card is authoritative)

`docs/internal/rtbcat-migration/CUTOVER-WINDOW-COMMAND-CARD-2026-08-01.md`
(private, mode 0600). Read its **GUARDIAN AMENDMENTS** and **PREP RESULTS**
sections — they override the body of the card, and they contain corrected
commands for several gates whose first drafts were wrong.

Order: G5 freeze LSN + convergence → G6 excluded private grant table →
G7 38-sequence sync → G8 final `.catscan` delta (~579 files / 6.8 GB;
needs the one-use SSH path re-opened, including a Hetzner Cloud Firewall
rule added and removed by hand) → G9 shadow start + frozen reconciliation
and private API smoke → G10 disable subscription, retain the slot for now →
**G11 writable activation** → G13a scheduler endpoint flags → G12 DNS
change and public acceptance → G13b resume Cloud Scheduler and run one
controlled cycle, then drop the source replication slot.

**G11 is the hard cutoff.** Writable startup runs migrations, populates
buyer seats and cleans sessions, so it writes to the target immediately.
After G11 there is no resume path: rollback becomes restore-or-fix-forward,
never "re-enable the subscription".

### Rollback (about five minutes, valid only before G11)

1. Restore the source login roles if Gate 4 was ever applied.
2. On the GCP VM: remove `/etc/nginx/sites-enabled/catscan-maintenance`,
   re-apply the real site with
   `DOMAIN_NAME=scan.rtb.cat bash /opt/catscan/scripts/apply_gcp_nginx_auth_contract.sh`
   (auto-detection fails because the site symlink was removed), then
   `systemctl start catscan.service`. The pre-cutover nginx tree is archived
   at `/var/tmp/nginx-precutover.tgz` on the VM.
3. Verify health on the VM before touching DNS. DNS needs no action unless
   G12 already ran.
4. Restart the four stopped timers and restore the docker-cleanup cron.
5. Resume the three Cloud Scheduler jobs and diff against the recorded
   pre-window state.
6. Re-run the read-only preflight and require all twelve checks green.

### Where the artifacts are

- Window evidence (private, 0600): `/home/jen/private/rtbcat-cutover-20260801/`
  — preflight receipt, scheduler before/after state, staged credentials.
- Staging status, approvals and deviations:
  `docs/internal/rtbcat-migration/PRE-FREEZE-STAGING-STATUS-2026-08-01.md`.
- Pre-window acceptance evidence (all green 2026-08-01): 12/12 read-only
  preflight, 10/10 public and 7/7 finance reconciliation with identical
  hashes, `.catscan` rsync dry-run, Cloudflare DNS preflight — all under
  `docs/internal/rtbcat-migration/`, checksummed in
  `LOCAL-SHA256SUMS-2026-08-01`.
- Prepared on the Hetzner app host before the window: production
  `scan.rtb.cat` nginx site and its TLS certificate (valid into late
  October, issued by DNS-01 **from the operator workstation** because the
  DNS token is IP-locked — renewal is a workstation task, not a host cron),
  activation scripts under `/root/rtbcat-scripts/`, and corrected login
  settings in `/etc/rtbcat/runtime.env` (backup alongside it).
- Prepared on the Hetzner database host: reconciliation and sequence tools
  with a vendored driver under `/var/tmp/rtbcat-cutover-tools/`.
- Source and target migration ledgers were proven identical before the
  window, so writable startup has no pending migration to replay.

## B3c `rtb_daily` acceptance — July 31, 2026

B3c is accepted through copy, post-copy construction, source-to-target
validation and fresh backup. Production authority has **not** moved: Cloud SQL,
GCP ingress, DNS and the source schedulers remain authoritative, while the
Hetzner application and schedulers remain stopped.

The July 30 partitioned restart completed its bulk copy, but the first
post-copy review found that target `buyer_id` was a nullable ordinary column
rather than the source's stored generated column. PostgreSQL 15 logical
replication does not supply the generated value, so accepting that copy would
have left it null. With explicit owner approval, only target `rtb_daily` was
recreated and recopied using the corrected generated-column contract. The
source table, publication, main slot, other 97 target tables and production
writers were not reset.

Accepted state:

- PR #117 was reviewed and merged as `ffaafad9812201588611a0c9d5814ef2f3911c43`.
  The schema-kit correction and regression coverage are on PR #118.
- The corrected retry copied 566,204,007 rows and reached 98/98 subscription
  tables `ready` at `2026-07-31T11:28:31Z`.
- Post-copy construction finished at `14:27:23Z`: 12 monthly partitions, all
  7 parent indexes valid, the four dependent views restored, populated
  `seat_report_completeness_daily` with all 3 indexes valid, and fresh
  statistics. `buyer_id` is stored-generated from `buyer_account_id`.
- Structural evidence is root-only under
  `/mnt/HC_Volume_106446141/logical-sync/20260731T142820Z-rtb-daily-acceptance`.
  Its canonical and normalized schema SHA-256 values are
  `58142d973f809b5774a4260885b63d267e6809c0b553f1eddde79cde59aaebed`
  and `d69f220f006d6461faaafac880b70676c6488119b83f4f626eba0cb4ffab107b`.
- January through July matched source exactly per day for row count, distinct
  row hash, spend, impressions, clicks, bid requests and generated buyer
  value. July also passed identical source-before/source-after snapshots.
  The 21 aggregate files and checksum manifest are root-only mode 0600 under
  `/mnt/HC_Volume_106446141/logical-sync/20260731T142927Z-rtb-daily-validation`.
- The main source slot is active at near-zero retained/confirmed lag and the
  safety monitor is healthy. Fresh differential
  `20260726-113211F_20260731-173611D` completed successfully at `18:10:14Z`;
  the repository/archive check passed at `18:11:04Z`. Its root-only checksummed
  receipt is under
  `/mnt/HC_Volume_106446141/logical-sync/20260731T181104Z-rtb-daily-backup-acceptance`.

This acceptance does not authorize sequence transfer, the excluded private
grant-table transfer, a source writer freeze, target application activation,
DNS changes or scheduler ownership changes. Those remain final-window gates.

## B3a source replication objects accepted — July 29, 2026

The owner directed the next migration step after B2. Guarded source tooling was
committed and pushed as `553c6127`, then its exact SHA-256-matched copy ran
against Cloud SQL. The deployment-critical suite passed 111 tests.

Accepted source state:

- login `rtbcat_migration_repl` has `LOGIN` and `REPLICATION`, but is not a
  superuser, `cloudsqlsuperuser` member, role/database creator or RLS bypasser;
- the login has database connect, usage on `public` and
  `financial_viability`, and SELECT on exactly 98 accepted tables;
- publication `rtbcat_migration_pub` explicitly contains those 98 tables,
  is not `FOR ALL TABLES`, publishes insert/update/delete/truncate, and has
  ordered table-name checksum `c2af91c3598c914e5c2493532e81adb8`;
- the one `agent_private` table is excluded;
- the temporary finance-owner membership existed only inside the creation
  transaction and was revoked before commit;
- the credential is escrowed root-only on the Hetzner application host; it was
  streamed for creation and login verification without being printed; and
- Cloud SQL still has zero replication slots. Production, DNS, all three Cloud
  Scheduler jobs and both GCP/Hetzner application postures remain unchanged.

An active `rtb_daily` autovacuum advanced WAL by about 640 MB in a 30-second
sample. Cloud Monitoring showed approximately 469.4 GB used of 514.3 GB before
auto-growth, while `pg_ls_waldir()` later reported about 1.49 GB of current WAL.
An unattached slot could therefore retain WAL dangerously quickly. The slot
must be created by the subscriber only when it is ready to consume immediately.

**Next authority boundary:** preserve the July 22 evidence, stop the Hetzner
shadow, replace the stale rehearsal database, restore the exact empty schema
and start the monitored subscriber. This is destructive and remains separately
approval-gated. Do not create an idle slot, freeze source writers, change DNS
or enable target writers/schedulers.

## B2 Cloud SQL logical decoding accepted — July 29, 2026, 11:23 UTC

The owner explicitly approved immediate B2 execution, overriding the earlier
August 1 watch hold. Preflight found a live Gmail import, so no maintenance
started until its real worker completed and released the production lock.

Accepted evidence:

- on-demand Cloud SQL backup `1785323946722` completed successfully from
  11:19:06 through 11:22:09 UTC;
- update operation `708af4fa-da73-4f34-8fa4-5dd400000031` set exactly
  `cloudsql.logical_decoding=on` and completed from 11:22:53 through
  11:23:25 UTC;
- the zonal PostgreSQL 15 instance returned `RUNNABLE`, PITR remained enabled
  with seven-day transaction-log retention, and PostgreSQL reported
  `wal_level=logical`;
- current capacity is 10 replication slots, 10 WAL senders and 4 logical
  replication workers; no additional capacity flag was needed for the planned
  single subscription;
- six consecutive database-backed production health checks passed on release
  `sha-10c4594`; the GCP API container remained healthy and Gmail import
  returned idle;
- all three Cloud Scheduler jobs remained enabled against `scan.rtb.cat`;
  production and temporary DNS continued to resolve to their original GCP and
  Hetzner IPv4 addresses; and
- zero publications and zero replication slots existed immediately after B2.

The first backup attempt under read-only `cat-scan@rtb.cat` was denied without
creating anything. The successful backup and patch used the existing
`billing@amazingdo.com` Editor binding; no IAM grant or active-account default
was changed.

This section predates the separately accepted B3a source-role/publication
checkpoint above. B2 by itself did not authorize those objects or any target
rehearsal-database replacement, subscriber, writer freeze, DNS change or target
writer/scheduler.

## Temporary public-path acceptance complete — July 29, 2026

The DNS-only Cloudflare `A` record `scan-hetzner.rtb.cat` now resolves only to
the stable Hetzner app IPv4. Nginx 1.24 serves a valid Let's Encrypt certificate
and restricts HTTPS to loopback plus the operator `/32`; an independent request
from the Hetzner database host returned 403. Production `scan.rtb.cat` still
resolves to GCP.

The temporary path returns healthy release `10c45949` and routes OAuth through
a hardened OAuth2 Proxy 7.6.0 listener on `127.0.0.1:4180`. The initial
secret-store client was stale and deleted; it was replaced through an
encrypted, non-persistent stream from the live GCP OAuth configuration.
`https://scan-hetzner.rtb.cat/oauth2/callback` was additively registered on the
existing Web OAuth client without removing the production callback. A real
browser login as the existing RTBcat account succeeded at 10:34 UTC, and
subsequent `/api/auth/me` requests returned 200.

The first browser attempt exposed that the API trusted only loopback even
though host-published Docker traffic arrives from gateway `172.18.0.1`.
Temporary Compose now discovers and trusts that exact gateway in addition to
loopback; it does not trust a broad Docker/private CIDR. Password login is
hidden only on this read-only rehearsal because creating a password session
writes session/audit rows. It remains unchanged on production and returns when
the Hetzner database is activated writable. The production GCP Google flow has
the same loopback-only trust setting and the operator reports it never worked;
production was not changed during this gate.

The API/dashboard remain on loopback, `CATSCAN_READ_ONLY_SHADOW=true`, the
database remains `rtbcat_serving_rehearsal`, and all three scheduler flags are
false. All three scheduled POST endpoints returned 405. The repo guards are
`scripts/hetzner/manage_temp_public_ingress.sh`,
`scripts/hetzner/install_temp_google_oauth_proxy.sh` and
`scripts/hetzner/rehearse_temp_google_login.sh`. GCP, Cloud SQL, production
writers and source schedulers are unchanged.

## B1 accepted — July 29, 2026, 08:11 UTC

The separately approved B1 boundary is complete. The accepted immutable
Hetzner release `10c45949` ran briefly in private writable mode against the
stale rehearsal database with all three schedulers disabled, then returned to
the accepted loopback-only read-only shadow posture.

Accepted evidence:

- GCP production, Cloud SQL, DNS and all three source scheduler jobs remained
  authoritative and unchanged;
- a fresh encrypted target differential backup completed before the rehearsal,
  and another completed after it; WAL archival still reports zero failures;
- writable release verification passed for the exact API/dashboard digests,
  PostgreSQL, retained Google access, scheduler guards and loopback listeners;
- Gmail, precompute and creative-cache scheduled endpoints each refused
  execution with HTTP 503;
- a real target write inserted one probe row inside a transaction, rolled it
  back and proved no schema or row residue remained;
- migrations 070 and 071 were applied to the stale rehearsal database during
  the first startup, as expected for release `10c45949`;
- the final application mode is `CATSCAN_READ_ONLY_SHADOW=true`, all scheduler
  flags are false, the database default is read-only, mutation middleware
  returns 405 and both containers are healthy; and
- the accepted receipt and failed-safe first-attempt receipt are mode 0600
  under
  `docs/internal/rtbcat-migration/b1-live-writable-rehearsal-2026-07-29/`.

The first attempt encountered a transient connection reset in the immediate
post-Compose verifier. Its failure path restored the database default and
shadow containers; a settled manual verification passed. The bounded operator
path was then hardened with verifier retries, its focused 28-test set passed,
and the controlled retry was accepted. The independent 15-minute deadman was
cancelled only after verified restoration.

This section predates the separately accepted B2 maintenance recorded above.
B1 by itself did not authorize B2 or any subscriber replacement, source writer
freeze, DNS, scheduler ownership change or final writable activation.

---

## Next engineer resume — July 28, 2026, ~08:35 UTC (urgent workstation reboot)

**Safe to reboot this PC.** Resume here. Do not re-derive production state from
scratch.

### Snapshot (verified ~08:23–08:35 UTC)

| Item | Value |
|------|--------|
| GCP production | healthy `git_sha` **`sha-10c4594`** (`main` image **`10c45949`**) |
| Production host | `catscan-production-sg` / project `catscan-prod-202601` / zone `asia-southeast1-b` |
| `origin/main` (docs tip) | **`f2070069`** — PR #115 reboot checklist; prior **`20e385ad`** PR #113 production checkpoint |
| App SHA serving traffic | still **`10c45949`** (do **not** redeploy without a new directive) |
| Hetzner | loopback **read-only shadow** @ same app SHA; **writable activation NOT authorized** |
| Deploy run that shipped 10c45949 | `30247640095` |
| Pre-deploy Cloud SQL backup | `1785138478528` SUCCESSFUL |
| Migrations live | 070 ledger + 071 currency |

### Exact next actions (priority order)

1. **After reboot — reauth if needed**  
   `gcloud auth login --account=cat-scan@rtb.cat`  
   (IAP SSH and A1 checks require it. Last good reauth was morning Jul 28.)

2. **A1 watch week (already armed — keep it running through ~Fri Aug 1)**  
   - Checker:  
     `docs/internal/rtbcat-migration/gcp-deploy-10c45949/a1-watch-check.sh`  
   - Criteria:  
     `…/a1-watch-week-criteria.md`  
   - Artifacts:  
     `…/a1-checks/check-*.txt`  
   - Scheduled task: durable **every 4h** (Grok scheduler id `019fa7b99abb` —
     re-create if lost after reboot).  
   - Manual smoke after reauth:  
     `bash docs/internal/rtbcat-migration/gcp-deploy-10c45949/a1-watch-check.sh`  
     Expect `A1_RESULT=CLEAN` outside incident criteria.  
   - **Last CLEAN run:** `20260728T082330Z` — health ok, `skip_count=0`,
     watchdog only knowns (299038253 + late non-spend kinds), D-1 check
     deferred until ≥13:45 UTC.  
   - **Incident = report to CTO, no self-remediation / no redeploy:**  
     unknown watchdog `ok:false`; **any** duplicate-batch alert;  
     `duplicate_downstream_skip_count` still elevated **Thu+** (expect ~0 by
     Wed); D-1 spend missing for active seats **at 13:45+ checks**; health
     leaves `10c4594`.  
   - **Friday close-out:** BQ multi-batch probe over July (expect zero) +
     watch-week summary.

3. **A2 ADT note — draft only, unsent**  
   Paths (same content family):  
   - `docs/internal/rtbcat-migration/gcp-deploy-10c45949/adt-daily-spend-notification-draft.md`  
   - `docs/internal/rtbcat-migration/gcp-deploy-10c45949/adt-note-draft-2026-07-28.md`  
   **No send without Jen’s explicit go.**

4. **A3 BQ `_bak_` drops** — **blocked** on ADT confirmation (A2).  
   Tables (when approved): `rtb_daily_dupbatch_0705x6_bak_20260721` + the two
   July 13/14 `_bak_` tables. One approved session, counts before/after.

5. **A4 Cloud SQL backup break-glass — plan ready, not executed**  
   Plan:  
   `docs/internal/rtbcat-migration/gcp-deploy-10c45949/a4-cloudsql-backup-role-plan.md`  
   Custom role `catscanCloudSqlBackupOperator`  
   (`backupRuns.create/get/list` + `instances.get`) → `cat-scan@rtb.cat`.  
   **Execute only after CTO “approve A4”** then prove one create+list.

6. **A5 Node-24 actions PR — open**  
   **https://github.com/jenbrannstrom/rtbcat-platform/pull/114**  
   Branch `chore/node24-actions-ready`.  
   Bumps `checkout` v4→v5, `upload-artifact` v4→v5, `setup-node` v4→v5.  
   Standing dependency-audit waiver applies if those reds gate merge.

7. **B1 live writable Hetzner rehearsal** — **CTO directive not issued yet**.  
   Execute nothing. **B2+ (logical decoding restart, etc.) not this week**
   (watch week).

### Private evidence (mode 0600 — never force-add / commit)

`docs/internal/rtbcat-migration/gcp-deploy-10c45949/` including:

- `postdeploy-proofs-brief-2026-07-27.md`  
- `proof1-*`, `proof1-and-2-*`, `proof3-*`, `watchdog-2026-07-27-1915.txt`  
- `phase-close-2026-07-27.json`  
- A1/A2/A4 files above  

### Standing rules

- Redaction grep before staging tracked docs (8 patterns; zero hits required;
  never paste spend totals into tracked docs).  
- Nothing serves that isn’t a pushed sha-tagged image — no hot-patch / `docker cp`.  
- Hetzner shadow stays untouched until B1 directive.  
- Local branch note: `fix/uplivo-agent-currency` may hold a private force-added
  commit — **never push it**.

### SSH (production, read-mostly)

```bash
gcloud compute ssh catscan-production-sg \
  --project=catscan-prod-202601 --zone=asia-southeast1-b \
  --account=cat-scan@rtb.cat --tunnel-through-iap
```

Inside API container: `sudo docker exec catscan-api …`  
Async DB: `python3 -c "import asyncio; from storage.postgres_database import pg_query; … asyncio.run(...)"`  
Avoid single quotes in SQL through SSH (`make_date` / `::bigint`).

---

## Previous resume — July 27, 2026, ~22:50 UTC (GCP production @ 10c45949)

Read this section before running anything. The detailed, chronological evidence
follows below.

### GCP production checkpoint — deploy `main` @ `10c45949` accepted

Production (`catscan-production-sg`, project `catscan-prod-202601`) is serving
`main` @ `10c45949d08f671c69743e9fc557cb9956921487` (health `git_sha`
`sha-10c4594`). Deployed 2026-07-27 morning via manual CD run `30247640095`
(contract gate included). Pre-deploy Cloud SQL on-demand backup
`1785138478528` SUCCESSFUL ~07:50 UTC. Migrations **070**
(`gmail_processed_messages` ledger) and **071** (`buyer_seats.currency_code`,
Tuky internet `8087233591` = EUR) applied at startup.

**What is live on GCP production:**

- parquet→BQ idempotency option A (100%-duplicate redelivery → raw export
  discarded + inline publish skipped);
- buyer currency contract (EUR seat returns EUR; legacy `spend_usd` null where
  appropriate);
- daily-spend completeness fields + unread-independent Gmail discovery via the
  070 ledger;
- D+1 missing-spend alerting;
- scheduler ownership guards (all three `CATSCAN_ENABLE_*_SCHEDULER=true` in
  the production container; `CATSCAN_READ_ONLY_SHADOW` absent).

**Time-based proofs (2026-07-27):**

| Proof | Result |
|-------|--------|
| 10:15 Gmail import | **PASS** — completed 12:44 UTC; 86 files; 49 duplicate-downstream skips; ledger 86 `imported`; MobYoung metric 07-26 present single-valued; Jul 1–20 continuity verified against baseline (exact values in private evidence only) |
| 13:45 + 19:15 watchdog | **PASS** with known notes — no multi-batch; seat `299038253` spend-lane missing is known/by-design; a few non-spend report kinds late with spend-lane still ok on active seats |
| 22:30 precompute | **PASS** — refresh began 22:30:01 UTC (home + config breakdowns for 07-26→07-27); **no 503 / no “Scheduler disabled”**; Cloud Scheduler reports status code 4 (DEADLINE_EXCEEDED) while work continues inside the API (retries visible) — flag path healthy |

Private evidence (mode 0600, never commit):  
`docs/internal/rtbcat-migration/gcp-deploy-10c45949/`.

### Debt register (carry forward)

1. **Cloud SQL backup break-glass** — human `gcloud sql backups create` 403 for
   operator accounts; only `catscan-ci` has `cloudsql.editor`. Nearly cost the
   pre-dispatch window. Document a Token Creator / break-glass path.
2. **GitHub Actions Node.js 20 deprecation** annotations on deploy workflow
   actions (Node 24 default cutoff risk).

### Optional business follow-ups (not this phase)

- Notify ADT that completeness fields + currency contract are live.
- Document permanent −1.08% residual on metric 07-05.
- Drop BQ `_bak_` tables once ADT confirms reconciliation.

### Authority boundary (unchanged for Hetzner cutover)

- Hetzner remains a loopback-only **read-only shadow**; shadow acceptance still
  does **not** authorize writable activation.
- No DNS, Cloud Scheduler *config*, or Cloud SQL flag changes were made in
  this phase (jobs left as scheduled).
- Do not redeploy or hot-patch from this checkpoint without a new phase
  directive.

Exact next action for migration work: still **writable activation blocked**
until separate explicit approval. Production feature ship of `10c45949` is
**closed**.

## Previous resume — July 26, 2026, 21:42 SAST (Hetzner shadow)

(Superseded for “what is on GCP production” by the July 27 checkpoint above;
retained for Hetzner shadow chronology.)

Current authority and safety boundary (Hetzner / migration):

- the migration has **not** cut over;
- Cloud SQL, GCP ingress, DNS and the three Cloud Scheduler jobs remain
  authoritative and unchanged;
- the Hetzner application is a loopback-only, **read-only shadow** with every
  scheduler flag false;
- **shadow acceptance does not authorize writable activation** — that is a
  separate phase with its own explicit approval;
- no live writer activation, DNS change, scheduler change or Cloud SQL restart
  is authorized; and
- private evidence stays under `docs/internal/` mode 0600, never committed.

### Accepted shadow release (this phase)

- Immutable merge SHA on `main`: `10c45949d08f671c69743e9fc557cb9956921487`
  (tree `9ff2ffae83decddc727d720384df780b202cb5a5`), PR #112 squash.
- Manual GHCR run `30215441691` (85 deployment-critical tests including
  scheduler/activation/shadow guards).
- Digests on Hetzner:
  - API `ghcr.io/jenbrannstrom/catscan-api@sha256:e046d1c355fb9a6436e85b9c18d43b91a7b57b365bb83798fa3494434574251f`
  - Dashboard `ghcr.io/jenbrannstrom/catscan-dashboard@sha256:c4becb3191772f7f02a43aeb6400675f0abbc22bd30bb105534dfd75804943ce`
- Prior accepted shadow still archived for rollback:
  `332ec985084085edef714525d118f6c6ad2db8d4`.
- Verification: digests match, API/dashboard on `127.0.0.1` only, **15/15**
  GET contracts `200` with `X-CatScan-Shadow: read-only`, **2/2** mutations
  `405`, all three scheduler flags `false`, Google access probes ok, rollback
  list includes prior + new release.
- One soak cycle vs GCP: **target_request_failures=0**,
  **target_shadow_header_failures=0**, 15/15 target `200`+shadow header;
  source had 2 request failures and expected snapshot drift (strict exit
  nonzero is not a target regression).
- Guardian note (auth): agent/API token GET may write `last_used_at`; soak ran
  on the July 25 baseline auth pattern; "zero mutations" is qualified that
  way. Production was not written as a soak target.

Rollback under incident (compose var rename this release):

```bash
export RTBCAT_DB_AUTH_FILE=/etc/rtbcat/secrets/postgres-password
# then rollback_app_release.sh to 332ec985… (artifacts under /var/lib/rtbcat/releases/)
```

Stage new releases **outside** `/var/lib/rtbcat/releases/` (e.g.
`/root/releases/<sha>/`) so stray compose files never shadow archived
checksums.

Private evidence: `docs/internal/rtbcat-migration/shadow-release-2026-07/`.

Exact next action: **writable activation remains blocked** until a separate
explicit approval. Do not run `activate_writable_release.sh` live. Logical
decoding, subscriber replacement, source writer freeze, DNS cutover, target
writes and target schedulers retain their own later gates.

## Previous resume — July 26, 2026, 17:01 SAST

(Superseded by the 21:42 shadow-acceptance resume above for “what is running
now”; retained for chronology.)

Current authority and safety boundary at 17:01:

- the migration had **not** cut over;
- Cloud SQL, GCP ingress, DNS and the three Cloud Scheduler jobs remained
  authoritative and unchanged;
- the Hetzner application was still a loopback-only, read-only shadow with every
  scheduler flag false;
- no live writer activation, DNS change, scheduler change or Cloud SQL restart
  was authorized; and
- the worktree was intentionally dirty. Preserve unrelated/user changes: do not
  reset, clean, restore or broadly stage it, and do not force-add
  `docs/internal/`.

Accepted gates at 17:01:

- encrypted pgBackRest backup/WAL archival uses the dedicated native-GCS
  repository in Singapore, not Johannesburg; two full backups, timers and a
  clean-host PITR restore were accepted;
- disposable Hetzner server `155417362`, firewall `11370709`, the unused HMAC
  credential and legacy environment file, and witness database
  `rtbcat_pgbackrest_pitr_probe` were removed; the refreshed Terraform plan is
  empty;
- the exact 38-sequence sync rehearsal passed, including compensating recovery
  after an induced partial apply and an idempotent exact reapply; and
- writable activation tooling passed local check-only rehearsal. This was not a
  live activation and made no external state change. The last combined focused
  run passed 51 relevant tests.

Private evidence is under `docs/internal/rtbcat-migration/`, including:

- `PGBACKREST-EXECUTION-2026-07-26.json`;
- `sequence-sync-rehearsal-2026-07-26/summary.json`; and
- `writable-activation-rehearsal-2026-07-26/summary.json`.

Keep that evidence mode 0600 and outside commits. The operating references are
`docs/HETZNER_MIGRATION_NEXT_ENGINEER.md` and
`docs/HETZNER_FINAL_SYNC_RUNBOOK.md`.

## Writable activation guard — check-only accepted — July 26, 2026, 16:54 SAST

Local activation engineering is complete without changing the running Hetzner
shadow, Cloud SQL, DNS, writers or schedulers. The checksum-matched Compose
artifact now defaults to shadow mode but can be rendered writable only through
`scripts/hetzner/activate_writable_release.sh`. The existing shadow deploy
explicitly overrides inherited shell values back to read-only/all-schedulers-off.

The activation entry point requires the exact live confirmation and mode-0600
evidence for source writer freeze, zero active source writer sessions,
subscriber catch-up, exact sequence sync, final reconciliation, target backup,
unchanged DNS and disabled target schedulers. It accepts only digest-pinned
images and the release-matched Compose checksum, keeps API/dashboard on
loopback, starts writable mode with all three scheduler flags false, and
restores verified shadow mode if live activation verification fails.

The check-only rehearsal passed:

- the rendered API was writable with Gmail, precompute and creative-cache
  schedulers all false;
- API/dashboard remained bound only to `127.0.0.1`;
- wrong confirmation returned exit 2 before rendering;
- evidence claiming an enabled scheduler returned exit 1 and created no
  receipt;
- inherited shell values attempting to enable all schedulers were neutralized;
- 29 activation/scheduler/read-only focused tests passed; and
- the manual immutable-image workflow now includes the scheduler and activation
  guard tests.

Private evidence is under
`docs/internal/rtbcat-migration/writable-activation-rehearsal-2026-07-26/`.
This is not a live activation acceptance. The changed Compose/tooling and
scheduler endpoint guards must be reviewed, published as a new immutable
release and deployed as a shadow before a live writable rehearsal. Publishing
or deploying that release is an external change and still requires explicit
approval.

## Sequence-state rehearsal accepted — July 26, 2026, 16:44 SAST

The next cutover-engineering gate passed without touching Cloud SQL, the
Hetzner rehearsal database, DNS, writers or schedulers. Two disposable,
loopback-only PostgreSQL 15.17 containers exercised the exact 38-sequence
inventory used by the final-sync helper, including mixed `is_called` states and
quoted/schema-qualified identifiers.

The rehearsal found a critical safety error before production use:
PostgreSQL `setval()` changes survive transaction rollback. The helper now
requires a mode-0600 JSON recovery record before apply, preflights target
`UPDATE` privileges, and compensates for apply failure by restoring and
verifying every pre-apply target state.

Accepted results:

- wrong confirmation and missing recovery evidence both refused with exit 2;
- initial read-only comparison found the deliberately divergent 38 states;
- an induced failure occurred after 37 partial `setval()` changes;
- compensating recovery restored all 38 original values/flags, and an
  independent reread matched the pre-apply evidence exactly;
- the successful apply changed all 38 states and produced an exact match;
- the post-apply compare passed and the idempotent reapply changed zero states;
- 11 focused tests, Ruff, Python compilation and diff checks passed; and
- both disposable containers were removed and their loopback ports closed.

Private evidence is under
`docs/internal/rtbcat-migration/sequence-sync-rehearsal-2026-07-26/`.
The next gate is the immutable writable-target activation rehearsal with every
scheduler initially disabled; it does not authorize a production writer,
scheduler, DNS or Cloud SQL change.

## Backup/PITR gate accepted — July 26, 2026, 14:31 SAST

Production authority remains unchanged. Cloud SQL is writable and
authoritative; the Hetzner application remains the loopback-only read-only
shadow with every scheduler disabled. No DNS, production writer, scheduler or
Cloud SQL setting changed.

The repository is the dedicated pgBackRest repository bucket (exact name in
private evidence) in Singapore (`asia-southeast1`), matching
the application region. It has uniform access, public-access prevention,
versioning, 14-day soft delete, 30-day noncurrent cleanup and seven-day
incomplete-multipart cleanup. The dedicated runtime service account has only
bucket-level `roles/storage.objectUser` and no project roles. The repository
uses pgBackRest's native GCS driver and AES-256-CBC encryption.

An initial GCS XML/S3-compatible attempt was rejected because the XML endpoint
returns HTTP 404 when pgBackRest deletes an absent object and pgBackRest's S3
driver treats that response as fatal. Runtime configuration was changed to the
native GCS driver, which explicitly accepts the missing-object result. The
native service-account JSON key and repository cipher passphrase are separately
escrowed as version-1 Secret Manager secrets with user-managed
`asia-southeast1` replication. After restore acceptance, the unused HMAC key
was deactivated and deleted, its Secret Manager secret was deleted, and its
root-only target environment file was removed. No credential payload is
recorded in evidence, and temporary workstation/transit copies were removed.

The accepted chain on `rtbcat-production-db` has `archive_mode=on`, zero
archive failures and two retained full backups. The selected full
`20260726-113211F` covered 438,979,227,000 source bytes, stored about 57.1 GB,
and completed in 1,977,336 ms. Full, differential and daily repository-check
timers are enabled with full retention 2 and differential retention 6.

The isolated PITR witness target was
`2026-07-26T12:06:53.141026Z`. The opt-in Terraform plan applied exactly one
firewall and one disposable Singapore `cpx62`, with zero updates or deletes.
The clean host restored 438,979,227,293 bytes from `20260726-113211F` in
409,337 ms and promoted at the selected target. Acceptance passed:

- PostgreSQL 15.17, checksums on, archive mode off and loopback-only listener;
- 98 application tables in `rtbcat_serving_rehearsal`;
- the before-target witness is present and the after-target witness is absent;
- PostgreSQL is no longer in recovery; and
- 177,329,164,288 bytes remained free on the local root disk.

The drill exposed and fixed two maintained-script defects without recopying
data: RFC3339 recovery targets are now normalized for PostgreSQL 15, and the
restore bootstrap no longer lowers `max_connections` below the source value.
Private evidence is in
`PGBACKREST-BACKUP-2026-07-26.json`,
`PGBACKREST-PITR-PROBE-2026-07-26.json`,
`PGBACKREST-CLEAN-HOST-PITR-2026-07-26.json` and
`PGBACKREST-EXECUTION-2026-07-26.json`.

Approved cleanup completed at 12:57 UTC: Terraform destroyed disposable server
`155417362` and firewall `11370709` with no other infrastructure changes. The
server exceeded Hetzner's graceful-shutdown timeout and was then deleted; its
local disk is not recoverable, while accepted evidence remains preserved
privately. The unused HMAC/secret and legacy environment file were removed,
and the isolated PITR witness database was dropped. A refreshed Terraform plan
is empty. A post-cleanup native-GCS check archived WAL through
`0000000100000068000000F4`; the repository retains both healthy full backups,
all three timers are enabled and archive failures remain zero.

## Backup/PITR gate preflight — July 26, 2026, 10:31 SAST

Production authority remains unchanged. Cloud SQL is writable and
authoritative; the Hetzner application is still the loopback-only read-only
shadow with every scheduler disabled. No DNS, writer, scheduler, GCP resource,
Hetzner resource or target-host configuration changed during this pass.

Read-only target preflight confirmed:

- PostgreSQL 15.17 and data checksums are healthy;
- the rehearsal cluster uses about 413 GB;
- pgBackRest 2.58.0 is installed, but the repository is empty/unconfigured;
- `archive_mode` is still off, no pgBackRest timers exist and no backup was
  started;
- public SSH remains available only through the retained operator `/32`; the
  database Tailscale peer was offline; and
- the existing 1,500 GB Volume quota has only 200 GB free, which cannot hold a
  second production-sized restore Volume.

Local backup/recovery engineering now includes:

- hardened non-blocking pgBackRest S3-compatible configuration in
  `scripts/hetzner/configure_pgbackrest_s3.sh`;
- a separate full-backup acceptance check before recurring timers can be
  enabled;
- metadata-only backup/WAL evidence generation in
  `scripts/hetzner/verify_pgbackrest_backup.sh`;
- isolated before/after PITR witness creation;
- guarded bootstrap and time-target restoration that refuse the production
  database host and a non-empty disposable cluster; and
- an opt-in Terraform `cpx62` clean-host drill resource using its 640 GB local
  disk, disabled by default so it consumes no Volume quota.

Validation passed: eight focused tests, Ruff, Bash parsing, Terraform format
and validation, and `git diff --check`. The default live Terraform plan remains
empty. The separately generated drill plan has exactly two creates (one
firewall and one `cpx62`), zero updates and zero deletes.

Superseded decision note: this preflight initially proposed Johannesburg for a
country-level failure boundary. The owner correctly clarified that the
application is in Singapore and approved Singapore storage to avoid needless
inter-region traffic and restore egress. No Johannesburg storage was created.
The accepted Singapore execution and exact private evidence are recorded in
the current checkpoint above.

## Night shutdown checkpoint — July 25, 2026, 22:14 SAST

Safe to shut down the operator workstation. Resume this migration; do not
restart it from discovery or repeat completed bulk transfers.

Start tomorrow with:

```bash
cd /home/jen/Documents/rtbcat-platform
git status --short --branch
sed -n '1,260p' docs/HETZNER_MIGRATION_NEXT_ENGINEER.md
sed -n '1,260p' docs/HETZNER_FINAL_SYNC_RUNBOOK.md
git check-ignore -v \
  docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md
```

Current authority and safety state:

- production has **not cut over**;
- Cloud SQL is still writable and authoritative;
- GCP application ingress, DNS and all three Cloud Scheduler jobs are
  unchanged;
- the Hetzner application remains the loopback-only, read-only shadow with
  scheduler flags false;
- no Cloud SQL flags, publications, slots, database roles or sessions were
  changed during final-sync planning;
- no target database was dropped or created;
- no target writer or scheduler was enabled;
- the six-hour soak and its SSH tunnel are stopped; no related local process
  was running at this checkpoint; and
- the worktree remains intentionally dirty on
  `fix/uplivo-agent-currency`, ahead of its configured remote base by one
  commit. Do not reset, clean, restore or broadly stage it.

Completed today:

- six-hour paired API soak accepted: 300/300 successful Hetzner requests,
  every read-only header present; GCP repeated the same two HTTP 500s and one
  timeout in all 20 cycles;
- immutable tree-identical A→B→A application rollback accepted and current
  manifest restored;
- Cloud SQL/target logical-replication and storage audit completed read-only;
- writer/scheduler inventory completed, including the dormant finance-schema
  owner role (name in private evidence);
- final synchronization, writer freeze, DNS, scheduler ownership and rollback
  cutoff documented in `docs/HETZNER_FINAL_SYNC_RUNBOOK.md`;
- concise resume checkpoint written to
  `docs/HETZNER_MIGRATION_NEXT_ENGINEER.md`;
- scheduled write endpoints now have local explicit-true ownership guards;
- guarded 38-sequence comparison/apply helper added at
  `scripts/hetzner/sync_postgres_sequences.py`; and
- touched-area validation passed: 49 tests, Ruff and `git diff --check`.

Do not attempt to catch up `rtbcat_serving_rehearsal`. Cloud SQL had no logical
slot preserving changes since July 22. The accepted plan is to preserve its
evidence, then—only after explicit destructive approval—replace it with a
fresh schema-matched subscriber that performs an online initial copy and
continuous logical catch-up.

The independent encrypted Hetzner pgBackRest/WAL backup chain, PITR and
clean-host restore are now accepted. The next local engineering gates are a
disposable rehearsal of the sequence helper and an immutable writable
activation that starts with every scheduler disabled.

Separate approvals remain mandatory for:

- Cloud SQL logical-decoding flags and restart;
- replication role/publication/slot creation;
- stopping the shadow and replacing the July 22 rehearsal database;
- writer freeze and final non-credential `.catscan` delta;
- subscription/slot finalization;
- DNS; and
- the first Hetzner write and scheduler enablement.

Hard rollback boundary: before the first accepted Hetzner write, return to
frozen GCP if necessary. After the first Hetzner write, Cloud SQL is stale
unless reverse synchronization has been proven; use fix-forward or the Hetzner
backup chain.

Exact private evidence is under `docs/internal/rtbcat-migration/`; that entire
tree is intentionally ignored and must never be force-added or included in a
public snapshot.

## Workstation reboot checkpoint — July 22, 2026

The local workspace is intentionally dirty and must be resumed, not reset.
Branch `fix/uplivo-agent-currency` contains uncommitted currency-contract and
BigQuery idempotency work plus untracked migration
`storage/postgres_migrations/071_buyer_seat_currency.sql`. No production
deploy, DNS change, GitHub push or Hetzner mutation was made during the
migration-readiness/reboot-preparation pass.

Migration documentation now has two privacy layers:

- Sanitized, intended for tracking after review:
  `docs/HETZNER_MIGRATION_PLAN.md`, `docs/HETZNER_MIGRATION_READINESS.md` and
  the updated `ROADMAP.md`.
- Private/ignored: `docs/internal/rtbcat-migration/`, including the full live
  inventory, reboot recovery material and backup manifest. `docs/internal/`
  is gitignored; do not force-add it and do not include it in a public
  snapshot.

Readiness verdict: provision and rehearse now; do not schedule production
cutover. The hard gates are a full timed restore, target WAL/PITR plus a clean
restore drill, target IaC/deploy/timers, off-provider Google access testing,
the writer-freeze/rollback runbook, and deployment of the local
data-correctness changes from a clean immutable SHA.

After reboot, start with:

```bash
cd /home/jen/Documents/rtbcat-platform
git status --short --branch
git check-ignore -v docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md
sed -n '1,220p' docs/internal/rtbcat-migration/REBOOT-CHECKPOINT-2026-07-22.md
```

Do not run `git reset`, clean ignored files, or deploy until that checkpoint
and the backup manifest have been reviewed.

### Migration execution checkpoint — July 23, 2026

Resume at **Part 1 provisioning** using the current-execution section at the
top of `docs/HETZNER_MIGRATION_PLAN.md`. Parts 1–3 are implemented locally but
no Hetzner resource has been created, no migration data has moved, and no DNS,
production-writer or scheduler change has occurred. Terraform is initialized
and an ignored placeholder-free tfvars file exists, but the project token is
absent and remote-state recovery, Singapore availability/limits, independent
backup storage and the off-GCP Google identity remain prerequisites. Exact
cost/account evidence is kept in the ignored private master inventory, not in
this tracked handover.

Continuation audit on July 23: an existing retained, versioned GCS state bucket
was identified and the stack was prepared for an isolated GCS backend prefix;
the exact bucket config remains ignored/private. `cat-scan@rtb.cat` was
reauthenticated and passed a write/read/delete recovery probe in the isolated
prefix; the probe was removed. Backend initialization completed July 23.
Current project-API pricing corrects the planning envelope to approximately USD
291.69/USD 261.01 because Volumes are USD 0.0767/GB-month. The revised cost
was approved July 23. Limits are also insufficient: only one server slot and
1,024 GB of Volume capacity are available; request at least six total servers
and 1,300 GB (eight/1,500 recommended). The first token was generated in the
wrong existing `amazingDO.com` project; read-only discovery exposed the
project mismatch. Its credential value was removed before Terraform use, an
isolated replacement token was saved mode `0600`, and read-only API checks
confirm its project is empty. The wrong token was revoked in the Console. The
stack is initialized against the isolated GCS backend using `cat-scan@rtb.cat`
ADC, with no resource-state object yet. An ignored saved plan (SHA-256
`174ef61e62388097dc25c1851a96f8000440af14eecc54ce0769ad517f9b25de`) has 13
expected Hetzner creates, no updates/deletes, no public PostgreSQL and no
non-Hetzner provider; regenerate it after limit approval. The account-wide
eight-server/1,500 GB limit increase was submitted July 23 and is pending. The
previously unprotected temporary 400 GB rehearsal Volume now has a dedicated
deletion-protection switch and documented two-apply removal path.
`terraform fmt -check -recursive` and `terraform validate` pass after those
changes. No Hetzner resource, saved plan, image, transfer, DNS change or writer
change was made.
The reboot checksum manifest now reports expected mismatches only for the two
living migration documents updated after the July 22 archive; every immutable
backup artifact and preserved source file still passes. Do not rewrite the
archive checksum manifest to hide those post-backup changes.

Privacy gate before any GitHub push: the local ahead commit contains a
force-added private investigation record, and older tracked handover material
also predates the current privacy boundary. Do not push this branch or run the
public-snapshot script until the private investigation is removed from the
branch history and the tracked tree has passed a dedicated sanitization review.

### Migration validation checkpoint — July 24, 2026

The full online restore is complete and the restored database remains
read-only. A new reusable suite at `scripts/catscan_mcp_db_smoke.py` ran eight
future-MCP-shaped media-buyer contracts against Cloud SQL and
`rtbcat_serving_rehearsal`. All six shared buyers and the closed 30-day window
`2026-06-22` through `2026-07-21` matched exactly (8/8 contracts, identical
normalized row hashes). Unit/API coverage passed 27/27. The target was faster
for every contract in this tunnelled smoke; do not treat cross-tunnel timings
as a controlled benchmark.

Preserve the suite, `docs/CATSCAN_MCP_DB_SMOKE.md` and the ignored detailed
evidence in
`docs/internal/rtbcat-migration/CATSCAN-MCP-DB-SMOKE-2026-07-24.json`.
The temporary local source-secret payload was removed and both tunnels exited.
The expanded gate later passed 10/10 public contracts through `2026-07-22`,
including exact calendar-month and all-time canonical spend, plus 7/7 private
finance contracts. The private schema has matching 154-column/14-table
structure and is empty on both sides; active finance audit data remains in its
separate SQLite store. Evidence is in
`docs/internal/rtbcat-migration/DATABASE-RECONCILIATION-2026-07-24.json`.

The next pass completed the online application-data rehearsal and local
read-only application shadow. The bulk source-to-target rsync plus delta copied
12,476 non-credential regular files and 100,810,997,029 logical bytes; target
count/bytes and runtime ownership match, credentials are absent and about 57.0
GB remains free. Production stayed live. The one-use SSH key and temporary
source `/32` cloud/UFW rules were removed and the direct path is blocked again.

The current API ran locally against `rtbcat_serving_rehearsal` with
`CATSCAN_READ_ONLY_SHADOW=true`. All 15 GET checks passed, two mutation checks
returned 405, and the run fixed compatibility with the restored pre-071 buyer
seat schema and the older publisher aggregate schema. QPS analysis now leaves
the FastAPI event loop and runs its size/geo queries concurrently; the live
90-day request completed in 42.7 seconds while health remained responsive.
Evidence is in the ignored
`docs/internal/rtbcat-migration/SHADOW-APPLICATION-AND-APPDATA-2026-07-24.json`.

Do not apply a Terraform plan that proposes host replacement. A temporary
firewall plan revealed that maintained cloud-init templates changed the
force-replacement `user_data` hash. Both server resources now explicitly ignore
post-provision `user_data`; formatting/validation pass and the live plan is
empty.

The digest-pinned target-host shadow is now accepted. Sanitized release
`332ec985084085edef714525d118f6c6ad2db8d4` was merged, its manual GHCR build
passed, and the exact API/dashboard digests run loopback-only on the target.
Deployment acceptance passed private PostgreSQL TLS and Google service probes.
The target-host suite passed 15/15 authenticated GET contracts and both
mutation probes returned 405; evidence is in the ignored
`docs/internal/rtbcat-migration/TARGET-HOST-SHADOW-APPLICATION-2026-07-24.json`.
The owner explicitly approved reusing the existing service-account key as a
migration bridge. DNS, production writers and all target schedulers remain
unchanged. Next work is a bounded read-only soak, rollback rehearsal and the
independent target backup/restore gate—not another bulk transfer or a cutover.

### Read-only soak checkpoint — July 25, 2026

`scripts/catscan_api_read_only_soak.py` now automates the paired GCP/Hetzner
application soak documented in `docs/CATSCAN_API_READ_ONLY_SOAK.md`. It sends
only the same 15 rehearsed GET contracts, requires every target response to
carry `X-CatScan-Shadow: read-only`, and records status, latency, response
size, exact hashes, value-free schema hashes and changed JSON paths. It does
not retain response bodies, credentials or buyer IDs. Focused soak, shadow and
QPS regression tests pass 11/11.

The July 25 one-cycle baseline completed 15/15 target requests with no missing
shadow headers. GCP returned HTTP 500 for the 90-day RTB funnel and publisher
contracts and exceeded the 120-second timeout for the 90-day QPS summary.
Seats and 90-day spend matched exactly. The remaining result drift is expected
to include post-July-22 source writes; request failures and JSON-shape changes
are counted separately. GCP is serving revision `30f24771`, while the target
runs accepted revision `332ec985084085edef714525d118f6c6ad2db8d4`; this is a
comparison of real deployed behavior, not a controlled same-build provider
benchmark. Detailed ignored evidence is under
`docs/internal/rtbcat-migration/api-soak/baseline-2026-07-25/`.

A supervised six-hour soak started at `2026-07-25T07:54:12Z`, using a
15-minute pause between cycles and a supervised loopback SSH tunnel. The
one-use API-key file was deleted immediately after startup. Both
`rtbcat-read-only-soak-20260725.service` and
`rtbcat-soak-tunnel-20260725.service` were active after launch. Evidence is
written after every completed cycle under
`docs/internal/rtbcat-migration/api-soak/six-hour-2026-07-25/`. After the run,
inspect `summary.json` and the two unit states before accepting the soak or
moving on to immutable rollback rehearsal. Do not enable writers, schedulers
or DNS as part of that review.

Rollback preflight ran while the soak continued, without restarting the target.
The host initially had only the current accepted manifest, so a real version
transition could not yet be rehearsed. PR-head SHA
`9aeb5732c5054d9a40e70e07fecb7a7913a89f93` has the exact same Git tree as
accepted merge SHA `332ec985084085edef714525d118f6c6ad2db8d4`. Its guarded
manual GHCR workflow run `30152700277` passed and produced a second
digest-pinned manifest, making it a behavior-identical alternate for an
A→B→A drill after the soak. The target deploy and verify helpers exactly match
the accepted commit. The initially absent rollback wrapper was installed from
that same immutable commit, checksum
`22862c8842e7d0896b13662150afab7322ab9fc1788fc1f995eaeb624a50a53b`,
without restarting the shadow; its list command resolves the current accepted
manifest. Private preflight evidence is in
`docs/internal/rtbcat-migration/ROLLBACK-REHEARSAL-PREFLIGHT-2026-07-25.json`.
No container, DNS, writer or scheduler changed during preflight.

The soak and rollback drill completed later on July 25. Twenty paired cycles
made 300 target requests; all 300 succeeded and every response retained the
read-only shadow header. GCP repeated the same two HTTP 500s and one
120-second QPS timeout in all 20 cycles, so strict mode correctly returned
nonzero for 60 source failures. Seats and 90-day spend matched exactly 20/20.
Target QPS p50/p95 was 30.0/30.7 seconds and data-health p50/p95 was
35.9/36.0 seconds.

The A→B→A immutable drill then activated tree-identical alternate SHA
`9aeb5732c5054d9a40e70e07fecb7a7913a89f93`, passed every deployment gate,
and used the actual rollback wrapper to restore accepted SHA
`332ec985084085edef714525d118f6c6ad2db8d4`. Independent post-rollback
verification again passed digest, database, Google access, read-only,
scheduler and listener checks. The candidate transfer was removed and the
local tunnel stopped. DNS, production writers and target schedulers never
changed. Consolidated private evidence is in
`docs/internal/rtbcat-migration/SOAK-AND-ROLLBACK-2026-07-25.json`.

### Final synchronization planning checkpoint — July 25, 2026

Read-only Cloud SQL inspection found PostgreSQL 15.17 with no instance flags,
publication, subscription or migration slot. Enabling
`cloudsql.logical_decoding` requires a restart. A slot created now cannot
recover changes since the July 22 rehearsal snapshot, so do not attempt an ad
hoc catch-up of `rtbcat_serving_rehearsal`. The accepted strategy is a fresh
schema-matched logical subscriber with `copy_data=true`, followed by continuous
catch-up and a final approved writer freeze.

The target audit found 98 ordinary tables, all with primary keys, 38 sequences,
two stored generated columns, no RLS/partition roots/large objects and no
existing logical-replication objects. Its permanent Volume cannot hold both the
438.9 GB rehearsal DB and a second full copy; preserve the checksummed dump and
acceptance evidence, then replace the rehearsal only under a separate
destructive approval.

Live writer inventory found three enabled Cloud Scheduler jobs (Gmail,
precompute and creative cache), general API mutations/background jobs, and
the dormant finance-schema owner role (name in private evidence), which owns
the 14 private-finance tables. The systemd report-delivery and contracts
timers are normally read-only but should be stopped during freeze for quiet
validation.

That owner role is now traced to its external controller (name in private
evidence). That controller's current store is local SQLite. Its sole `archi`
timer reads RTBcat through the buyer-scoped HTTP API and has no current
PostgreSQL path; the Cloud SQL role/schema are provisioned for a possible
future runtime. Treat the role as dormant, recreate its ownership/grants on
target, and still set it `NOLOGIN` during the source freeze.

The three scheduler flags were discovered to be reporting-only: with secrets
present, the scheduled endpoints could still execute after DNS moved even when
the target environment said `false`. Local code now enforces an explicit-true
flag at each scheduled write endpoint and defaults absent flags to disabled.
The focused scheduler/health tests pass 28/28 and Ruff passes. This is not yet a
production control; it must be reviewed and shipped in the immutable cutover
release.

`scripts/hetzner/sync_postgres_sequences.py` now supplies the required
dry-run-by-default 38-sequence comparison and guarded target apply. It preserves
`last_value` plus `is_called`, requires
`--confirm APPLY_SEQUENCE_STATE` plus a mode-0600 pre-apply recovery record.
Because `setval()` is nontransactional, failure triggers verified compensating
restoration rather than relying on rollback. The PostgreSQL 15.17 rehearsal and
11 focused tests are accepted.

The sanitized plan is `docs/HETZNER_FINAL_SYNC_RUNBOOK.md`; exact private
findings are in
`docs/internal/rtbcat-migration/FINAL-DATABASE-SYNC-AND-CUTOVER-2026-07-25.md`.
The concise resume document for the next engineer is
`docs/HETZNER_MIGRATION_NEXT_ENGINEER.md`; use it before reconstructing state
from the older chronological sections in this file.
No Cloud SQL flag, database, role, scheduler, API, DNS or writer state changed
during planning.

## Incident addendum (July 21-22, 2026) — daily-spend 07-05 multiplied 7×

Author: incident session of July 21-22 (ADT spend over-report brief). Full
evidence-backed RCA + remediation record:
`investigations/RCA-mobyoung-0705-multiplied-2026-07-21.md` (in local commit
`27051027` — the force-added record covered by the privacy gate above).

- ADT reported `/api/agent/v1/daily-spend` for buyer `6634662463` ~30% above
  the AB console month-to-date. Sole cause: metric **2026-07-05** served at
  (exact values in private evidence) micros — exactly **7 identical 557,102-row
  `buyer_spend` batches**. The `5JULY` recovery re-run (the "in flight" item
  in the July 14 handover below) was created as a **recurring** AB schedule
  and never deleted; it re-delivered the same file daily Jul 15-21. The PG
  lane deduped every repeat (`rows_imported=0`); the BQ raw-export lane
  appended (`WRITE_APPEND`, no idempotency); publisher #108 summed all
  batches.
- The delivery watchdog alerted twice daily Jul 16-19 (journal/status-JSON
  only — nobody consumes it), then 07-05 **aged out of the 14-day duplicate
  sweep** on Jul 20 and went silent while the day kept growing. Both gaps
  (alert channel, latching) are still open.
- Remediation (guardian-approved, executed Jul 21 ~19:50 UTC, verified
  Jul 22 ~04:55 UTC): 6 duplicate batches backed up to BQ
  `rtb_daily_dupbatch_0705x6_bak_20260721` (3,342,612 rows), deleted, day
  re-materialized (refresh run `a2fc5379`, EXIT=0; gmail-import lock held
  during the window, removed after). Serving state now: 07-05 =
  (exact values in private evidence) micros; Jul 1-20 total = (exact values in
  private evidence); single batch `a2451dad` in BQ; zero multi-batch spend
  days for any seat since Jul 1.
- Owner deleted the `5JULY` schedule Jul 22 morning. Conclusive confirmation
  is the first post-deletion delivery wave (~10:00 UTC) + 10:15 import
  passing with no re-delivery — a one-shot check runs 10:40 UTC Jul 22.
  **Until the idempotency guard deploys there is no protection**: any
  re-delivery re-inflates the day within minutes and the watchdog will NOT
  alert (aged out). Re-dedupe steps are in the RCA's remediation section.
- Client-facing: Jul 1-20 now reads (exact values in private evidence) vs
  console (exact values in private evidence). The residual **(−1.08%) is
  permanent**: the recovered 07-05 file is a display-formatted (2 dp) export
  that zeroes the sub-cent tail (July 13 RCA). Document it to ADT; do not
  chase it as a live bug.
- Follow-up work is scoped in `docs/BRIEF_PARQUET_BQ_IDEMPOTENCY.md` (same
  local commit): option A (discard the raw parquet export + skip the inline
  publish when a file imports as 100% duplicates) is implemented locally in
  this working tree, **not deployed**; durable option C (batch-aware
  readers) remains open.
- Drop `rtb_daily_dupbatch_0705x6_bak_20260721` together with the two
  July 13/14 `_bak_` tables once ADT confirms reconciliation.

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

### Local follow-up: buyer-currency API contract (not deployed)

Branch `fix/uplivo-agent-currency` adds migration 071 and makes Agent API money
denomination-aware. One known non-USD seat is explicitly EUR; other currently
known seats are USD. Exact buyer mappings and reconciliation evidence are in
the ignored private reboot checkpoint. `/daily-spend` now returns the currency
in both `buyer.currency` and `data_source.currency`, while
`/stats-summary` adds neutral `currency`, `spend`, and `avg_cpm` fields. Legacy
`spend_usd` / `avg_cpm_usd` fields are `null` for non-USD seats instead of
mislabeling EUR values. Unknown currencies remain `null` and are never guessed.

The private reconciliation evidence matches the canonical API micros value.
A separate historical invoice discrepancy remains unresolved and was not
edited. Apply migrations 070 and 071 when deploying the combined branch, then
verify the known non-USD seat returns `EUR`. Until that deployment, production
still exposes the old currency-ambiguous response contract.

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
- Staging/old VM: `catscan-production-sg2` was permanently deleted July 22,
  2026 together with its 80 GB boot disk and static IPv4. Retirement snapshot
  `catscan-production-sg2-retirement-20260506-0327` is retained. The deploy
  workflow only supports `production`.
- Terraform state bucket: `gs://catscan-prod-202601-tfstate`, prefix
  `terraform/gcp`
- Production access from a workstation: `gcloud --account=billing@amazingdo.com`
  with `--tunnel-through-iap` (plain SSH times out)

Do not recreate `catscan-production-sg2`; its retirement snapshot is the
retained recovery artifact.

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
5. Run a full Terraform plan with privileged credentials and review drift.
6. Address the GitHub Actions Node.js 20 deprecation warnings before GitHub's
   Node 24 default cutoff (June 16, 2026 per run annotations). **Carried from
   2026-07-27 production deploy close-out.**
7. **Cloud SQL on-demand backup break-glass** — operator accounts cannot
   `gcloud sql backups create` (403); only `catscan-ci` holds
   `roles/cloudsql.editor`. Document Token Creator / break-glass before the
   next production deploy that needs a pre-dispatch backup. **New 2026-07-27.**
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
