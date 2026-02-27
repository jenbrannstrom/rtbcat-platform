"""SQL-only repository for creative analysis runs and evidence."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from storage.postgres_database import pg_execute, pg_query, pg_query_one


class CreativeAnalysisRepository:
    """Repository for creative_analysis_runs and creative_analysis_evidence tables."""

    # ==================== Run Methods ====================

    async def create_run(
        self,
        run_id: str,
        creative_id: str,
        analysis_type: str = "geo_linguistic",
        triggered_by: Optional[str] = None,
        force_rerun: bool = False,
    ) -> dict[str, Any]:
        """Create a new analysis run."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO creative_analysis_runs
                (id, creative_id, analysis_type, status, triggered_by, force_rerun, started_at, created_at)
            VALUES (%s, %s, %s, 'running', %s, %s, %s, %s)
            """,
            (run_id, creative_id, analysis_type, triggered_by, force_rerun, now, now),
        )
        return {
            "id": run_id,
            "creative_id": creative_id,
            "analysis_type": analysis_type,
            "status": "running",
            "triggered_by": triggered_by,
            "force_rerun": force_rerun,
            "started_at": now,
            "created_at": now,
        }

    async def get_latest_run(
        self,
        creative_id: str,
        analysis_type: str = "geo_linguistic",
    ) -> Optional[dict[str, Any]]:
        """Get the most recent analysis run for a creative."""
        return await pg_query_one(
            """
            SELECT id, creative_id, analysis_type, status, result,
                   error_message, triggered_by, force_rerun,
                   started_at, completed_at, created_at,
                   retry_count, next_retry_at
            FROM creative_analysis_runs
            WHERE creative_id = %s AND analysis_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (creative_id, analysis_type),
        )

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the status and optionally the result of a run."""
        now = datetime.utcnow().isoformat()
        if result is not None:
            import json

            await pg_execute(
                """
                UPDATE creative_analysis_runs
                SET status = %s, result = %s::jsonb, completed_at = %s
                WHERE id = %s
                """,
                (status, json.dumps(result), now, run_id),
            )
        elif error_message is not None:
            await pg_execute(
                """
                UPDATE creative_analysis_runs
                SET status = %s, error_message = %s, completed_at = %s
                WHERE id = %s
                """,
                (status, error_message, now, run_id),
            )
        else:
            await pg_execute(
                """
                UPDATE creative_analysis_runs
                SET status = %s, completed_at = %s
                WHERE id = %s
                """,
                (status, now, run_id),
            )

    async def should_skip_analysis(
        self,
        creative_id: str,
        analysis_type: str = "geo_linguistic",
        max_age_hours: int = 24,
    ) -> bool:
        """Return True if a recent successful analysis exists (skip re-analysis)."""
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        row = await pg_query_one(
            """
            SELECT id FROM creative_analysis_runs
            WHERE creative_id = %s
              AND analysis_type = %s
              AND status = 'completed'
              AND completed_at > %s
            LIMIT 1
            """,
            (creative_id, analysis_type, cutoff),
        )
        return row is not None

    # ==================== Evidence Methods ====================

    async def add_evidence(
        self,
        evidence_id: str,
        run_id: str,
        evidence_type: str,
        file_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Add an evidence record for an analysis run."""
        import json

        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata) if metadata else None
        await pg_execute(
            """
            INSERT INTO creative_analysis_evidence
                (id, run_id, evidence_type, file_path, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (evidence_id, run_id, evidence_type, file_path, meta_json, now),
        )
        return {
            "id": evidence_id,
            "run_id": run_id,
            "evidence_type": evidence_type,
            "file_path": file_path,
            "metadata": metadata,
            "created_at": now,
        }

    async def get_evidence_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """Get all evidence records for a run."""
        return await pg_query(
            """
            SELECT id, run_id, evidence_type, file_path, metadata, created_at
            FROM creative_analysis_evidence
            WHERE run_id = %s
            ORDER BY created_at
            """,
            (run_id,),
        )
