"""Configuration Router - Credentials and settings management endpoints.

Handles Google service account credentials upload, status, and deletion.
Supports multiple service accounts for multi-account setups.
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import ConfigManager
from config.config_manager import AuthorizedBuyersConfig, AppConfig
from api.dependencies import get_config, get_store
from storage.sqlite_store import SQLiteStore, ServiceAccount

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration"])


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


class CredentialsStatusResponse(BaseModel):
    """Response model for credentials status (legacy single-account)."""
    configured: bool
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    credentials_path: Optional[str] = None
    account_id: Optional[str] = None


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
    store: SQLiteStore = Depends(get_store),
):
    """List all configured service accounts."""
    accounts = await store.get_service_accounts(active_only=active_only)
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
    store: SQLiteStore = Depends(get_store),
):
    """Add a new Google service account.

    Accepts the JSON contents of a Google Cloud service account key file,
    validates it, saves it securely, and stores metadata in the database.
    """
    # Parse and validate JSON
    try:
        creds_data = json.loads(request.service_account_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}",
        )

    # Validate required fields
    required_fields = ["type", "client_email", "private_key", "project_id"]
    missing = [f for f in required_fields if f not in creds_data]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}. This doesn't appear to be a valid service account key.",
        )

    if creds_data.get("type") != "service_account":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credential type: '{creds_data.get('type')}'. Expected 'service_account'.",
        )

    client_email = creds_data.get("client_email")
    project_id = creds_data.get("project_id")

    # Check if this account already exists
    existing = await store.get_service_account_by_email(client_email)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Service account {client_email} is already configured.",
        )

    # Generate UUID for this account
    account_id = str(uuid.uuid4())

    # Create credentials directory
    creds_dir = Path.home() / ".catscan" / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(creds_dir, 0o700)

    # Save credentials file with UUID filename
    creds_path = creds_dir / f"{account_id}.json"
    with open(creds_path, "w") as f:
        json.dump(creds_data, f, indent=2)
    os.chmod(creds_path, 0o600)

    # Save to database
    try:
        service_account = ServiceAccount(
            id=account_id,
            client_email=client_email,
            project_id=project_id,
            display_name=request.display_name or project_id or client_email.split("@")[0],
            credentials_path=str(creds_path),
            is_active=True,
        )
        await store.save_service_account(service_account)

        logger.info(f"Service account added: {client_email} (id={account_id})")

        return CredentialsUploadResponse(
            success=True,
            id=account_id,
            client_email=client_email,
            project_id=project_id,
            message="Service account added successfully",
        )

    except Exception as e:
        # Clean up credentials file on failure
        if creds_path.exists():
            creds_path.unlink()
        logger.error(f"Failed to save service account: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save service account: {str(e)}",
        )


@router.get("/config/service-accounts/{account_id}", response_model=ServiceAccountResponse)
async def get_service_account(
    account_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific service account by ID."""
    account = await store.get_service_account(account_id)
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


@router.delete("/config/service-accounts/{account_id}", response_model=DeleteResponse)
async def delete_service_account(
    account_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Delete a service account and its credentials file."""
    # Get the account first to find credentials path
    account = await store.get_service_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")

    try:
        # Delete credentials file
        creds_path = Path(account.credentials_path)
        if creds_path.exists():
            creds_path.unlink()

        # Delete from database (will set buyer_seats.service_account_id to NULL)
        deleted = await store.delete_service_account(account_id)

        if deleted:
            logger.info(f"Service account deleted: {account.client_email} (id={account_id})")
            return DeleteResponse(success=True, message="Service account deleted")
        else:
            raise HTTPException(status_code=500, detail="Failed to delete service account from database")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete service account: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete service account: {str(e)}",
        )


# =============================================================================
# Legacy Single-Account Endpoints (Deprecated but kept for compatibility)
# =============================================================================

@router.get("/config/credentials", response_model=CredentialsStatusResponse)
async def get_credentials_status(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Get current credentials configuration status.

    DEPRECATED: Use /config/service-accounts instead for multi-account support.
    This endpoint returns the first active service account for backward compatibility.
    """
    # Try new multi-account system first
    accounts = await store.get_service_accounts(active_only=True)
    if accounts:
        account = accounts[0]
        return CredentialsStatusResponse(
            configured=True,
            client_email=account.client_email,
            project_id=account.project_id,
            credentials_path=account.credentials_path,
            account_id=None,  # This was bidder account ID, not relevant for multi-account
        )

    # Fall back to legacy config system
    if not config.is_configured():
        return CredentialsStatusResponse(configured=False)

    try:
        app_config = config.get_config()
        if not app_config.authorized_buyers:
            return CredentialsStatusResponse(configured=False)

        creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()

        if not creds_path.exists():
            return CredentialsStatusResponse(
                configured=False,
                credentials_path=str(creds_path),
            )

        # Read the credentials file to get client_email
        with open(creds_path) as f:
            creds_data = json.load(f)

        return CredentialsStatusResponse(
            configured=True,
            client_email=creds_data.get("client_email"),
            project_id=creds_data.get("project_id"),
            credentials_path=str(creds_path),
            account_id=app_config.authorized_buyers.account_id,
        )
    except Exception as e:
        logger.error(f"Error reading credentials: {e}")
        return CredentialsStatusResponse(configured=False)


@router.post("/config/credentials", response_model=CredentialsUploadResponse)
async def upload_credentials(
    request: CredentialsUploadRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Upload Google service account credentials.

    DEPRECATED: Use POST /config/service-accounts instead.
    This endpoint now creates a service account in the new multi-account system.
    """
    # Redirect to new multi-account endpoint
    return await add_service_account(request, store)


@router.delete("/config/credentials", response_model=DeleteResponse)
async def delete_credentials(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Remove stored credentials and reset configuration.

    DEPRECATED: Use DELETE /config/service-accounts/{id} instead.
    This endpoint removes ALL service accounts for backward compatibility.
    """
    try:
        # Delete all service accounts from new system
        accounts = await store.get_service_accounts()
        for account in accounts:
            creds_path = Path(account.credentials_path)
            if creds_path.exists():
                creds_path.unlink()
            await store.delete_service_account(account.id)

        # Also clean up legacy credentials file
        legacy_path = Path.home() / ".catscan" / "credentials" / "google-credentials.json"
        if legacy_path.exists():
            legacy_path.unlink()

        # Reset legacy configuration
        config.reset()

        return DeleteResponse(success=True, message="All credentials removed")

    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete credentials: {str(e)}",
        )
