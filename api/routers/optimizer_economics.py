"""Optimizer economics endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_economics_service import OptimizerEconomicsService


router = APIRouter(prefix="/optimizer/economics", tags=["Optimizer"])


class EffectiveCpmResponse(BaseModel):
    buyer_id: str
    billing_id: Optional[str] = None
    start_date: str
    end_date: str
    days: int
    impressions: int
    media_spend_usd: float
    monthly_hosting_cost_usd: Optional[float] = None
    infra_cost_period_usd: Optional[float] = None
    media_cpm_usd: Optional[float] = None
    infra_cpm_usd: Optional[float] = None
    effective_cpm_usd: Optional[float] = None
    cost_context_ready: bool


class AssumedValueComponents(BaseModel):
    spend_level_score: float
    spend_trend_score: float
    bid_rate_score: float
    win_rate_score: float
    ctr_score: float
    age_score: float
    viewability_score: float


class AssumedValueMetrics(BaseModel):
    spend_usd: float
    avg_daily_spend_usd: float
    recent_spend_usd: float
    previous_spend_usd: float
    impressions: int
    clicks: int
    reached_queries: int
    bids_in_auction: int
    auctions_won: int
    bid_rate: float
    win_rate: float
    ctr: float
    viewability: Optional[float] = None
    account_age_months: float


class AssumedValueResponse(BaseModel):
    buyer_id: str
    billing_id: Optional[str] = None
    start_date: str
    end_date: str
    days: int
    assumed_value_score: float
    components: AssumedValueComponents
    metrics: AssumedValueMetrics


class EfficiencySummaryResponse(BaseModel):
    buyer_id: str
    billing_id: Optional[str] = None
    start_date: str
    end_date: str
    days: int
    spend_usd: float
    impressions: int
    bid_requests: int
    reached_queries: int
    avg_daily_spend_usd: float
    avg_allocated_qps: Optional[float] = None
    assumed_value_score: float
    qps_efficiency: Optional[float] = None
    assumed_value_per_qps: Optional[float] = None
    has_bid_request_data: bool
    has_reached_query_data: bool


@router.get("/effective-cpm", response_model=EffectiveCpmResponse)
async def get_effective_cpm(
    buyer_id: Optional[str] = Query(None),
    billing_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> EffectiveCpmResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerEconomicsService()
    try:
        payload = await service.get_effective_cpm(
            buyer_id=buyer_id or "unknown",
            billing_id=billing_id,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EffectiveCpmResponse(**payload)


@router.get("/assumed-value", response_model=AssumedValueResponse)
async def get_assumed_value(
    buyer_id: Optional[str] = Query(None),
    billing_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> AssumedValueResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerEconomicsService()
    try:
        payload = await service.get_assumed_value(
            buyer_id=buyer_id or "unknown",
            billing_id=billing_id,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssumedValueResponse(**payload)


@router.get("/efficiency", response_model=EfficiencySummaryResponse)
async def get_efficiency_summary(
    buyer_id: Optional[str] = Query(None),
    billing_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> EfficiencySummaryResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerEconomicsService()
    try:
        payload = await service.get_efficiency_summary(
            buyer_id=buyer_id or "unknown",
            billing_id=billing_id,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EfficiencySummaryResponse(**payload)
