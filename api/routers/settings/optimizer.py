"""Optimizer setup settings routes."""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_store, require_admin
from services.auth_service import User


router = APIRouter(tags=["RTB Settings"])

_MONTHLY_HOSTING_COST_KEY = "optimizer_monthly_hosting_cost_usd"


class OptimizerSetupResponse(BaseModel):
    monthly_hosting_cost_usd: Optional[float] = None
    effective_cpm_enabled: bool


class UpdateOptimizerSetupRequest(BaseModel):
    monthly_hosting_cost_usd: float = Field(..., ge=0.0)


@router.get("/settings/optimizer/setup", response_model=OptimizerSetupResponse)
async def get_optimizer_setup(
    store=Depends(get_store),
) -> OptimizerSetupResponse:
    raw_value = await store.get_setting(_MONTHLY_HOSTING_COST_KEY)
    monthly_cost: Optional[float] = None
    if raw_value not in (None, ""):
        try:
            monthly_cost = float(raw_value)
        except (TypeError, ValueError):
            monthly_cost = None

    return OptimizerSetupResponse(
        monthly_hosting_cost_usd=monthly_cost,
        effective_cpm_enabled=monthly_cost is not None and monthly_cost > 0,
    )


@router.put("/settings/optimizer/setup", response_model=OptimizerSetupResponse)
async def update_optimizer_setup(
    request: UpdateOptimizerSetupRequest,
    store=Depends(get_store),
    user: User = Depends(require_admin),
) -> OptimizerSetupResponse:
    monthly_cost = float(request.monthly_hosting_cost_usd)
    if monthly_cost < 0:
        raise HTTPException(status_code=400, detail="monthly_hosting_cost_usd must be >= 0")

    await store.set_setting(
        _MONTHLY_HOSTING_COST_KEY,
        f"{monthly_cost:.6f}",
        updated_by=getattr(user, "id", None),
    )
    await store.log_audit(
        audit_id=str(uuid.uuid4()),
        action="optimizer_setup_updated",
        user_id=getattr(user, "id", None),
        resource_type="system_setting",
        resource_id=_MONTHLY_HOSTING_COST_KEY,
        details=json.dumps({"monthly_hosting_cost_usd": monthly_cost}),
    )

    return OptimizerSetupResponse(
        monthly_hosting_cost_usd=monthly_cost,
        effective_cpm_enabled=monthly_cost > 0,
    )
