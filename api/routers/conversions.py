"""Conversion aggregates and health endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel

from api.dependencies import (
    get_current_user,
    get_store,
    is_sudo,
    require_buyer_admin_access,
    resolve_buyer_id,
)
from services.auth_service import User
from services.conversion_ingestion_service import ConversionIngestionService
from services.conversion_normalizers import (
    normalize_adjust_payload,
    normalize_appsflyer_payload,
    normalize_branch_payload,
    normalize_generic_payload,
)
from services.conversion_readiness import compute_conversion_readiness_payload
from services.conversions_service import ConversionsService

router = APIRouter(prefix="/conversions", tags=["Conversions"])


class ConversionAggregateRow(BaseModel):
    agg_date: Optional[str] = None
    buyer_id: str
    billing_id: str
    country: str
    publisher_id: str
    creative_id: str
    app_id: str
    source_type: str
    event_type: str
    event_count: int
    event_value_total: float
    impressions: int
    clicks: int
    spend_usd: float
    cost_per_event: Optional[float] = None
    event_rate_pct: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversionAggregatesMeta(BaseModel):
    start_date: str
    end_date: str
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class ConversionAggregatesResponse(BaseModel):
    rows: list[ConversionAggregateRow]
    meta: ConversionAggregatesMeta


class ConversionRefreshResponse(BaseModel):
    start_date: str
    end_date: str
    buyer_id: Optional[str] = None
    deleted_rows: int
    upserted_rows: int


class ConversionIngestionHealth(BaseModel):
    total_events: int
    max_event_ts: Optional[str] = None
    last_ingested_at: Optional[str] = None
    lag_hours: Optional[float] = None


class ConversionAggregationHealth(BaseModel):
    total_rows: int
    max_agg_date: Optional[str] = None
    last_aggregated_at: Optional[str] = None
    lag_days: Optional[int] = None


class ConversionHealthResponse(BaseModel):
    state: str
    buyer_id: Optional[str] = None
    ingestion: ConversionIngestionHealth
    aggregation: ConversionAggregationHealth
    checked_at: str


class ConversionReadinessResponse(BaseModel):
    state: str
    buyer_id: Optional[str] = None
    window_days: int
    freshness_threshold_hours: int
    accepted_total: int
    rejected_total: int
    active_sources: int
    ingestion_lag_hours: Optional[float] = None
    ingestion_fresh: bool
    reasons: list[str]
    checked_at: str


class ConversionWebhookSecuritySourceStatus(BaseModel):
    source_type: str
    secret_enabled: bool
    secret_values_configured: int
    using_shared_secret: bool
    hmac_enabled: bool
    hmac_values_configured: int
    using_shared_hmac: bool


class ConversionWebhookSecurityStatusResponse(BaseModel):
    shared_secret_enabled: bool
    shared_secret_values_configured: int
    shared_hmac_enabled: bool
    shared_hmac_values_configured: int
    sources: list[ConversionWebhookSecuritySourceStatus]
    freshness_enforced: bool
    max_skew_seconds: int
    rate_limit_enabled: bool
    rate_limit_per_window: int
    rate_limit_window_seconds: int
    checked_at: str


class ConversionFieldMappingProfileResponse(BaseModel):
    source_type: str
    buyer_id: Optional[str] = None
    scope: str
    field_map: dict[str, list[str]]
    setting_key: Optional[str] = None
    fallback_setting_key: Optional[str] = None


class ConversionFieldMappingProfileUpsertRequest(BaseModel):
    source_type: str = "appsflyer"
    buyer_id: Optional[str] = None
    field_map: dict[str, str | list[str]]


class ConversionIngestResponse(BaseModel):
    accepted: bool
    duplicate: bool
    source_type: str
    event_id: str
    event_type: str
    buyer_id: str
    event_ts: str
    import_batch_id: str


class ConversionCSVIngestResponse(BaseModel):
    accepted: bool
    source_type: str
    import_batch_id: str
    rows_read: int
    rows_inserted: int
    rows_duplicate: int
    rows_skipped: int
    errors: list[str]


class ConversionIngestionFailureRow(BaseModel):
    id: int
    source_type: str
    buyer_id: Optional[str] = None
    endpoint_path: Optional[str] = None
    error_code: str
    error_message: str
    payload: dict
    request_headers: dict
    idempotency_key: Optional[str] = None
    status: str
    replay_attempts: int
    last_replayed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversionIngestionFailuresMeta(BaseModel):
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class ConversionIngestionFailuresResponse(BaseModel):
    rows: list[ConversionIngestionFailureRow]
    meta: ConversionIngestionFailuresMeta


class ConversionReplayFailureResponse(BaseModel):
    failure_id: int
    status: str
    result: ConversionIngestResponse


class ConversionDiscardFailureResponse(BaseModel):
    failure_id: int
    discarded: bool


class ConversionIngestionStatsRow(BaseModel):
    metric_date: Optional[str] = None
    source_type: str
    accepted_count: int
    rejected_count: int


class ConversionIngestionStatsResponse(BaseModel):
    days: int
    source_type: Optional[str] = None
    buyer_id: Optional[str] = None
    accepted_total: int
    rejected_total: int
    rows: list[ConversionIngestionStatsRow]


class ConversionFailureTaxonomyRow(BaseModel):
    error_code: str
    failure_count: int
    last_seen_at: Optional[str] = None
    sample_error_message: str


class ConversionFailureTaxonomyResponse(BaseModel):
    days: int
    source_type: Optional[str] = None
    buyer_id: Optional[str] = None
    total_failures: int
    other_count: int
    rows: list[ConversionFailureTaxonomyRow]


_SECRET_ENV_BY_SOURCE = {
    "appsflyer": "CATSCAN_APPSFLYER_WEBHOOK_SECRET",
    "adjust": "CATSCAN_ADJUST_WEBHOOK_SECRET",
    "branch": "CATSCAN_BRANCH_WEBHOOK_SECRET",
    "generic": "CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET",
}
_HMAC_SECRET_ENV_BY_SOURCE = {
    "appsflyer": "CATSCAN_APPSFLYER_WEBHOOK_HMAC_SECRET",
    "adjust": "CATSCAN_ADJUST_WEBHOOK_HMAC_SECRET",
    "branch": "CATSCAN_BRANCH_WEBHOOK_HMAC_SECRET",
    "generic": "CATSCAN_GENERIC_CONVERSION_WEBHOOK_HMAC_SECRET",
}

_WEBHOOK_RATE_LIMIT_STATE: dict[str, deque[int]] = {}
_WEBHOOK_RATE_LIMIT_LOCK = Lock()
_PIXEL_GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)

_SUPPORTED_MAPPING_PROFILE_SOURCES = {"appsflyer"}


def _mapping_profile_setting_key(source_type: str, buyer_id: Optional[str]) -> str:
    if buyer_id:
        return f"conversion_mapping_profile:{source_type}:buyer:{buyer_id}"
    return f"conversion_mapping_profile:{source_type}:default"


async def _load_field_mapping_profile(
    *,
    store,
    source_type: str,
    buyer_id: Optional[str],
) -> tuple[dict[str, list[str]], str, Optional[str], Optional[str]]:
    """Load buyer/default field mapping profile for a source type."""
    if source_type != "appsflyer":
        return {}, "unsupported_source", None, None

    primary_key = _mapping_profile_setting_key(source_type, buyer_id)
    fallback_key = _mapping_profile_setting_key(source_type, None)
    raw_value: Optional[str] = None
    setting_key: Optional[str] = None
    scope = "builtin_default"

    getter = getattr(store, "get_setting", None)
    if callable(getter):
        if buyer_id:
            raw_value = await getter(primary_key)
            if raw_value:
                scope = "buyer"
                setting_key = primary_key
        if not raw_value:
            raw_value = await getter(fallback_key)
            if raw_value:
                scope = "default"
                setting_key = fallback_key

    if not raw_value:
        return {}, scope, setting_key, (fallback_key if buyer_id else None)

    parsed: dict[str, Any]
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}, "invalid_profile_json", setting_key, (fallback_key if buyer_id else None)

    raw_field_map: dict[str, Any]
    if isinstance(parsed, dict) and isinstance(parsed.get("field_map"), dict):
        raw_field_map = parsed["field_map"]
    elif isinstance(parsed, dict):
        raw_field_map = parsed
    else:
        return {}, "invalid_profile_shape", setting_key, (fallback_key if buyer_id else None)

    normalized: dict[str, list[str]] = {}
    for canonical_key, sources in raw_field_map.items():
        if isinstance(sources, str):
            source_list = [sources]
        elif isinstance(sources, list):
            source_list = [str(item) for item in sources if item]
        else:
            continue
        cleaned: list[str] = []
        for source_field in source_list:
            field_name = source_field.strip()
            if not field_name or field_name in cleaned:
                continue
            cleaned.append(field_name)
        if cleaned:
            normalized[str(canonical_key)] = cleaned
    return normalized, scope, setting_key, (fallback_key if buyer_id else None)


def _extract_auth_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _clear_webhook_rate_limit_state() -> None:
    with _WEBHOOK_RATE_LIMIT_LOCK:
        _WEBHOOK_RATE_LIMIT_STATE.clear()


def _parse_env_secret_list(env_name: str) -> list[str]:
    raw = os.getenv(env_name, "")
    if not raw:
        return []
    # Allow rotation windows with multiple active secrets in one env value.
    candidates = raw.replace("\n", ",").replace(";", ",").split(",")
    secrets_list: list[str] = []
    for candidate in candidates:
        token = candidate.strip()
        if token and token not in secrets_list:
            secrets_list.append(token)
    return secrets_list


def _env_flag(env_name: str) -> bool:
    return os.getenv(env_name, "").strip().lower() in {"1", "true", "yes", "on"}


def _webhook_security_status_payload() -> dict:
    shared_secret_values = _parse_env_secret_list("CATSCAN_CONVERSIONS_SHARED_SECRET")
    shared_hmac_values = _parse_env_secret_list("CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET")

    sources: list[dict] = []
    for source_type in sorted(_SECRET_ENV_BY_SOURCE.keys()):
        source_secret_env = _SECRET_ENV_BY_SOURCE.get(source_type, "")
        source_hmac_env = _HMAC_SECRET_ENV_BY_SOURCE.get(source_type, "")
        source_secret_values = _parse_env_secret_list(source_secret_env) if source_secret_env else []
        source_hmac_values = _parse_env_secret_list(source_hmac_env) if source_hmac_env else []

        using_shared_secret = not source_secret_values and bool(shared_secret_values)
        using_shared_hmac = not source_hmac_values and bool(shared_hmac_values)

        effective_secret_values = source_secret_values or shared_secret_values
        effective_hmac_values = source_hmac_values or shared_hmac_values

        sources.append(
            {
                "source_type": source_type,
                "secret_enabled": bool(effective_secret_values),
                "secret_values_configured": len(effective_secret_values),
                "using_shared_secret": using_shared_secret,
                "hmac_enabled": bool(effective_hmac_values),
                "hmac_values_configured": len(effective_hmac_values),
                "using_shared_hmac": using_shared_hmac,
            }
        )

    max_skew_seconds = max(1, int(os.getenv("CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS", "900") or "900"))
    rate_limit_per_window = max(
        1,
        int(os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_PER_MINUTE", "240") or "240"),
    )
    rate_limit_window_seconds = max(
        1,
        int(os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", "60") or "60"),
    )
    return {
        "shared_secret_enabled": bool(shared_secret_values),
        "shared_secret_values_configured": len(shared_secret_values),
        "shared_hmac_enabled": bool(shared_hmac_values),
        "shared_hmac_values_configured": len(shared_hmac_values),
        "sources": sources,
        "freshness_enforced": _env_flag("CATSCAN_CONVERSIONS_ENFORCE_FRESHNESS"),
        "max_skew_seconds": max_skew_seconds,
        "rate_limit_enabled": _env_flag("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_ENABLED"),
        "rate_limit_per_window": rate_limit_per_window,
        "rate_limit_window_seconds": rate_limit_window_seconds,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _get_expected_webhook_secrets(source_type: str) -> list[str]:
    source_env = _SECRET_ENV_BY_SOURCE.get(source_type, "")
    source_secrets = _parse_env_secret_list(source_env) if source_env else []
    if source_secrets:
        return source_secrets
    return _parse_env_secret_list("CATSCAN_CONVERSIONS_SHARED_SECRET")


def _get_expected_hmac_secrets(source_type: str) -> list[str]:
    source_env = _HMAC_SECRET_ENV_BY_SOURCE.get(source_type, "")
    source_secrets = _parse_env_secret_list(source_env) if source_env else []
    if source_secrets:
        return source_secrets
    return _parse_env_secret_list("CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET")


def _canonical_payload(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _current_unix_ts() -> int:
    return int(time.time())


def _extract_signature_candidates(request: Request, payload: dict) -> list[str]:
    return [
        request.headers.get("X-Webhook-Signature", ""),
        request.headers.get("X-Signature", ""),
        request.headers.get("X-Hub-Signature-256", ""),
        str(payload.get("signature", "")).strip(),
    ]


def _extract_signature_hexes(raw_signature: str) -> list[str]:
    value = str(raw_signature or "").strip()
    if not value:
        return []
    lowered = value.lower()
    if lowered.startswith("sha256="):
        return [value.split("=", 1)[1].strip()]
    if "v1=" in value:
        parts = [part.strip() for part in value.split(",")]
        for part in parts:
            if part.startswith("v1="):
                return [part.split("=", 1)[1].strip()]
    return [value]


def _parse_unix_timestamp(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def _extract_request_timestamp(request: Request, payload: dict) -> Optional[int]:
    candidates: list[object] = [
        request.headers.get("X-Webhook-Timestamp"),
        request.headers.get("X-Timestamp"),
        request.query_params.get("timestamp"),
        request.query_params.get("ts"),
        payload.get("timestamp"),
        payload.get("event_ts"),
        payload.get("eventTime"),
        payload.get("created_at"),
    ]
    for candidate in candidates:
        ts = _parse_unix_timestamp(candidate)
        if ts is not None:
            return ts
    return None


def _verify_webhook_secret(source_type: str, request: Request, payload: dict) -> None:
    """Optional per-provider/shared secret check for inbound conversion webhooks."""
    expected_secrets = _get_expected_webhook_secrets(source_type)
    if not expected_secrets:
        return

    candidates = [
        request.headers.get("X-Webhook-Secret", ""),
        request.headers.get("X-Provider-Secret", ""),
        request.headers.get("X-Signature", ""),
        _extract_auth_bearer_token(request) or "",
        str(request.query_params.get("secret", "")).strip(),
        str(payload.get("secret", "")).strip(),
        str(payload.get("token", "")).strip(),
        str(payload.get("signature", "")).strip(),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        if any(
            secrets.compare_digest(candidate, expected_secret)
            for expected_secret in expected_secrets
        ):
            return

    raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")


def _verify_webhook_signature(source_type: str, request: Request, payload: dict) -> None:
    """Optional HMAC verification with freshness gate for replay protection."""
    secrets_list = _get_expected_hmac_secrets(source_type)
    if not secrets_list:
        return

    message = _canonical_payload(payload)
    timestamp = _extract_request_timestamp(request, payload)
    candidates = _extract_signature_candidates(request, payload)
    if not candidates:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    digests: list[str] = []
    timestamp_message = f"{timestamp}.{message}" if timestamp is not None else None
    for secret in secrets_list:
        digests.append(
            hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        )
        if timestamp_message is not None:
            digests.append(
                hmac.new(
                    secret.encode("utf-8"),
                    timestamp_message.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            )

    for raw_signature in candidates:
        for candidate_hex in _extract_signature_hexes(raw_signature):
            if any(secrets.compare_digest(candidate_hex, digest) for digest in digests):
                break
        else:
            continue
        break
    else:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    enforce_freshness = os.getenv("CATSCAN_CONVERSIONS_ENFORCE_FRESHNESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enforce_freshness:
        return

    if timestamp is None:
        raise HTTPException(status_code=401, detail="Missing webhook timestamp")

    max_skew = int(os.getenv("CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS", "900") or "900")
    now = _current_unix_ts()
    if abs(now - timestamp) > max_skew:
        raise HTTPException(status_code=401, detail="Webhook timestamp outside allowed skew")


def _extract_request_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_webhook_rate_limit(source_type: str, request: Request) -> None:
    enabled = os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return

    limit = int(os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_PER_MINUTE", "240") or "240")
    window_seconds = int(os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", "60") or "60")
    limit = max(1, limit)
    window_seconds = max(1, window_seconds)
    now = _current_unix_ts()
    client_key = _extract_request_client_key(request)
    bucket_key = f"{source_type}:{client_key}"

    with _WEBHOOK_RATE_LIMIT_LOCK:
        bucket = _WEBHOOK_RATE_LIMIT_STATE.setdefault(bucket_key, deque())
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Webhook rate limit exceeded; retry later",
            )

        bucket.append(now)


async def _parse_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON payload must be an object")
        return payload

    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form = await request.form()
        if form:
            return {str(k): form[k] for k in form.keys()}

    query_payload = {str(k): v for k, v in request.query_params.items() if k not in {"buyer_id", "secret"}}
    if query_payload:
        return query_payload

    # Last attempt: maybe content-type missing but body is JSON.
    try:
        payload = await request.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        return payload

    raise HTTPException(status_code=400, detail="Unsupported or empty payload format")


def _safe_request_headers(request: Request) -> dict[str, str]:
    keep = {
        "user-agent",
        "content-type",
        "x-request-id",
        "x-forwarded-for",
        "x-forwarded-proto",
    }
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() in keep and value
    }


def _pixel_response(*, ingest_status: str) -> Response:
    return Response(
        content=_PIXEL_GIF_BYTES,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-CatScan-Conversion-Status": ingest_status,
        },
    )


async def _ingest_with_dlq(
    *,
    request: Request,
    source_type: str,
    payload: dict,
    buyer_id: Optional[str],
) -> ConversionIngestResponse:
    service = ConversionIngestionService()
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        result = await service.ingest_provider_payload(
            source_type=source_type,
            payload=payload,
            buyer_id_override=buyer_id,
            idempotency_key=idempotency_key,
        )
        return ConversionIngestResponse(**result)
    except Exception as exc:
        failure_id = await service.record_failure(
            source_type=source_type,
            payload=payload,
            error_code="ingestion_error",
            error_message=str(exc),
            buyer_id=buyer_id,
            endpoint_path=request.url.path,
            idempotency_key=idempotency_key,
            headers=_safe_request_headers(request),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Conversion ingestion failed: {exc}",
                "failure_id": failure_id,
            },
        ) from exc


async def _ingest_generic_family_postback(
    *,
    request: Request,
    buyer_id: Optional[str],
    default_source_type: str,
) -> ConversionIngestResponse:
    payload = await _parse_payload(request)
    payload = normalize_generic_payload(payload)
    _verify_webhook_secret("generic", request, payload)
    _verify_webhook_signature("generic", request, payload)
    source_type = str(payload.get("source_type") or default_source_type)
    _enforce_webhook_rate_limit(source_type, request)
    return await _ingest_with_dlq(
        request=request,
        source_type=source_type,
        payload=payload,
        buyer_id=buyer_id,
    )


@router.post("/appsflyer/postback", response_model=ConversionIngestResponse)
async def ingest_appsflyer_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
    store=Depends(get_store),
):
    payload = await _parse_payload(request)
    baseline_payload = normalize_appsflyer_payload(payload)
    inferred_buyer_id = buyer_id or baseline_payload.get("buyer_id")
    field_map, _, _, _ = await _load_field_mapping_profile(
        store=store,
        source_type="appsflyer",
        buyer_id=inferred_buyer_id if isinstance(inferred_buyer_id, str) else None,
    )
    payload = normalize_appsflyer_payload(payload, field_map=field_map or None)
    _verify_webhook_secret("appsflyer", request, payload)
    _verify_webhook_signature("appsflyer", request, payload)
    _enforce_webhook_rate_limit("appsflyer", request)
    return await _ingest_with_dlq(
        request=request,
        source_type="appsflyer",
        payload=payload,
        buyer_id=buyer_id,
    )


@router.post("/adjust/callback", response_model=ConversionIngestResponse)
async def ingest_adjust_callback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_payload(request)
    payload = normalize_adjust_payload(payload)
    _verify_webhook_secret("adjust", request, payload)
    _verify_webhook_signature("adjust", request, payload)
    _enforce_webhook_rate_limit("adjust", request)
    return await _ingest_with_dlq(
        request=request,
        source_type="adjust",
        payload=payload,
        buyer_id=buyer_id,
    )


@router.post("/branch/webhook", response_model=ConversionIngestResponse)
async def ingest_branch_webhook(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_payload(request)
    payload = normalize_branch_payload(payload)
    _verify_webhook_secret("branch", request, payload)
    _verify_webhook_signature("branch", request, payload)
    _enforce_webhook_rate_limit("branch", request)
    return await _ingest_with_dlq(
        request=request,
        source_type="branch",
        payload=payload,
        buyer_id=buyer_id,
    )


@router.post("/generic/postback", response_model=ConversionIngestResponse)
async def ingest_generic_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    return await _ingest_generic_family_postback(
        request=request,
        buyer_id=buyer_id,
        default_source_type="generic",
    )


@router.post("/redtrack/postback", response_model=ConversionIngestResponse)
async def ingest_redtrack_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    return await _ingest_generic_family_postback(
        request=request,
        buyer_id=buyer_id,
        default_source_type="redtrack",
    )


@router.post("/voluum/postback", response_model=ConversionIngestResponse)
async def ingest_voluum_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    return await _ingest_generic_family_postback(
        request=request,
        buyer_id=buyer_id,
        default_source_type="voluum",
    )


@router.get("/pixel")
async def ingest_conversion_pixel(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    try:
        await _ingest_generic_family_postback(
            request=request,
            buyer_id=buyer_id,
            default_source_type="pixel",
        )
    except HTTPException:
        return _pixel_response(ingest_status="rejected")
    return _pixel_response(ingest_status="accepted")


@router.post("/csv/upload", response_model=ConversionCSVIngestResponse)
async def ingest_conversion_csv(
    file: UploadFile = File(...),
    source_type: str = Form("manual_csv"),
    buyer_id: Optional[str] = Form(None),
):
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    try:
        csv_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = raw_bytes.decode("utf-8", errors="replace")

    service = ConversionIngestionService()
    result = await service.ingest_csv(
        csv_text=csv_text,
        source_type=source_type,
        buyer_id_override=buyer_id,
    )
    return ConversionCSVIngestResponse(**result)


@router.get("/ingestion/failures", response_model=ConversionIngestionFailuresResponse)
async def list_conversion_ingestion_failures(
    source_type: Optional[str] = Query(None),
    buyer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="pending | replayed | discarded"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionIngestionService()
    payload = await service.list_failures(
        source_type=source_type,
        buyer_id=buyer_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversionIngestionFailuresResponse(**payload)


@router.post(
    "/ingestion/failures/{failure_id}/replay",
    response_model=ConversionReplayFailureResponse,
)
async def replay_conversion_ingestion_failure(
    failure_id: int,
    user: User = Depends(get_current_user),
):
    service = ConversionIngestionService()
    try:
        payload = await service.replay_failure(failure_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Replay failed for failure_id={failure_id}: {exc}",
        ) from exc
    return ConversionReplayFailureResponse(**payload)


@router.post(
    "/ingestion/failures/{failure_id}/discard",
    response_model=ConversionDiscardFailureResponse,
)
async def discard_conversion_ingestion_failure(
    failure_id: int,
    user: User = Depends(get_current_user),
):
    service = ConversionIngestionService()
    discarded = await service.discard_failure(failure_id)
    if not discarded:
        raise HTTPException(status_code=404, detail="Failure item not found")
    return ConversionDiscardFailureResponse(
        failure_id=failure_id,
        discarded=True,
    )


@router.get("/ingestion/stats", response_model=ConversionIngestionStatsResponse)
async def get_conversion_ingestion_stats(
    days: int = Query(7, ge=1, le=365),
    source_type: Optional[str] = Query(None),
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionIngestionService()
    payload = await service.get_ingestion_stats(
        days=days,
        source_type=source_type,
        buyer_id=buyer_id,
    )
    return ConversionIngestionStatsResponse(**payload)


@router.get("/ingestion/error-taxonomy", response_model=ConversionFailureTaxonomyResponse)
async def get_conversion_ingestion_error_taxonomy(
    days: int = Query(7, ge=1, le=365),
    source_type: Optional[str] = Query(None),
    buyer_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionIngestionService()
    payload = await service.get_failure_taxonomy(
        days=days,
        source_type=source_type,
        buyer_id=buyer_id,
        limit=limit,
    )
    return ConversionFailureTaxonomyResponse(**payload)


@router.get("/aggregates", response_model=ConversionAggregatesResponse)
async def get_conversion_aggregates(
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    buyer_id: Optional[str] = Query(None),
    billing_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    publisher_id: Optional[str] = Query(None),
    creative_id: Optional[str] = Query(None),
    app_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionsService()
    payload = await service.get_aggregates(
        days=days,
        start_date=start_date,
        end_date=end_date,
        buyer_id=buyer_id,
        billing_id=billing_id,
        country=country,
        publisher_id=publisher_id,
        creative_id=creative_id,
        app_id=app_id,
        source_type=source_type,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return ConversionAggregatesResponse(**payload)


@router.post("/aggregates/refresh", response_model=ConversionRefreshResponse)
async def refresh_conversion_aggregates(
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionsService()
    payload = await service.refresh_aggregates(
        days=days,
        start_date=start_date,
        end_date=end_date,
        buyer_id=buyer_id,
    )
    return ConversionRefreshResponse(**payload)


@router.get("/health", response_model=ConversionHealthResponse)
async def get_conversion_health(
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = ConversionsService()
    return ConversionHealthResponse(**await service.get_health(buyer_id=buyer_id))


@router.get("/security/status", response_model=ConversionWebhookSecurityStatusResponse)
async def get_conversion_webhook_security_status(
    user: User = Depends(get_current_user),
):
    return ConversionWebhookSecurityStatusResponse(**_webhook_security_status_payload())


@router.get("/mapping-profile", response_model=ConversionFieldMappingProfileResponse)
async def get_conversion_mapping_profile(
    source_type: str = Query("appsflyer"),
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    source_type = (source_type or "").strip().lower()
    if source_type not in _SUPPORTED_MAPPING_PROFILE_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_type '{source_type}'. Supported: {sorted(_SUPPORTED_MAPPING_PROFILE_SOURCES)}",
        )

    resolved_buyer_id = buyer_id
    if buyer_id:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

    field_map, scope, setting_key, fallback_key = await _load_field_mapping_profile(
        store=store,
        source_type=source_type,
        buyer_id=resolved_buyer_id,
    )

    return ConversionFieldMappingProfileResponse(
        source_type=source_type,
        buyer_id=resolved_buyer_id,
        scope=scope,
        field_map=field_map,
        setting_key=setting_key,
        fallback_setting_key=fallback_key,
    )


@router.put("/mapping-profile", response_model=ConversionFieldMappingProfileResponse)
async def upsert_conversion_mapping_profile(
    body: ConversionFieldMappingProfileUpsertRequest,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    source_type = (body.source_type or "").strip().lower()
    if source_type not in _SUPPORTED_MAPPING_PROFILE_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_type '{source_type}'. Supported: {sorted(_SUPPORTED_MAPPING_PROFILE_SOURCES)}",
        )

    buyer_id = body.buyer_id
    if buyer_id:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        await require_buyer_admin_access(buyer_id, user=user)
    elif not is_sudo(user):
        raise HTTPException(
            status_code=403,
            detail="Default mapping profile updates require sudo access.",
        )

    field_map: dict[str, list[str]] = {}
    for canonical_key, sources in body.field_map.items():
        source_list = [sources] if isinstance(sources, str) else list(sources or [])
        normalized_sources: list[str] = []
        for source_field in source_list:
            name = str(source_field).strip()
            if not name or name in normalized_sources:
                continue
            normalized_sources.append(name)
        if normalized_sources:
            field_map[str(canonical_key).strip()] = normalized_sources

    if not field_map:
        raise HTTPException(status_code=400, detail="field_map cannot be empty")

    key = _mapping_profile_setting_key(source_type, buyer_id)
    payload = json.dumps({"field_map": field_map}, sort_keys=True, separators=(",", ":"))
    await store.set_setting(key, payload, updated_by=getattr(user, "id", None))

    _, scope, setting_key, fallback_key = await _load_field_mapping_profile(
        store=store,
        source_type=source_type,
        buyer_id=buyer_id,
    )
    return ConversionFieldMappingProfileResponse(
        source_type=source_type,
        buyer_id=buyer_id,
        scope=scope,
        field_map=field_map,
        setting_key=setting_key,
        fallback_setting_key=fallback_key,
    )


@router.get("/readiness", response_model=ConversionReadinessResponse)
async def get_conversion_readiness(
    buyer_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    freshness_hours: int = Query(72, ge=1, le=720),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    conversions_service = ConversionsService()
    ingestion_service = ConversionIngestionService()

    health = await conversions_service.get_health(buyer_id=buyer_id)
    stats = await ingestion_service.get_ingestion_stats(
        days=days,
        source_type=None,
        buyer_id=buyer_id,
    )
    payload = compute_conversion_readiness_payload(
        health_payload=health,
        stats_payload=stats,
        buyer_id=buyer_id,
        days=days,
        freshness_hours=freshness_hours,
    )
    return ConversionReadinessResponse(**payload)
