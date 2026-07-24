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

Native logical replication is not enabled by these scripts because it changes
the live Cloud SQL instance settings and requires a restart, publication/slot
design, sequence handling and a separately approved rollback boundary.

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

Prepare a root-owned mode-0600 env file using `pgbackrest-s3.env.example`, then:

```bash
sudo scripts/hetzner/configure_pgbackrest_s3.sh \
  --env-file /etc/rtbcat/pgbackrest-s3.env
```

Success requires stanza creation, archive push/check and an initial encrypted
full backup. The script also installs weekly-full, Monday-to-Saturday
differential, and daily repository/archive-check timers. A clean-host restore
drill is still required before cutover. Escrow the encryption passphrase in an
approved secret manager outside both Hetzner and the backup bucket; losing it
makes every encrypted backup unrecoverable.

After the production-sized rehearsal restore, take a new pgBackRest full backup
and restore that backup onto a separate clean disposable host/Volume. The
initial empty-cluster backup proves the transport and WAL archive path, not
production-data recoverability.

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
