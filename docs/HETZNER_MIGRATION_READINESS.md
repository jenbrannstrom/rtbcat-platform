# Hetzner migration readiness

Last updated: July 29, 2026

## Decision

RTBcat's Hetzner foundation and complete online database restore rehearsal are
accepted. The restored-target media-buyer, calendar-month/all-time and private
finance-schema comparisons are also accepted. Local read-only application
compatibility and heavy-request validation against that target are accepted;
the immutable target-host deployment and first same-network application smoke
are accepted. The encrypted target WAL/backup chain and clean-host PITR restore
are also accepted. RTBcat is not ready for production cutover.

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
[`HETZNER_MIGRATION_PLAN.md`](HETZNER_MIGRATION_PLAN.md). Its July 25 execution
checkpoint is the authoritative resume order for the next engineer. Part 1 has
a local Terraform implementation under `terraform/hetzner/` and is now
provisioned in the isolated RTBcat Hetzner project. The accepted read-only
rehearsal evidence remains protected, but B3b stopped the shadow and removed
the stale rehearsal database to make room for the fresh logical subscriber.
Empty `rtbcat_serving` remains. Production authority, DNS and writer state have
not changed.
The concise resume checkpoint is
[`HETZNER_MIGRATION_NEXT_ENGINEER.md`](HETZNER_MIGRATION_NEXT_ENGINEER.md).

Part 2 has guarded local scripts for Tailscale, PostgreSQL 15.17, independent
pgBackRest/WAL backups and a direct Cloud SQL-to-Hetzner rehearsal.
Private networking, Tailscale, the protected database/app-data Volume mounts and
the empty PostgreSQL foundation have been run and accepted. The owner directed
that retained Cloud SQL backups/PITR serve as recovery for this rehearsal and
deferred a new S3 account. A dedicated temporary Cloud SQL Client identity and
read-only dump user passed preflight. The full 452,996,676,967-byte online
source dumped in 8,037 seconds and restored/analyzed in 20,042 seconds. Every
dump checksum passed twice; the read-only target contains the exact 98 expected
user tables with no invalid indexes. All temporary source credentials and
grants were then removed. Independent target backup/recovery was the remaining
Part 2 production-cutover gate at that checkpoint.

That final Part 2 gate passed on July 26. Native GCS in Singapore now holds an
AES-256-CBC pgBackRest repository with two full backups, zero archive failures
and enabled full/differential/check timers. A disposable Singapore clean host
restored full `20260726-113211F` to
`2026-07-26T12:06:53.141026Z`; PostgreSQL 15.17/checksums, 98 application
tables, loopback-only/archive-off isolation and the before-present/after-absent
PITR witness all passed.

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
off-GCP Google credential probe and immutable rollback tooling. Sanitized
release `332ec985084085edef714525d118f6c6ad2db8d4` was merged, its manual
workflow passed, and the API/dashboard were published and deployed by exact
digest on the target app host.

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

The target-host rerun then passed all 15 authenticated GET contracts and
blocked both mutation routes. It ran inside the immutable API container against
the rehearsal database over the Hetzner private network. The two longest
requests completed in 35.3 and 31.1 seconds while a concurrent health request
returned 200 in 0.054 seconds. Deployment acceptance also passed exact image
revision, PostgreSQL TLS, Secret Manager, BigQuery, GCS, scheduler guards and
loopback-only listener checks. DNS, production writers and production
schedulers remain unchanged.

On July 29, the separately approved B1 boundary briefly ran the accepted
release in private writable mode against the stale rehearsal database with all
three schedulers disabled. Each scheduled endpoint refused with HTTP 503; a
real database probe write rolled back with no residue. The application and
database then returned to verified read-only shadow posture. Fresh encrypted
differential backups bracketed the rehearsal, and GCP, Cloud SQL, DNS and
source scheduler ownership were unchanged.

The temporary public path is active at `scan-hetzner.rtb.cat`. Its DNS-only
Cloudflare record resolves only to the Hetzner app IPv4; Nginx serves a valid
Let's Encrypt certificate and restricts HTTPS to loopback plus the operator
`/32`. A second Hetzner host received 403. Health, provider discovery and all
three read-only scheduler refusals passed while the API/dashboard/OAuth
listeners remained loopback-only, shadow mode remained true and every target
scheduler remained false. Google OAuth routing uses the current live production
client, and its temporary callback was additively registered without removing
the production callback. A real browser Google login completed and
`/api/auth/me` returned 200. The API trusts only loopback plus its exact Docker
gateway for injected OAuth identity. Password login is intentionally hidden
while the rehearsal database remains read-only because password sessions write
database state. The production hostname is unchanged.

On July 29, approved B2 completed after the active Gmail import became idle.
On-demand backup `1785323946722` succeeded, and the single-flag Cloud SQL
update set `cloudsql.logical_decoding=on`. The instance returned `RUNNABLE`,
PostgreSQL reports `wal_level=logical`, six consecutive database-backed health
checks passed, and scheduler ownership plus both DNS records were unchanged.
No publication, replication slot or replication login was created.

Later on July 29, approved B3a used guarded source setup commit `553c6127` to
create restricted login `rtbcat_migration_repl` and explicit publication
`rtbcat_migration_pub`. The login can connect and SELECT exactly the accepted
98 tables but has no superuser, `cloudsqlsuperuser`, role/database-creation or
RLS-bypass authority. The publication excludes `agent_private`, is not
`FOR ALL TABLES` and has ordered table-name checksum
`c2af91c3598c914e5c2493532e81adb8`. The transaction-scoped finance-owner grant
was revoked before commit.

No slot was created. A production autovacuum advanced WAL by about 640 MB over
30 seconds, and Cloud Monitoring showed about 45 GB free before automatic disk
growth. The subscriber must therefore create and immediately consume the slot;
do not retain WAL while the old target database is still present.

On July 25, `scripts/catscan_api_read_only_soak.py` began the paired
application soak. The one-cycle baseline completed all 15 Hetzner GETs with
zero missing read-only shadow headers. GCP returned HTTP 500 on the 90-day RTB
funnel and publisher contracts and exceeded 120 seconds for the QPS summary;
the Hetzner equivalents returned 200. Seats and 90-day spend matched exactly.
Other current-window result drift is expected while GCP advances beyond the
July 22 target snapshot and is tracked separately from request and JSON-shape
failures. A supervised six-hour run started at `2026-07-25T07:54:12Z`; it is
complete and accepted: 300/300 target requests passed with zero missing
read-only shadow headers. The same three GCP failures repeated in every cycle.
GCP serves revision `30f24771`, whereas the shadow serves accepted revision
`332ec985084085edef714525d118f6c6ad2db8d4`; this compared actual deployed
behavior but was not a controlled same-build provider benchmark.
The harness and evidence format are documented in
[`CATSCAN_API_READ_ONLY_SOAK.md`](CATSCAN_API_READ_ONLY_SOAK.md).

The July 25 final-sync audit found that Cloud SQL then had no logical-decoding
flag, publication or retained migration slot. B2 and B3a have since enabled
logical decoding and created the source login/publication, but there is still
no retained slot. The July 22 rehearsal database
therefore cannot be retroactively caught up: it must be preserved as evidence
and replaced by a fresh schema-matched logical subscriber, which can take an
online initial copy and then continuously catch up. All 98 target tables have
primary keys, but 38 sequences require a frozen-state transfer and two
generated columns need explicit replication validation. The permanent target
Volume has room for one production-sized database, not the old rehearsal and a
new subscriber simultaneously. The planned approval gates and rollback cutoff
are documented in
[`HETZNER_FINAL_SYNC_RUNBOOK.md`](HETZNER_FINAL_SYNC_RUNBOOK.md).

Writer inventory found three enabled Cloud Scheduler jobs whose HTTP targets
follow the public hostname, plus general API mutations/background work and a
separate login that owns the private finance schema. The three scheduler flags
previously described ownership but did not enforce it at the endpoints. Local
code now rejects scheduled Gmail, precompute and creative-cache work unless its
flag is explicitly true; 28 focused tests and Ruff pass. That fix still must be
reviewed, built and deployed in an immutable cutover release.

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
provider/credentials and encryption-passphrase escrow are not configured yet.
The shadow uses the owner-approved existing production service-account key as
a migration bridge; replacement with a renewable off-GCP identity remains
recommended before long-term operation.

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
  differences. Local and immutable target-host heavy shadow checks also pass.
  The six-hour read-only soak completed 300/300 successful target requests with
  zero missing shadow headers and is accepted.
- The independent encrypted pgBackRest/WAL chain, recurring timers and
  clean-host PITR restore are accepted. Approved cleanup removed the disposable
  drill host/firewall, unused HMAC/legacy environment and witness database; the
  post-cleanup Terraform plan is empty.
- The Hetzner release path and tree-identical A→B→A rollback are exercised and
  accepted; the current manifest is restored to SHA `332ec985...`.
- Scheduled imports, refreshes, delivery checks, contracts, retention and a
  dated purge are not yet represented as one target-host timer manifest.
- The live analytics lane still writes to object storage and reads/writes the
  warehouse. Target read access is proven; ownership and one-time cutover of
  every writer/scheduler still need an explicit manifest.
- Cloud SQL logical decoding is on after accepted B2 and PostgreSQL reports
  `wal_level=logical`. B3a added the restricted login and explicit 98-table
  publication. A fresh logical subscriber, active slot monitoring and
  source-to-target catch-up rehearsal are not yet complete; no slot exists yet.
- The current immutable target deployment has returned to shadow-only after
  the accepted bounded B1 live writable rehearsal. Final synchronized
  activation still requires source freeze, logical catch-up, exact sequence
  state, reconciliation and backup evidence. Single-owner scheduler enable
  remains a later approval gate.
- The private-finance schema owner is traced to the separate ADT finance
  controller. Its active runtime uses local SQLite plus read-only RTBcat HTTP,
  not Cloud SQL, but the dormant owner login must still be recreated on target
  and blocked on source during freeze.

## Required acceptance evidence

> **Corrected July 30, 2026.** The first item below still reflects the original
> dump/restore plan, in which `rtb_daily` was to be rebuilt as partitioned via
> `scripts/partition_migration/` Path A. The executed B3c copied it as a plain
> unpartitioned clone with all 16 indexes, and no rehearsal evidence rejecting
> Path A was recorded. Either take the partitioned design when the `rtb_daily`
> copy is restarted, or explicitly retire this acceptance item with a written
> reason. Do not leave it silently unmet. See
> `docs/internal/MIGRATION-ENGINEER-BRIEF-2026-07-30.md`.

- Full restore timing and zero-difference partition validation.
- Heavy dashboard and API performance checks against the restored target
  (local tunnelled and target-host immutable-image passes complete).
- Point-in-time recovery and clean-host restore from the target backup chain
  (complete July 26).
- Re-ingesting the same report leaves published values unchanged.
- All scheduled operations run once from the target, with the old scheduler
  disabled so there is never dual delivery.
- Authentication, critical agent consumers, daily spend and finance-facing
  aggregates reconcile before and after cutover.
- A written writer-freeze order, DNS/TLS plan and explicit rollback cutoff.
- All logical tables are `ready`, the subscriber reaches the frozen source LSN,
  and all 38 sequence states match before DNS changes.
- The enforced scheduler guards are present in the accepted immutable image,
  and only one target API deployment can execute scheduled writes.

## Privacy boundary

Keep this file sanitized. Exact project names, account identifiers, client
names, IP addresses, spend values, secret names and detailed resource
inventory belong only in the ignored private master document and its encrypted
or access-controlled operational backup.
