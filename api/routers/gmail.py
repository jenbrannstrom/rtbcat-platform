"""Gmail Router - Gmail import endpoints.

Handles Gmail import status and triggering manual imports.
"""

import logging
from pathlib import Path
from typing import Optional

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import require_admin
from storage.repositories.user_repository import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Gmail Import"])


# =============================================================================
# Pydantic Models
# =============================================================================

class GmailStatusResponse(BaseModel):
    """Response model for Gmail import status."""
    configured: bool = Field(description="Whether Gmail OAuth client is configured")
    authorized: bool = Field(description="Whether Gmail is authorized (token exists)")
    last_run: Optional[str] = Field(None, description="ISO timestamp of last import run")
    last_success: Optional[str] = Field(None, description="ISO timestamp of last successful import")
    last_error: Optional[str] = Field(None, description="Error message from last failed run")
    total_imports: int = Field(0, description="Total files imported all time")
    recent_history: list = Field(default_factory=list, description="Recent import history")
    running: bool = Field(False, description="Whether an import is currently running")
    current_job_id: Optional[str] = Field(None, description="Current import job ID")


class GmailImportResponse(BaseModel):
    """Response model for Gmail import trigger."""
    success: bool
    queued: bool = False
    job_id: Optional[str] = None
    message: Optional[str] = None
    emails_skipped: int = 0
    skipped_seat_ids: list[str] = Field(default_factory=list)
    emails_processed: int = 0
    files_imported: int = 0
    files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/gmail/status", response_model=GmailStatusResponse)
async def get_gmail_status():
    """
    Get the current Gmail import configuration and status.

    Returns whether Gmail is configured/authorized and the last import results.
    """
    try:
        from scripts.gmail_import import get_status
        status = get_status()
        return GmailStatusResponse(**status)
    except ImportError:
        # Fallback if script not found
        catscan_dir = Path.home() / '.catscan'
        credentials_dir = catscan_dir / 'credentials'

        return GmailStatusResponse(
            configured=(credentials_dir / 'gmail-oauth-client.json').exists(),
            authorized=(credentials_dir / 'gmail-token.json').exists(),
            total_imports=0,
            recent_history=[]
        )
    except Exception as e:
        logger.error(f"Failed to get Gmail status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/import", response_model=GmailImportResponse)
async def trigger_gmail_import(
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
):
    """
    Trigger a manual Gmail import.

    Checks Gmail for new report emails and imports any found CSVs.
    This is the same operation that runs via cron.
    """
    try:
        from scripts.gmail_import import run_import, get_status

        # Check if configured first
        status = get_status()
        if not status.get("configured"):
            raise HTTPException(
                status_code=400,
                detail="Gmail not configured. Upload gmail-oauth-client.json to ~/.catscan/credentials/"
            )

        if not status.get("authorized"):
            raise HTTPException(
                status_code=400,
                detail="Gmail not authorized. Run the import script manually first to complete OAuth flow."
            )

        if status.get("running"):
            raise HTTPException(status_code=409, detail="Gmail import already running")

        job_id = str(uuid.uuid4())
        background_tasks.add_task(run_import, False, job_id)

        return GmailImportResponse(
            success=True,
            queued=True,
            job_id=job_id,
            message="Gmail import queued",
            emails_skipped=0,
            skipped_seat_ids=[],
            emails_processed=0,
            files_imported=0,
            files=[],
            errors=[],
        )

    except ImportError as e:
        logger.error(f"Gmail import script not found: {e}")
        raise HTTPException(
            status_code=500,
            detail="Gmail import script not available. Check scripts/gmail_import.py"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
