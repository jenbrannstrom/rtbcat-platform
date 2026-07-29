# GCP to Hetzner migration plan

Last updated: July 29, 2026

The migration is intentionally split into independently reviewable parts. A
part is complete only when its verification evidence exists; completing code
does not by itself authorize provisioning or production cutover.

## Current execution checkpoint — July 29, 2026

Resume from **Parts 5–6 final-sync engineering**, not provisioning, discovery,
independent backup configuration, another bulk rehearsal or application
cutover. Parts 0–2 are accepted and the Part 3 immutable target-host shadow is
running. The database restore, application-data copy, reconciliations, six-hour
API soak, immutable A→B→A application rollback, encrypted backup/WAL chain and
clean-host PITR rehearsal are complete. Production authority, DNS and writers
are unchanged. The separately approved B1 bounded live writable rehearsal is
also accepted; the target returned to read-only shadow mode afterward. The
separately approved B2 Cloud SQL restart is also accepted:
`cloudsql.logical_decoding=on` and PostgreSQL reports `wal_level=logical`, with
no publication or slot created.

Current target state:

- the approved eight-server/1,500 GB account limit is active. The reviewed
  replacement plan had 13 creates and no updates/deletes; its SHA-256 was
  `b35f4f13b423f8fc03e350aa39adc69f9ca500f8bae3467ac4908c3b12770524`;
- that exact plan was applied to the isolated RTBcat Hetzner project: protected,
  backed-up CPX22 app and CCX23 database hosts, protected fixed IPv4s, private
  network, placement group, layered firewalls and protected 150/750/400 GB XFS
  Volumes. A post-apply Terraform plan reports no changes;
- the isolated GCS backend now holds the resource state. Its independent
  recovery identity and write/read/delete recovery path were proven before
  apply;
- both hosts passed cloud-init. Their static `10.60.1.10` and `10.60.1.20`
  guest addresses pass bidirectional private-network checks. Public PostgreSQL
  is closed and the app-to-database private TCP/5432 path passes;
- PostgreSQL 15.17 is installed on the protected 750 GB Volume with
  `en_US.UTF-8`, data checksums and TLS. It listens only on loopback and
  `10.60.1.20`. pgBackRest 2.58.0 archives encrypted WAL to a dedicated native
  GCS repository in Singapore. Two full backups, recurring timers and a
  before-present/after-absent clean-host PITR restore are accepted;
- the protected 150 GB app-data Volume is mounted at
  `/var/lib/rtbcat/app-data`. A direct server-to-server bulk rsync plus online
  delta copied 12,476 regular non-credential files and 100,810,997,029 logical
  bytes. Source and target file counts/bytes match, every target entry has the
  runtime UID/GID, credentials were excluded and 57,021,091,840 bytes remain
  free. The protected 400 GB rehearsal dump Volume holds the completed
  checksummed database directory dump;
- both nodes joined the existing shared `amazingdo.com` Tailscale tailnet. That
  tailnet is auxiliary access, not an RTBcat isolation boundary. Public SSH
  therefore remains restricted to the operator `/32` until default-deny
  tailnet grants/tags or a separate tailnet are accepted; and
- retained Cloud SQL managed backups/PITR protected the initial online
  rehearsal. On July 26 the independent target backup/WAL and clean-host
  recovery gate was added and accepted against native GCS in Singapore;
- on July 29, fresh encrypted differential backups bracketed a bounded B1
  rehearsal of release `10c45949`. The private target became writable with
  every scheduler disabled, all three scheduled endpoints refused execution,
  a rollback-only database write left no residue, and the app/database returned
  to verified read-only shadow posture. GCP, Cloud SQL, DNS and source
  scheduler ownership were unchanged;
- the complete online dump/restore rehearsal ran from
  `2026-07-23T18:49:38Z` through `2026-07-24T02:40:25Z`. The 452,996,676,967-byte
  source dumped in 8,037 seconds and restored/analyzed in 20,042 seconds. The
  resulting read-only target was 438,891,765,095 bytes;
- every compressed dump object passed SHA-256 twice, the restore catalog is
  readable, all 98 expected user tables exist and no restored index is invalid.
  The temporary database grants/user, IAM binding and Cloud SQL service account
  were all removed after acceptance. GCP remains writable and authoritative;
- on July 24 the reusable CatScan database suite completed both the initial
  30-day smoke and a 90-day/all-time reconciliation through the restored
  cutoff `2026-07-22`. Ten media-buyer contracts across all six shared buyers,
  including 32 buyer/month rows and all-time canonical spend, produced
  identical normalized rows and SHA-256 hashes on Cloud SQL and
  `rtbcat_serving_rehearsal` (10/10 pass). A separate private-finance suite
  verified 154 schema columns, all 14 table cardinalities and five monthly
  finance aggregate contracts (7/7 pass). Every finance data table is
  intentionally empty on both sides; the active finance audit store is not in
  this Cloud SQL schema. The target was faster for every query on the
  tunnelled runs. GCP and Hetzner used different tunnel paths, so retain those
  timings as smoke evidence rather than a controlled benchmark;
- the current application then ran locally in explicit read-only-shadow mode
  against the rehearsal database. All 15 representative GET contracts passed,
  including the 90-day home, RTB, data-health and QPS paths plus a 200-creative
  payload. Both tested mutation routes returned 405. The run found and fixed
  pre-migration schema compatibility for buyer currency and publisher spend,
  and moved blocking QPS analysis off the API event loop. The 90-day QPS
  summary completed in 42.7 seconds while a concurrent health request remained
  responsive. The data-health response was deliberately `degraded` because
  expected source report types are absent and one 15-second completeness scan
  timed out; this is visible product/data health, not a source-target mismatch;
- sanitized release `332ec985084085edef714525d118f6c6ad2db8d4` was merged,
  built by the passing manual GHCR workflow and published as immutable API and
  dashboard digests. The exact digest-pinned release is running on the target
  app host against `rtbcat_serving_rehearsal`. Deployment acceptance passed
  private PostgreSQL TLS, Secret Manager, BigQuery, GCS, image revision,
  loopback-listener and scheduler checks;
- the same target-host smoke ran inside the API container. All 15 authenticated
  GET contracts returned 200 and both mutation probes returned 405. The two
  slowest requests completed in 35.3 and 31.1 seconds while concurrent health
  returned in 0.054 seconds. Evidence is in the ignored
  `TARGET-HOST-SHADOW-APPLICATION-2026-07-24.json`; and
- the paired application soak is now automated by
  `scripts/catscan_api_read_only_soak.py`. Its July 25 baseline passed all 15
  Hetzner GETs with every read-only shadow header present. GCP returned two
  HTTP 500s on the RTB funnel/publisher paths and timed out the 90-day QPS
  summary at 120 seconds; seats and 90-day spend matched exactly. A supervised
  six-hour run completed 20 cycles and 300/300 successful target requests with
  zero missing read-only headers. Snapshot-age value drift is reported separately from
  request and JSON-shape failures. GCP is on revision `30f24771`, not the
  target's accepted `332ec985084085edef714525d118f6c6ad2db8d4`, so these are
  real deployed-behavior comparisons rather than same-build benchmarks; and
- the one-use transfer key and source `/32` firewall/UFW path were removed
  after the app-data copy, and source-to-target SSH is blocked again. A
  lifecycle guard now prevents post-provision cloud-init template edits from
  silently forcing server replacement. Terraform formatting/validation pass
  and the post-transfer live plan reports no changes.

The revised planning envelope is approximately USD 291.69/month while the
temporary 400 GB rehearsal Volume exists and approximately USD 261.01/month
after it is removed, plus independent offsite backup storage and traffic. This
replaces the earlier USD 255/USD 236 estimate and was approved by the owner on
July 23. The exact GCP billing reconciliation and account inventory are
recorded only in the ignored private master document referenced below.

The project-scoped `/v1/pricing` response was checked on July 23 against
Hetzner's
[post-June 15 Singapore prices](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/):
USD 30.99/month for CPX22 and USD 127.99/month for CCX23, with
[server backups billed at 20%](https://docs.hetzner.com/cloud/billing/faq/)
and the project API reporting USD 0.0767/GB-month for Volumes and USD
0.60/month per Primary IPv4. That reconstructs USD 291.69 during rehearsal and
USD 261.01 after removing 400 GB. The API reported USD billing and zero VAT.

### Exact continuation order for the next engineer

1. Preserve the dirty worktree. Read this file, the readiness brief and
   `docs/HETZNER_MIGRATION_NEXT_ENGINEER.md`, then
   `docs/internal/rtbcat-migration/GCP-FULL-MIGRATION-INVENTORY-CHECKLIST.md`.
   Never force-add `docs/internal/` or `terraform.tfvars`.
2. Do not reapply or recreate the provisioned foundation. A fresh Terraform
   plan must remain empty before any later infrastructure change.
3. Do not repeat the completed full database transfer without a new reason.
   Preserve the dump, timing metadata and corrected acceptance evidence.
4. Preserve the completed 10/10 public and 7/7 private-finance reconciliation
   evidence. The calendar-month/all-time database gate is complete.
5. Preserve the completed app-data manifest and read-only application-shadow
   evidence. Do not repeat the 100.8 GB bulk transfer without a new reason;
   production remains live, so a later bounded delta is still required.
6. Preserve the accepted immutable release and target-host smoke evidence.
   The six-hour soak and tree-identical A→B→A immutable rollback drill are
   accepted. Preserve their private evidence and the restored current manifest
   for SHA `10c45949d08f671c69743e9fc557cb9956921487`. Preserve the accepted
   bounded B1 evidence; do not leave a target writer or scheduler enabled. The
   installed existing service-account key is an
   explicitly approved migration bridge, not the final renewable identity
   design.
7. Preserve the accepted independent target backup/WAL and clean-host recovery
   proof. Approved cleanup destroyed the disposable restore host/firewall,
   retired the unused HMAC/legacy environment and dropped the PITR witness
   database; the post-cleanup Terraform plan is empty.
8. Resolve the shared-tailnet policy before closing `/32` public SSH. This must
   not delay the backup or online restore rehearsal, but the shared tailnet must
   not be treated as project isolation.
9. Keep the deployed Part 3 shadow loopback-only with every target scheduler
   disabled. Its successful acceptance does not authorize DNS or writers.
10. Follow `docs/HETZNER_FINAL_SYNC_RUNBOOK.md`. The July 22 database cannot be
    incrementally caught up because no logical slot retained its missing WAL;
    prepare a fresh logical-replication initial copy and continuous catch-up.
    Preserve accepted B2 and do not repeat the Cloud SQL restart. Do not create
    a publication/slot/login, replace the rehearsal DB, freeze writers, change
    DNS or enable target writes without their separate approvals.

Do not replace the full rehearsal with a sample. The roughly 420 GiB database
moves server-to-server from Cloud SQL to the Hetzner database host; the laptop
is control-plane only. Cloud SQL remains the writable authority throughout the
online rehearsal and remains retained through production cutover soak. Do not
change DNS, enable a target writer/scheduler, delete Cloud SQL, or delete a GCP
project while resuming Parts 1–4.

## Part 0 — inventory and boundary (complete)

- Live GCP compute, database, backup, registry, BigQuery and GCS state was
  re-checked.
- Phase one is app plus PostgreSQL in Hetzner Singapore.
- Google Secret Manager, Gmail/OAuth, Authorized Buyers, BigQuery and the
  active GCS lane remain on Google during phase one.
- The production database is PostgreSQL 15.17 and about 420 GiB. The target
  starts with 750 GB permanent database storage plus a temporary 400 GB dump
  Volume for the production-sized rehearsal.
- The live app host has about 93 GB under `.catscan`, so the CPX22 target uses
  a separate protected 150 GB app-data Volume rather than relying on its 80 GB
  system disk.

Evidence: `docs/HETZNER_MIGRATION_READINESS.md` and the ignored private master
inventory referenced there.

## Part 1 — target infrastructure foundation (provisioned and accepted)

The Terraform stack in `terraform/hetzner/` defines separate app and database
hosts, fixed IPv4s, private networking, public and host firewalls, a protected
150 GB app-data Volume, a protected 750 GB permanent database Volume, a
protected/removable 400 GB rehearsal-dump Volume and deletion guards. Its
backend is GCS, but it has no managed GCP, DNS or application deploy resources.

Acceptance evidence:

- reviewed Terraform plan from the intended Hetzner project;
- approved current hourly/monthly cost and confirmed Singapore quota;
- remote state backend selected and recovery access tested;
- both hosts pass cloud-init and firewall checks;
- public PostgreSQL port scan is closed and private app-to-database path is
  the only accepted TCP/5432 path.

## Part 2 — database, private access and recovery (in progress)

- Tailscale is installed; close bootstrap public SSH only after RTBcat-specific
  default-deny tailnet policy is proven.
- Pin PostgreSQL 15.17 without combining the provider migration with a major
  database upgrade.
- Mount the Hetzner Volume at a stable database path and capture mount checks.
- Install pgBackRest or wal-g with encryption and WAL archiving to storage in
  an independent provider/failure domain.
- Prove a small PITR and a clean-host restore before the full rehearsal.
- Add disk, WAL, backup-age and database health alerts.

The guarded implementation is under `scripts/hetzner/`. Rehearsal database
bytes move directly from Cloud SQL to the Hetzner database host through a
localhost-only Cloud SQL Auth Proxy; the operator laptop is control-plane only.
Cloud SQL remains live and writable during these consistent online dumps.
Keeping Cloud SQL authoritative until cutover does not defer the bulk transfer:
the full copy is timed and rehearsed in advance, and the final cutover should
move only a bounded delta if the full-copy timing exceeds the approved window.

Exit criteria before this part is operationally complete:

- Tailscale SSH is proven on both hosts and public SSH is closed in UFW and the
  Hetzner firewalls without server replacement;
- PostgreSQL reports exactly 15.17, the expected locale and data checksums;
- PostgreSQL listens only on loopback and the private database IP;
- encrypted WAL archive check, initial full backup and clean-host restore pass
  against an independent backup provider;
- the Cloud SQL Auth Proxy uses an approved off-GCP ADC/WIF identity and an
  online dump reaches the target without traversing the operator laptop.

The live source was checked read-only on July 22: public IPv4 is enabled and no
private network is configured, so this direct Auth Proxy path does not require
a laptop tunnel or a new authorized-network rule.

## Part 3 — immutable hybrid application shadow (deployed and accepted)

- Add a Hetzner compose file with a direct private PostgreSQL DSN and no Cloud
  SQL Auth Proxy.
- Publish the frozen SHA images to GHCR and deploy by immutable SHA only.
- Preserve Google-native dependencies and prove off-GCP Google credentials
  without committing or embedding secret values in Terraform state.
- Add an immutable-SHA rollback command and acceptance checks.

The implementation is under `deploy/hetzner/`, `scripts/hetzner/` and the
manual `build-and-push-ghcr.yml` workflow. The shadow Compose file accepts only
digest-pinned GHCR images, binds API/dashboard to loopback, connects directly to
the private target PostgreSQL address with certificate verification, mounts ADC
outside image/state and hard-disables all three schedulers. Deployment verifies
the full image revision, Compose checksum, target database, retained Google
services and rollback manifest before activation.

Accepted shadow evidence:

- one frozen commit passes the manual GHCR build and produces two digest refs;
- the target pulls the images without a mutable tag or a source checkout build;
- the API health SHA and container revision labels equal the frozen full SHA;
- target PostgreSQL TLS and health pass while Cloud SQL remains authoritative;
- read-only Secret Manager, BigQuery and GCS probes pass from the Hetzner ADC;
- both app ports remain loopback-only and all scheduler flags remain false; and
- the full target-host suite passes 15/15 GET contracts and blocks both tested
  mutation routes.

The July 25 tree-identical A→B→A rehearsal exercised the rollback command and
restored the accepted current manifest successfully.

## Part 4 — full restore rehearsal

- Place the parallel dump on the temporary Volume and restore onto the separate
  permanent database Volume; remove the temporary Volume only after evidence is
  retained and the mount is cleanly unmounted.
- Restore the full production dump, using the partition migration Path A for
  `rtb_daily` unless rehearsal evidence rejects it.
- Record dump, transfer, restore and index-build durations.
- Require zero-difference monthly row/hash/spend/impression/click validation.
- Exercise heavy API/dashboard paths and compare query plans and latency.
- Repeat the same report ingestion and prove published values do not change.

## Part 5 — writers and scheduler single-ownership drill

- Inventory every database writer and write the exact freeze/quiescence order.
- Check in one target timer manifest for imports, refreshes, delivery checks,
  contracts, retention and the dated purge.
- Run each operation once on target while the old scheduler is disabled.
- Prove that GCP and Hetzner never deliver or ingest concurrently.

The July 25 read-only inventory found three enabled Cloud Scheduler HTTP jobs:
Gmail import, precompute and creative-cache refresh. Their targets use the
public hostname and therefore follow DNS. The feature flags previously affected
only secrets-health reporting and did not block those endpoints. Release
`10c45949` now enforces each flag and defaults it to disabled. Its bounded B1
writable/all-schedulers-off rehearsal passed on July 29: each scheduled
endpoint returned 503, a rollback-only database write left no residue and the
target returned to read-only shadow mode. This does not satisfy the later
single-owner drill, where each operation must run once on the synchronized
target while the source trigger is paused.

The GCP API is itself a general writer through authenticated mutations,
conversion postbacks and background jobs. The database also has the dormant
finance-schema owner role (name in private evidence) that owns the private
finance schema. Its external controller currently uses local SQLite and the
read-only RTBcat HTTP API, so this is a dormant future-runtime login rather
than an observed active PostgreSQL writer;
block it during freeze anyway. The exact drain/pause/NOLOGIN and session checks
are in
[`HETZNER_FINAL_SYNC_RUNBOOK.md`](HETZNER_FINAL_SYNC_RUNBOOK.md).

## Part 6 — cutover rehearsal and production cutover

- Lower DNS TTL in advance and preflight TLS, OAuth redirect behavior, agent
  consumers, egress allowlists and health checks.
- Validate the public path first on a DNS-only temporary Hetzner hostname. Keep
  it operator-restricted, read-only and scheduler-disabled; seal it again
  before the production cutover window. The temporary record does not replace
  the final production-hostname switch. Public TLS, routing, provider parity
  and read-only scheduler refusal passed on July 29; the temporary callback was
  additively registered and real browser Google sign-in passed.
- Preserve the accepted B2 logical-decoding state. Under separate approvals,
  replace the July 22 target with a fresh schema-matched logical subscriber,
  allow the initial copy to finish and continuously catch up while GCP remains
  authoritative.
- Freeze writers, confirm quiescence, wait for the subscriber to pass the
  freeze LSN, transfer all sequence state, take the final non-credential
  `.catscan` delta and reconcile.
- State the rollback cutoff explicitly: rollback is safe only before target
  writers resume unless reverse synchronization has been proven.
- Change DNS in a separately approved action and resume one scheduler system.

The executable planning record is
[`HETZNER_FINAL_SYNC_RUNBOOK.md`](HETZNER_FINAL_SYNC_RUNBOOK.md). PostgreSQL
logical replication does not transfer DDL or sequences, and the target Volume
cannot hold the old rehearsal plus a second full database. Replacing that
database, creating source replication state, freezing writers and changing DNS
are separate approval gates.

## Part 7 — soak and decommission

- Keep the old database read-only through the agreed soak.
- Reconcile authentication, finance aggregates, agent daily spend and target
  backups daily.
- Complete a clean-target restore drill from the production backup chain.
- Stop billable GCP compute/database resources only after acceptance. Keep the
  Google project shells and all explicitly retained Google-native services.
