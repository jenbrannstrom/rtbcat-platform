"""Service layer for Gmail import workflow."""

from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

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

    async def queue_import(self) -> dict[str, Any]:
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
        self._spawn_import_worker(job_id)

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

    def _spawn_import_worker(self, job_id: str) -> None:
        """Spawn detached worker process so import survives request/SSH disconnects."""
        worker_path = Path(__file__).resolve().parent.parent / "scripts" / "gmail_import_worker.py"
        if not worker_path.exists():
            raise HTTPException(status_code=500, detail="Gmail worker script not found")

        logs_dir = Path.home() / ".catscan" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "gmail_import_worker.log"

        with open(log_file, "a", encoding="utf-8") as fp:
            subprocess.Popen(
                [sys.executable, str(worker_path), "--job-id", job_id, "--quiet"],
                stdout=fp,
                stderr=fp,
                start_new_session=True,
            )
