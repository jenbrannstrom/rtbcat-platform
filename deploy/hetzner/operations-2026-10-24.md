# RTBcat follow-up operations, 24 October 2026

Approved by Jen: “ok, can you fix it?” following the remaining-fixes list.
All administration runs directly from the laptop to the two servers; never archi.

## Bidstream retention

`retain_bidstream.py` installs as `/usr/local/sbin/rtbcat-retain-bidstream`
on `rtbcat-production-db`. Run as postgres. No additional Python packages are required.
Without `--apply` it prints a read-only plan. `--apply --once --batch-size 10000`
commits at most one bounded batch. The daily service processes all expired rows
using 50,000-row batches; the timer runs at 04:30–04:40 UTC.

The worker reads the global raw retention policy, requires 180–365 days, and refuses
longer seat-specific exceptions. It locks the policy while processing each batch.
Each batch selects and locks only expired rows, skipping concurrently locked rows.
Every column is archived as JSON with PostgreSQL type metadata. Gzip is fully
decoded and compared before deletion; the archive and manifest are fsynced first.
Deletion uses locked physical row IDs and compares every returned primary key
with the archive before committing. A failed check rolls back the transaction.

Archives are on the separate database-host volume:
`/mnt/HC_Volume_106446141/retention-archives/bidstream/`.
They are not an off-host archive and are not automatically expired. Each compressed
JSONL file starts with a format/table/schema/cutoff/count header; later lines are
complete original rows. Its adjacent JSON manifest records SHA-256, byte and row
counts, and commit state. A crash after archiving but before commit can leave a
complete extra archive; preserve it and reconcile its IDs against the live table.
An `archived-before-delete` manifest does not prove whether COMMIT occurred.

Recovery: first validate the compressed checksum and full decode. Restore into an
isolated table matching the header schema using PostgreSQL `jsonb_populate_record`,
and compare every field/row count. Resolve live ID/hash conflicts before any
approved production reinsertion. Do not blindly replay old archives into production.
The first actual production archive (10,000 rows, all 25 columns) was restored on
the laptop in an ephemeral PostgreSQL database; every value matched exactly.

Safety gates: separate mounted archive filesystem; >=40 GiB archive free;
>=80 GiB database free; healthy backup <=36 hours old; <=32 ready WAL segments;
two-second lock timeout; 45-second SQL timeout for mutation transactions;
180-second read-only inventory/completion timeout; single-worker file lock.
SQL/schema/archival failures stop cleanup. Retained data remains online. Ordinary
DELETE provides reusable database space; it does not guarantee an immediate
filesystem reduction. No VACUUM FULL, table swap or index removal is part of this worker.

`test_bidstream_retention.py` runs nine actual PostgreSQL tests in a disposable
laptop container, including full-field restore, failure rollback, policy/retention
boundaries, longer seat policies, row locks, schema changes and indexed completion
verification with stale statistics after deletion. The test database
and container are explicitly isolated from production.

## Certificate checking

`check_certificates.py` installs as `/usr/local/sbin/rtbcat-check-certificates`
on the app host. The daily timer checks the locally served scan, MCP and temporary
hostname certificates, with real name/trust verification and a fourteen-day expiry
margin. Failure appears in systemd/journal; no external notifications are configured.
The unit uses a dynamic unprivileged user.

The actual certificate lifecycle is managed by the existing Certbot timer, with
the new `rtbcat-production` lineage covering scan.rtb.cat and mcp.rtb.cat. Its webroot
is `/var/www/html`; both HTTP routes serve ACME challenges there. The renewal deploy
hook validates and reloads Nginx. Live renewal and a staging renewal/deploy-hook test
both passed. Prior certificates and root-only configuration backups remain available.

## Other completed host changes

- PostgreSQL server/client upgraded 15.17 to 15.19 after a fresh pgBackRest backup.
  The two apt holds remain, preserving deliberate scheduling of future restarts.
- Both MOTD scripts restored from mode 0644 to 0755 and successful service runs verified.
- The app's cloud-init udev rule skips `/devices/virtual/net/*`, preserving physical
  cloud NIC hotplug handling. Syntax verified and rules reloaded without retriggering devices.
- Removed only the obsolete optional `pam_lastlog.so` session line from app PAM login.
- Root-only originals/config backups are under `/var/backups/rtbcat-remediation-20261024/`.

The large lossless rtb_daily row/index redesign is not included in this operational fix.

## Source release and deployment

The reusable programs now live under `scripts/hetzner/`; services and timers
live beside this document. `operations-manifest.json` maps each source to its
installed path and exact SHA-256, separated by app/database host role.
The Python programs and units are byte-for-byte the versions already verified
in production. Historical one-time scripts are under
`scripts/hetzner/history/2026-10-24/`; do not replay them as a deployment step.
The two guarded SQL migrations beside the workers also record previously
completed changes and are not part of routine installation.

For this release, compare every installed file to its manifest hash before
publishing the source snapshot. A difference is drift to investigate, not an
instruction to overwrite production. Store the exact committed source and a
verification receipt under `/var/lib/rtbcat/operations-releases/<git-sha>/` on
each host and update `current` only after all hashes match. Keep previous
receipts. This records the deployed operations version without rerunning
retention, restarting the app/database or changing the application release.

For a future worker change, review and test its diff first, preserve the old
file, install atomically at the mapped path, verify its checksum, and reload
systemd only if a unit changed. Coordinate an active worker before replacing
its program. Use the read-only default for a smoke check; running an `--apply`
worker may delete newly expired rows. Timers are already enabled. A script
rollback restores program behavior, not data already pruned; use the archive
recovery procedure for approved data restoration.

Validation is repeatable through `.github/workflows/retention-operations.yml`:
eleven partition safety tests and nine PostgreSQL bidstream integration tests.
The integration tests require explicit `RTBCAT_RETENTION_TEST_CONTAINER` opt-in
and a dedicated `rtbcat-retention-test-*` Docker container with database
`rtbcat_retention_tests`. They never use a production DSN. The workflow uses
PostgreSQL 15.19, tmpfs data and automatic disposable-container removal.

The next-stage [storage plan](../../docs/POSTGRES_STORAGE_PLAN_2026-10-24.md)
covers bidstream compaction, measured capacity/recovery gates, and a lossless
rtb_daily pilot with exact UI/data parity and a staged rollback strategy.
