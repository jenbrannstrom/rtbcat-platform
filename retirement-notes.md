# Retirement Notes — CTO Retrospective

**Date:** 2026-07-09
**Scope:** rtbcat-platform (Cat-Scan) retrospective + GCP → Hetzner migration opinion.
**Context:** Written on handover/retirement. Companion to `handover.md` and the GCP Full Migration Inventory & Checklist.

---

## Production state — verified at handover (2026-07-09)

- The daily-spend buyer-level fix `d48e8ae0` is **on `origin/main` and durably deployed**: `/api/health` reports `git_sha: d48e8ae0` (verified 2026-07-09).
- Remote `main` is at `c4e8e2df` — two smoke-test PRs (#98, #99) landed on top of the deployed commit. Not deployed yet; redeploy at leisure, nothing customer-facing.
- **Caveat found while verifying:** the prod VM's local git refs were stale enough to make `d48e8ae0` *look* unpushed. Before any migration step, `git fetch` on the VM first — do not trust its cached view of GitHub.
- **SSH key gotcha on the VM:** `~catscan/.ssh/config` pins GitHub to `id_ed25519_sg`, a **read-only** deploy key, so pushes from the VM fail by default. The write-capable key is `id_ed25519` (use `GIT_SSH_COMMAND='ssh -i /home/catscan/.ssh/id_ed25519 -o IdentitiesOnly=yes -F /dev/null'`). Read-only-by-default is arguably correct — but document it, because it silently strands local commits on the box (see §4 below).

---

## What went right — keep these

- **Sitting beside Authorized Buyers instead of inside the bidder.** The CSV/Gmail ingestion path is ugly, but Google genuinely doesn't expose those reporting dimensions in one API. Right call, correctly documented as such.
- **Docs discipline.** An ARCHITECTURE.md that says "this is what exists, not a wish list," a METRICS_GUIDE with verified funnel semantics, dated handovers. The observed-QPS fix (a **1,800× understatement** from using `reached_queries` instead of `bid_requests`) was only findable because metric semantics were written down and re-verified against a live seat.
- **Precompute-first serving** and the router/service/repository split — both real, both paid off.

---

## What I'd do differently

### 1. Treat ingestion trust as the product, with continuous data contracts

Every serious incident in the history is the same incident wearing different clothes:

- Gmail importer silently marking non-allowlisted reports as read → **3.5 weeks of a seat's data destroyed** with zero trace.
- `app_name` 100% NULL upstream → an entire feature shipped reading a **permanently empty table** (`rtb_app_daily`), returning spend=0 for all customers.
- NULL aggregates rolling back whole precompute refresh transactions.
- Per-buyer daily spend overflowing INTEGER micros.

A per-seat, per-report-type completeness monitor ("this column is 100% NULL," "this seat's freshest row is 4 days old") would have caught all four before customers did. The deploy-time contract gate added in June 2026 is the right idea — it should have existed from month two, and it should run **daily**, not only on deploy.

### 2. Ruthless scope control

For roughly six buyer seats and a handful of operators, the repo carries ~28 routers, 40+ services, six conversion connectors (one proven in production), three auth systems, three AI providers, 11 locales, a four-module optimizer suite, and 17 GHA workflows (many stale `v1-*` pilot gates).

The June cleanup (deleting the dead QPS router, making no-op stubs return 501 instead of fake success) was the right instinct applied two years late. The rule to enforce from day one: **proven in prod within a quarter, or deleted.** Half the maintenance and security-audit surface is features waiting for users who never arrived.

### 3. Partition the fact tables by day from the start

`rtb_daily` is 157 GB / 227M rows with 68 GB of index bloat, growing ~1.5 GB/day; the retention settings page exists but retention was never enforced. With daily partitions:

- Retention is `DROP PARTITION` — instant, no bloat, no vacuum storm.
- The migration would be a stream of small chunks instead of a 183 GB monolith.

Money in BIGINT micros from day one, too — the schema has it now, but only after the overflow bit.

### 4. Never let the prod VM become a dev environment

Hot-patched containers that survive restart but not recreation; `.env` changes that need recreation, not restart; unpushed commits on the box. Each is a small drift; together they mean the system's true state exists nowhere but on one VM in Singapore.

One invariant eliminates the class: **nothing serves traffic that isn't a pushed, sha-tagged image.**

---

## Migration: additions to the checklist

The existing inventory/checklist is genuinely good — writers-inventory, aggregate-then-prune, collation warning, rollback cutoff are all things usually learned the hard way. Additions and decisions:

### Registry: switch to GHCR now

Deploy path is GHA → `asia-southeast1-docker.pkg.dev` (Artifact Registry). Since GitHub is already the source of truth, pushing to GHCR removes an entire GCP auth dependency from the Hetzner box (which has no metadata server). One workflow edit plus a pull token.

### Cloud Scheduler is missing as a checklist section

The precompute / Gmail / creative-cache refresh jobs are Cloud Scheduler HTTPS calls carrying secret headers into `scan.rtb.cat`. On Hetzner these become **systemd timers doing authenticated curls to localhost** — simpler, and one less GCP tie.

Also: the one-time purge routine for seat `299038253` fires **2026-09-11** — make sure that runbook still points at the right host by then.

### Restore into a partitioned schema (rehearsal-gated)

The migration is the one free rewrite of the big tables. Rehearse it: restore `rtb_daily` into daily (or monthly) partitions on the target, point a test instance at it, time it.

- Rehearsal clean → cut over onto partitions, get retention-by-DROP forever.
- Rehearsal hairy → migrate as-is, partition later.

Decide from rehearsal evidence, not nerves.

### Backups: pg_dump-cron isn't enough at 180 GB

Cloud SQL gave PITR for free; self-hosted needs **pgBackRest (or wal-g) with WAL archiving** to object storage, plus a *scheduled restore test*. Verify Hetzner object storage availability in SIN — if not, Cloudflare R2 / Backblaze B2.

Cloud SQL also auto-grew the disk; Hetzner won't. **Disk-space alerting is now your job.**

### SSH story changes

Prod access today is IAP tunnels; Hetzner is a raw public IP. Key-only SSH plus Tailscale (or at minimum firewall allowlist for port 22) **before** the box holds customer finance data.

### Freshness alerting is the highest-value ops investment on the new stack

The Gmail incident's real lesson: alert when a *seat's data goes stale*, not when a *job fails* — the job "succeeded" the whole time it was destroying reports. A daily contract-check cron paging on staleness turns a 3.5-week loss into a 1-day blip.

### Hetzner SIN caveat

Included traffic in Singapore is far lower than EU and prices carry a premium. Current traffic is modest so it likely doesn't matter, but price it before assuming EU economics.

---

## Recommended target shape (Hetzner SIN)

- **App box:** one CPX/CCX instance — Caddy + oauth2-proxy + api + dashboard via a trimmed `docker-compose.production.yml`, no cloud-sql-proxy.
- **Database:** Postgres 16 (pin the exact Cloud SQL version) on the same box or a second one. Cloud SQL handled this workload on 1 vCPU / 3.75 GB — don't overprovision.
- **Backups:** pgBackRest → object storage, WAL archiving, weekly restore test.
- **Images:** GHCR, pulled with a GitHub token.
- **Schedulers:** systemd timers replacing Cloud Scheduler.
- **Secrets:** GSM stays (per checklist Section 0); one SA key (or WIF) wired into provisioning, **tested from a Hetzner box before cutover**.
- **DNS/TLS:** Cloudflare; if proxied (orange cloud), Caddy needs DNS-01 or origin certs (already in the checklist).

---

*It's a good system to hand over: honest docs, real incidents learned from, and a migration plan already better than most. Push that commit.*
