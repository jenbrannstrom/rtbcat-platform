# Hetzner migration — next engineer checkpoint

Last updated: July 29, 2026 (B1 bounded live writable rehearsal accepted)

## Read this first

The migration has **not cut over**. Cloud SQL, GCP application ingress, DNS and
the three production Cloud Scheduler jobs remain authoritative and unchanged.
The Hetzner application is a loopback-only, **read-only shadow** with all
scheduler flags false.

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

Cloud SQL has no logical-decoding flag, publication or retained migration slot.
A slot created now cannot reproduce changes since the July 22 snapshot. The
safe plan is:

1. Preserve the accepted independent Hetzner backup/PITR evidence.
2. Freeze DDL.
3. In an approved maintenance window, enable Cloud SQL logical decoding. This
   restarts the instance.
4. Preserve the accepted July 22 evidence and dump.
5. Under separate destructive approval, replace the old rehearsal database
   with an empty schema-matched logical subscriber.
6. Let the initial copy and continuous logical catch-up finish while GCP
   remains authoritative.
7. In the approved cutover window, freeze every source writer, wait past the
   captured source LSN, synchronize all sequence state, run the final
   non-credential `.catscan` delta and reconcile.
8. Switch DNS, start one writable Hetzner deployment, and enable one scheduler
   owner only.

The target contains 98 ordinary tables, all with primary keys, 38 sequences and
two stored generated columns. It has no RLS tables, partition roots or large
objects. The permanent target Volume can hold one production database but
cannot safely hold both the 438.9 GB rehearsal and a second full copy.

## Writer and scheduler findings

Three enabled Cloud Scheduler jobs trigger Gmail import, precompute refresh and
creative-cache refresh. Their URLs use the public hostname, so the jobs follow
DNS.

The scheduler feature flags were previously reporting-only. Local code now
enforces them at each scheduled endpoint and defaults absent flags to disabled:

- `services/scheduler_guard.py`
- `api/routers/gmail.py`
- `api/routers/precompute.py`
- `api/routers/creative_cache.py`

This control is local only until reviewed, built into a new immutable image and
deployed. Do not cut over using the old image as a writable release.

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
7. Review and source-control the bounded B1 operator script and its focused
   tests; do not confuse it with final activation.
8. Complete the A1 production watch week, then measure source WAL generation
   and set explicit slot/disk alarm and abort
   thresholds.
9. Request separate approvals for:
   - Cloud SQL logical-decoding restart;
   - source publication/replication role/slot creation;
   - stopping the shadow and replacing the July 22 rehearsal DB;
   - writer freeze and final `.catscan` delta;
   - subscription/slot finalization;
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
- Do not restart Cloud SQL merely to “get ready” without an approved window.
- Do not drop `rtbcat_serving_rehearsal` without explicit destructive approval.
- Do not leave an unused logical slot retaining unbounded WAL.
- Do not run both GCP and Hetzner application writers.
- Do not install parallel systemd triggers for the three existing Cloud
  Scheduler jobs.
- Do not remove Cloud SQL or its managed backups at cutover.
- Do not route database or `.catscan` bytes through the operator laptop.
