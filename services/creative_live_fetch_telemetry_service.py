"""Telemetry recording for live creative fetch fallbacks."""

from __future__ import annotations

from typing import Optional

from storage.postgres_database import pg_execute


class CreativeLiveFetchTelemetryService:
    """Persists live fetch fallback events for observability."""

    async def record_fallback(
        self,
        *,
        creative_id: str,
        buyer_id: Optional[str],
        error_type: str,
        error_message: Optional[str],
    ) -> None:
        await pg_execute(
            """
            INSERT INTO creative_live_fetch_telemetry (
                creative_id,
                buyer_id,
                event_type,
                error_type,
                error_message,
                occurred_at
            ) VALUES (%s, %s, 'fallback', %s, %s, CURRENT_TIMESTAMP)
            """,
            (creative_id, buyer_id, error_type, error_message),
        )

