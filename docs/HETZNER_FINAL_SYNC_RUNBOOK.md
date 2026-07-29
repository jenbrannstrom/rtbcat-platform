# Hetzner final database synchronization and cutover runbook

Last updated: July 29, 2026

Status: **B3c schema restore and monitored logical initial copy are in
progress; B3c is not yet accepted**. The source schema and target normalized
schema hash match, subscription/slot `rtbcat_hetzner_migration` is immediately
consumed and the shadow application remains stopped. This runbook does not
authorize repeating source setup, a writer freeze, private-table data or
sequence transfer, DNS changes or target writes.

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
   endpoint guards, plus a rehearsed production activation path (accepted B1
   July 29). Release `10c45949` passed a bounded private writable rehearsal:
   all scheduler endpoints refused, a rollback-only database write left no
   residue, and the app/database returned to read-only shadow posture. Preserve
   its private receipts and pre/post differential backups.
3. Current source schema and migration state frozen and reproduced on the empty
   subscriber. No DDL may change from schema capture through cutover unless it
   is applied to the subscriber first and separately verified.
4. Cloud SQL logical-decoding restart accepted July 29 as B2. Preserve backup
   `1785323946722` and update operation
   `708af4fa-da73-4f34-8fa4-5dd400000031`; do not repeat it.
5. Source login/publication accepted July 29 as B3a. Preserve guarded setup
   commit `553c6127`, the explicit 98-table publication checksum
   `c2af91c3598c914e5c2493532e81adb8` and zero-slot state. Do not repeat source
   setup or create a slot until the subscriber can consume immediately.
6. Target replacement accepted as B3b on July 29. The July dump passed its
   complete checksum verification, a final encrypted differential backup
   `20260726-113211F_20260729-144851D` completed, the shadow application was
   stopped and the 438,948,781,415-byte rehearsal database was removed. The
   empty `rtbcat_serving` database remains and the target Volume has about
   785 GB free. Preserve the private B3b receipt.
7. A separately approved cutover window covering writer freeze, final
   reconciliation, `.catscan` delta, DNS and writer activation.

## Phase A — create the continuously catching-up database

This phase does not move production authority.

1. Record source engine, flags, storage headroom, backup/PITR health, schema
   hash, active migrations, sequence inventory and login roles.
2. Freeze DDL. Keep ordinary DML running.
3. Preserve the accepted B2 state: `cloudsql.logical_decoding=on`,
   `wal_level=logical`, 10 slots, 10 WAL senders and 4 logical workers. The
   restart completed and production recovery passed; do not repeat it.
4. Preserve the accepted B3a login `rtbcat_migration_repl` and publication
   `rtbcat_migration_pub`. It contains the accepted 98 tables explicitly and
   excludes `agent_private`; do not repeat setup or broaden it to
   `FOR ALL TABLES`.
5. Completed as B3b July 29: the Hetzner API/dashboard and temporary OAuth
   service are stopped; the July validation records and checksum-verified dump
   remain on protected storage; final differential backup
   `20260726-113211F_20260729-144851D` protects the pre-drop state; and only
   stale database `rtbcat_serving_rehearsal` was removed. Empty cutover
   database `rtbcat_serving` remains on the same Volume.
6. Completed under B3c July 29: restore schema only, including exact collation,
   generated expressions, owners and grants. The target has 98 replicated
   tables, 38 sequences, both generated columns, zero invalid indexes and an
   exact normalized source/target schema SHA-256 of
   `4c8ba3e47fd6a92216e4969a5fc65a41ccd7939f52e169a20d67ea33d12da3fb`.
   `agent_private.buyer_role_grants` exists empty because its data is
   deliberately outside the publication.
7. Started under B3c July 29: long-lived Cloud SQL Auth Proxy
   `rtbcat-cloudsql-logical-proxy.service` listens only on
   `127.0.0.1:15432`. Subscription and slot `rtbcat_hetzner_migration` were
   created together with `copy_data=true`; consumption began immediately. The
   target app remains stopped.
8. In progress: monitor until all 98 subscription-table states are `ready`.
   The persistent 30-second monitor records source retained WAL, target disk,
   subscription state and proxy health. Continue checking source
   disk/autoresize, subscriber conflicts and apply delay.

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
- the frozen contents of excluded
  `agent_private.buyer_role_grants` are transferred separately and verified;
- target backups include this fresh database and a restore is proven;
- the immutable writable release and a scheduler-disabled activation have been
  rehearsed;
- the temporary Hetzner-only hostname has passed public TLS, reverse-proxy and
  representative read-only checks while restricted to approved operators, with
  every target scheduler still disabled; the temporary callback was additively
  registered and a real interactive Google sign-in plus `/api/auth/me`
  succeeded;
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

1. Seal the temporary hostname before opening the production cutover window.
   Preserve its TLS/public-path acceptance evidence, but do not treat the
   temporary record as production routing.
2. Start the immutable Hetzner release writable with all three scheduler flags
   still false by using `scripts/hetzner/activate_writable_release.sh` and the
   accepted final-sync evidence. The activation command does not change DNS;
   retain its mode-0600 receipt and validate health privately.
3. Switch DNS and verify TLS, OAuth, dashboard, API health and representative
   reads from public paths.
4. Keep GCP API/writers stopped. Enable the three scheduler endpoint flags on
   exactly one Hetzner API deployment, then resume the existing three Cloud
   Scheduler jobs as the sole phase-one trigger set. Do not install a parallel
   Hetzner timer set for the same work.
5. Run one controlled import/refresh cycle and verify PostgreSQL, BigQuery/GCS
   idempotency, finance-facing aggregates and delivery monitoring.
6. Keep Cloud SQL frozen and intact as the rollback snapshot.

## Rollback boundary

Before any accepted Hetzner write, rollback is straightforward: disable the
target, return DNS to GCP, re-enable the source roles/API/jobs and verify GCP
health.

The first accepted target write is the hard cutoff. Without proven reverse
synchronization, Cloud SQL is stale from that moment and DNS rollback would
lose Hetzner writes. After the cutoff, prefer fix-forward or restore the
Hetzner database from its own backup chain. Never describe frozen Cloud SQL as
a current backup after target writes begin.
