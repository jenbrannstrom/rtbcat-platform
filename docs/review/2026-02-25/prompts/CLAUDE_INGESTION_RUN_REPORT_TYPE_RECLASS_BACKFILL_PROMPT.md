# Claude Prompt: `ingestion_runs.report_type` Reclassification Backfill (Prod)

```text
Run the ingestion_runs report_type reclassification backfill script on production (dry-run first, then apply if results look correct).

Context
- We confirmed TUKY’s “2 of 5 CSVs” issue is largely import tracking misclassification (`unknown` report_type), not missing raw data.
- New script is now on `unified-platform` branch:
  - `scripts/backfill_ingestion_run_report_types.py`
  - commit `488c93b`
- It reclassifies historical `ingestion_runs.report_type` values into canonical UI categories using filename + parser type + import_history.columns_found heuristics.
- It updates ONLY `ingestion_runs.report_type` (no raw data/precompute writes).

Your goals
1. Run a TUKY-only dry-run first (safety)
2. Run a broader dry-run
3. Apply the backfill
4. Verify import matrix/report_type counts improved
5. Document what changed

Important safety notes
- Start with `--dry-run`
- Review sample output before `--apply`
- This is a tracking fix only; do not rerun Gmail imports as part of this step
- If results look wrong, stop and report (don’t apply)

Prep
1. Ensure prod VM/container is on a build that includes commit `488c93b`
   - If not deployed yet, either:
     - deploy first, OR
     - temporarily copy the script into the VM/container and run it there
2. Confirm script exists inside container:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo docker exec catscan-api ls -l /app/scripts/backfill_ingestion_run_report_types.py"
```

Step 1 — TUKY-only dry-run (required)
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo docker exec catscan-api python /app/scripts/backfill_ingestion_run_report_types.py --dry-run --buyer-id 299038253 --since 2026-02-10"
```

What to check in output
- `Would update / Updated` is > 0
- Sample changes show rows like:
  - `unknown -> catscan-pipeline` / `catscan-bidsinauction` / `catscan-quality`
  - parser types like `rtb_bidstream_publisher -> catscan-pipeline`
- `Skipped unresolved` is not unexpectedly huge for TUKY

Step 2 — Verify TUKY counts before apply (baseline snapshot)
Run this and save output:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT COALESCE(report_type, %s) AS rt, COUNT(*) AS runs, SUM(CASE WHEN status=%s THEN 1 ELSE 0 END) AS success_runs, MAX(COALESCE(finished_at, started_at)) AS latest_run FROM ingestion_runs WHERE COALESCE(buyer_id,bidder_id)=%s AND COALESCE(finished_at, started_at) >= %s::timestamptz GROUP BY 1 ORDER BY 2 DESC, 1\", (\"(null)\", \"success\", \"299038253\", \"2026-02-10\")); print(json.dumps(cur.fetchall(), default=str))"'
```

Step 3 — Broader dry-run (recommended)
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo docker exec catscan-api python /app/scripts/backfill_ingestion_run_report_types.py --dry-run --since 2026-02-01"
```

Review:
- Total `Would update`
- Sample rows look sane
- `Skipped unresolved` is expected (e.g. quality_signals or genuinely ambiguous rows)

Step 4 — Apply the backfill
If dry-runs look correct:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo docker exec catscan-api python /app/scripts/backfill_ingestion_run_report_types.py --apply --since 2026-02-01"
```

Step 5 — Verify after apply (required)
1) TUKY report_type counts (same query as Step 2)
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT COALESCE(report_type, %s) AS rt, COUNT(*) AS runs, SUM(CASE WHEN status=%s THEN 1 ELSE 0 END) AS success_runs, MAX(COALESCE(finished_at, started_at)) AS latest_run FROM ingestion_runs WHERE COALESCE(buyer_id,bidder_id)=%s AND COALESCE(finished_at, started_at) >= %s::timestamptz GROUP BY 1 ORDER BY 2 DESC, 1\", (\"(null)\", \"success\", \"299038253\", \"2026-02-10\")); print(json.dumps(cur.fetchall(), default=str))"'
```

2) Global unknown count trend (optional but useful)
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT COALESCE(report_type, %s) AS rt, COUNT(*) FROM ingestion_runs WHERE source_type=%s AND COALESCE(finished_at, started_at) >= %s::timestamptz GROUP BY 1 ORDER BY 2 DESC, 1\", (\"(null)\", \"csv\", \"2026-02-01\")); print(json.dumps(cur.fetchall(), default=str))"'
```

3) If possible, refresh/reload TUKY Import UI and confirm matrix now reflects more than 2 CSV types

Step 6 — Documentation
Create/update a review note (docs-only in repo) with:
- exact commands run
- dry-run outputs (TUKY + global)
- apply output summary
- before/after TUKY report_type counts
- any unresolved/skipped rows and why

Suggested doc path:
- `docs/review/2026-02-25/audit/TUKY_IMPORT_TRACKING_RECLASSIFICATION_BACKFILL.md`

Return to me
- dry-run summary (TUKY + global)
- apply summary (`Updated`, `Skipped unresolved`)
- before/after TUKY report_type counts
- whether the Import UI improved for TUKY
- any anomalies
```
