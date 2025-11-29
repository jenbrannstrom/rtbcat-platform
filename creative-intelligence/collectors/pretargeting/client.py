"""Pretargeting-specific client for Authorized Buyers RTB API.

This module provides the PretargetingClient class for fetching and managing
pretargeting configurations from the Google Authorized Buyers RTB API.
"""

import logging
from typing import Optional

from googleapiclient.errors import HttpError

from collectors.base import BaseAuthorizedBuyersClient
from collectors.pretargeting.parsers import parse_pretargeting_config
from collectors.pretargeting.schemas import PretargetingConfigDict

logger = logging.getLogger(__name__)


class PretargetingClient(BaseAuthorizedBuyersClient):
    """Client for fetching pretargeting configs from Authorized Buyers RTB API.

    This client handles pretargeting configuration retrieval with
    proper error handling and rate limiting.

    Example:
        >>> client = PretargetingClient(
        ...     credentials_path="/path/to/credentials.json",
        ...     account_id="123456789"
        ... )
        >>> configs = await client.fetch_all_pretargeting_configs()
        >>> for config in configs:
        ...     print(f"{config['configId']}: {config['displayName']}")

    API Reference:
        https://developers.google.com/authorized-buyers/apis/reference/rest/v1/bidders.pretargetingConfigs
    """

    async def fetch_all_pretargeting_configs(self) -> list[PretargetingConfigDict]:
        """Fetch all pretargeting configurations for the account.

        Retrieves all pretargeting configs from the Authorized Buyers API.

        Returns:
            List of PretargetingConfigDict objects.

        Raises:
            HttpError: If the API request fails.

        Example:
            >>> configs = await client.fetch_all_pretargeting_configs()
            >>> print(f"Found {len(configs)} pretargeting configs")
        """
        service = self._get_service()

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders()
                .pretargetingConfigs()
                .list(parent=self.parent)
            )

            raw_configs = response.get("pretargetingConfigs", [])
            return [parse_pretargeting_config(config) for config in raw_configs]

        except HttpError as ex:
            logger.error(
                f"Failed to list pretargeting configs: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    async def get_pretargeting_config_by_id(
        self, config_id: str
    ) -> Optional[PretargetingConfigDict]:
        """Fetch a single pretargeting configuration by ID.

        Args:
            config_id: The config ID to fetch (not the full resource name).

        Returns:
            PretargetingConfigDict if found, None if doesn't exist.

        Raises:
            HttpError: If the API request fails (except 404).

        Example:
            >>> config = await client.get_pretargeting_config_by_id("123")
            >>> if config:
            ...     print(f"Found: {config['displayName']}")
        """
        service = self._get_service()
        name = f"{self.parent}/pretargetingConfigs/{config_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders().pretargetingConfigs().get(name=name)
            )
            return parse_pretargeting_config(response)

        except HttpError as ex:
            if ex.resp.status == 404:
                logger.debug(f"Pretargeting config {config_id} not found")
                return None
            logger.error(
                f"Failed to fetch pretargeting config {config_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise
