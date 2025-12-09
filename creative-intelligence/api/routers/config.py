"""Configuration Router - Credentials and settings management endpoints.

Handles Google service account credentials upload, status, and deletion.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import ConfigManager
from config.config_manager import AuthorizedBuyersConfig, AppConfig
from api.dependencies import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration"])


# =============================================================================
# Pydantic Models
# =============================================================================

class CredentialsUploadRequest(BaseModel):
    """Request model for uploading service account credentials."""
    service_account_json: str = Field(..., description="JSON string of service account key file")
    account_id: Optional[str] = Field(None, description="Optional bidder account ID override")


class CredentialsUploadResponse(BaseModel):
    """Response model for credentials upload."""
    success: bool
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    message: str


class CredentialsStatusResponse(BaseModel):
    """Response model for credentials status."""
    configured: bool
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    credentials_path: Optional[str] = None
    account_id: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/config/credentials", response_model=CredentialsStatusResponse)
async def get_credentials_status(config: ConfigManager = Depends(get_config)):
    """Get current credentials configuration status."""
    if not config.is_configured():
        return CredentialsStatusResponse(
            configured=False,
        )

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
    config: ConfigManager = Depends(get_config),
):
    """Upload Google service account credentials.

    Accepts the JSON contents of a Google Cloud service account key file,
    validates it, saves it securely, and updates the configuration.
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

    # Create credentials directory
    creds_dir = Path.home() / ".catscan" / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(creds_dir, 0o700)

    # Save credentials file
    creds_path = creds_dir / "google-credentials.json"
    with open(creds_path, "w") as f:
        json.dump(creds_data, f, indent=2)
    os.chmod(creds_path, 0o600)

    # Determine account_id - use provided or extract from client_email
    account_id = request.account_id
    if not account_id:
        # Default to empty, user will need to set it via discover seats
        account_id = ""

    # Update configuration
    try:
        try:
            app_config = config.get_config()
        except Exception:
            # No existing config, create new one
            app_config = AppConfig()

        app_config.authorized_buyers = AuthorizedBuyersConfig(
            service_account_path=str(creds_path),
            account_id=account_id,
        )
        config.save(app_config)

        logger.info(f"Credentials uploaded successfully for {creds_data.get('client_email')}")

        return CredentialsUploadResponse(
            success=True,
            client_email=creds_data.get("client_email"),
            project_id=creds_data.get("project_id"),
            message="Credentials saved successfully",
        )

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save configuration: {str(e)}",
        )


@router.delete("/config/credentials")
async def delete_credentials(config: ConfigManager = Depends(get_config)):
    """Remove stored credentials and reset configuration."""
    try:
        # Remove credentials file
        creds_path = Path.home() / ".catscan" / "credentials" / "google-credentials.json"
        if creds_path.exists():
            creds_path.unlink()

        # Reset configuration
        config.reset()

        return {"success": True, "message": "Credentials removed"}

    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete credentials: {str(e)}",
        )
