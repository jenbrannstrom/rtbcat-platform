"""BYOM optimizer model registry API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_models_service import OptimizerModelsService


router = APIRouter(prefix="/optimizer/models", tags=["Optimizer"])


class OptimizerModelRow(BaseModel):
    model_id: str
    buyer_id: str
    name: str
    description: Optional[str] = None
    model_type: str
    endpoint_url: Optional[str] = None
    has_auth_header: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OptimizerModelsMeta(BaseModel):
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class OptimizerModelsResponse(BaseModel):
    rows: list[OptimizerModelRow]
    meta: OptimizerModelsMeta


class CreateOptimizerModelRequest(BaseModel):
    buyer_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    model_type: str = "api"
    endpoint_url: Optional[str] = None
    auth_header_encrypted: Optional[str] = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class UpdateOptimizerModelRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_type: Optional[str] = None
    endpoint_url: Optional[str] = None
    auth_header_encrypted: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = None
    output_schema: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class OptimizerModelUpdateActiveResponse(BaseModel):
    model_id: str
    is_active: bool


@router.get("", response_model=OptimizerModelsResponse)
async def list_optimizer_models(
    buyer_id: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    payload = await service.list_models(
        buyer_id=buyer_id,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    return OptimizerModelsResponse(**payload)


@router.post("", response_model=OptimizerModelRow)
async def create_optimizer_model(
    request: CreateOptimizerModelRequest,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(request.buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    try:
        payload = await service.create_model(
            buyer_id=buyer_id or "unknown",
            name=request.name,
            description=request.description,
            model_type=request.model_type,
            endpoint_url=request.endpoint_url,
            auth_header_encrypted=request.auth_header_encrypted,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
            is_active=request.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OptimizerModelRow(**payload)


@router.get("/{model_id}", response_model=OptimizerModelRow)
async def get_optimizer_model(
    model_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    payload = await service.get_model(model_id=model_id, buyer_id=buyer_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Model not found")
    return OptimizerModelRow(**payload)


@router.patch("/{model_id}", response_model=OptimizerModelRow)
async def update_optimizer_model(
    model_id: str,
    request: UpdateOptimizerModelRequest,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    updates = request.model_dump(exclude_unset=True)
    try:
        payload = await service.update_model(
            model_id=model_id,
            buyer_id=buyer_id,
            updates=updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload:
        raise HTTPException(status_code=404, detail="Model not found")
    return OptimizerModelRow(**payload)


@router.post("/{model_id}/activate", response_model=OptimizerModelUpdateActiveResponse)
async def activate_optimizer_model(
    model_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    payload = await service.update_model(
        model_id=model_id,
        buyer_id=buyer_id,
        updates={"is_active": True},
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Model not found")
    return OptimizerModelUpdateActiveResponse(
        model_id=payload["model_id"],
        is_active=bool(payload["is_active"]),
    )


@router.post("/{model_id}/deactivate", response_model=OptimizerModelUpdateActiveResponse)
async def deactivate_optimizer_model(
    model_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerModelsService()
    payload = await service.update_model(
        model_id=model_id,
        buyer_id=buyer_id,
        updates={"is_active": False},
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Model not found")
    return OptimizerModelUpdateActiveResponse(
        model_id=payload["model_id"],
        is_active=bool(payload["is_active"]),
    )

