"""Creative-specific client for Authorized Buyers RTB API.

This module provides the CreativesClient class for fetching and managing
creative data from the Google Authorized Buyers Real-Time Bidding API.
"""

import logging
from typing import AsyncIterator, Optional

from googleapiclient.errors import HttpError

from collectors.base import BaseAuthorizedBuyersClient
from collectors.creatives.parsers import parse_creative_response
from collectors.creatives.schemas import CreativeDict

logger = logging.getLogger(__name__)


class CreativesClient(BaseAuthorizedBuyersClient):
    """Client for fetching creatives from Authorized Buyers RTB API.

    This client handles creative retrieval with automatic pagination
    and rate limit handling.

    Example:
        >>> client = CreativesClient(
        ...     credentials_path="/path/to/credentials.json",
        ...     account_id="123456789"
        ... )
        >>> creatives = await client.fetch_all_creatives()
        >>> for c in creatives:
        ...     print(f"{c['creativeId']}: {c['format']}")

    API Reference:
        https://developers.google.com/authorized-buyers/apis/reference/rest/v1/bidders.creatives
    """

    async def fetch_creatives(
        self,
        filter_query: Optional[str] = None,
        view: str = "FULL",
    ) -> AsyncIterator[CreativeDict]:
        """Fetch creatives with pagination support.

        Retrieves creatives from the Authorized Buyers API with automatic
        pagination and rate limit handling.

        Args:
            filter_query: Optional filter string for the API.
                Example: 'creativeServingDecision.networkPolicyCompliance.status=APPROVED'
            view: View type - 'FULL' for all fields or 'SERVING_DECISION_ONLY'.

        Yields:
            CreativeDict for each creative found.

        Raises:
            HttpError: If the API request fails after retries.

        Example:
            >>> async for creative in client.fetch_creatives():
            ...     print(f"{creative['creativeId']}: {creative['format']}")
        """
        service = self._get_service()
        page_token: Optional[str] = None

        while True:
            request_params: dict = {
                "parent": self.parent,
                "pageSize": self.page_size,
                "view": view,
            }

            if page_token:
                request_params["pageToken"] = page_token

            if filter_query:
                request_params["filter"] = filter_query

            try:
                params = request_params.copy()
                response = await self._execute_with_retry(
                    lambda p=params: service.bidders().creatives().list(**p)
                )

                creatives = response.get("creatives", [])
                for creative_data in creatives:
                    yield parse_creative_response(creative_data, self.account_id)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as ex:
                logger.error(
                    f"Authorized Buyers API error: {ex.resp.status} - {ex.reason}"
                )
                raise

    async def fetch_all_creatives(
        self,
        filter_query: Optional[str] = None,
    ) -> list[CreativeDict]:
        """Fetch all creatives as a list.

        Convenience method that collects all creatives from the async iterator
        into a single list. Use fetch_creatives() for memory-efficient streaming.

        Args:
            filter_query: Optional filter string for the API.

        Returns:
            List of all CreativeDict objects matching the filter.

        Example:
            >>> creatives = await client.fetch_all_creatives()
            >>> print(f"Found {len(creatives)} creatives")
        """
        creatives: list[CreativeDict] = []
        async for creative in self.fetch_creatives(filter_query):
            creatives.append(creative)
        return creatives

    async def get_creative_by_id(self, creative_id: str) -> Optional[CreativeDict]:
        """Fetch a single creative by ID.

        Args:
            creative_id: The creative ID to fetch (not the full resource name).

        Returns:
            CreativeDict if found, None if the creative doesn't exist.

        Raises:
            HttpError: If the API request fails (except 404).

        Example:
            >>> creative = await client.get_creative_by_id("abc123xyz")
            >>> if creative:
            ...     print(f"Found: {creative['format']} creative")
        """
        service = self._get_service()
        name = f"{self.parent}/creatives/{creative_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders().creatives().get(name=name)
            )
            return parse_creative_response(response, self.account_id)

        except HttpError as ex:
            if ex.resp.status == 404:
                logger.debug(f"Creative {creative_id} not found")
                return None
            logger.error(
                f"Failed to fetch creative {creative_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise
