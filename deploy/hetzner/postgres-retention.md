# PostgreSQL partition retention

`rtbcat-postgres-retention.timer` runs daily at 04:00–04:10 UTC. The service
runs as the PostgreSQL operating-system user using local peer authentication.
It needs only Python's standard library, PostgreSQL client tools and pgBackRest.

The global `retention_config.raw_retention_days` controls the rolling window.
The deployed safety floor is 180 days. Conflicting global rows or a value below
180 abort the run. A whole monthly partition expires only when its actual upper
date bound is at or before the cutoff. Thus a 180-day policy keeps up to one
additional partial month. No columns, metrics, dimensions or retained rows are
removed. Historical/lifetime UI totals may decrease when old months expire.

The default invocation is read-only. `--apply` requires the dedicated archive
volume, a successful pgBackRest backup within 36 hours, sufficient archive
space, a complete compressed dump and a successful full data decode before
dropping each expired partition. Metadata and checksums are stored with each
archive. These checks are not a restore rehearsal. Archives stay on the second
volume and are not automatically expired or copied off-host.

Incomplete or mismatched archives stop cleanup for manual review. Each DROP
uses a two-second lock timeout, checks the table OID and actual bounds again,
and does not use CASCADE. Missing future partitions are created through three
months ahead with the application owner. Existing partitions are untouched.

The initial 24 October 2026 archive combines January–March in a separate file;
the daily worker archives subsequent expired partitions individually. Local
archive space must be monitored; it is distinct from the live 180-day window.

This service covers `rtb_daily` only. The separate `rtbcat-bidstream-retention`
service now archives and prunes expired bidstream rows in bounded batches; see
[operations and recovery notes](operations-2026-10-24.md). The API's existing
retention endpoint covers legacy metrics, summaries and conversion tables.

`normalize_retention_config.sql` consolidates identical global 180-day settings
and adds a PostgreSQL 15 `UNIQUE NULLS NOT DISTINCT (seat_id)` constraint. This
makes the existing dashboard upsert work for the global NULL seat and prevents
future duplicate global settings. No application redeploy is needed.

`scripts/hetzner/drop_duplicate_rtb_daily_indexes.sql` separately removes
three exact duplicate index trees, retaining the equivalent migration-created
indexes. It validates keys, expressions, predicates, collations, options,
validity, uniqueness, constraints and corresponding children before dropping.
It changes no rows or columns. Run when the archive's pg_dump has completed,
because the dump holds read locks. The short lock timeout avoids long waits.
