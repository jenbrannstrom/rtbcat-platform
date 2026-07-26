# Hetzner final database synchronization and cutover runbook

Last updated: July 25, 2026

Status: **planned, not authorized for execution**. This runbook does not
authorize a Cloud SQL restart, replacement of the July 22 rehearsal database,
a writer freeze, DNS changes or target writes.

## Synchronization decision

Use a fresh PostgreSQL logical-replication initial copy followed by continuous
catch-up. Do not try to calculate an ad hoc delta from the July 22 rehearsal
database.

The live Cloud SQL instance did not have logical decoding or a replication slot
at the July 22 snapshot. A slot created now cannot recover WAL that was not
retained for it, so that old database cannot be made an exact current replica.
A second frozen full dump is also unsuitable: the measured dump plus
restore/analyze path took about 7.8 hours.

The fresh-copy approach is viable because:

- source and target are PostgreSQL 15.17;
- all 98 replicated tables are ordinary leaf tables and have primary keys;
- there are no large objects, row-level-security tables or existing
  publications/subscriptions;
- the target has enough space for one production-sized database, but not the
  old rehearsal database and a second full copy at the same time; and
- normal source writes can continue while the initial table copy and logical
  catch-up run.

PostgreSQL logical replication does not reproduce DDL or sequence state. The 38
sequences therefore require a final frozen-state transfer. Two stored generated
columns also require an explicit same-schema replication test. See the
[PostgreSQL 15 restrictions](https://www.postgresql.org/docs/15/logical-replication-restrictions.html)
and [configuration guidance](https://www.postgresql.org/docs/15/logical-replication-config.html).
Cloud SQL requires `cloudsql.logical_decoding=on`; changing that flag restarts
the instance, so it belongs in its own approved maintenance action. See
[Google Cloud's logical replication procedure](https://docs.cloud.google.com/sql/docs/postgres/replication/configure-logical-replication).

## Hard gates

Do not start the initial copy until all of these are accepted:

1. Independent encrypted target WAL backup, PITR and clean-host restore proof
   (accepted July 26; preserve the private pgBackRest execution evidence).
2. A reviewed immutable application release containing the enforced scheduler
   endpoint guards, plus a rehearsed production activation path. Local
   writable/all-schedulers-off rendering and refusal guards pass, but the
   changed immutable release is not yet published, shadow-deployed or
   live-rehearsed.
3. Current source schema and migration state frozen and reproduced on the empty
   subscriber. No DDL may change from schema capture through cutover unless it
   is applied to the subscriber first and separately verified.
4. An approved Cloud SQL maintenance window for the logical-decoding restart.
5. Explicit approval to preserve the accepted rehearsal evidence and replace
   the July 22 database. The target Volume cannot hold both full databases.
6. A separately approved cutover window covering writer freeze, final
   reconciliation, `.catscan` delta, DNS and writer activation.

## Phase A — create the continuously catching-up database

This phase does not move production authority.

1. Record source engine, flags, storage headroom, backup/PITR health, schema
   hash, active migrations, sequence inventory and login roles.
2. Freeze DDL. Keep ordinary DML running.
3. In the approved maintenance window, enable Cloud SQL logical decoding and
   the measured replication-slot/worker capacity. Prove the restart completed,
   the app recovered and existing source behavior remains healthy.
4. Create a dedicated least-privilege replication login and an explicit
   publication containing the accepted 98 tables. Do not use `FOR ALL TABLES`;
   additions must remain deliberate.
5. Stop the Hetzner shadow app. Preserve the July 22 validation records and
   checksummed dump, then—in a separately approved destructive action—replace
   the rehearsal database with an empty cutover database on the same Volume.
6. Restore schema only, including the exact extensions, collation, generated
   expressions, owners and grants needed at cutover. Validate the expected
   schemas, 98 tables, 38 sequences and zero invalid indexes before copying
   data.
7. Run a long-lived, loopback-only Cloud SQL Auth Proxy on the database host.
   Create one subscription with `copy_data=true`. The target app must remain
   stopped and have no writable database credentials during this copy.
8. Monitor until all subscription-table states are `ready`. Continue monitoring
   source retained WAL, source disk/autoresize, subscriber conflicts, target
   disk, apply delay and proxy/service health.

Abort and cleanly remove the slot/subscription if retained WAL threatens source
availability, the target has less than 20% free space, the schema changes
unexpectedly, a table-copy worker repeatedly fails or the replication
connection cannot be made reliable. WAL thresholds must be calculated from the
observed source write rate before enabling the slot; do not leave an abandoned
slot consuming disk.

## Phase B — pre-cutover acceptance

Before requesting the final window:

- every one of the 98 subscription tables is `ready`;
- repeated samples show stable near-zero logical lag with no apply errors;
- table counts and the fixed-cutoff 10/10 database suite reconcile;
- the 7/7 private-finance suite reconciles;
- both generated columns produce the same values on source and target;
- target backups include this fresh database and a restore is proven;
- the immutable writable release and a scheduler-disabled activation have been
  rehearsed;
- DNS TTL, TLS, OAuth callbacks, API clients and rollback ownership are signed
  off; and
- a named operator and verifier are assigned to every approval gate.

## Writer inventory and freeze order

The three Cloud Scheduler jobs are the live Gmail import, precompute refresh and
creative-cache refresh triggers. Their HTTP targets use the public application
hostname, so they follow DNS; they are not tied to the GCP VM. The feature flags
must therefore be real endpoint guards, not documentation labels.

The production API is also a general writer: authenticated mutation routes,
conversion postbacks and queued Gmail/background work can write PostgreSQL and
retained Google-native storage. Stopping only the scheduled jobs is not a
writer freeze.

In the approved window, use this order:

1. Confirm no Gmail import/background refresh is running. If one is active,
   wait for a clean completion or abort the window.
2. Pause all three Cloud Scheduler jobs and record their prior state.
3. Put the GCP application behind maintenance/write-blocking ingress, then stop
   the GCP API container. Keep the Cloud SQL proxy and the dedicated logical
   replication path running.
4. Stop the report-delivery and contract-check timers for quiet validation.
   Their normal invocations are read-only, but they must not obscure the
   cutover state.
5. Block both application database login roles, terminate their remaining
   sessions and confirm that only the dedicated replication connection and
   approved administrator validation sessions remain.
6. Confirm no manual deploy, database migration, retention job, one-shot
   recovery process, export operation or external finance writer is active.
7. Capture the source freeze LSN and repeat the activity/transaction check.
   Any unexpected writer aborts the cutover.

The scheduled GitHub security and live-smoke workflows are not database
writers. The logical-backup workflow reads Cloud SQL and creates a GCS export;
ensure no export is in progress during the freeze to avoid unnecessary load.
The separate ADT finance controller currently uses local SQLite and reads
RTBcat through the buyer-scoped HTTP API; the dormant finance-schema owner role
(name in private evidence) is a dormant future-runtime identity. Block it during
freeze anyway, and validate the read-only HTTP consumer after DNS changes.

## Final convergence and validation

With source writers frozen:

1. Wait until the subscriber has replayed at least the captured freeze LSN,
   source retained-lag bytes are zero and the same result holds for three
   consecutive samples.
2. Capture all 38 source sequence `last_value`/`is_called` pairs in one
   read-only source snapshot and apply them to the matching target sequences.
   Re-read both sides and require an exact match. Use
   `scripts/hetzner/sync_postgres_sequences.py`: it compares by default,
   requires an exact 38-sequence inventory and refuses writes unless both
   `--apply` and `--confirm APPLY_SEQUENCE_STATE` are present. Apply also
   requires a mode-0600 `--json-out` recovery record written before the first
   target change. PostgreSQL does not roll back `setval()`; if apply fails, the
   helper must report `recovery.recovered_target_before=true` before any retry.
   The successful final report must have `status=accepted`,
   `sequence_count=38` and `exact_match=true`.
3. Run the final non-credential `.catscan` rsync delta directly from source
   server to target Volume. Stop the target app first; never transfer credential
   paths or route data through the operator laptop. Recompute source/target
   count, logical-byte, ownership and credential-exclusion manifests.
4. Run fixed-cutoff table counts/hashes, the 10/10 public database suite, the
   7/7 private-finance suite, generated-column checks and the authenticated API
   smoke against the still-private target.
5. Record the caught-up LSN, validation hashes, sequence manifest, application
   release/digests and database backup identity in immutable evidence.
6. Disable the subscription at the accepted LSN before target writes start.
   Either remove the source slot promptly or retain it under an explicit,
   monitored reverse-sync decision; an idle retained slot can exhaust source
   WAL storage.

No target write is allowed if any convergence or validation check differs.

## DNS and single writer activation

These are separately approved mutations:

1. Start the immutable Hetzner release writable with all three scheduler flags
   still false by using `scripts/hetzner/activate_writable_release.sh` and the
   accepted final-sync evidence. The activation command does not change DNS;
   retain its mode-0600 receipt and validate health privately.
2. Switch DNS and verify TLS, OAuth, dashboard, API health and representative
   reads from public paths.
3. Keep GCP API/writers stopped. Enable the three scheduler endpoint flags on
   exactly one Hetzner API deployment, then resume the existing three Cloud
   Scheduler jobs as the sole phase-one trigger set. Do not install a parallel
   Hetzner timer set for the same work.
4. Run one controlled import/refresh cycle and verify PostgreSQL, BigQuery/GCS
   idempotency, finance-facing aggregates and delivery monitoring.
5. Keep Cloud SQL frozen and intact as the rollback snapshot.

## Rollback boundary

Before any accepted Hetzner write, rollback is straightforward: disable the
target, return DNS to GCP, re-enable the source roles/API/jobs and verify GCP
health.

The first accepted target write is the hard cutoff. Without proven reverse
synchronization, Cloud SQL is stale from that moment and DNS rollback would
lose Hetzner writes. After the cutoff, prefer fix-forward or restore the
Hetzner database from its own backup chain. Never describe frozen Cloud SQL as
a current backup after target writes begin.
