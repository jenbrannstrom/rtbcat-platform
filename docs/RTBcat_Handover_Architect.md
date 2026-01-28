# RTB.cat Platform - Architect Handover

**Date:** January 28, 2026  
**Role:** Senior Developer & Architect (Codex)  
**Scope:** Own the roadmap, system architecture, and cross‑cutting decisions.  
**Team:** Claude CLI is the ground‑level implementer.  

---

## 🎯 Executive Purpose (Architect)

Your job is to **keep the long‑term mountain view** and ensure the system converges on the QPS optimizer mission:

1. **Accurate, complete data pipeline** (Gmail → Parquet → BigQuery → Postgres)
2. **Canonical schema alignment** (DATA_MODEL.md is authoritative, but must be reconciled with UI + QPS requirements)
3. **Precompute / aggregation correctness** (summary tables for UI + QPS optimization)
4. **Operational reliability** (automation, recoverability, minimal manual steps)

You are **junior to the written plans and documentation** (DATA_MODEL.md, POSTGRES_MIGRATION_RUNBOOK.md, ROADMAP.md, UI specs).  
You are **senior to Claude** and responsible for **delegation, sequencing, and architecture decisions**.

---

## 🧭 Team Protocol

**Roles:**
- **Architect (Codex):** sets architecture, validates alignment with docs, prioritizes risks, sequences work.
- **Claude (ground expert):** executes the detailed tasks, runs migrations, fixes scripts, validates outputs.

**Rule:** If Claude sees a conflict between Codex instructions and written docs/plan, Claude must pause and ask for clarification.

---

## ✅ Current System Status (Jan 28, 2026)

**Schema & Pipeline:**
- Postgres schema alignment migration `027_schema_alignment.sql` applied on SG VM.
  - Added Postgres raw fact tables: `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality`
  - Added normalized `pretargeting_publishers`
  - BIGINT upgrades for aggregated tables
- Gmail batch importer works, including OAuth fallback for link‑only emails.
- BigQuery raw_facts coverage: 2026‑01‑11 → 2026‑01‑25.

**Aggregations:**
- `home_publisher_daily`, `rtb_publisher_daily` populated through 2026‑01‑25.
- Size/config aggregations disabled previously due to schema gaps; now must be restored after canonical pipeline is complete.

**Source of Truth:**
- `DATA_MODEL.md` updated with canonical QPS requirements and schema gaps.
- `POSTGRES_MIGRATION_RUNBOOK.md` updated with pipeline env requirements and schema gap notes.
- `ROADMAP.md` updated with schema alignment + backfill status.

---

## 🔧 Responsibilities of the Architect

1) **Schema Ownership:** ensure Postgres schema matches canonical model and UI/QPS requirements.  
2) **Data Completeness:** ensure the pipeline fills required fields (report_type, billing_id, creative_size, etc.).  
3) **Aggregation Correctness:** ensure all required summary tables populate and stay in sync.  
4) **Operational Safety:** prefer deterministic, resumable workflows and crash recovery.  
5) **Delegation:** assign ground work to Claude with explicit steps, validation criteria, and rollback plans.

---

## 🗺️ Roadmap Execution Sequence (Current)

**Phase A — Canonical Schema Complete**
1. Align Postgres raw fact tables with `DATA_MODEL.md` (done via migration 027).
2. Ensure pipeline writes **report_type** and all required fields into raw facts.
3. Ensure BIGINT for all aggregated counters (done; verify in remaining tables).

**Phase B — Backfill & Re‑aggregation**
4. Backfill new Postgres raw fact tables from BigQuery (BQ → Postgres).
5. Re-enable size/config aggregations once `creative_size` and `billing_id` are consistently present.
6. Re-run aggregation to populate **all** `home_*_daily` and `rtb_*_daily` tables.

**Phase C — QPS Optimizer Readiness**
7. Verify QPS optimizer joins work (`rtb_daily` + `rtb_bidstream` + `rtb_bid_filtering` + `rtb_quality`).
8. Validate UI endpoints expect populated summary tables; update if missing.

**Phase D — Automation**
9. Make ingest + pipeline + aggregation fully automatic (nightly or on‑import).
10. Add monitoring for missing coverage gaps (BQ dates, summary table row counts).

---

## 📌 Immediate Tasks (Active)

1) **Backfill Postgres raw fact tables** from BigQuery.  
2) **Update pipeline** to write required fields consistently:
   - `report_type`, `billing_id`, `creative_size`, `creative_format`, `publisher_id`, `publisher_name`
3) **Re-run aggregation** and confirm populated tables:
   - `home_publisher_daily`, `home_geo_daily`, `home_seat_daily`
   - `home_size_daily`, `home_config_daily`
   - `rtb_funnel_daily`, `rtb_publisher_daily`, `rtb_geo_daily`

---

## 📂 Key Files (Architect should know)

- `DATA_MODEL.md` — canonical schema + gap analysis
- `docs/POSTGRES_MIGRATION_RUNBOOK.md` — migration & pipeline steps
- `docs/HANDOVER_CRASH_RECOVERY.md` — crash restart guide
- `scripts/gmail_import.py` / `scripts/gmail_import_batch.py`
- `scripts/export_csv_to_parquet.py`
- `importers/parquet_pipeline.py`
- `scripts/load_parquet_to_bigquery.py`
- `scripts/bq_aggregate_to_pg.py`
- `scripts/bq_backfill_raw_facts.py`

---

## ✅ Operating Principles

- **Follow the docs**: if docs conflict, resolve by updating the docs first.  
- **No silent drift**: changes must be reflected in DATA_MODEL.md + runbook.  
- **Data correctness over speed**: complete, accurate data is mandatory for QPS optimization.  
- **Claude executes, Architect decides**: Claude should not make architectural choices without approval.  

