# RTBcat Crash Recovery Handover

Purpose: fast restart if any terminal or AI session crashes.

## Current Status (Jan 28, 2026)
- PR #86 merged into `unified-platform`.
- Postgres schema alignment migration `027_schema_alignment.sql` applied on SG VM.
- Postgres DSNs in `/opt/catscan/.env` use `host.docker.internal`.
- OAuth fallback for GCS link-only Gmail downloads works.
- BigQuery raw_facts date range currently 2026-01-11 → 2026-01-25.
- Raw fact backfill to Postgres completed:
  - `rtb_daily`: 9,082,712 rows (2026-01-07 → 2026-01-25)
  - `rtb_bidstream`: 3,547,431 rows (2026-01-07 → 2026-01-25)
  - `rtb_bid_filtering`: 44,936 rows (2026-01-13 → 2026-01-25)

## Active Log Protocol
- Use: `docs/ai_logs/ai_log_2026-01-27.md`
- Append-only, timestamps in Asia/Singapore (UTC+08:00).
- If >500 lines, start a new part file.

## Immediate Next Tasks (DB Roadmap)
1) Re-run aggregation to populate:
   - `home_size_daily`, `home_config_daily` (now re-enabled with join logic)
2) Verify QPS optimizer joins against Postgres raw facts.
3) Wire UI to normalized `pretargeting_publishers` endpoints.

## SG VM Essentials
**Env file:** `/opt/catscan/.env`
```
POSTGRES_DSN=postgresql://...@host.docker.internal:5432/rtbcat_serving
POSTGRES_SERVING_DSN=postgresql://...@host.docker.internal:5432/rtbcat_serving
CATSCAN_PIPELINE_ENABLED=true
CATSCAN_GCS_BUCKET=...
RAW_PARQUET_BUCKET=...
CATSCAN_BQ_DATASET=rtbcat_analytics
CATSCAN_BQ_PROJECT=...
```

**Docker compose:** `/opt/catscan/docker-compose.gcp.yml`
- Has `env_file: .env` and `extra_hosts` for `host.docker.internal`.

**Restart API container:**
```
cd /opt/catscan
sudo docker compose -f docker-compose.gcp.yml down
sudo docker compose -f docker-compose.gcp.yml up -d
```

**Check Postgres connectivity:**
```
sudo docker exec catscan-api env | grep -i postgres
```

## Gmail Batch Import (nohup)
```
sudo docker exec catscan-api bash -c "nohup python3 scripts/gmail_import_batch.py --batch-size 10 >> /home/rtbcat/.catscan/logs/gmail_batch.log 2>&1 &"
sudo docker exec catscan-api tail -f /home/rtbcat/.catscan/logs/gmail_batch.log
sudo docker exec catscan-api cat /home/rtbcat/.catscan/gmail_batch_checkpoint.json
```

## Key Files
- `DATA_MODEL.md` — canonical schema (updated with QPS requirements)
- `docs/POSTGRES_MIGRATION_RUNBOOK.md` — migration & pipeline requirements
- `scripts/gmail_import.py` — OAuth fallback for GCS links
- `scripts/gmail_import_batch.py` — checkpointed batch import
- `scripts/bq_aggregate_to_pg.py` — aggregation queries
- `importers/parquet_pipeline.py` and `scripts/export_csv_to_parquet.py` — schema + currency parsing
