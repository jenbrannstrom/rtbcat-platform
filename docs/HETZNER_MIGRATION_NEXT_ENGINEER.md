# Hetzner migration — next engineer checkpoint

Last updated: July 30, 2026, evening (`rtb_daily` restarted onto the
partitioned schema; copy in progress)

> **Start here, then read
> `docs/internal/MIGRATION-ENGINEER-BRIEF-2026-07-30.md`.** That brief holds the
> verified live state, the measured evidence behind the July 30 findings, the
> open decision on `rtb_daily`, and the explicitly-flagged unverified
> assumptions. Several statements in the July 29 checkpoint below were stale or
> wrong and have been corrected in place, each marked "Corrected July 30, 2026".

## Read this first

The migration has **not cut over**. Cloud SQL, GCP application ingress, DNS and
the three production Cloud Scheduler jobs remain authoritative and unchanged.
After accepted B3b, the Hetzner API/dashboard containers and temporary OAuth
service are stopped. Nginx still terminates the guarded temporary hostname but
returns HTTP 502 because the shadow is deliberately sealed. The deployed
artifact still defaults to read-only mode with all scheduler flags false.

Approved B3c is currently copying the 98 published tables into
`rtbcat_serving`. Do not stop PostgreSQL,
`rtbcat-cloudsql-logical-proxy.service`, subscription
`rtbcat_hetzner_migration`, `rtbcat-b3c-monitor.timer` or the temporary
Cloud SQL Client identity while this copy is active.

**Shadow acceptance does not authorize writable activation.** Do not run
`scripts/hetzner/activate_writable_release.sh` live without a separate explicit
approval. That next phase has its own gates (source writer freeze, sequence
sync, final reconciliation, evidence mode 0600, exact confirmation token).

Never force-add `docs/internal/` or Terraform variable/state material.

Primary operating documents:

1. `docs/HETZNER_MIGRATION_NEXT_ENGINEER.md` — this resume checkpoint.
2. `docs/HETZNER_FINAL_SYNC_RUNBOOK.md` — approval-gated synchronization and
   cutover order.
3. `docs/HETZNER_MIGRATION_PLAN.md` — complete phased plan and accepted state.
4. `docs/HETZNER_MIGRATION_READINESS.md` — remaining gates and evidence.
5. `handover.md` — chronological engineering and incident context.
6. Private exact inventory:
   `docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md`.

## July 29 B3c schema and logical initial copy — in progress

The exact current schema was captured through a loopback-only Cloud SQL Auth
Proxy. After excluding only the unpublished private table's data, the
normalized source/target schema SHA-256 matches exactly:
`4c8ba3e47fd6a92216e4969a5fc65a41ccd7939f52e169a20d67ea33d12da3fb`.
The target has 98 replicated tables, 38 sequences, both generated columns,
exact owners/grants and zero invalid indexes.

Subscription and source slot `rtbcat_hetzner_migration` were created together;
the slot was consumed immediately. A root-only 30-second monitor logs to
`/var/log/rtbcat/logical-replication-monitor.jsonl` and treats target free
space below 20%, retained source WAL above 20 GiB or an inactive proxy as
critical. At `2026-07-29T15:58:11Z`, 71/98 tables were ready, two were copying,
target free space was about 770 GB, retained WAL was negligible and no
PostgreSQL copy/apply error was present.

**Corrected July 30, 2026 — the above is a snapshot, not current state.**
Verified at ~17:30Z on July 30:

- **97/98 tables are `ready`. `rtb_daily` alone is still copying**, 25 hours in,
  at 151,160,435 of ~460M rows. Measured throughput 0.98 MB/s, so roughly
  66 hours remain and the rate degrades as its 16 indexes grow.
- **The monitor is reporting `critical_source_wal`.** The `rtb_daily` tablesync
  slot `pg_30304_sync_28572_…` is inactive-by-design during COPY but pins
  **43.7 GB** of source WAL — over 2x the 20 GiB critical threshold.
- **Cloud SQL disk is growing 45.5 GB/day** (468.6 → 514.1 GB over 24 h) with
  52.8 GB of headroom, so auto-resize fires in about 1.2 days. Cloud SQL disks
  cannot be shrunk, so that growth is permanent cost.
  `storageAutoResizeLimit` is `0` (no ceiling), which closes the outage path
  but removes the cost ceiling — **there is no alert on this**.
- The copy is **not stuck**: worker pid 184656 is alive and I/O bound on index
  pages, with zero network waits across 20 samples.

Do **not** attempt to drop indexes to speed this up in place. The worker holds
one 25-hour transaction, so both `DROP INDEX` and `DROP INDEX CONCURRENTLY`
block behind it. Speeding it up requires restarting that table's copy from
zero. That decision, its options and its runbook are in the July 30 brief.

**Updated July 30, 2026 (evening) — the decision is resolved and executed.**
With owner approval, the `rtb_daily` copy was restarted at ~20:23Z onto the
partition kit's schema (the Path A design, applied under logical replication):
monthly partitions on `metric_date`, `BIGINT` `id`, primary key
`(metric_date, id)`, dedup unique `(metric_date, row_hash)`, with the five
secondary indexes deferred until after the copy. A fresh differential backup
gated the change; the dependent `agent_read` views and the
`seat_report_completeness_daily` matview were captured and recreated (the
matview needs a `REFRESH` once the copy completes). The orphaned tablesync
slot was dropped on the source afterwards — the monitor is back to `ok`, the
retained-WAL disk growth has stopped, and a Cloud Monitoring disk alert now
exists on the instance. Early measured copy throughput is ~25 MB/s versus
~0.5 MB/s before the restart.

Consequences: the schema hash `4c8ba3e4…` quoted above is intentionally void
for `rtb_daily` only — its acceptance evidence must be re-recorded against the
partitioned schema (zero-difference per-month validation vs the source) — and
the cutover sequence handoff must set `rtb_daily_id_seq` past source
`max(id)`, because the target sequence was recreated fresh. The deployed
image needs no change: the importer probes `pg_partitioned_table` at runtime
and switches its `ON CONFLICT` target accordingly.

The unpublished `agent_private.buyer_role_grants` table exists with exact
schema but zero rows. Its frozen data requires a separate verified transfer
before cutover. B3c remains in progress until all 98 table states are `ready`,
lag is stable, schema has not drifted and a current target backup is accepted.
Private evidence:
`docs/internal/rtbcat-migration/B3C-LOGICAL-INITIAL-COPY-2026-07-29.md`.

## July 29 B3b target replacement — accepted

The owner explicitly approved preserving the rehearsal evidence, stopping the
shadow and replacing only stale database `rtbcat_serving_rehearsal`. Before the
drop, every July dump checksum passed again, the pgBackRest repository check
passed, the database had zero active sessions and final encrypted differential
backup `20260726-113211F_20260729-144851D` completed.

The guarded preflight resolved exactly one 438,948,781,415-byte rehearsal
database, exactly one empty `rtbcat_serving` database and zero user tables in
the latter. Only the rehearsal database was dropped. PostgreSQL 15.17,
checksums, WAL archiving and the protected dump Volume remain healthy; the
database Volume now has about 785 GB free. GCP production health and
`scan.rtb.cat` DNS were unchanged. The private execution receipt is
`docs/internal/rtbcat-migration/B3B-TARGET-REPLACEMENT-2026-07-29.md`.

The next gate is schema-only restore plus subscription/slot creation and
monitored initial copy. It requires separate approval. Do not start it from the
B3b approval.

## July 29 B3a source role and publication — accepted

Guarded source setup commit `553c6127` passed 111 deployment-critical tests and
its exact copy ran against Cloud SQL. Login `rtbcat_migration_repl` has
`LOGIN`/`REPLICATION`, database connect, both schema usage grants and SELECT on
exactly 98 accepted tables. It is not a superuser, `cloudsqlsuperuser` member,
role/database creator or RLS bypasser.

Publication `rtbcat_migration_pub` explicitly contains the 84 `public` and 14
`financial_viability` tables, excludes the single `agent_private` table and is
not `FOR ALL TABLES`. Its ordered table-name checksum is
`c2af91c3598c914e5c2493532e81adb8`. The transaction-scoped finance-owner grant
was revoked before commit. The credential is root-only on the Hetzner app host
and a real login verified all 98 SELECT grants.

There is deliberately **no slot yet**. A live autovacuum produced roughly
640 MB of WAL in 30 seconds while Cloud Monitoring showed about 45 GB free
before auto-growth. Create the slot only as part of subscriber creation when
the target is ready to consume immediately. Production health, schedulers, DNS
and both application postures remained unchanged.

The separately approved B3b phase later preserved the July evidence, stopped
the shadow and removed `rtbcat_serving_rehearsal`. Restoring the exact empty
schema, starting the subscriber and monitoring source WAL/target copy remain a
separate gate.

## July 29 B2 Cloud SQL logical decoding — accepted

After an active production Gmail import completed, on-demand backup
`1785323946722` succeeded. Cloud SQL update operation
`708af4fa-da73-4f34-8fa4-5dd400000031` then set only
`cloudsql.logical_decoding=on` and completed in 31.5 seconds. The instance is
`RUNNABLE`, PITR remains enabled with seven-day log retention, and PostgreSQL
reports `wal_level=logical`, 10 replication slots, 10 WAL senders and 4 logical
replication workers.

Six consecutive GCP database-backed health checks passed after recovery, Gmail
import was idle, the three Cloud Scheduler jobs remained enabled on
`scan.rtb.cat`, and both DNS records remained unchanged. No publication,
replication slot or replication login was created during B2. The existing
`billing@amazingdo.com` Editor identity performed the backup and patch after the
read-only `cat-scan@rtb.cat` attempt was denied; no IAM binding changed.

**Do not repeat B2.** The later B3a checkpoint created the bounded login and
publication, but not a slot. Neither checkpoint authorizes replacement of
`rtbcat_serving_rehearsal`, subscription initial copy, writer freeze, DNS or
target writer/scheduler activation.

## July 29 B1 bounded live writable rehearsal — accepted

The accepted `10c45949` release ran briefly in writable mode against the stale
Hetzner rehearsal database while API/dashboard remained loopback-only and all
three scheduler flags remained false. All scheduled endpoints refused with
HTTP 503. A real database write was inserted in a transaction, rolled back and
proved residue-free. The application and database were then restored to
read-only shadow posture and verified.

The first attempt safely restored after an immediate post-Compose verifier
connection reset. That startup applied the expected migrations 070 and 071 to
the rehearsal database. Verifier retries were added to the bounded operator
path, 28 focused tests passed and the controlled retry was accepted. Fresh
encrypted differential backups completed immediately before and after B1; WAL
archival still has zero failures.

Private mode-0600 evidence:
`docs/internal/rtbcat-migration/b1-live-writable-rehearsal-2026-07-29/`.

GCP, Cloud SQL, DNS and source scheduler ownership were unchanged. B1 does not
authorize the final activation command or any B2+ action.

## July 29 temporary public-path gate — accepted

`scan-hetzner.rtb.cat` is a DNS-only Cloudflare `A` record to the stable
Hetzner app IPv4. Nginx 1.24 serves a valid Let's Encrypt certificate and
allows HTTPS only from loopback and the current operator `/32`; a request from
the Hetzner database host returned 403. Production `scan.rtb.cat` still resolves
to GCP.

The temporary host returns healthy release `10c45949`, Google as its only
read-only-host login provider, and 405 for each of the three scheduled POST
endpoints. API/dashboard/OAuth listeners remain loopback-only, shadow mode is
true, the database is `rtbcat_serving_rehearsal` and all scheduler flags are
false. OAuth2 Proxy 7.6.0 uses the same valid client as the running GCP service.
The temporary callback was additively registered while preserving
`https://scan.rtb.cat/oauth2/callback`; a real browser Google login succeeded
and `/api/auth/me` returned 200.

The API trusts OAuth identity only from loopback plus the exact discovered
Docker gateway, currently `172.18.0.1`. Password login is hidden on this
read-only rehearsal because it creates database session/audit rows; restore it
only with the separately approved writable activation. GCP has the same
loopback-only OAuth trust issue and the operator reports Google never worked
there; this gate did not change production.

The guarded paths are `scripts/hetzner/manage_temp_public_ingress.sh`,
`scripts/hetzner/install_temp_google_oauth_proxy.sh` and
`scripts/hetzner/rehearse_temp_google_login.sh`. Do not edit production DNS or
treat the temporary record as a production cutover.

## July 26 immutable shadow release — accepted

- **Accepted SHA:** `10c45949d08f671c69743e9fc557cb9956921487` (tree
  `9ff2ffae83decddc727d720384df780b202cb5a5`), merged via PR #112.
- **Prior rollback SHA:** `332ec985084085edef714525d118f6c6ad2db8d4` (artifacts
  remain under `/var/lib/rtbcat/releases/`).
- **GHCR run:** `30215441691` — digest-pinned API and dashboard images.
- **Host posture:** API `127.0.0.1:8000`, dashboard `127.0.0.1:3000`;
  `CATSCAN_READ_ONLY_SHADOW=true`; all three scheduler flags false; serving DB
  is the Hetzner private rehearsal (`10.60.1.20` /
  `rtbcat_serving_rehearsal`).
- **Acceptance:** 15/15 GET contracts with `X-CatScan-Shadow: read-only`, 2/2
  mutation probes `405`, Google access probes ok, one soak cycle with
  **zero target request failures** and **zero target shadow-header failures**.
- **Rollback note:** this release renames the compose password bind env to
  `RTBCAT_POSTGRES_PASSWORD_FILE`. Rolling back to `332ec985…` through tooling
  that still renders the old compose requires:

  ```bash
  export RTBCAT_DB_AUTH_FILE=/etc/rtbcat/secrets/postgres-password
  ```

- **Staging rule:** place new release env/compose under
  `/root/releases/<sha>/` (not a loose file in `/var/lib/rtbcat/releases/`) so
  archived per-SHA compose checksums stay authoritative.
- Private evidence:
  `docs/internal/rtbcat-migration/shadow-release-2026-07/`.

## July 26 backup gate — accepted

The independent encrypted backup/WAL and clean-host PITR gate passed.
PostgreSQL 15.17/checksums remain healthy and the rehearsal database is
409 GB. Cloud SQL, GCP application ingress, DNS, production writers and
schedulers remain authoritative and unchanged.

The guarded local backup/PITR implementation is accepted. The opt-in clean-host
drill plan applied exactly one firewall and one disposable Singapore `cpx62`
with a 640 GB local disk, avoiding the current Volume-quota limit. After
acceptance, approved cleanup destroyed the server and firewall; a refreshed
Terraform plan is empty.

The approved repository is a dedicated Standard GCS bucket in Singapore
(`asia-southeast1`). This is provider-independent from Hetzner and avoids
unnecessary inter-region traffic, but it is not a country-level disaster
copy. The bucket has uniform access, public-access prevention, versioning,
14-day soft delete and lifecycle cleanup. Its only bucket IAM binding is the
dedicated service account with `roles/storage.objectUser`; that account has no
project roles. Runtime uses pgBackRest's native GCS driver with a separately
escrowed service-account JSON key and AES-256-CBC passphrase. An earlier HMAC
key was deactivated/deleted after the native-driver correction; its Secret
Manager secret and legacy root-only environment file were also removed.

Two retained full backups are healthy with zero archive failures. The selected
full `20260726-113211F` covered 438,979,227,000 source bytes and stored about
57.1 GB. Full, differential and daily check timers are enabled. The clean host
restored 438,979,227,293 bytes in 409,337 ms to
`2026-07-26T12:06:53.141026Z`; it passed PostgreSQL 15.17, checksum,
loopback-listener, archive-off, 98-table and before-present/after-absent witness
checks. Maintained scripts now normalize the target timestamp for PostgreSQL
15 and preserve the source's 100-connection recovery floor.

Private acceptance evidence:

- `docs/internal/rtbcat-migration/PGBACKREST-BACKUP-2026-07-26.json`
- `docs/internal/rtbcat-migration/PGBACKREST-PITR-PROBE-2026-07-26.json`
- `docs/internal/rtbcat-migration/PGBACKREST-CLEAN-HOST-PITR-2026-07-26.json`
- `docs/internal/rtbcat-migration/PGBACKREST-EXECUTION-2026-07-26.json`

## Completed and accepted

- Separate Hetzner app/database hosts, private network, protected Volumes,
  firewalls and PostgreSQL 15.17 foundation are provisioned.
- The production-sized online database dump/restore rehearsal completed.
  Source dump took 8,037 seconds; restore/analyze took 20,042 seconds.
- The July 22 read-only database passed 10/10 public reconciliation contracts
  and 7/7 private-finance contracts.
- The non-credential `.catscan` rehearsal transfer copied 12,476 files and
  100,810,997,029 logical bytes. Count/bytes/ownership matched and credentials
  were excluded.
- Immutable target release
  `332ec985084085edef714525d118f6c6ad2db8d4` passed image, PostgreSQL, Google,
  read-only and listener acceptance.
- The target-host API suite passed all 15 GET contracts and blocked both
  mutation probes.
- The six-hour paired soak completed 20 cycles and 300/300 successful Hetzner
  requests with every read-only shadow header present. GCP repeated the same
  two HTTP 500s and one 120-second timeout in all 20 cycles.
- A tree-identical A→B→A immutable application drill passed and restored the
  accepted release. No DNS, writer or scheduler changed.
- The encrypted Singapore GCS backup/WAL chain, recurring timers and clean-host
  time-target restore passed. No production authority changed.
- Final synchronization, writer freeze, DNS, single-scheduler ownership and
  rollback-boundary planning is written in
  `docs/HETZNER_FINAL_SYNC_RUNBOOK.md`.

Private acceptance evidence:

- `docs/internal/rtbcat-migration/DATABASE-RECONCILIATION-2026-07-24.json`
- `docs/internal/rtbcat-migration/SHADOW-APPLICATION-AND-APPDATA-2026-07-24.json`
- `docs/internal/rtbcat-migration/TARGET-HOST-SHADOW-APPLICATION-2026-07-24.json`
- `docs/internal/rtbcat-migration/api-soak/six-hour-2026-07-25/summary.json`
- `docs/internal/rtbcat-migration/SOAK-AND-ROLLBACK-2026-07-25.json`
- `docs/internal/rtbcat-migration/FINAL-DATABASE-SYNC-AND-CUTOVER-2026-07-25.md`

## Final synchronization decision

Do not attempt an ad hoc delta from `rtbcat_serving_rehearsal`.

Cloud SQL now has `cloudsql.logical_decoding=on` plus the accepted B3a
restricted login and explicit publication, but it still has no retained
migration slot. A slot created now cannot reproduce changes since the July 22
snapshot. The safe plan is:

1. Preserve the accepted independent Hetzner backup/PITR evidence.
2. Freeze DDL.
3. Preserve the accepted July 29 B2 logical-decoding/restart evidence; do not
   repeat the restart.
4. Preserve the accepted B3a source role/publication and zero-slot state; do
   not create the slot before a ready subscriber.
5. Preserve the accepted July 22 evidence and dump.
6. Preserve accepted B3b: the old rehearsal database is gone and empty
   `rtbcat_serving` remains. Do not recreate the stale rehearsal database.
7. Let the initial copy and continuous logical catch-up finish while GCP
   remains authoritative.
8. In the approved cutover window, freeze every source writer, wait past the
   captured source LSN, synchronize all sequence state, run the final
   non-credential `.catscan` delta and reconcile.
9. Switch DNS, start one writable Hetzner deployment, and enable one scheduler
   owner only.

The target contains 98 ordinary tables, all with primary keys, 38 sequences and
two stored generated columns. It has no RLS tables, partition roots or large
objects. The permanent target Volume can hold one production database but
cannot safely hold both the 438.9 GB rehearsal and a second full copy.

**Added July 30, 2026 — B3c deviated from the plan for `rtb_daily`, and this
was not recorded anywhere.**

`docs/HETZNER_MIGRATION_PLAN.md` says to restore `rtb_daily` "using the
partition migration Path A … unless rehearsal evidence rejects it", and
`docs/HETZNER_MIGRATION_READINESS.md` still lists zero-difference **partition**
validation as required acceptance evidence. The kit exists at
`scripts/partition_migration/` (commit `5c93f029`, July 28) and its README
calls the restore onto the new box "the one free rewrite of this table".

B3c instead copied `rtb_daily` as a plain unpartitioned clone with all 16
indexes. No rehearsal evidence rejecting Path A was recorded. The likeliest
explanation is that the kit was written for a dump/restore flow and the
migration pivoted to logical replication the next day without reconciling the
two — but **nobody wrote that decision down, so confirm with whoever ran B3c
rather than assuming.**

This matters now because the `rtb_daily` copy has to be restarted either way.
That restart is the last free moment to take the partitioned design. Carrying
the current design to Hetzner also carries three known problems the kit
already measured: six months of history against a configured 30-day raw
retention that has never been enforced; nine indexes with single- or
double-digit scan counts over 5.5 months; and an `id` column that is `INTEGER`
with roughly 16 months of sequence headroom left.

Options, break-even arithmetic and the runbook are in
`docs/internal/MIGRATION-ENGINEER-BRIEF-2026-07-30.md`. Do not purge history on
the **source** to shrink the copy — a mass DELETE would generate WAL that the
pinned slot must retain, making the current problem worse.

**Resolved July 30, 2026 (evening):** the restart took the partitioned
design. See the updated B3c section above.

## Writer and scheduler findings

Three enabled Cloud Scheduler jobs trigger Gmail import, precompute refresh and
creative-cache refresh. Their URLs use the public hostname, so the jobs follow
DNS.

The scheduler feature flags were previously reporting-only. Code now enforces
them at each scheduled endpoint and defaults absent flags to disabled:

- `services/scheduler_guard.py`
- `api/routers/gmail.py`
- `api/routers/precompute.py`
- `api/routers/creative_cache.py`

**Corrected July 30, 2026.** This paragraph previously said the control was
"local only until reviewed, built into a new immutable image and deployed".
That was already stale when written and contradicted the accepted-release note
below. `services/scheduler_guard.py` is present in accepted `10c45949`, and
`git diff 10c45949..HEAD` shows no `api/`, `services/` or `dashboard/` changes.
**The accepted shadow image already contains these guards; no rebuild is owed
before cutover.** Verify with `git cat-file -e 10c45949:services/scheduler_guard.py`
before acting on any claim to the contrary.

The API is also a general writer through authenticated mutations, conversion
postbacks and queued/background work. A freeze must block ingress and stop the
GCP API after active jobs drain; pausing Cloud Scheduler alone is insufficient.

The dormant finance-schema owner role (name in private evidence) owns the 14
private-finance tables, but it is not a current PostgreSQL writer. Its external
controller currently uses local SQLite, and its sole `archi` timer reads RTBcat
through the buyer-scoped HTTP API. Preserve that role's ownership/grants on
target and still set it `NOLOGIN` during freeze.

## Local cutover-preparation changes

- `scripts/hetzner/sync_postgres_sequences.py` compares all 38 sequences by
  default, preserves `last_value` and `is_called`, and refuses target writes
  unless both `--apply` and
  `--confirm APPLY_SEQUENCE_STATE` plus a recovery evidence path are provided.
- The PostgreSQL 15.17 disposable rehearsal is accepted. It proved exact
  compensation after 37 partial nontransactional `setval()` changes, then an
  exact 38-state apply and a zero-change idempotent reapply. Eleven focused
  tests pass.
- Scheduler/health guards have 28 focused passing tests.
- The expanded touched-area suite has 49 passing tests; Ruff and
  `git diff --check` pass.

The checksum-matched Compose artifact still defaults to read-only shadow mode.
`activate_writable_release.sh` remains the final-sync-only command: it requires
source freeze, subscriber catch-up, exact sequence state, reconciliation and
backup evidence. Release `10c45949`, including its scheduler guards and
activation tooling, is published and deployed as the accepted shadow.

The bounded B1 path is implemented separately in
`scripts/hetzner/rehearse_live_writable_release.sh`. It is restricted to the
stale rehearsal database, arms a 15-minute restoration deadman, performs only
a rollback-only probe and always returns the database and application to
read-only shadow posture. B1 acceptance does not weaken the final activation
gates.

## Exact resume order

1. Preserve and inspect the dirty worktree:

   ```bash
   cd /home/jen/Documents/rtbcat-platform
   git status --short --branch
   git check-ignore -v \
     docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md
   ```

2. Re-read this checkpoint and `docs/HETZNER_FINAL_SYNC_RUNBOOK.md`.
3. Do not repeat the bulk database or `.catscan` transfer without new evidence
   that the accepted rehearsal is invalid.
4. Preserve the completed cleanup evidence: the disposable pgBackRest restore
   server/firewall, unused HMAC/legacy environment and isolated PITR witness
   database have been removed.
5. Preserve the accepted private sequence-sync rehearsal evidence; do not
   repeat it without a new reason.
6. Preserve the accepted B1 evidence and both pre/post differential backups.
7. Preserve pushed B3a setup commit `553c6127`, the exact 98-table publication
   checksum and the root-only target credential; do not repeat source setup.
8. Preserve the measured autovacuum WAL burst and Cloud SQL disk-headroom
   evidence. Do not create a slot until the subscriber can consume immediately.
9. Preserve accepted B3b and request separate approvals for:
   - schema-only restore plus subscription/slot creation and monitored copy;
   - writer freeze and final `.catscan` delta;
   - subscription/slot finalization at the caught-up LSN;
   - DNS;
   - first target write and scheduler enablement.
10. Execute the final-sync runbook exactly; do not combine approval gates.

## Hard rollback boundary

Before the first accepted Hetzner write, DNS/application rollback to frozen GCP
is safe. After the first Hetzner write, Cloud SQL is stale unless reverse
synchronization has been proven. At that point, use fix-forward or the Hetzner
backup chain; do not describe Cloud SQL as a current backup.

## Do not do these

- Do not change DNS or enable a target scheduler during preparation.
- Do not repeat the accepted Cloud SQL restart.
- Do not recreate or restore `rtbcat_serving_rehearsal`; preserve the accepted
  B3b receipt and use empty `rtbcat_serving` for the fresh subscriber.
- Do not leave an unused logical slot retaining unbounded WAL.
- Do not run both GCP and Hetzner application writers.
- Do not install parallel systemd triggers for the three existing Cloud
  Scheduler jobs.
- Do not remove Cloud SQL or its managed backups at cutover.
- Do not route database or `.catscan` bytes through the operator laptop.
