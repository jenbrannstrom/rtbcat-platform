# RTBcat Crash Recovery Handover

Purpose: fast restart if any terminal or AI session crashes.

## Current Status (Jan 28, 2026)
- PR #86 merged into `unified-platform`.
- Postgres schema alignment migration `027_schema_alignment.sql` applied on SG VM.
- Postgres DSNs in `/opt/catscan/.env` use `host.docker.internal`.
- OAuth fallback for GCS link-only Gmail downloads works.
- BigQuery raw_facts date range currently 2026-01-11 → 2026-01-25.
- Postgres summary tables populated through 2026-01-25:
  - `home_publisher_daily` and `rtb_publisher_daily` populated (11,299 rows each).

## Active Log Protocol
- Use: `docs/ai_logs/ai_log_2026-01-27.md`
- Append-only, timestamps in Asia/Singapore (UTC+08:00).
- If >500 lines, start a new part file.

## Immediate Next Tasks (DB Roadmap)
1) Backfill new Postgres raw fact tables:
   - `rtb_daily`, `rtb_bidstream`, `rtb_bid_filtering`, `rtb_quality`
   - Prefer BigQuery → Postgres load.
2) Update pipeline to write required fields consistently:
   - `report_type`, `billing_id`, `creative_size`, `creative_format`, `publisher_id`, `publisher_name`
3) Re-run aggregation after backfill to populate size/config views.

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

