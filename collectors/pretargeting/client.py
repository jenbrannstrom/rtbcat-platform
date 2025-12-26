"""Pretargeting-specific client for Authorized Buyers RTB API.

This module provides the PretargetingClient class for fetching and managing
pretargeting configurations from the Google Authorized Buyers RTB API.

Supports both read and write operations:
- Read: list, get pretargeting configs
- Write: patch, activate, suspend configs
"""

import logging
from typing import Any, Optional

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

    # =========================================================================
    # Write Operations
    # =========================================================================

    async def patch_pretargeting_config(
        self,
        config_id: str,
        update_body: dict[str, Any],
        update_mask: Optional[str] = None,
    ) -> PretargetingConfigDict:
        """Update a pretargeting configuration.

        Patches specific fields of an existing pretargeting config.
        Only fields specified in the update_mask will be modified.

        Args:
            config_id: The config ID to update (not the full resource name).
            update_body: Dictionary of fields to update.
            update_mask: Comma-separated field paths to update. If not provided,
                         all fields in update_body will be updated.

        Returns:
            Updated PretargetingConfigDict.

        Raises:
            HttpError: If the API request fails.

        Example:
            >>> # Add a creative size
            >>> updated = await client.patch_pretargeting_config(
            ...     config_id="123",
            ...     update_body={
            ...         "includedCreativeDimensions": [
            ...             {"width": 300, "height": 250},
            ...             {"width": 728, "height": 90}
            ...         ]
            ...     },
            ...     update_mask="includedCreativeDimensions"
            ... )

        API Reference:
            https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/bidders.pretargetingConfigs/patch
        """
        service = self._get_service()
        name = f"{self.parent}/pretargetingConfigs/{config_id}"

        try:
            request_params: dict[str, Any] = {
                "name": name,
                "body": update_body,
            }
            if update_mask:
                request_params["updateMask"] = update_mask

            response = await self._execute_with_retry(
                lambda: service.bidders()
                .pretargetingConfigs()
                .patch(**request_params)
            )

            logger.info(f"Successfully patched pretargeting config {config_id}")
            return parse_pretargeting_config(response)

        except HttpError as ex:
            logger.error(
                f"Failed to patch pretargeting config {config_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    async def activate_pretargeting_config(
        self, config_id: str
    ) -> PretargetingConfigDict:
        """Activate a suspended pretargeting configuration.

        Changes the state from SUSPENDED to ACTIVE.

        Args:
            config_id: The config ID to activate (not the full resource name).

        Returns:
            Updated PretargetingConfigDict with state=ACTIVE.

        Raises:
            HttpError: If the API request fails.

        Example:
            >>> config = await client.activate_pretargeting_config("123")
            >>> print(f"Config {config['configId']} is now {config['state']}")
        """
        service = self._get_service()
        name = f"{self.parent}/pretargetingConfigs/{config_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders()
                .pretargetingConfigs()
                .activate(name=name, body={})
            )

            logger.info(f"Successfully activated pretargeting config {config_id}")
            return parse_pretargeting_config(response)

        except HttpError as ex:
            logger.error(
                f"Failed to activate pretargeting config {config_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    async def suspend_pretargeting_config(
        self, config_id: str
    ) -> PretargetingConfigDict:
        """Suspend an active pretargeting configuration.

        Changes the state from ACTIVE to SUSPENDED.

        Args:
            config_id: The config ID to suspend (not the full resource name).

        Returns:
            Updated PretargetingConfigDict with state=SUSPENDED.

        Raises:
            HttpError: If the API request fails.

        Example:
            >>> config = await client.suspend_pretargeting_config("123")
            >>> print(f"Config {config['configId']} is now {config['state']}")
        """
        service = self._get_service()
        name = f"{self.parent}/pretargetingConfigs/{config_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders()
                .pretargetingConfigs()
                .suspend(name=name, body={})
            )

            logger.info(f"Successfully suspended pretargeting config {config_id}")
            return parse_pretargeting_config(response)

        except HttpError as ex:
            logger.error(
                f"Failed to suspend pretargeting config {config_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    async def add_sizes_to_config(
        self, config_id: str, sizes: list[dict[str, int]]
    ) -> PretargetingConfigDict:
        """Add creative sizes to a pretargeting configuration.

        Convenience method that fetches current sizes, adds new ones,
        and patches the config.

        Args:
            config_id: The config ID to update.
            sizes: List of sizes to add, e.g., [{"width": 300, "height": 250}]

        Returns:
            Updated PretargetingConfigDict.

        Example:
            >>> config = await client.add_sizes_to_config(
            ...     "123",
            ...     [{"width": 300, "height": 250}, {"width": 728, "height": 90}]
            ... )
        """
        # Get current config
        current = await self.get_pretargeting_config_by_id(config_id)
        if not current:
            raise ValueError(f"Pretargeting config {config_id} not found")

        # Merge sizes (avoid duplicates)
        current_sizes = current.get("includedCreativeDimensions", [])
        existing_set = {(s["width"], s["height"]) for s in current_sizes}

        new_sizes = list(current_sizes)
        for size in sizes:
            if (size["width"], size["height"]) not in existing_set:
                new_sizes.append(size)

        return await self.patch_pretargeting_config(
            config_id=config_id,
            update_body={"includedCreativeDimensions": new_sizes},
            update_mask="includedCreativeDimensions",
        )

    async def remove_sizes_from_config(
        self, config_id: str, sizes: list[dict[str, int]]
    ) -> PretargetingConfigDict:
        """Remove creative sizes from a pretargeting configuration.

        Args:
            config_id: The config ID to update.
            sizes: List of sizes to remove, e.g., [{"width": 728, "height": 90}]

        Returns:
            Updated PretargetingConfigDict.

        Example:
            >>> config = await client.remove_sizes_from_config(
            ...     "123",
            ...     [{"width": 728, "height": 90}]
            ... )
        """
        # Get current config
        current = await self.get_pretargeting_config_by_id(config_id)
        if not current:
            raise ValueError(f"Pretargeting config {config_id} not found")

        # Remove specified sizes
        sizes_to_remove = {(s["width"], s["height"]) for s in sizes}
        current_sizes = current.get("includedCreativeDimensions", [])

        new_sizes = [
            s for s in current_sizes
            if (s["width"], s["height"]) not in sizes_to_remove
        ]

        return await self.patch_pretargeting_config(
            config_id=config_id,
            update_body={"includedCreativeDimensions": new_sizes},
            update_mask="includedCreativeDimensions",
        )

    async def add_geos_to_config(
        self, config_id: str, geo_ids: list[str], exclude: bool = False
    ) -> PretargetingConfigDict:
        """Add geographic targeting to a pretargeting configuration.

        Args:
            config_id: The config ID to update.
            geo_ids: List of geo criterion IDs to add.
            exclude: If True, add to excludedIds. If False, add to includedIds.

        Returns:
            Updated PretargetingConfigDict.

        Example:
            >>> # Include USA (geo ID 2840)
            >>> config = await client.add_geos_to_config("123", ["2840"])
            >>> # Exclude China (geo ID 2156)
            >>> config = await client.add_geos_to_config("123", ["2156"], exclude=True)
        """
        current = await self.get_pretargeting_config_by_id(config_id)
        if not current:
            raise ValueError(f"Pretargeting config {config_id} not found")

        geo_targeting = current.get("geoTargeting", {}) or {}
        included = list(geo_targeting.get("includedIds", []))
        excluded = list(geo_targeting.get("excludedIds", []))

        if exclude:
            excluded = list(set(excluded + geo_ids))
        else:
            included = list(set(included + geo_ids))

        new_geo = {"includedIds": included, "excludedIds": excluded}

        return await self.patch_pretargeting_config(
            config_id=config_id,
            update_body={"geoTargeting": new_geo},
            update_mask="geoTargeting",
        )

    async def remove_geos_from_config(
        self, config_id: str, geo_ids: list[str], from_excluded: bool = False
    ) -> PretargetingConfigDict:
        """Remove geographic targeting from a pretargeting configuration.

        Args:
            config_id: The config ID to update.
            geo_ids: List of geo criterion IDs to remove.
            from_excluded: If True, remove from excludedIds. If False, from includedIds.

        Returns:
            Updated PretargetingConfigDict.
        """
        current = await self.get_pretargeting_config_by_id(config_id)
        if not current:
            raise ValueError(f"Pretargeting config {config_id} not found")

        geo_targeting = current.get("geoTargeting", {}) or {}
        included = list(geo_targeting.get("includedIds", []))
        excluded = list(geo_targeting.get("excludedIds", []))
        geo_set = set(geo_ids)

        if from_excluded:
            excluded = [g for g in excluded if g not in geo_set]
        else:
            included = [g for g in included if g not in geo_set]

        new_geo = {"includedIds": included, "excludedIds": excluded}

        return await self.patch_pretargeting_config(
            config_id=config_id,
            update_body={"geoTargeting": new_geo},
            update_mask="geoTargeting",
        )
