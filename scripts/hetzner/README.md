# Hetzner migration operations — Part 2

These scripts implement the database-host, private-access and recovery portion
of the migration. They are designed to run on the target Hetzner hosts after a
reviewed `terraform apply`; none should run on the operator laptop except
syntax/tests.

The old 160 GB figure belonged to the superseded CPX32 proposal. PostgreSQL is
currently about 420 GiB. The right-sized target uses a 750 GB permanent database
Volume and a separate temporary 400 GB directory-dump Volume during rehearsal.

## Data path

```text
Online rehearsal (no writer freeze)

Cloud SQL primary ──TLS via localhost-only Cloud SQL Auth Proxy──▶ Hetzner DB host
                                                               ├─ directory dump
                                                               └─ rehearsal restore

Operator laptop ──SSH control commands only────────────────────▶ Hetzner DB host
```

The laptop does not proxy, download or retain database bytes. Cloud SQL remains
the writable production source throughout rehearsals. `pg_dump` uses a
consistent snapshot while normal readers and writers continue.

The bulk copy is not left until the last minute. The rehearsal measures it in
advance; if that duration is longer than the approved freeze window, the final
method must pre-copy the data and retain WAL from a coordinated snapshot so
cutover transfers only a bounded logical-replication delta.

A July 22 read-only live check confirmed that the Cloud SQL source has public
IPv4 enabled and is not private-network-only. The localhost-only Auth Proxy can
therefore connect from Hetzner without adding an authorized-network rule.

Production cutover is later and separately approved:

1. Use the measured rehearsal results to choose either a rehearsed freeze plus
   final dump/restore window or, preferably for a long window, initial copy plus
   native logical replication of the delta.
2. Keep Cloud SQL authoritative until the target is caught up and reconciled.
3. Freeze every writer, confirm quiescence, capture the final delta and validate.
4. Repoint the app DSN and resume writers on Hetzner.
5. Keep Cloud SQL read-only through soak. Do not delete it at cutover.

Native logical replication remains approval-gated. The guarded source helper
can create only the restricted login and explicit publication after logical
decoding is already enabled; it deliberately does not create a slot. Target
replacement, subscriber creation, sequence handling and the rollback boundary
remain separate actions.

## Order of operations

### 1. Verify the Hetzner private interface on both hosts

Recent Hetzner images normally configure an attached Cloud Network
automatically. If the API shows the fixed private address but the guest leaves
`enp7s0` unmanaged, apply the documented static `/32` route:

```bash
sudo scripts/hetzner/configure_private_network.sh \
  --private-ip HOST_PRIVATE_IP \
  --network-cidr 10.60.0.0/16 \
  --gateway 10.60.0.1
```

Run it with `10.60.1.10` on the app host and `10.60.1.20` on the database host,
then prove bidirectional private connectivity before installing services.

### 2. Install and authorize Tailscale on both hosts

```bash
sudo scripts/hetzner/install_tailscale.sh --authenticate
```

Open and verify a second SSH session over the tailnet. Then close the host rule:

```bash
sudo scripts/hetzner/close_public_ssh.sh \
  --confirmed-tailnet-ssh \
  --cidr YOUR_BOOTSTRAP_CIDR
```

Set `enable_public_bootstrap_ssh=false` in the Hetzner tfvars and apply only
after confirming Terraform proposes two firewall updates and no server
replacement.

### 3. Bootstrap PostgreSQL on the database host

Create the initial app password in a root-owned mode-0600 file. Then use the
Terraform outputs for the Volume and private addresses:

```bash
sudo scripts/hetzner/bootstrap_database_host.sh \
  --volume-id HETZNER_VOLUME_ID \
  --private-ip 10.60.1.20 \
  --app-private-ip 10.60.1.10 \
  --password-file /secure/path/rtbcat-db-password
```

The script refuses to format storage, refuses a non-empty Volume, selects only
PGDG 15.17 packages, creates a checksummed `en_US.UTF-8` cluster, listens only
on loopback/private IPv4 and admits PostgreSQL only from the app private IP.

### 4. Prove independent backup and PITR prerequisites

Select and approve the repository provider, region and failure boundary first.
The repository needs a dedicated bucket/prefix, object-version protection, a
bucket-scoped machine identity and an explicitly accepted recurring cost. The
current approved deployment uses GCS `asia-southeast1`: it is independent of
Hetzner at the provider/credential layer and keeps traffic local to Singapore,
but it is not a country-level disaster copy. Use pgBackRest's native GCS
repository driver with a dedicated service-account JSON key:

```text
repo1-type         = gcs
repo1-gcs-key-type = service
```

Do not route GCS through pgBackRest's S3 driver. GCS returns `404 NoSuchKey`
when an XML `DELETE` targets a missing object, unlike S3's idempotent delete
behavior. pgBackRest 2.58's native GCS driver explicitly accepts that response.

Do not use a user key or a project-wide Storage Admin identity. The pgBackRest
identity needs object access only to the dedicated backup bucket.
Escrow the independent repository encryption passphrase in an approved secret
manager outside both Hetzner and the backup bucket; losing it makes every
encrypted backup unrecoverable.

Prepare a root-owned mode-0600 env file using
`pgbackrest-s3.env.example`, install it on the database host, then configure
the repository and launch the initial production-sized full backup:

```bash
sudo scripts/hetzner/configure_pgbackrest_s3.sh \
  --env-file /etc/rtbcat/pgbackrest-s3.env \
  --start-full-backup
```

The full backup runs as a non-blocking systemd job because the current
PostgreSQL cluster is about 413 GB:

```bash
systemctl status rtbcat-pgbackrest-full.service
journalctl -fu rtbcat-pgbackrest-full.service
```

After it succeeds, enable the recurring weekly-full and Monday-to-Saturday
differential timers. The daily archive/repository check timer is enabled during
initial configuration:

```bash
sudo scripts/hetzner/configure_pgbackrest_s3.sh \
  --env-file /etc/rtbcat/pgbackrest-s3.env \
  --enable-backup-timers

sudo scripts/hetzner/verify_pgbackrest_backup.sh \
  --json-out /secure/evidence/pgbackrest-backup.json
```

After the production-sized rehearsal restore, take a new pgBackRest full backup
and restore it onto a separate clean disposable host. The optional Terraform
resource `enable_pgbackrest_restore_drill_host` uses a `cpx62` with a 640 GB
local disk, so the drill does not exceed the current 1,500 GB Volume quota. It
is disabled by default and requires a separate reviewed plan/cost approval.

Create an isolated before/after WAL witness only after the full backup and
continuous archive checks pass:

```bash
sudo scripts/hetzner/create_pgbackrest_pitr_probe.sh \
  --json-out /secure/evidence/pgbackrest-pitr-probe.json \
  --confirm CREATE_ISOLATED_PITR_WITNESS
```

On the opt-in clean host, bootstrap the pinned stopped cluster:

```bash
sudo scripts/hetzner/bootstrap_pgbackrest_restore_host.sh \
  --confirm BOOTSTRAP_DISPOSABLE_RESTORE_HOST
```

Install a postgres-owned mode-0600 copy of the exact repository configuration
at `/etc/pgbackrest/pgbackrest.conf`. Then use the backup label, time target and
two markers from the private probe evidence:

```bash
sudo scripts/hetzner/restore_pgbackrest_pitr_drill.sh \
  --backup-set BACKUP_LABEL \
  --target-time TARGET_TIME \
  --before-marker BEFORE_MARKER \
  --after-marker AFTER_MARKER \
  --json-out /secure/evidence/pgbackrest-clean-host-pitr.json \
  --confirm DESTROY_EMPTY_RESTORE_DRILL_CLUSTER
```

Acceptance requires PostgreSQL 15.17 with checksums, loopback-only listeners,
archive mode off on the restored drill host, all 98 expected user tables, the
before marker present and the after marker absent. Preserve the evidence before
requesting the separate destructive approval to remove the disposable host.

### 5. Install the source connector on the database host

```bash
sudo scripts/hetzner/install_cloud_sql_proxy.sh
```

The proxy is pinned to version 2.22.0 and a checked SHA-256. Authenticate it
with approved off-GCP Application Default Credentials. Prefer Workload Identity
Federation; if a temporary service-account key is approved for rehearsal,
restrict it to Cloud SQL Client, store it mode 0600 and revoke it afterward.

### 6. Run an online server-to-server rehearsal

Create a mode-0600 libpq passfile on the database host. Run the script there,
not through a local pipe or SSH port forward:

```bash
sudo scripts/hetzner/rehearse_cloudsql_restore.sh \
  --source-instance PROJECT:REGION:INSTANCE \
  --source-database SOURCE_DATABASE \
  --source-user SOURCE_DATABASE_USER \
  --source-pgpass-file /secure/path/source.pgpass \
  --credentials-file /secure/path/google-adc.json \
  --dump-root /mnt/HC_Volume_REHEARSAL_DUMP_ID/migration-dumps \
  --restore \
  --confirm online-rehearsal-source-stays-live
```

The destination must end in `_rehearsal`. The script checks both servers are
PostgreSQL 15.17, confirms the source is the primary, proves the dump and
database paths are separate XFS Hetzner Volumes with independent capacity,
takes a parallel directory dump, checksums every dump file, restores locally,
analyzes the target and makes the rehearsal database read-only by default.

After the restore evidence and required recovery copy are retained, unmount the
temporary dump Volume, set `enable_rehearsal_dump_volume=false`, review the
Terraform plan and apply only that Volume deletion. Hetzner Volumes cannot be
shrunk, which is why dump capacity is temporary rather than permanent.

This first restore is deliberately as-is. The partitioned `rtb_daily` Path A
and zero-difference financial/data validation remain Part 4 acceptance work.

### 7. Prepare the logical-replication source

Run the read-only preflight from an environment with the live source DSN.
`RTBCAT_FINANCE_OWNER_ROLE` must name the `financial_viability` schema owner
role; that name is private and is deliberately not stored in this public
repository, so export it from the root-only operator environment first:

```bash
export RTBCAT_FINANCE_OWNER_ROLE=…   # exact name in private evidence
scripts/hetzner/setup_source_logical_replication.py
```

It requires exactly 84 `public` plus 14 `financial_viability` tables, primary
keys on all 98, no RLS, one excluded `agent_private` table, logical WAL and zero
existing slots. Applying requires a password on stdin and both explicit gates:

```bash
secret_command \
  | scripts/hetzner/setup_source_logical_replication.py \
      --apply \
      --confirm CREATE_SOURCE_REPLICATION \
      --password-stdin
```

The helper creates fixed role `rtbcat_migration_repl` and fixed publication
`rtbcat_migration_pub`. It grants SELECT on the explicit 98-table list, never
uses `FOR ALL TABLES`, and revokes the temporary finance-owner membership
before committing. It creates no slot. Let a ready subscriber create and
immediately consume the slot so an idle migration cannot retain unbounded WAL.

### 8. Compare and transfer frozen sequence state

Native logical replication does not copy sequence counters. The final-sync
runbook therefore uses a separate guarded helper after source writers are
frozen:

```bash
SOURCE_POSTGRES_DSN='source-dsn' \
TARGET_POSTGRES_DSN='target-dsn' \
scripts/hetzner/sync_postgres_sequences.py \
  --json-out /secure/evidence/sequence-compare.json
```

That invocation is read-only. Applying requires both `--apply` and the exact
`--confirm APPLY_SEQUENCE_STATE` string, plus `--json-out` for a mode-0600
pre-apply recovery record. The helper refuses a count other than 38 by default,
refuses different source/target sequence inventories, preflights `UPDATE`
privilege and preserves both `last_value` and `is_called`.

The
[PostgreSQL 15 sequence documentation](https://www.postgresql.org/docs/15/functions-sequence.html)
states that `setval()` changes are not undone when a transaction aborts. If
apply or verification fails, the helper therefore restores every pre-apply
target state, verifies that compensating restoration and records the result.
Source and target writers must still be frozen: compensation is recovery from
a helper failure, not concurrent-write protection. This behavior passed a
PostgreSQL 15.17 disposable rehearsal, including a failure after 37 partial
sequence changes, exact recovery, a 38-state apply and a zero-change idempotent
reapply. See
`docs/HETZNER_FINAL_SYNC_RUNBOOK.md` for ordering and approval boundaries.
