"""Conversion aggregates and health endpoints."""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.conversion_ingestion_service import ConversionIngestionService
from services.conversion_normalizers import (
    normalize_adjust_payload,
    normalize_appsflyer_payload,
    normalize_branch_payload,
    normalize_generic_payload,
)
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


_SECRET_ENV_BY_SOURCE = {
    "appsflyer": "CATSCAN_APPSFLYER_WEBHOOK_SECRET",
    "adjust": "CATSCAN_ADJUST_WEBHOOK_SECRET",
    "branch": "CATSCAN_BRANCH_WEBHOOK_SECRET",
    "generic": "CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET",
}


def _extract_auth_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _get_expected_webhook_secret(source_type: str) -> Optional[str]:
    source_secret = os.getenv(_SECRET_ENV_BY_SOURCE.get(source_type, ""), "").strip()
    if source_secret:
        return source_secret
    shared = os.getenv("CATSCAN_CONVERSIONS_SHARED_SECRET", "").strip()
    if shared:
        return shared
    return None


def _verify_webhook_secret(source_type: str, request: Request, payload: dict) -> None:
    """Optional per-provider/shared secret check for inbound conversion webhooks."""
    expected = _get_expected_webhook_secret(source_type)
    if not expected:
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

    if any(secrets.compare_digest(candidate, expected) for candidate in candidates if candidate):
        return

    raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")


async def _parse_json_payload(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON payload must be an object")
    return payload


@router.post("/appsflyer/postback", response_model=ConversionIngestResponse)
async def ingest_appsflyer_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_json_payload(request)
    payload = normalize_appsflyer_payload(payload)
    _verify_webhook_secret("appsflyer", request, payload)
    service = ConversionIngestionService()
    result = await service.ingest_provider_payload(
        source_type="appsflyer",
        payload=payload,
        buyer_id_override=buyer_id,
        idempotency_key=request.headers.get("X-Idempotency-Key"),
    )
    return ConversionIngestResponse(**result)


@router.post("/adjust/callback", response_model=ConversionIngestResponse)
async def ingest_adjust_callback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_json_payload(request)
    payload = normalize_adjust_payload(payload)
    _verify_webhook_secret("adjust", request, payload)
    service = ConversionIngestionService()
    result = await service.ingest_provider_payload(
        source_type="adjust",
        payload=payload,
        buyer_id_override=buyer_id,
        idempotency_key=request.headers.get("X-Idempotency-Key"),
    )
    return ConversionIngestResponse(**result)


@router.post("/branch/webhook", response_model=ConversionIngestResponse)
async def ingest_branch_webhook(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_json_payload(request)
    payload = normalize_branch_payload(payload)
    _verify_webhook_secret("branch", request, payload)
    service = ConversionIngestionService()
    result = await service.ingest_provider_payload(
        source_type="branch",
        payload=payload,
        buyer_id_override=buyer_id,
        idempotency_key=request.headers.get("X-Idempotency-Key"),
    )
    return ConversionIngestResponse(**result)


@router.post("/generic/postback", response_model=ConversionIngestResponse)
async def ingest_generic_postback(
    request: Request,
    buyer_id: Optional[str] = Query(None, description="Optional buyer override"),
):
    payload = await _parse_json_payload(request)
    payload = normalize_generic_payload(payload)
    _verify_webhook_secret("generic", request, payload)
    source_type = str(payload.get("source_type") or "generic")
    service = ConversionIngestionService()
    result = await service.ingest_provider_payload(
        source_type=source_type,
        payload=payload,
        buyer_id_override=buyer_id,
        idempotency_key=request.headers.get("X-Idempotency-Key"),
    )
    return ConversionIngestResponse(**result)


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
