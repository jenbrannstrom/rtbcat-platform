# Creative Audit Agent Skill

Use this skill for Cat-Scan agents that generate buyer-specific reports about
creative language/country mismatch and campaign or creative inefficiency.

## Boundaries

- Query `agent_read` views for analysis.
- Call Cat-Scan APIs for refreshes and scans.
- Never write directly to Postgres tables.
- Never query raw `public` tables unless an operator explicitly grants and asks
  for internal debugging.
- Always include `buyer_id` in API calls when the agent is buyer-scoped.
- Do not report another buyer's rows in a client report.

## Main SQL Views

Use these views first:

```sql
SELECT * FROM agent_read.accessible_buyers;
SELECT * FROM agent_read.buyer_daily_report_summary;
SELECT * FROM agent_read.creative_scan_queue;
SELECT * FROM agent_read.creative_language_country_signals;
SELECT * FROM agent_read.creative_performance_issues;
```

## Report Workflow

1. Confirm the visible buyer:

   ```sql
   SELECT buyer_id, display_name, last_synced
   FROM agent_read.accessible_buyers;
   ```

2. Check report readiness:

   ```sql
   SELECT *
   FROM agent_read.buyer_daily_report_summary
   WHERE buyer_id = 'BUYER_ID';
   ```

3. Find stale or missing scans:

   ```sql
   SELECT creative_id, creative_name, recommended_action, spend_30d_micros
   FROM agent_read.creative_scan_queue
   WHERE buyer_id = 'BUYER_ID'
   ORDER BY spend_30d_micros DESC
   LIMIT 100;
   ```

4. If scan coverage is poor, call:

   ```text
   POST /api/creatives/language-flag-coverage/refresh?buyer_id=BUYER_ID&refresh_limit=500&force=true&days=7
   ```

5. Pull mismatch candidates:

   ```sql
   SELECT
       creative_id,
       creative_name,
       detected_language_code,
       serving_countries_7d,
       geo_linguistic_status,
       geo_linguistic_decision,
       geo_linguistic_risk_score,
       spend_30d_micros,
       impressions_30d,
       geo_findings
   FROM agent_read.creative_language_country_signals
   WHERE buyer_id = 'BUYER_ID'
     AND geo_linguistic_status IN ('red', 'orange')
   ORDER BY geo_linguistic_status DESC, spend_30d_micros DESC
   LIMIT 200;
   ```

6. Pull performance issues:

   ```sql
   SELECT *
   FROM agent_read.creative_performance_issues
   WHERE buyer_id = 'BUYER_ID'
   ORDER BY spend_30d_micros DESC
   LIMIT 100;
   ```

7. Produce a concise client report with:

   - executive summary
   - mismatch count and spend affected
   - top creative issues with evidence
   - recommended next actions
   - data freshness notes

## Refresh Rules

Use refreshes only when needed:

- If latest metric dates are stale, trigger precompute refresh through the
  scheduler-secret endpoint.
- If creative payloads are stale, trigger creative cache refresh through the
  scheduler-secret endpoint.
- If language/geo scan coverage is missing or stale, call the
  language-flag refresh endpoint as the buyer-scoped app user.

## Forbidden Actions

- Do not edit pretargeting unless explicitly asked and authenticated as a
  seat-admin or sudo user.
- Do not delete creatives, assign clusters, or override detected language in a
  read-only report workflow.
- Do not include raw URLs, secrets, cookies, or credentials in client reports.
- Do not infer final recommendations when scan status is missing; request or
  trigger scans first.
