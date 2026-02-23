"""Creatives Router - Creative management endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import (
    get_current_user,
    get_store,
    require_buyer_access,
    resolve_buyer_id,
)
from api.schemas.common import PaginationMeta
from api.schemas.creatives import (
    ClusterAssignment,
    CreativeCountryBreakdownResponse,
    CreativeResponse,
    NewlyUploadedCreativesResponse,
    PaginatedCreativesResponse,
)
from services.auth_service import User
from services.creative_countries_service import CreativeCountriesService
from services.creative_response_builder import build_creative_response
from services.creatives_service import CreativesService, CreativeListContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])
countries_service = CreativeCountriesService()
creatives_service = CreativesService()


@router.get("/creatives", response_model=list[CreativeResponse])
async def list_creatives(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields (vast_xml, html snippets) for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    active_only: bool = Query(False, description="Only return creatives with activity (impressions/clicks/spend) in timeframe"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives with optional filtering."""
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,
        offset=offset,
        include_raw_data=not slim,
    )

    if active_only and creatives:
        creatives = await creatives_service.filter_active_creatives(creatives, days, limit)

    creative_ids = [c.id for c in creatives]
    if slim:
        thumbnail_statuses = await creatives_service.get_thumbnail_statuses(store, creative_ids)
        ctx = CreativeListContext(
            thumbnail_statuses=thumbnail_statuses,
            waste_flags={},
            country_data={},
        )
    else:
        ctx = await creatives_service.get_list_context(store, creative_ids, days)

    return [
        build_creative_response(
            c,
            ctx,
            c.id,
            creatives_service,
            slim=slim,
            source="cache",
        )
        for c in creatives
    ]


@router.get("/creatives/v2", response_model=PaginatedCreativesResponse)
async def list_creatives_paginated(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection"),
    active_only: bool = Query(False, description="Only return creatives with activity in timeframe"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives with pagination metadata."""
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

    total = await store.get_creative_count(
        buyer_id=buyer_id,
        format=format,
    )

    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,
        offset=offset,
        include_raw_data=not slim,
    )

    if active_only and creatives:
        creatives = await creatives_service.filter_active_creatives(creatives, days, limit)

    creative_ids = [c.id for c in creatives]
    if slim:
        thumbnail_statuses = await creatives_service.get_thumbnail_statuses(store, creative_ids)
        ctx = CreativeListContext(
            thumbnail_statuses=thumbnail_statuses,
            waste_flags={},
            country_data={},
        )
    else:
        ctx = await creatives_service.get_list_context(store, creative_ids, days)

    data = [
        build_creative_response(
            c,
            ctx,
            c.id,
            creatives_service,
            slim=slim,
            source="cache",
        )
        for c in creatives
    ]

    return PaginatedCreativesResponse(
        data=data,
        meta=PaginationMeta(
            timeframe_days=days,
            total=total,
            returned=len(data),
            limit=limit,
            offset=offset,
            has_more=offset + len(data) < total,
        ),
    )


@router.get("/creatives/newly-uploaded", response_model=NewlyUploadedCreativesResponse)
async def get_newly_uploaded_creatives(
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    limit: int = Query(100, description="Maximum number of creatives to return", ge=1, le=1000),
    format: Optional[str] = Query(None, description="Filter by format (HTML, VIDEO, NATIVE)"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get creatives first seen within the specified period."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        result = await creatives_service.get_newly_uploaded_creatives(
            days=days,
            limit=limit,
            creative_format=format,
            buyer_id=buyer_id,
        )
        return NewlyUploadedCreativesResponse(
            creatives=result.creatives,
            total_count=result.total_count or 0,
            period_start=result.period_start.strftime("%Y-%m-%d"),
            period_end=result.period_end.strftime("%Y-%m-%d"),
        )
    except Exception as e:
        logger.error(f"Failed to get newly uploaded creatives: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get newly uploaded creatives: {str(e)}")


@router.get("/creatives/{creative_id}", response_model=CreativeResponse)
async def get_creative(
    creative_id: str,
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get a specific creative by ID with preview context."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    ctx = await creatives_service.get_list_context(store, [creative_id], days)
    return build_creative_response(
        creative,
        ctx,
        creative_id,
        creatives_service,
        slim=False,
        source="cache",
    )


@router.delete("/creatives/{creative_id}")
async def delete_creative(
    creative_id: str,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Delete a creative by ID."""
    creative = await store.get_creative(creative_id)
    if creative and creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)
    deleted = await store.delete_creative(creative_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Creative not found")
    return {"status": "deleted", "id": creative_id}


@router.post("/creatives/cluster")
async def assign_cluster(
    assignment: ClusterAssignment,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Assign a creative to a cluster."""
    creative = await store.get_creative(assignment.creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)
    await store.update_creative_cluster(assignment.creative_id, assignment.cluster_id)
    return {"status": "updated", "creative_id": assignment.creative_id}


@router.delete("/creatives/{creative_id}/campaign")
async def remove_from_campaign(
    creative_id: str,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Remove a creative from its campaign."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    await store.update_creative_campaign(creative_id, None)
    return {"status": "removed", "creative_id": creative_id}


@router.get("/creatives/{creative_id}/countries", response_model=CreativeCountryBreakdownResponse)
async def get_creative_countries(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get country breakdown for a specific creative."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    payload = await countries_service.build_country_metrics(creative_id, days)
    return CreativeCountryBreakdownResponse(**payload)
