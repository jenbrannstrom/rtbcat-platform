"""Buyer seats client for discovering multi-seat buyer accounts.

This module provides the BuyerSeatsClient class for enumerating and managing
buyer accounts in the Google Authorized Buyers RTB API.

API Reference:
    https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/buyers
"""

import logging
from typing import AsyncIterator, Optional

from googleapiclient.errors import HttpError

from collectors.base import BaseAuthorizedBuyersClient
from storage.sqlite_store import BuyerSeat

logger = logging.getLogger(__name__)


class BuyerSeatsClient(BaseAuthorizedBuyersClient):
    """Client for discovering buyer seats accessible to the service account.

    This client handles buyer seat enumeration with automatic pagination
    and rate limit handling. Uses the buyers.list() endpoint at the API root.

    Example:
        >>> client = BuyerSeatsClient(
        ...     credentials_path="/path/to/credentials.json",
        ...     account_id="123456789"  # bidder_id
        ... )
        >>> seats = await client.discover_buyer_seats()
        >>> for seat in seats:
        ...     print(f"{seat.buyer_id}: {seat.display_name}")

    API Reference:
        https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/buyers
    """

    async def discover_buyer_seats(self) -> list[BuyerSeat]:
        """Enumerate all buyer accounts accessible to the service account.

        Uses buyers.list() at root level to discover all buyer seats.
        The API returns buyers that the authenticated service account has access to.

        Returns:
            List of BuyerSeat objects for each accessible buyer.

        Raises:
            HttpError: If the API request fails after retries.

        Example:
            >>> seats = await client.discover_buyer_seats()
            >>> print(f"Found {len(seats)} buyer seats")
        """
        service = self._get_service()
        page_token: Optional[str] = None
        seats: list[BuyerSeat] = []

        while True:
            # buyers.list() is at root level and doesn't require a parent param
            request_params: dict = {
                "pageSize": self.page_size,
            }

            if page_token:
                request_params["pageToken"] = page_token

            try:
                params = request_params.copy()
                response = await self._execute_with_retry(
                    lambda p=params: service.buyers().list(**p)
                )

                buyers = response.get("buyers", [])
                for buyer_data in buyers:
                    seat = self._parse_buyer_response(buyer_data)
                    seats.append(seat)
                    logger.debug(f"Found buyer seat: {seat.buyer_id} - {seat.display_name}")

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as ex:
                logger.error(
                    f"Authorized Buyers API error: {ex.resp.status} - {ex.reason}"
                )
                raise

        logger.info(f"Discovered {len(seats)} buyer seats under bidder {self.account_id}")
        return seats

    async def get_buyer_info(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get details for a specific buyer account.

        Args:
            buyer_id: The buyer account ID (not the full resource name).

        Returns:
            BuyerSeat if found, None if the buyer doesn't exist.

        Raises:
            HttpError: If the API request fails (except 404).

        Example:
            >>> seat = await client.get_buyer_info("456")
            >>> if seat:
            ...     print(f"Found: {seat.display_name}")
        """
        service = self._get_service()
        name = f"buyers/{buyer_id}"

        try:
            response = await self._execute_with_retry(
                lambda: service.buyers().get(name=name)
            )
            return self._parse_buyer_response(response)

        except HttpError as ex:
            if ex.resp.status == 404:
                logger.debug(f"Buyer {buyer_id} not found")
                return None
            logger.error(
                f"Failed to fetch buyer {buyer_id}: "
                f"{ex.resp.status} - {ex.reason}"
            )
            raise

    def _parse_buyer_response(self, data: dict) -> BuyerSeat:
        """Parse a buyer API response into a BuyerSeat object.

        Args:
            data: Raw buyer data from the API.

        Returns:
            BuyerSeat object populated with buyer information.
        """
        # Extract buyer_id from resource name (e.g., "buyers/456" -> "456")
        name = data.get("name", "")
        buyer_id = name.split("/")[-1] if "/" in name else name

        # Extract bidder_id from bidder field (e.g., "bidders/299038253" -> "299038253")
        # This is more reliable than using the value passed to the constructor
        bidder = data.get("bidder", "")
        bidder_id = bidder.split("/")[-1] if "/" in bidder else self.account_id

        # Get display name, falling back to buyer_id
        display_name = data.get("displayName") or f"Buyer {buyer_id}"

        # Check if active (state == "ACTIVE")
        state = data.get("state", "ACTIVE")
        active = state == "ACTIVE"

        return BuyerSeat(
            buyer_id=buyer_id,
            bidder_id=bidder_id,
            display_name=display_name,
            active=active,
            creative_count=0,  # Will be updated after syncing
            last_synced=None,
            created_at=None,
        )

    async def iter_buyer_seats(self) -> AsyncIterator[BuyerSeat]:
        """Iterate over buyer seats with streaming support.

        Yields BuyerSeat objects as they are discovered, useful for
        processing large numbers of seats without loading all into memory.

        Yields:
            BuyerSeat for each buyer found.

        Example:
            >>> async for seat in client.iter_buyer_seats():
            ...     print(f"Processing {seat.buyer_id}")
        """
        service = self._get_service()
        page_token: Optional[str] = None

        while True:
            # buyers.list() is at root level and doesn't require a parent param
            request_params: dict = {
                "pageSize": self.page_size,
            }

            if page_token:
                request_params["pageToken"] = page_token

            try:
                params = request_params.copy()
                response = await self._execute_with_retry(
                    lambda p=params: service.buyers().list(**p)
                )

                buyers = response.get("buyers", [])
                for buyer_data in buyers:
                    yield self._parse_buyer_response(buyer_data)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as ex:
                logger.error(
                    f"Authorized Buyers API error: {ex.resp.status} - {ex.reason}"
                )
                raise
