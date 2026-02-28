# Conversion Connectors Setup Guide

**Last updated:** 2026-02-28  
**Scope:** AppsFlyer, Adjust, Branch, generic postback, and CSV upload ingestion for Cat-Scan v1.

## 1. Endpoint Map

Use these API routes for inbound conversion events:

- `POST /conversions/appsflyer/postback`
- `POST /conversions/adjust/callback`
- `POST /conversions/branch/webhook`
- `POST /conversions/generic/postback`
- `POST /conversions/csv/upload`

Optional query/form override:

- `buyer_id=<seat_id>` can be passed for provider endpoints and CSV uploads when payloads do not include buyer seat identifiers.

## 2. Security Controls

Configure at least one of the secret mechanisms before exposing endpoints publicly.

### 2.1 Shared or provider secret (recommended baseline)

- Shared:
  - `CATSCAN_CONVERSIONS_SHARED_SECRET`
- Provider-specific overrides:
  - `CATSCAN_APPSFLYER_WEBHOOK_SECRET`
  - `CATSCAN_ADJUST_WEBHOOK_SECRET`
  - `CATSCAN_BRANCH_WEBHOOK_SECRET`
  - `CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET`

Accepted secret carriers:

- Header: `X-Webhook-Secret`, `X-Provider-Secret`, `X-Signature`
- Header bearer token: `Authorization: Bearer <secret>`
- Query/body: `secret`, `token`, `signature`

### 2.2 Optional HMAC verification

- Shared:
  - `CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET`
- Provider-specific overrides:
  - `CATSCAN_APPSFLYER_WEBHOOK_HMAC_SECRET`
  - `CATSCAN_ADJUST_WEBHOOK_HMAC_SECRET`
  - `CATSCAN_BRANCH_WEBHOOK_HMAC_SECRET`
  - `CATSCAN_GENERIC_CONVERSION_WEBHOOK_HMAC_SECRET`

Supported signature headers:

- `X-Webhook-Signature`
- `X-Signature`
- `X-Hub-Signature-256`

### 2.3 Optional replay/freshness enforcement

- `CATSCAN_CONVERSIONS_ENFORCE_FRESHNESS=1`
- `CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS=900`

### 2.4 Optional ingress rate limiting

- `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_ENABLED=1`
- `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_PER_MINUTE=240`
- `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS=60`

## 3. Provider Payload Mapping Notes

Cat-Scan normalizes common provider fields automatically.

### 3.1 AppsFlyer

- `eventName` -> `event_name`
- `eventTime` -> `event_ts`
- `af_sub1` -> `buyer_id`
- `af_sub2` -> `billing_id`
- `af_click_id` -> `click_id`
- `af_impression_id` -> `impression_id`
- `country_code` -> `country`

Example:

```bash
curl -sS -X POST "https://<host>/api/conversions/appsflyer/postback" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${CATSCAN_APPSFLYER_WEBHOOK_SECRET}" \
  -d '{
    "eventName":"af_first_deposit",
    "eventTime":"2026-02-28T12:34:56Z",
    "eventValue":"{\"af_revenue\":\"42.5\",\"af_currency\":\"usd\"}",
    "af_sub1":"1111111111",
    "af_sub2":"cfg-100",
    "af_click_id":"af-click-1",
    "af_impression_id":"imp-1",
    "campaign":"campaign-alpha",
    "country_code":"US",
    "platform":"android"
  }'
```

### 3.2 Adjust

- `event_token` -> `event_name`
- `created_at` -> `event_ts`
- `click_time` -> `click_ts`
- `campaign_name` -> `campaign_id`
- `tracker_token` -> `click_id`
- `revenue` -> `event_value`
- `os_name` -> `platform`
- `app_token` -> `app_id`

Example:

```bash
curl -sS -X POST "https://<host>/api/conversions/adjust/callback?buyer_id=1111111111" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${CATSCAN_ADJUST_WEBHOOK_SECRET}" \
  -d '{
    "event_token":"first_deposit",
    "created_at":"2026-02-28T13:00:00Z",
    "click_time":"2026-02-28T12:50:00Z",
    "campaign_name":"campaign-beta",
    "tracker_token":"trk-1",
    "revenue":"15.75",
    "currency":"eur",
    "os_name":"ios",
    "app_token":"com.example.adjust"
  }'
```

### 3.3 Branch

- `name` -> `event_name`
- `timestamp` -> `event_ts`
- `~campaign` -> `campaign_id`
- `~id` -> `click_id`
- `revenue` -> `event_value`
- `os` -> `platform`

Example:

```bash
curl -sS -X POST "https://<host>/api/conversions/branch/webhook?buyer_id=1111111111" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${CATSCAN_BRANCH_WEBHOOK_SECRET}" \
  -d '{
    "name":"first_purchase",
    "timestamp":"2026-02-28T14:00:00Z",
    "~campaign":"campaign-gamma",
    "~id":"branch-click-7",
    "revenue":9.99,
    "currency":"USD",
    "os":"android",
    "app_id":"com.example.branch"
  }'
```

### 3.4 Generic postback

Generic route accepts arbitrary JSON and normalizes standard keys where present. Prefer sending:

- `source_type` (for source segmentation)
- `buyer_id`
- `billing_id`
- `event_name` and/or `event_type`
- `event_ts`
- `event_value`, `currency`

Example:

```bash
curl -sS -X POST "https://<host>/api/conversions/generic/postback" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET}" \
  -d '{
    "source_type":"redtrack",
    "buyer_id":"1111111111",
    "billing_id":"cfg-200",
    "event_name":"purchase",
    "event_ts":"2026-02-28T15:00:00Z",
    "event_value":"29.99",
    "currency":"USD",
    "click_id":"clk-200"
  }'
```

### 3.5 CSV upload

Endpoint:

- `POST /conversions/csv/upload` (`multipart/form-data`)

Form fields:

- `file` (required)
- `source_type` (optional, defaults to `manual_csv`)
- `buyer_id` (optional)

Example:

```bash
curl -sS -X POST "https://<host>/api/conversions/csv/upload" \
  -F "file=@/tmp/conversions.csv" \
  -F "source_type=manual_csv" \
  -F "buyer_id=1111111111"
```

## 4. Post-Setup Validation Checklist

After enabling a connector, run:

1. `GET /conversions/health?buyer_id=<buyer_id>`
2. `GET /conversions/ingestion/stats?buyer_id=<buyer_id>&days=7`
3. `GET /conversions/ingestion/error-taxonomy?buyer_id=<buyer_id>&days=7`
4. `GET /conversions/ingestion/failures?buyer_id=<buyer_id>&status=pending`

If failures appear, use DLQ actions:

1. Replay: `POST /conversions/ingestion/failures/{failure_id}/replay`
2. Discard: `POST /conversions/ingestion/failures/{failure_id}/discard`

## 5. Minimum Production Readiness Standard

Declare a connector production-ready only when:

1. Secret validation is enabled (`*_WEBHOOK_SECRET` or shared secret).
2. At least one end-to-end postback is accepted with expected `buyer_id`/`event_type`.
3. Error taxonomy has no unresolved high-volume parsing/auth failures.
4. Health endpoint does not show stale ingestion for the active buyer.
