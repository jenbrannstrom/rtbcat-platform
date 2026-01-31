"""Gmail Router - Gmail import endpoints.

Handles Gmail import status and triggering manual imports.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.dependencies import require_admin
from services.auth_service import User
from services.gmail_service import GmailService

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
        service = GmailService()
        status = service.get_status()
        return GmailStatusResponse(**status)
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
        service = GmailService()
        result = await service.queue_import(background_tasks)
        return GmailImportResponse(**result)

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


@router.post("/gmail/import/scheduled", response_model=GmailImportResponse)
async def trigger_gmail_import_scheduled(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Trigger Gmail import for schedulers (Cloud Scheduler/systemd).

    Requires header: X-Gmail-Import-Secret matching GMAIL_IMPORT_SECRET.
    """
    secret = os.getenv("GMAIL_IMPORT_SECRET")
    header_secret = request.headers.get("X-Gmail-Import-Secret")
    if not secret or not header_secret or header_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")

    try:
        service = GmailService()
        result = await service.queue_import(background_tasks)
        return GmailImportResponse(**result)
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

