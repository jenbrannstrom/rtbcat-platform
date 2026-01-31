"""Service layer for Gmail import workflow."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException

from services.config_precompute import refresh_config_breakdowns
from services.home_precompute import refresh_home_summaries

logger = logging.getLogger(__name__)


class GmailService:
    """Orchestrates Gmail import operations."""

    def get_status(self) -> dict[str, Any]:
        """Return Gmail import configuration/status."""
        try:
            from scripts.gmail_import import get_status
            return get_status()
        except ImportError:
            catscan_dir = Path.home() / ".catscan"
            credentials_dir = catscan_dir / "credentials"
            return {
                "configured": (credentials_dir / "gmail-oauth-client.json").exists(),
                "authorized": (credentials_dir / "gmail-token.json").exists(),
                "total_imports": 0,
                "recent_history": [],
            }

    async def queue_import(self, background_tasks: BackgroundTasks) -> dict[str, Any]:
        """Validate and enqueue a Gmail import job."""
        from scripts.gmail_import import get_status

        status = get_status()
        if not status.get("configured"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Gmail not configured. Upload gmail-oauth-client.json "
                    "to ~/.catscan/credentials/"
                ),
            )

        if not status.get("authorized"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Gmail not authorized. Run the import script manually first "
                    "to complete OAuth flow."
                ),
            )

        if status.get("running"):
            raise HTTPException(status_code=409, detail="Gmail import already running")

        job_id = str(uuid.uuid4())
        background_tasks.add_task(self.run_import_and_refresh, job_id)

        return {
            "success": True,
            "queued": True,
            "job_id": job_id,
            "message": "Gmail import queued",
            "emails_skipped": 0,
            "skipped_seat_ids": [],
            "emails_processed": 0,
            "files_imported": 0,
            "files": [],
            "errors": [],
        }

    def run_import_and_refresh(self, job_id: str) -> None:
        """Run import and refresh summaries if files were imported."""
        from scripts.gmail_import import run_import

        result = run_import(False, job_id)
        if not result.get("success") or result.get("files_imported", 0) == 0:
            return

        asyncio.run(refresh_home_summaries(days=30))
        asyncio.run(refresh_config_breakdowns(days=30))
