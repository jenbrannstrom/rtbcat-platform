"""Live creative cache refresh service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Any

from collectors import CreativesClient
from config import ConfigManager
from services.seats_service import SeatsService, is_gcp_mode
from storage.adapters import creative_dict_to_storage
from storage.postgres_database import pg_query
from storage.postgres_store import PostgresStore

logger = logging.getLogger(__name__)


@dataclass
class CreativeCacheRefreshResult:
    scanned: int = 0
    refreshed: int = 0
    failed: int = 0
    skipped: int = 0
    html_thumbnails: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "refreshed": self.refreshed,
            "failed": self.failed,
            "skipped": self.skipped,
            "html_thumbnails": self.html_thumbnails,
        }


class CreativeCacheService:
    """Refreshes live creatives into local cache and optional HTML thumbnails."""

    def __init__(
        self,
        store: Optional[PostgresStore] = None,
        config: Optional[ConfigManager] = None,
    ) -> None:
        self._store = store or PostgresStore()
        self._config = config or ConfigManager()
        self._seats_service = SeatsService()

    async def resolve_live_client(self, creative) -> CreativesClient:
        if not creative.buyer_id:
            raise ValueError("creative has no buyer_id")

        seat = await self._seats_service.get_buyer_seat(creative.buyer_id)
        bidder_id = seat.bidder_id if seat else creative.account_id
        if not bidder_id:
            raise ValueError("unable to resolve bidder_id")

        credentials_path: Optional[str] = None
        if seat:
            credentials_path = await self._seats_service.get_credentials_with_fallback(
                seat, self._config
            )
        else:
            accounts = await self._seats_service.get_service_accounts(active_only=True)
            if accounts:
                account = accounts[0]
                credentials_path = account.credentials_path
                await self._seats_service.update_service_account_last_used(account.id)
            elif self._config.is_configured():
                try:
                    credentials_path = str(self._config.get_service_account_path())
                except Exception:
                    credentials_path = None
            elif is_gcp_mode():
                credentials_path = None

        if not credentials_path and not is_gcp_mode():
            raise ValueError("no credentials available")

        return CreativesClient(
            credentials_path=credentials_path,
            account_id=bidder_id,
        )

    async def refresh_active_creatives(
        self,
        *,
        days: int = 7,
        limit: int = 500,
        include_html_thumbnails: bool = True,
        force_html_thumbnail_retry: bool = False,
    ) -> CreativeCacheRefreshResult:
        """Refresh live creative payloads for creatives with recent activity."""
        result = CreativeCacheRefreshResult()

        rows = await pg_query(
            """
            SELECT pm.creative_id
            FROM performance_metrics pm
            WHERE pm.metric_date >= CURRENT_DATE - (%s::int * INTERVAL '1 day')
              AND (pm.impressions > 0 OR pm.spend_micros > 0 OR pm.clicks > 0)
            GROUP BY pm.creative_id
            ORDER BY SUM(pm.impressions) DESC, SUM(pm.spend_micros) DESC
            LIMIT %s
            """,
            (days, limit),
        )
        creative_ids = [r["creative_id"] for r in rows if r.get("creative_id")]
        result.scanned = len(creative_ids)

        for creative_id in creative_ids:
            creative = await self._store.get_creative(creative_id)
            if not creative or not creative.buyer_id:
                result.skipped += 1
                continue

            try:
                client = await self.resolve_live_client(creative)
                live_dict = await client.get_creative_by_id(
                    creative_id=creative_id,
                    view="FULL",
                    buyer_id=creative.buyer_id,
                )
                if not live_dict:
                    result.failed += 1
                    continue

                live_creative = creative_dict_to_storage(live_dict)
                live_creative.campaign_id = creative.campaign_id
                live_creative.cluster_id = creative.cluster_id
                live_creative.detected_language = creative.detected_language
                live_creative.detected_language_code = creative.detected_language_code
                live_creative.language_confidence = creative.language_confidence
                live_creative.language_source = creative.language_source
                live_creative.language_analyzed_at = creative.language_analyzed_at
                live_creative.language_analysis_error = creative.language_analysis_error

                await self._store.save_creatives([live_creative])
                result.refreshed += 1
            except Exception as e:
                logger.warning(
                    "Failed to refresh creative cache for %s: %s", creative_id, e
                )
                result.failed += 1

        if include_html_thumbnails and creative_ids:
            try:
                result.html_thumbnails = await self._store.process_html_thumbnails(
                    limit=max(limit, len(creative_ids)),
                    force_retry=force_html_thumbnail_retry,
                    creative_ids=creative_ids,
                )
            except Exception as e:
                logger.warning("HTML thumbnail refresh failed: %s", e)
                result.html_thumbnails = {
                    "processed": 0,
                    "success": 0,
                    "failed": 0,
                    "no_image_found": 0,
                    "message": f"HTML thumbnail refresh failed: {e}",
                }

        return result
