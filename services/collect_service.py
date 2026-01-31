"""Service layer for creative collection."""

from __future__ import annotations

from typing import Any

from collectors import CreativesClient
from storage import creative_dicts_to_storage


class CollectService:
    """Orchestrates collection and storage of creatives."""

    async def collect_and_save(
        self,
        credentials_path: str,
        account_id: str,
        filter_query: str | None,
        store: Any,
    ) -> tuple[int, int]:
        """Fetch creatives from API and persist to storage.

        Returns (fetched_count, saved_count).
        """
        client = CreativesClient(
            credentials_path=credentials_path,
            account_id=account_id,
        )

        api_creatives = await client.fetch_all_creatives(filter_query=filter_query)
        storage_creatives = creative_dicts_to_storage(api_creatives)
        saved_count = await store.save_creatives(storage_creatives)
        return len(api_creatives), saved_count
