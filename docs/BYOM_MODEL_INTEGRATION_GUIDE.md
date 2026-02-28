# BYOM Model Integration Guide

**Last updated:** 2026-02-28  
**Scope:** Registering, validating, and running external scoring models for Cat-Scan optimizer v1.

## 1. BYOM Contract Summary

Cat-Scan supports `model_type=api` for external model scoring.

High-level flow:

1. Register model metadata in Cat-Scan (`POST /optimizer/models`).
2. Validate endpoint contract (`POST /optimizer/models/{model_id}/validate`).
3. Run scoring (`POST /optimizer/scoring/run`).
4. Generate/apply proposals (`POST /optimizer/proposals/generate` or `POST /optimizer/workflows/score-and-propose`).

## 2. Register a Model

Endpoint:

- `POST /optimizer/models`

Minimum request for external API model:

```json
{
  "buyer_id": "1111111111",
  "name": "customer-external-model-v1",
  "model_type": "api",
  "endpoint_url": "https://model.example.com/score",
  "auth_header_encrypted": "Bearer <token>",
  "input_schema": {
    "type": "object",
    "required": ["features"]
  },
  "output_schema": {
    "type": "object",
    "required": ["scores"]
  },
  "is_active": true
}
```

Notes:

- `endpoint_url` is required for `model_type=api`.
- `auth_header_encrypted` is stored encrypted-at-rest when `CATSCAN_OPTIMIZER_MODEL_SECRET_KEY` is configured; otherwise it falls back to plaintext compatibility mode.
- Supported model types are `api`, `rules`, `csv`.

## 3. External Scoring Endpoint Contract

Cat-Scan sends `POST` JSON payload:

```json
{
  "model_id": "mdl_...",
  "buyer_id": "1111111111",
  "event_type": "purchase",
  "start_date": "2026-02-15",
  "end_date": "2026-02-28",
  "features": [
    {
      "feature_id": "cfg-1|US|pub-1|com.app|2026-02-28",
      "score_date": "2026-02-28",
      "billing_id": "cfg-1",
      "country": "US",
      "publisher_id": "pub-1",
      "app_id": "com.app",
      "event_count": 12,
      "impressions": 14000,
      "clicks": 210,
      "spend_usd": 88.4,
      "event_value_total": 220.0,
      "event_rate": 0.000857,
      "cost_per_event": 7.37,
      "roas": 2.49
    }
  ]
}
```

Expected response:

```json
{
  "scores": [
    {
      "feature_id": "cfg-1|US|pub-1|com.app|2026-02-28",
      "value_score": 0.82,
      "confidence": 0.74,
      "reason_codes": ["strong_roas", "stable_volume"]
    }
  ]
}
```

Accepted score output fields:

- Required:
  - `scores` (array)
- Recommended per score item:
  - `feature_id` (if omitted, Cat-Scan falls back to same index mapping)
  - `value_score` (0..1; Cat-Scan clamps outside range)
  - `confidence` (0..1; Cat-Scan clamps outside range)
  - `reason_codes` (string array)
- Optional enrichment fields passed through to stored score row:
  - `creative_size`, `platform`, `environment`, `hour`

## 4. Validate Before Running

Endpoint:

- `POST /optimizer/models/{model_id}/validate?buyer_id=<buyer_id>&timeout_seconds=10`

Validation passes when endpoint returns:

1. JSON object with `scores` array, or
2. JSON object with `{"ok": true}` for ping-style health.

## 5. Run Scoring and Proposals

### 5.1 Scoring only

- `POST /optimizer/scoring/run?model_id=<model_id>&buyer_id=<buyer_id>&days=14&limit=1000`

### 5.2 One-shot workflow (recommended)

- `POST /optimizer/workflows/score-and-propose?model_id=<model_id>&buyer_id=<buyer_id>&days=14&score_limit=1000&min_confidence=0.3&max_delta_pct=0.3&proposal_limit=200`

Then review/approve/apply:

1. `GET /optimizer/proposals?buyer_id=<buyer_id>&status=draft`
2. `POST /optimizer/proposals/{proposal_id}/approve?buyer_id=<buyer_id>`
3. `POST /optimizer/proposals/{proposal_id}/apply?buyer_id=<buyer_id>&mode=queue`
4. `POST /optimizer/proposals/{proposal_id}/sync-apply-status?buyer_id=<buyer_id>`

## 6. Failure Handling Checklist

When external model scoring fails:

1. Run validate endpoint and inspect `response_preview`.
2. Confirm endpoint returns JSON object (not plaintext/html).
3. Confirm response includes `scores` list.
4. Confirm auth header value is still valid.
5. Fallback to `rules` model for continuity.

## 7. Security and Operational Recommendations

1. Always configure `CATSCAN_OPTIMIZER_MODEL_SECRET_KEY` in production.
2. Use short-lived model API credentials and rotate regularly.
3. Keep human approval enabled (no auto-apply in v1).
4. Start with queue mode applies before live mode.
