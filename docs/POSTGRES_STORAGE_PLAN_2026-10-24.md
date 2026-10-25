# PostgreSQL compaction and lossless rtb_daily redesign

Status: implementation plan, 24 October 2026. The deployed retention and query fixes are complete; the compaction and redesigned storage described below have not been executed. Run production administration directly from the operator laptop to the app and database hosts, never through archi.

## Recommendation

Keep the 180-day retention workers running. Finish measuring bidstream after its current vacuum, rehearse recovery and compaction on an isolated copy, then choose the smallest operation that produces worthwhile filesystem savings. In parallel, benchmark a single closed month of `rtb_daily` with a lossless layout. Do not replace detailed data with summaries or promise a target disk percentage before those measurements.

An operational release records the existing retention workers, certificate checker, tests and historical host fixes. Deploying that release does not execute this future storage migration. Current application images remain at release `a4428f55f1ddc0745c73e58cf49cf2c6bac4dc7e`.

## Verified baseline

Direct checks at approximately 23:53 SAST on 24 October reconfirmed the following. Statistics such as row estimates can lag a large deletion; they are not exact counts.

| Resource | Evidence | Meaning |
| --- | --- | --- |
| PostgreSQL | 15.19; no failed system units; app containers healthy | Current operating baseline |
| Database filesystem | 804,913,152,000 bytes total; 252,663,054,336 bytes available; 69% used | About 235.31 GiB available; `df -h` rounds to 236 GiB |
| `rtb_bidstream` with indexes | 94,028,472,320 bytes / 87.57 GiB; ten valid indexes | Physical size after deletion, not a savings estimate |
| Expired bidstream cleanup | 61,985,593 rows archived and deleted; earliest retained date 27 April at the 24 October cutoff | The 180-day deletion is complete; future cutoffs roll daily |
| Bidstream archives | 1,241 verified files, 3,141,384,991 compressed bytes | Complete rows and all 25 fields; separate attached volume, not off-host |
| Vacuum | `vacuuming indexes` at the check | Reclaiming reusable internal space; completion time unmeasured |
| `rtb_daily` with indexes | 420,474,544,128 bytes / 391.60 GiB | The largest remaining storage consumer |
| Archive volume | About 360 GiB available | Also holds recovery artifacts; not automatically free migration workspace |

Ordinary vacuum usually makes deleted space reusable by PostgreSQL; it does not compact the whole relation and can return space only where free pages can be removed from its end. A rewrite can return more space but requires additional disk and introduces locking and recovery consequences. [PostgreSQL vacuum guidance](https://www.postgresql.org/docs/15/routine-vacuuming.html).

`rtb_daily` retention removes whole expired monthly partitions, so the retained boundary month can extend beyond exactly 180 days. Bidstream deletes individual expired dates. Neither archive set has automatic expiry or a verified off-host archival copy. A successful backup and a decoded archive are not substitutes for a full recovery rehearsal.

## Track A: bidstream physical compaction

### A1. Measure after vacuum

1. Observe the existing vacuum until completion; check for long transactions or old snapshots if progress stalls. Do not launch a second vacuum or terminate sessions just to speed it up.
2. Record heap, TOAST and each index size separately, vacuum/analyze timestamps, estimated live/dead rows, filesystem headroom, WAL archive backlog and backup age. Record the statistics reset time; unavailable or reset counters cannot establish that an index is unused.
3. Measure actual free-page density on an isolated restored copy. If production inspection needs a new extension such as `pgstattuple`, make installation an explicit scoped change; current observations alone do not prove the reclaimable bytes.
4. Compare the retained table after a rehearsal rewrite with the source, including all fields, keys, constraints, indexes and relevant API responses. Record WAL generated, peak temporary space, wall time and throughput.

Deliverable: a before/after capacity sheet and a measured maintenance estimate. Reject compaction if its gain is small relative to expected near-term ingestion, I/O cost and recovery risk.

### A2. Select the operation from measurements

| Option | Appropriate use | Operational cost |
| --- | --- | --- |
| Leave reusable space in place | Ingestion will reuse it and capacity is adequate | No rewrite; filesystem percentage may remain unchanged |
| Rebuild an individually bloated index concurrently | Measured index bloat dominates | Extra index copy and WAL; concurrent work still has lock/wait phases |
| `pg_repack` on bidstream only | Heap and indexes have material reclaimable space and rehearsal passes | New matched client/extension installation; copy, change capture, temporary space and brief exclusive locks |
| `VACUUM FULL` on bidstream only | A measured outage is acceptable and online repack is unsuitable | Exclusive table lock for the rewrite; new table/index storage and WAL |

Preferred rewrite candidate is a single-table `pg_repack` rehearsal, not an immediate live execution. Its documentation estimates approximately twice the target table-plus-index size in additional space: about 175.14 GiB for the current 87.57 GiB relation. Against 235.31 GiB available, that leaves only about 60.17 GiB before WAL, temporary files and normal growth. This fails the proposed 80 GiB minimum remaining database headroom. Provide additional measured capacity or choose a smaller operation before proceeding. Do not use the archive filesystem for a tablespace without separately budgeting and protecting its recovery contents. [pg_repack requirements](https://reorg.github.io/pg_repack/#requirements).

For concurrent index rebuilding, record both original and new index identities, verify the replacement is valid, and handle any invalid leftover explicitly. PostgreSQL 15 cannot concurrently reindex a partitioned parent; any later `rtb_daily` index maintenance must target individual leaf indexes. [PostgreSQL REINDEX](https://www.postgresql.org/docs/15/sql-reindex.html).

### A3. Rehearse and execute a bounded maintenance window

Prerequisites: restore the latest pgBackRest backup to an isolated database; replay required WAL; verify representative data and application queries; prove the actual restore duration. Before the live window, complete a fresh backup and current archive check, confirm no active imports/precompute/backups compete for I/O, and record a restart/recovery procedure.

The execution plan must name one table or index, exact software versions and options, working-space budget, operator, time limit and rollback point. Start with one worker. For repack, use its no-backend-killing mode and a short tested lock-wait bound; abandon the attempt rather than cancel user work. Hold conflicting schema/index changes and coordinate retention jobs for that table. A dry run identifies targets; it does not prove peak capacity or runtime. [pg_repack usage](https://reorg.github.io/pg_repack/#usage).

Proposed stop thresholds, to confirm in rehearsal: database free space below 80 GiB, archive free space below 40 GiB, more than 32 unarchived WAL segments for five minutes, sustained API p95 latency above twice baseline for five minutes, or any data-validation mismatch. Track temporary tablespaces separately. Stopping a tool may leave temporary objects; inspect its documented cleanup state instead of dropping objects by guesswork.

After completion: compare all original rows/fields and constraints using a consistent dataset, verify index validity, refresh statistics as needed, test imports/deduplication and the affected UI queries, run release acceptance checks, and take a post-maintenance backup. Report actual filesystem bytes reclaimed and maximum observed service impact.

Before the swap, a failed repack should leave the original authoritative table; verify that state. After a successful physical rewrite there is no guaranteed instant old-table rollback: recovery can require restoring backup plus WAL to a separate database and reconciling later writes. `VACUUM FULL` likewise requires a tested recovery plan. Do not advertise either as risk-free or zero downtime.

## Track B: lossless rtb_daily redesign

### B1. Freeze the data contract and query baseline

Preserve every retained row's identity and source provenance, hour, creative, buyer, bidder, billing, country/geography, publisher, app, size, format and all metrics. Preserve NULL versus zero, NULL versus empty string, historical labels, tenant boundaries, import deduplication, exact numeric precision, filters, ordering/pagination, exports and drilldowns.

Inventory actual importer, API, precompute, dashboard and MCP readers. Include creative performance and clicks, billing economics, buyer/date reports, geography and size coverage, QPS optimisation, data-health coverage and raw fallback queries. Record representative 1-, 7-, 30-, 90- and 180-day cases, cold/warm latency, buffers, temporary spill and import/refresh throughput. Existing summary tables do not yet reproduce the full contract.

Keep the billing/date and bidder index families: previous query-plan investigation demonstrated their use despite zero recorded execution scans. The date/creative family already removed saved 4.73 GiB; do not count it again. Do not infer feature adoption from index statistics.

### B2. Benchmark independent candidates

| Candidate | Earlier evidence | Required proof |
| --- | --- | --- |
| Narrower creative/date index plus exact summary support | Existing covering index family is about 56.99 GiB | Every current filter and clicks calculation remains exact; raw fallback still works; total replacement storage and write cost are lower |
| Compact row hash | Sampled hashes were 32 hexadecimal characters; 16 bytes retain their bits | Validate every hash, preserve canonical external text and NULL/case semantics, and retain collision/deduplication behavior |
| Dictionary keys for repeated dimensions | Many repeated string identifiers | Preserve original strings, historical versions, NULL/empty values and account scope; measure lookup/index/join overhead |
| Sparse storage for eight metrics | Eight bigint fields were non-NULL zero in the earlier sample | Preserve every nonzero and explicit NULL; absent exception means exactly zero; reconstruct all fields and support future values |

The eight sampled fields were `video_first_quartile`, `video_midpoint`, `video_third_quartile`, `vast_errors`, `engaged_views`, `active_view_measurable`, `active_view_viewable` and `bid_requests`. A zero-only sample is not permission to remove them.

Earlier arithmetic suggested about 9.75 GiB less raw hash payload and 36.72 GiB of raw zero-metric payload. These are estimates from sampled widths and planner row counts, not measured filesystem savings, and cannot be added to index sizes as a guaranteed reduction. Compare complete heap, TOAST, indexes, lookup/exception tables and compatibility costs. Benchmark one change at a time, then the combined design.

### B3. Build one closed-month pilot

Use an isolated database on separately budgeted capacity. Choose a retained closed month large enough to exercise real cardinalities and supplement with fixtures for rare/nonzero/NULL values and current-month ingestion. The earlier largest month was about 73 GiB including indexes. A complete duplicate of the 391.60 GiB live table does not fit current headroom.

Implement a versioned read/write contract. A view can reconstruct fields but is not automatically a drop-in replacement for `INSERT ... ON CONFLICT`, ORM metadata or partition pruning. Test the actual importer, sequence behavior, uniqueness, late corrections, duplicate retry, source provenance and failure recovery. Decide explicitly whether compact hashes use a 16-byte binary or UUID representation after validating conversion semantics. Keep a reversible decoder to the original schema.

Acceptance gates:

- Full row counts and two-way, field-by-field multiset comparison on a consistent snapshot; NULL-safe equality and exact numeric values. Hashes and samples are supporting evidence only.
- Identical aggregates at each supported filter combination, plus API response/export parity and a real authenticated walkthrough of affected dashboard flows.
- All existing relevant regression tests and new round-trip/import/conflict tests pass.
- Proposed performance budget: no more than 10% p95 regression in any critical query family or ingestion/refresh throughput; investigate measurement noise with repeated runs. Tighten this if current service objectives require it.
- Positive measured net storage gain after all supporting structures; enough working space for backfill, WAL, rollback and normal growth.

Deliverable: measured savings in GiB, query results, workload timings and a recommended final schema. A failed candidate is dropped from the proposal without changing production data.

### B4. Stage the migration and retain a real rollback path

1. Commit the final schema, migrations, compatibility readers/writers, tests and recovery instructions in a dedicated PR after pilot acceptance.
2. Build a new physical parent/schema for a changed row layout. Existing partitions attached to one parent must share that parent's column definition; mixed layouts cannot simply be attached one by one. Use a tested compatibility layer across old/new storage or a controlled parent cutover. [PostgreSQL partitioning](https://www.postgresql.org/docs/15/ddl-partitioning.html).
3. Backfill one month at a time. Choose and test either a brief write pause or transactional change capture that handles concurrent inserts, updates, deletes and late imports. A month is not immutable merely because it is closed.
4. Reconcile a consistent final delta under a bounded write boundary; move readers only after exact comparisons pass. Preserve grants, constraints, sequences, ownership and dependencies that bind to relation identity. A rename alone does not redirect every dependent view or foreign key.
5. Canary affected queries and one import, then expand. Define a proposed seven-day observation period with capacity for old data; budget it explicitly before migration.
6. During the rollback period keep the old representation current through a tested reverse-write path, or retain a durable replayable change log and reconcile before reverting. Old tables that stop receiving writes are not a complete rollback solution.
7. Remove replaced storage only after acceptance and expiry of the agreed rollback period. Confirm a recoverable backup, exact objects and expected bytes immediately before the consequential removal. Coordinate retention so old/new layouts cannot independently prune incompatible boundaries.

## Delivery order and effort estimates

These are engineering planning ranges, not measured production runtimes. Dependencies are dataset access, isolated storage, backup restore speed and query coverage.

| Stage | Planning estimate | Exit condition |
| --- | --- | --- |
| Vacuum follow-up, inventory and recovery rehearsal | 0.5–1 engineering day, plus measured restore elapsed time | Trustworthy capacity/recovery baseline |
| Bidstream compaction rehearsal and runbook | 0.5–1.5 days | Measured gain, peak disk/WAL and approved maintenance duration |
| `rtb_daily` contract inventory and single-month pilot | 2–4 days | Exact parity and benchmark report |
| Migration implementation and rehearsal | 2–5 days after the pilot | Tested cutover, rollback and deployment checks |
| Staged rollout and observation | Maintenance window measured in rehearsal, then proposed seven-day observation | Stable workload, exact data and verified capacity |

The next concrete deliverable is the post-vacuum capacity sheet and isolated restore/pilot specification. No physical compaction, new extension, tablespace, production schema redesign or additional data removal is authorized merely by publishing this plan. Schedule the concrete production operation once its measured scope, interruption and capacity requirements are reviewable.
