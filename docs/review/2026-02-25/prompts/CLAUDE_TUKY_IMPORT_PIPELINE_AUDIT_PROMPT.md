# Claude Prompt: TUKY Import Pipeline RCA (End-to-End)

```text
Do a full production audit of the TUKY email import -> import tracking -> BQ/Postgres -> precompute -> Home endpoint observed-QPS path, and determine whether the issue is true data corruption or a tracking/unit mismatch.

This is an evidence-first RCA. Do not guess. Collect concrete outputs.

Context / why this audit is needed
- User reports TUKY import UI shows only 2 of 5 CSV types imported (they only see `catscan-quality` and `catscan-pipeline-geo` in Import page).
- There are unread Gmail report emails remaining (Feb 11–14 stragglers). Gmail system marks messages as read when touched, so unread alone is not proof of “not ingested”.
- Home shows endpoint observed QPS values like `4.5`, `13.6`, `22.7` (7d view), while attached TUKY “bidding metrics 7day” CSV shows ~3.5M reached queries/day and ~0.8M impressions/day.
- We need to verify whether data is being corrupted or whether:
  1) the Home values are QPS derived from daily reached queries, and/or
  2) import tracking is misclassifying some imported reports.

Known likely issue to test explicitly
- Gmail GCS downloads use generic filenames like `catscan-report-<seat>-<timestamp>.csv`, and `record_import_run()` infers `report_kind` from local filename (`detect_report_kind(filepath.name)`), which likely records many successful imports as `unknown`.
- If true, Import UI matrix can underreport “imported” CSV types even when data landed.

Target account
- TUKY seat/buyer shown in UI: `299038253` (display name `Tuky Display`)
- Audit window: `2026-02-18` through `2026-02-24` (matches attached 7-day CSV)

Deliverables
1. Concrete RCA with evidence (prod queries/logs)
2. Classification of the root issue(s):
   - import tracking/UI misclassification?
   - Gmail backlog/stragglers?
   - true numeric corruption?
   - unit/UX mismatch (QPS vs daily counts)?
3. List of code fixes required (by file/function)
4. Audit doc + roadmap/status note (if appropriate)

Important constraints
- Prefer read-only prod queries unless a bounded Gmail inspection/import run is necessary for classification.
- Do not mutate production data unless explicitly needed for evidence (and if so, note exactly what changed).
- Do not claim “corruption” unless you can prove a numeric mismatch between source CSV and stored/precomputed values after unit normalization.

Environment
- VM: `catscan-production-sg`
- API container: `catscan-api`
- Use `gcloud compute ssh ... --tunnel-through-iap`
- `psql` is not installed in `catscan-api`; use `python + psycopg` inside container for SQL.

PHASE A — Confirm identities + baseline (prod, read-only)
1) Confirm TUKY seat mapping
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT buyer_id, bidder_id, display_name, active FROM buyer_seats WHERE buyer_id=%s OR display_name ILIKE %s ORDER BY active DESC, buyer_id\", (\"299038253\", \"%Tuky%\")); print(json.dumps(cur.fetchall(), default=str))"'
```
Expected: `299038253` maps to TUKY (buyer_id/bidder_id likely same here).

2) Confirm Home seat daily values for the 7-day window
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT metric_date, reached_queries, impressions, bid_requests, bids, successful_responses, auctions_won FROM home_seat_daily WHERE buyer_account_id=%s AND metric_date BETWEEN %s AND %s ORDER BY metric_date\", (\"299038253\", \"2026-02-18\", \"2026-02-24\")); print(json.dumps(cur.fetchall(), default=str))"'
```

3) (Optional but useful) Also inspect `seat_daily` if it exists separately
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT to_regclass(%s)\", (\"public.seat_daily\",)); print(cur.fetchone())"'
```
If table exists, query same 7-day rows for `buyer_account_id='299038253'`.

PHASE B — Prove/disprove “Home observed QPS mismatch” (prod, read-only)
Goal: show whether Home endpoint `Observed` values are derived QPS (avg reached_queries/day/86400) rather than daily counts.

1) Compute 7-day average reached_queries and derived seat QPS from `home_seat_daily`
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT COUNT(*), SUM(reached_queries), AVG(reached_queries::double precision), AVG(reached_queries::double precision)/86400.0, SUM(impressions), AVG(impressions::double precision) FROM home_seat_daily WHERE buyer_account_id=%s AND metric_date BETWEEN %s AND %s\", (\"299038253\", \"2026-02-18\", \"2026-02-24\")); r=cur.fetchone(); print(json.dumps({\"days\":r[0],\"sum_reached\":r[1],\"avg_reached_per_day\":r[2],\"avg_reached_qps\":r[3],\"sum_impressions\":r[4],\"avg_impressions_per_day\":r[5]}, default=str))"'
```

2) Query endpoint allocations and observed endpoint QPS (`rtb_endpoints_current`) for TUKY
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT e.endpoint_id, e.maximum_qps, ec.current_qps FROM rtb_endpoints e LEFT JOIN rtb_endpoints_current ec ON ec.bidder_id=e.bidder_id AND ec.endpoint_id=e.endpoint_id WHERE e.bidder_id=%s ORDER BY e.endpoint_id\", (\"299038253\",)); rows=cur.fetchall(); cur.execute(\"SELECT SUM(current_qps) FROM rtb_endpoints_current WHERE bidder_id=%s\", (\"299038253\",)); s=cur.fetchone()[0]; print(json.dumps({\"endpoints\": rows, \"sum_current_qps\": s}, default=str))"'
```

3) Compare with screenshot values
- Check whether `sum_current_qps` is approximately `4.5 + 13.6 + 22.7 ≈ 40.8`
- Check whether `avg_reached_per_day / 86400` from step B1 is approximately the same (~40.x)
- If yes: this is a unit mismatch / label misunderstanding, not corruption

PHASE C — Import tracking audit for “2 of 5 CSVs” (prod, read-only)
Goal: determine whether TUKY actually imported only 2 types, or imports are being recorded under `unknown`.

1) Ingestion runs by report_type for TUKY (Feb 10 onward)
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT COALESCE(report_type, %s) AS report_type_norm, COUNT(*) AS runs, SUM(CASE WHEN status=%s THEN 1 ELSE 0 END) AS success_runs, MAX(COALESCE(finished_at, started_at)) AS latest_run FROM ingestion_runs WHERE COALESCE(buyer_id,bidder_id)=%s AND COALESCE(finished_at, started_at) >= %s::timestamptz GROUP BY 1 ORDER BY runs DESC, 1\", (\"(null)\", \"success\", \"299038253\", \"2026-02-10\")); print(json.dumps(cur.fetchall(), default=str))"'
```

2) Inspect recent `unknown`/null report-type runs for TUKY
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT report_type, filename, status, row_count, error_summary, import_trigger, buyer_id, bidder_id, started_at, finished_at FROM ingestion_runs WHERE COALESCE(buyer_id,bidder_id)=%s AND (report_type IS NULL OR report_type=%s) AND COALESCE(finished_at, started_at) >= %s::timestamptz ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 50\", (\"299038253\", \"unknown\", \"2026-02-10\")); print(json.dumps(cur.fetchall(), default=str))"'
```

3) Inspect `import_history` filenames / rows for TUKY in same window
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT filename, rows_imported, rows_duplicate, status, error_message, import_trigger, imported_at FROM import_history WHERE COALESCE(buyer_id,bidder_id)=%s AND imported_at >= %s::timestamptz ORDER BY imported_at DESC LIMIT 100\", (\"299038253\", \"2026-02-10\")); print(json.dumps(cur.fetchall(), default=str))"'
```

4) Interpret evidence
- If many filenames are generic like `catscan-report-299038253-<timestamp>.csv` and `ingestion_runs.report_type='unknown'`, conclude import tracking is misclassifying (UI underreports)
- If rows truly absent for expected report types and no corresponding imports exist, conclude ingestion gap for those report types

PHASE D — Gmail straggler audit (the 12 unread from Feb 11–14)
Goal: classify the remaining unread report emails and determine if any are true missed imports.

1) Baseline batch importer status + checkpoint
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo docker exec catscan-api python /app/scripts/gmail_import_batch.py --status"
```

2) Dump checkpoint + status files
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo sh -lc 'for f in /home/catscan/.catscan/gmail_import_status.json /home/catscan/.catscan/gmail_batch_checkpoint.json; do echo ==== \$f ====; [ -f \$f ] && cat \$f || true; done'"
```

3) Tail Gmail worker log
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
"sudo tail -n 200 /home/catscan/.catscan/logs/gmail_import_worker.log 2>/dev/null || true"
```

4) If needed for classification, run one bounded batch with `--reset` ONLY if you explicitly want to reprocess checkpointed messages
- Be careful: reset changes checkpoint behavior.
- Prefer read-only classification first.

5) Correlate with screenshot subjects (Feb 11–14)
- Categories to assign:
  - already processed (checkpointed)
  - imported but tracking says unknown
  - no CSV / skipped
  - import failed
  - unsupported report kind
  - not in allowlist / skipped seat

PHASE E — BQ/raw/precompute integrity spot checks (prod, read-only)
Goal: verify the TUKY values in precompute are plausible reflections of ingested raw data, not corruption.

1) Raw table coverage in Postgres for TUKY and dates
Run:
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); out={}; tables=[(\"rtb_daily\",\"buyer_account_id\"),(\"rtb_bidstream\",\"buyer_account_id\"),(\"rtb_bid_filtering\",\"buyer_account_id\"),(\"rtb_quality\",\"buyer_account_id\")];\
for t,c in tables:\
  try:\
    cur.execute(f\"SELECT metric_date, COUNT(*) FROM {t} WHERE {c}=%s AND metric_date BETWEEN %s AND %s GROUP BY metric_date ORDER BY metric_date\", (\"299038253\",\"2026-02-18\",\"2026-02-24\")); out[t]=cur.fetchall()\
  except Exception as e:\
    out[t]=str(e)\
print(json.dumps(out, default=str))"'
```

2) (If easy) Compare `home_seat_daily` sums to `rtb_publisher_daily` for same dates (sanity check no large divergence)
```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap -- \
'sudo docker exec catscan-api python -c "import os, psycopg, json; conn=psycopg.connect(os.environ[\"POSTGRES_DSN\"]); cur=conn.cursor(); cur.execute(\"SELECT metric_date, SUM(reached_queries), SUM(impressions) FROM rtb_publisher_daily WHERE buyer_account_id=%s AND metric_date BETWEEN %s AND %s GROUP BY metric_date ORDER BY metric_date\", (\"299038253\",\"2026-02-18\",\"2026-02-24\")); print(json.dumps(cur.fetchall(), default=str))"'
```

PHASE F — Code-path audit (local repo; no prod changes)
Inspect and confirm likely bugs with file references:
1) `scripts/gmail_import.py`
- `download_from_url()` renames to generic `catscan-report-<seat>-<timestamp>.csv`
- `record_import_run()` receives `report_kind = detect_report_kind(filepath.name)`
- `detect_report_kind()` only detects canonical kinds from filename tokens
Question: does this cause `report_type='unknown'` for GCS-downloaded reports? (likely yes)

2) `scripts/gmail_import_batch.py`
- Message loop marks as read + checkpointed at message granularity
- If a message has multiple CSVs and one import fails, check whether successful + failed mixed outcomes still mark message read and processed (potential loss/retry bug)
- Note the known `CatscanImportResult` tuple-unpack mismatch if still present in deployed script

3) Home endpoint observed QPS path
- `storage/postgres_repositories/endpoints_repo.py::refresh_endpoints_current()`
- Confirm the formula is:
  `SUM(reached_queries) / DISTINCT_DAYS / 86400`, distributed by endpoint `maximum_qps`
- This should explain screenshot 4.5 / 13.6 / 22.7 if seat average reached/day is ~3.5M

Required output format (strict)
Return a structured summary with these sections:

1. **Findings (Evidence-backed)**
- Bullet list, severity-ordered
- Include file/line refs for code issues
- Include prod query outputs summarized with key numbers

2. **TUKY Numeric Reconciliation**
- CSV daily reached/impressions summary
- `home_seat_daily` daily summary
- Derived average seat QPS
- `rtb_endpoints_current` sum/current endpoint values
- Conclusion: corruption vs unit mismatch

3. **Import Tracking Audit**
- Which CSV types truly imported vs shown in UI
- Whether `unknown` report types explain missing matrix cells
- TUKY specific evidence (`ingestion_runs`, `import_history`)

4. **Unread Straggler Classification (12 emails)**
- Count by category
- Which ones, if any, are true missed imports

5. **Root Causes**
- Separate “tracking/observability bug” from “data correctness bug” from “UX labeling confusion”

6. **Fix Plan (ranked)**
- Smallest high-impact fixes first
- Include exact files/functions to patch
- Mention whether data backfill/repair is needed (e.g., reclassify `ingestion_runs.report_type`)

7. **Residual Risks**
- What remains unproven after this audit

Documentation
- Create a review note in `docs/review/2026-02-25/audit/`, e.g.:
  `TUKY_IMPORT_PIPELINE_RCA.md`
- Put the raw command list + summarized outputs there.

Do not make code changes yet unless you find a one-line obvious safety fix and call it out separately.
This pass is primarily RCA + evidence collection.
```
