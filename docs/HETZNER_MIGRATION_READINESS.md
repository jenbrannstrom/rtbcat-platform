# Hetzner migration readiness

Last updated: July 24, 2026

## Decision

RTBcat's Hetzner foundation and complete online database restore rehearsal are
accepted. The restored-target media-buyer, calendar-month/all-time and private
finance-schema comparisons are also accepted. Local read-only application
compatibility and heavy-request validation against that target are accepted;
the immutable target-host deployment and same-network soak remain open. RTBcat
is not ready for production cutover.

The private master inventory is stored locally at
`docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md`.
That path is intentionally gitignored and must never be force-added. It holds
provider identifiers, operational inventory and customer-sensitive context
that do not belong in GitHub or a public snapshot.

## Recommended sequence

1. Move the application and PostgreSQL to Hetzner while retaining the
   Google-native reporting, identity and secret services needed by the live
   application.
2. Treat replacement of the analytics/object-storage lane as a later,
   separately rehearsed data-platform project.
3. Decommission old compute and database resources only after a read-only soak,
   business reconciliation, working target backups and a successful restore
   drill.

The reviewable, part-by-part execution plan is tracked in
[`HETZNER_MIGRATION_PLAN.md`](HETZNER_MIGRATION_PLAN.md). Its July 24 execution
checkpoint is the authoritative resume order for the next engineer. Part 1 has
a local Terraform implementation under `terraform/hetzner/` and is now
provisioned in the isolated RTBcat Hetzner project. The read-only rehearsal copy
exists, but production authority, DNS and writer state have not changed.

Part 2 now has guarded local scripts for Tailscale, PostgreSQL 15.17,
independent pgBackRest/WAL backups and a direct Cloud SQL-to-Hetzner rehearsal.
Private networking, Tailscale, the protected database/app-data Volume mounts and
the empty PostgreSQL foundation have been run and accepted. The owner directed
that retained Cloud SQL backups/PITR serve as recovery for this rehearsal and
deferred a new S3 account. A dedicated temporary Cloud SQL Client identity and
read-only dump user passed preflight. The full 452,996,676,967-byte online
source dumped in 8,037 seconds and restored/analyzed in 20,042 seconds. Every
dump checksum passed twice; the read-only target contains the exact 98 expected
user tables with no invalid indexes. All temporary source credentials and
grants were then removed. Independent target backup/recovery remains a
production cutover gate.

On July 24, `scripts/catscan_mcp_db_smoke.py` compared eight deterministic,
read-only media-buyer contracts across all six shared buyers for
`2026-06-22` through `2026-07-21`. Cloud SQL and the rehearsal database
returned identical normalized rows and SHA-256 hashes for buyer discovery,
freshness, daily canonical spend, performance totals, report completeness,
top geos, top publishers and top configurations (8/8 pass). All eight target
queries were faster in this tunnelled smoke run, although the different tunnel
paths make this directional evidence rather than a controlled benchmark. The
suite and future MCP boundary are documented in
[`CATSCAN_MCP_DB_SMOKE.md`](CATSCAN_MCP_DB_SMOKE.md).

The expanded run then compared ten contracts over the 90-day window ending at
the restored cutoff `2026-07-22`; its calendar-month and all-time canonical
spend hashes also matched exactly. The migration-only
`scripts/catscan_finance_db_reconcile.py` separately matched all 154 private
finance schema columns, 14 exact table cardinalities and five monthly finance
aggregate contracts (7/7). All 14 finance tables are empty on both databases;
the active finance audit data remains in its separate local SQLite store and
was therefore not part of this Cloud SQL transfer.

Part 3 now has a manual GHCR build, digest/commit/Compose release manifest,
loopback-only shadow Compose deployment, private-TLS PostgreSQL connection,
off-GCP Google credential probe and immutable rollback tooling. None has been
published or deployed.

The July 24 application rehearsal ran the current API locally in explicit
read-only-shadow mode against the Hetzner database. All 15 representative GET
contracts eventually returned 200, including 90-day home/RTB/data-health/QPS
queries and a 200-creative, 1.26 MB response; both tested mutation routes
returned 405. The smoke exposed and fixed two old-schema assumptions
(`buyer_seats.currency_code` and `rtb_publisher_daily.spend_micros`) without
mutating the restored database. It also moved synchronous QPS analyzers off the
event loop and ran size/geo analysis concurrently: the 90-day summary completed
in 42.7 seconds while a concurrent health request returned 200 in 6.4 seconds.
Tunnelled timings are directional only. Data health returned its intended
`degraded` state for absent report types and a timed-out completeness scan; it
did not identify a transfer difference.

The application-data rehearsal is also complete. A source-to-target rsync,
followed by an online delta, copied 12,476 non-credential regular files and
100,810,997,029 logical bytes to the protected app-data Volume. Target
count/bytes match exactly, ownership is entirely the runtime UID/GID,
credentials are absent and about 57.0 GB remains free. The one-use key and
temporary source `/32` firewall rules were removed and the path is blocked
again. Terraform now ignores post-provision `user_data` drift so an unrelated
plan cannot replace both servers; validation passes and the live plan is empty.

The July 22 cost review right-sized the provisioned target to CPX22 for the
app, CCX23 for PostgreSQL, a protected 150 GB app-data Volume, a protected
750 GB permanent database Volume and a protected/removable 400 GB
rehearsal-dump Volume. The app Volume covers the observed 93 GB `.catscan`
tree; temporary dump capacity avoids permanently sizing the database Volume
for both a dump and restored indexes. The current project API reports a
planning envelope of approximately USD 291.69/month during the full rehearsal
and USD 261.01/month after removing the temporary Volume, plus an independent
offsite backup provider.

Terraform uses the isolated access-controlled, versioned GCS backend whose
independent recovery path was proven before apply. Hetzner approved the
eight-server/1,500 GB account limit. The regenerated plan SHA-256 was
`b35f4f13b423f8fc03e350aa39adc69f9ca500f8bae3467ac4908c3b12770524`;
it had exactly 13 creates and no updates/deletes, and that exact plan was
applied. A post-apply plan reports no changes.

The created foundation contains two protected/backed-up Singapore hosts, two
protected IPv4s, the private network/subnet, placement group, SSH key, layered
firewalls and protected 150/750/400 GB XFS Volumes. Both hosts passed cloud-init
and private-network checks. Public PostgreSQL is closed, and TCP/5432 is
reachable from only the app's fixed private path. PostgreSQL 15.17 is active on
the 750 GB Volume with TLS, data checksums and loopback/private-only listeners.
The populated 150 GB app-data Volume is mounted at its stable path; its
rehearsal manifest excludes credentials and matches the live source count and
logical bytes after the online delta.

Both target nodes currently belong to the existing shared `amazingdo.com`
Tailscale tailnet. Until default-deny project tags/grants or a separate tailnet
is accepted, it is auxiliary access rather than an isolation boundary and the
operator `/32` public SSH path remains open. The independent backup
provider/credentials, encryption-passphrase escrow and renewable off-GCP Google
identity are not configured yet.

The approximately USD 291.69/USD 261.01 provider envelope was rechecked on
July 23 from the intended-project API: CPX22 is USD 30.99/month, CCX23 is USD
127.99/month, backups are 20%, Volumes are USD 0.0767/GB-month and each Primary
IPv4 is USD 0.60/month. This supersedes the earlier USD 255/USD 236 estimate
and was explicitly approved on July 23.

The same review removed the already-retired `catscan-production-sg2` VM, its
80 GB SSD and dedicated IPv4 after verifying the retained retirement snapshot.
That cleanup saves about USD 17/month independently of the migration.

## Cutover blockers

- The full production-sized database completed a timed target restore and the
  90-day/all-time public and private-finance comparisons passed with zero
  differences. Local heavy shadow API/dashboard checks also pass. The
  digest-pinned target-host deployment and same-network soak remain open.
- The independent logical-backup path is not healthy; managed-provider backups
  cannot be the only recovery path before self-hosting.
- The RTBcat-specific Hetzner foundation is provisioned, but the independent
  encrypted pgBackRest/WAL chain and clean-host recovery drill remain open.
- The current production deployment workflow, container registry
  authentication and database connector are provider-specific; the prepared
  Hetzner path has not yet been published or exercised.
- Scheduled imports, refreshes, delivery checks, contracts, retention and a
  dated purge are not yet represented as one target-host timer manifest.
- The live analytics lane still writes to object storage and reads/writes the
  warehouse. Off-provider credentials and connectivity must be proven from
  the target.
- Local data-correctness work must be merged, deployed and acceptance-tested
  before the migration release SHA is frozen.

## Required acceptance evidence

- Full restore timing and zero-difference partition validation.
- Heavy dashboard and API performance checks against the restored target
  (local tunnelled pass complete; target-host immutable-image rerun required).
- Point-in-time recovery and clean-host restore from the target backup chain.
- Re-ingesting the same report leaves published values unchanged.
- All scheduled operations run once from the target, with the old scheduler
  disabled so there is never dual delivery.
- Authentication, critical agent consumers, daily spend and finance-facing
  aggregates reconcile before and after cutover.
- A written writer-freeze order, DNS/TLS plan and explicit rollback cutoff.

## Privacy boundary

Keep this file sanitized. Exact project names, account identifiers, client
names, IP addresses, spend values, secret names and detailed resource
inventory belong only in the ignored private master document and its encrypted
or access-controlled operational backup.
