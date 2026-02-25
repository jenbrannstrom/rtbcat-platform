"""RTB Endpoints client for Authorized Buyers RTB API.

This module provides the EndpointsClient class for fetching and managing
RTB endpoint configurations from the Google Authorized Buyers Real-Time Bidding API.

API Reference:
    https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/bidders.endpoints
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from googleapiclient.errors import HttpError

from collectors.base import BaseAuthorizedBuyersClient
from collectors.endpoints.schemas import EndpointDict

logger = logging.getLogger(__name__)


def parse_endpoint_response(endpoint_data: dict) -> EndpointDict:
    """Convert an API response to normalized EndpointDict.

    Args:
        endpoint_data: Raw endpoint resource from the API.

    Returns:
        EndpointDict with normalized data.

    Example:
        >>> raw = {"name": "bidders/123/endpoints/456", "url": "https://bid.example.com"}
        >>> endpoint = parse_endpoint_response(raw)
        >>> endpoint["endpointId"]
        '456'
    """
    name = endpoint_data.get("name", "")
    parts = name.split("/")
    endpoint_id = parts[-1] if len(parts) >= 4 else ""

    # Google API returns maximumQps as string (int64 format); normalise to int|None
    raw_qps = endpoint_data.get("maximumQps")
    if raw_qps is not None:
        try:
            raw_qps = int(raw_qps)
        except (TypeError, ValueError):
            raw_qps = None

    return EndpointDict(
        endpointId=endpoint_id,
        name=name,
        url=endpoint_data.get("url", ""),
        maximumQps=raw_qps,
        tradingLocation=endpoint_data.get("tradingLocation", "TRADING_LOCATION_UNSPECIFIED"),
        bidProtocol=endpoint_data.get("bidProtocol", "BID_PROTOCOL_UNSPECIFIED"),
        collectedAt=datetime.now(timezone.utc).isoformat(),
        source="authorized_buyers_api",
    )


class EndpointsClient(BaseAuthorizedBuyersClient):
    """Client for fetching RTB endpoints from Authorized Buyers RTB API.

    This client handles endpoint retrieval with proper error handling
    and rate limiting.

    Example:
        >>> client = EndpointsClient(
        ...     credentials_path="/path/to/credentials.json",
        ...     account_id="123456789"
        ... )
        >>> endpoints = await client.list_endpoints()
        >>> for ep in endpoints:
        ...     print(f"{ep['endpointId']}: {ep['url']} ({ep['maximumQps']} QPS)")

    API Reference:
        https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/bidders.endpoints
    """

    async def list_endpoints(self) -> list[EndpointDict]:
        """Fetch all RTB endpoints for the bidder account.

        Retrieves all endpoint configurations from the Authorized Buyers API.

        Returns:
            List of EndpointDict objects.

        Raises:
            HttpError: If the API request fails.

        Example:
            >>> endpoints = await client.list_endpoints()
            >>> print(f"Found {len(endpoints)} RTB endpoints")
        """
        service = self._get_service()

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders().endpoints().list(parent=self.parent)
            )

            raw_endpoints = response.get("endpoints", [])
            return [parse_endpoint_response(ep) for ep in raw_endpoints]

        except HttpError as ex:
            logger.error(
                f"Failed to list RTB endpoints: {ex.resp.status} - {ex.reason}"
            )
            raise

    async def patch_endpoint(self, endpoint_id: str, maximum_qps: int) -> EndpointDict:
        """Update the maximum QPS for an RTB endpoint.

        Args:
            endpoint_id: The endpoint ID to update.
            maximum_qps: New QPS limit (>= 0).

        Returns:
            Updated EndpointDict.

        Raises:
            HttpError: If the API request fails.
        """
        service = self._get_service()
        name = f"{self.parent}/endpoints/{endpoint_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders().endpoints().patch(
                    name=name,
                    body={"maximumQps": str(maximum_qps)},
                    updateMask="maximumQps",
                )
            )
            return parse_endpoint_response(response)

        except HttpError as ex:
            logger.error(
                f"Failed to patch endpoint {endpoint_id} QPS to {maximum_qps}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    async def get_endpoint(self, endpoint_id: str) -> Optional[EndpointDict]:
        """Fetch a single RTB endpoint by ID.

        Args:
            endpoint_id: The endpoint ID to fetch (not the full resource name).

        Returns:
            EndpointDict if found, None if doesn't exist.

        Raises:
            HttpError: If the API request fails (except 404).

        Example:
            >>> endpoint = await client.get_endpoint("456")
            >>> if endpoint:
            ...     print(f"URL: {endpoint['url']}, QPS: {endpoint['maximumQps']}")
        """
        service = self._get_service()
        name = f"{self.parent}/endpoints/{endpoint_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.bidders().endpoints().get(name=name)
            )
            return parse_endpoint_response(response)

        except HttpError as ex:
            if ex.resp.status == 404:
                logger.debug(f"Endpoint {endpoint_id} not found")
                return None
            logger.error(
                f"Failed to fetch endpoint {endpoint_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise
