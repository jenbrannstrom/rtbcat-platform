"""Buyer-authorized publisher identity lookup for the app and outside agents."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import (
    get_config,
    get_current_user,
    get_store,
    require_buyer_access,
)
from api.routers.agent import (
    _enforce_token_buyer,
    get_auth_service,
    require_agent_scope,
)
from api.schemas.publisher_lookup import PublisherLookupRequest
from collectors.publisher_profiles import PublisherProfilesClient
from config import ConfigManager
from services.agent_token_service import AGENT_PUBLISHERS_READ_SCOPE, AgentAuthContext
from services.auth_service import AuthService, User
from services.publisher_lookup_service import PublisherLookupService
from services.seats_service import SeatsService, is_gcp_mode

router = APIRouter(tags=["Publisher lookup"])
require_publisher_context = require_agent_scope(AGENT_PUBLISHERS_READ_SCOPE)


def get_lookup_service() -> PublisherLookupService:
    return PublisherLookupService()


def get_lookup_seats_service() -> SeatsService:
    return SeatsService()


async def _lookup(payload, service, seats, config):
    client = None
    google_status = "not_requested"
    if payload.include_google:
        google_status = "credentials_missing"
        seat = await seats.get_buyer_seat(payload.buyer_id)
        if not seat or not seat.active:
            raise HTTPException(status_code=404, detail="Active buyer seat not found")
        credentials_path = None
        # Do not use the generic fallback resolver: it can relink a seat to an
        # arbitrary first account. Identity lookups must not mutate seat setup.
        if seat.service_account_id:
            account = await seats.get_service_account(seat.service_account_id)
            if account and account.is_active:
                credentials_path = account.credentials_path
        elif config.is_configured():
            try:
                credentials_path = str(config.get_service_account_path())
            except (ValueError, FileNotFoundError):
                pass
        if credentials_path or (not seat.service_account_id and is_gcp_mode()):
            client = PublisherProfilesClient(payload.buyer_id, credentials_path)
    return await service.lookup(
        app_id=payload.app_id,
        domain=payload.domain,
        publisher_name=payload.publisher_name,
        google_client=client,
        google_status=google_status,
    )


@router.post("/publisher-lookup")
async def lookup_publisher(
    payload: PublisherLookupRequest,
    store=Depends(get_store),
    config: ConfigManager = Depends(get_config),
    user: User = Depends(get_current_user),
    service: PublisherLookupService = Depends(get_lookup_service),
    seats: SeatsService = Depends(get_lookup_seats_service),
) -> dict:
    """Read current Google and public publisher evidence; no spend qualification."""
    await require_buyer_access(payload.buyer_id, store=store, user=user)
    return await _lookup(payload, service, seats, config)


@router.post("/agent/v1/publisher-lookup")
async def lookup_agent_publisher(
    payload: PublisherLookupRequest,
    request: Request,
    store=Depends(get_store),
    config: ConfigManager = Depends(get_config),
    context: AgentAuthContext = Depends(require_publisher_context),
    service: PublisherLookupService = Depends(get_lookup_service),
    seats: SeatsService = Depends(get_lookup_seats_service),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Separate publisher-read scope; check token and live seat grants before fetching."""
    _enforce_token_buyer(context, payload.buyer_id)
    await require_buyer_access(payload.buyer_id, store=store, user=context.user)
    await auth.log_audit(
        audit_id=str(uuid.uuid4()),
        action="agent_publisher_lookup",
        user_id=context.user.id,
        resource_type="agent_api",
        resource_id=payload.buyer_id,
        details=f"token_id={context.token.id}; app_id={payload.app_id}; domain={payload.domain}; publisher_name={payload.publisher_name}",
        ip_address=request.client.host if request.client else None,
    )
    return await _lookup(payload, service, seats, config)
