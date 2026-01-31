"""Configuration Router - Credentials and settings management endpoints.

Handles Google service account credentials upload, status, and deletion.
Supports multiple service accounts for multi-account setups.

In GCP mode (OAuth2 Proxy enabled), supports Application Default Credentials (ADC)
which uses the VM's attached service account automatically.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_store
from services.config_service import ConfigService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration"])


# =============================================================================
# GCP / ADC Mode Endpoints
# =============================================================================

class GCPStatusResponse(BaseModel):
    """Response model for GCP mode status."""
    gcp_mode: bool
    adc_available: bool
    service_account_email: Optional[str] = None
    project_id: Optional[str] = None
    message: str


class GCPDiscoverRequest(BaseModel):
    """Request model for GCP-native seat discovery."""
    bidder_id: str = Field(..., description="Your Authorized Buyers bidder account ID")


class DiscoveryResponse(BaseModel):
    """Response model for bidder discovery."""
    success: bool
    bidder_ids: List[str] = []
    buyer_seats_count: int = 0
    message: str


@router.get("/config/gcp-status", response_model=GCPStatusResponse)
async def get_gcp_status():
    """Get GCP deployment mode status.

    Returns information about whether the app is running in GCP mode
    with Application Default Credentials (ADC) from the VM's attached
    service account.
    """
    service = ConfigService()
    status = service.get_gcp_status()
    return GCPStatusResponse(**status)


@router.post("/config/gcp-discover", response_model=DiscoveryResponse)
async def discover_via_adc(
    request: GCPDiscoverRequest,
    store=Depends(get_store),
):
    """Discover buyer seats using GCP Application Default Credentials.

    This endpoint uses the VM's attached service account to discover
    buyer seats without requiring manual credential upload.

    The service account must have been added to the Authorized Buyers
    account in the RTB API Console.
    """
    service = ConfigService()
    result = await service.discover_via_adc(request.bidder_id, store)
    return DiscoveryResponse(**result)


# =============================================================================
# Pydantic Models
# =============================================================================

class ServiceAccountResponse(BaseModel):
    """Response model for a service account."""
    id: str
    client_email: str
    project_id: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    last_used: Optional[str] = None


class ServiceAccountListResponse(BaseModel):
    """Response model for listing service accounts."""
    accounts: List[ServiceAccountResponse]
    count: int


class CredentialsUploadRequest(BaseModel):
    """Request model for uploading service account credentials."""
    service_account_json: str = Field(..., description="JSON string of service account key file")
    display_name: Optional[str] = Field(None, description="Optional display name for the account")


class CredentialsUploadResponse(BaseModel):
    """Response model for credentials upload."""
    success: bool
    id: Optional[str] = None
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    message: str


class DeleteResponse(BaseModel):
    """Response model for delete operations."""
    success: bool
    message: str


# =============================================================================
# Multi-Account Endpoints (New)
# =============================================================================

@router.get("/config/service-accounts", response_model=ServiceAccountListResponse)
async def list_service_accounts(
    active_only: bool = False,
    store=Depends(get_store),
):
    """List all configured service accounts."""
    service = ConfigService()
    accounts = await service.list_service_accounts(store, active_only)
    return ServiceAccountListResponse(
        accounts=[
            ServiceAccountResponse(
                id=acc.id,
                client_email=acc.client_email,
                project_id=acc.project_id,
                display_name=acc.display_name,
                is_active=acc.is_active,
                created_at=str(acc.created_at) if acc.created_at else None,
                last_used=str(acc.last_used) if acc.last_used else None,
            )
            for acc in accounts
        ],
        count=len(accounts),
    )


@router.post("/config/service-accounts", response_model=CredentialsUploadResponse)
async def add_service_account(
    request: CredentialsUploadRequest,
    store=Depends(get_store),
):
    """Add a new Google service account.

    Accepts the JSON contents of a Google Cloud service account key file,
    validates it, saves it securely, and stores metadata in the database.
    """
    service = ConfigService()
    result = await service.add_service_account(
        store=store,
        service_account_json=request.service_account_json,
        display_name=request.display_name,
    )
    return CredentialsUploadResponse(**result)


@router.get("/config/service-accounts/{account_id}", response_model=ServiceAccountResponse)
async def get_service_account(
    account_id: str,
    store=Depends(get_store),
):
    """Get a specific service account by ID."""
    service = ConfigService()
    account = await service.get_service_account(store, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")

    return ServiceAccountResponse(
        id=account.id,
        client_email=account.client_email,
        project_id=account.project_id,
        display_name=account.display_name,
        is_active=account.is_active,
        created_at=str(account.created_at) if account.created_at else None,
        last_used=str(account.last_used) if account.last_used else None,
    )


@router.post("/config/service-accounts/{account_id}/discover", response_model=DiscoveryResponse)
async def discover_bidders_for_account(
    account_id: str,
    store=Depends(get_store),
):
    """Discover bidder accounts accessible by this service account.

    Queries the Google Authorized Buyers API to find all bidder and buyer
    accounts that this service account has access to. Discovered accounts
    are saved to the buyer_seats table and linked to this service account.
    """
    service = ConfigService()
    account = await service.get_service_account(store, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")
    result = await service.discover_bidders_for_account(store, account_id, account)
    return DiscoveryResponse(**result)


@router.delete("/config/service-accounts/{account_id}", response_model=DeleteResponse)
async def delete_service_account(
    account_id: str,
    store=Depends(get_store),
):
    """Delete a service account and its credentials file."""
    # Get the account first to find credentials path
    service = ConfigService()
    account = await service.get_service_account(store, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")
    result = await service.delete_service_account(store, account)
    return DeleteResponse(**result)


# =============================================================================
# Gemini API Key Endpoints
# =============================================================================

class GeminiKeyStatusResponse(BaseModel):
    """Response model for Gemini API key status."""
    configured: bool
    masked_key: Optional[str] = None  # e.g., "AIza...x7Qm"
    message: str


class GeminiKeyUpdateRequest(BaseModel):
    """Request to update Gemini API key."""
    api_key: str = Field(..., min_length=10, description="Gemini API key")


class GeminiKeyUpdateResponse(BaseModel):
    """Response after updating Gemini API key."""
    success: bool
    message: str


@router.get("/config/gemini-key", response_model=GeminiKeyStatusResponse)
async def get_gemini_key_status(
    store=Depends(get_store),
):
    """Get Gemini API key configuration status.

    The key is used for AI-powered language detection in creatives.
    Returns masked key for security.
    """
    service = ConfigService()
    status = await service.get_gemini_key_status(store)
    return GeminiKeyStatusResponse(**status)


@router.put("/config/gemini-key", response_model=GeminiKeyUpdateResponse)
async def update_gemini_key(
    request: GeminiKeyUpdateRequest,
    store=Depends(get_store),
):
    """Update Gemini API key.

    The key is stored securely in the database and used for AI-powered
    language detection in creatives.
    """
    service = ConfigService()
    result = await service.update_gemini_key(store, request.api_key)
    return GeminiKeyUpdateResponse(**result)


@router.delete("/config/gemini-key", response_model=GeminiKeyUpdateResponse)
async def delete_gemini_key(
    store=Depends(get_store),
):
    """Delete Gemini API key from database.

    Note: If GEMINI_API_KEY environment variable is set, it will be used as fallback.
    """
    service = ConfigService()
    result = await service.delete_gemini_key(store)
    return GeminiKeyUpdateResponse(**result)
