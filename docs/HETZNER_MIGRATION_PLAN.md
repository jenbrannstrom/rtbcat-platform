# GCP to Hetzner migration plan

Last updated: July 24, 2026

The migration is intentionally split into independently reviewable parts. A
part is complete only when its verification evidence exists; completing code
does not by itself authorize provisioning or production cutover.

## Current execution checkpoint — July 24, 2026

Resume from **Part 2 independent backup configuration**, not provisioning,
discovery or application cutover. Part 0 is complete and Part 1 is provisioned
and accepted. The full read-only database rehearsal copy has moved, but
production authority has not. The non-credential `.catscan` application-data
rehearsal copy and local read-only application shadow checks are complete. No
migration image has been published, and DNS and production writers are
unchanged.

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
  `10.60.1.20`. pgBackRest 2.58.0 is installed but has no repository yet;
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
- on July 23 the owner explicitly directed that retained Cloud SQL managed
  backups/PITR are the recovery copy for the online rehearsal and deferred a
  separate S3 account until after the migration test. Independent target
  backup/restore proof remains mandatory before production cutover;
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
  and
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
6. Resolve the branch privacy gate and approved renewable off-GCP Google
   identity, then freeze a sanitized immutable SHA, publish its image digests
   and run the same application suite on the target app host.
7. Before production cutover, add the independent target backup/WAL chain and
   clean-host recovery proof that the owner deferred for this rehearsal.
8. Resolve the shared-tailnet policy before closing `/32` public SSH. This must
   not delay the backup or online restore rehearsal, but the shared tailnet must
   not be treated as project isolation.
9. Only after the privacy/identity gates pass, deploy the Part 3 digest-pinned
   shadow application with every target scheduler disabled. Keep it loopback
   only; this does not authorize DNS or writers.

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

## Part 3 — immutable hybrid application deploy (tooling prepared, not run)

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

Exit criteria before this part is operationally complete:

- one frozen commit passes the manual GHCR build and produces two digest refs;
- the target pulls the images without a mutable tag or a source checkout build;
- the API health SHA and container revision labels equal the frozen full SHA;
- target PostgreSQL TLS and health pass while Cloud SQL remains authoritative;
- read-only Secret Manager, BigQuery and GCS probes pass from the Hetzner ADC;
- both app ports remain loopback-only and all scheduler flags remain false; and
- a previous digest rollback is executed successfully before any writer cutover.

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

## Part 6 — cutover rehearsal and production cutover

- Lower DNS TTL in advance and preflight TLS, OAuth redirect behavior, agent
  consumers, egress allowlists and health checks.
- Freeze writers, confirm quiescence, take the final sync/dump and reconcile.
- State the rollback cutoff explicitly: rollback is safe only before target
  writers resume unless reverse synchronization has been proven.
- Change DNS in a separately approved action and resume one scheduler system.

## Part 7 — soak and decommission

- Keep the old database read-only through the agreed soak.
- Reconcile authentication, finance aggregates, agent daily spend and target
  backups daily.
- Complete a clean-target restore drill from the production backup chain.
- Stop billable GCP compute/database resources only after acceptance. Keep the
  Google project shells and all explicitly retained Google-native services.
