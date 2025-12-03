"""Base client for Google Authorized Buyers Real-Time Bidding API.

This module provides the base class with authentication, service initialization,
and retry logic that is shared across all specialized clients.
"""

import asyncio
import logging
import time
from typing import Callable, Optional, TypeVar

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Authorized Buyers API scopes
AUTHORIZED_BUYERS_SCOPE = "https://www.googleapis.com/auth/realtime-bidding"
ADEXCHANGE_BUYER_SCOPE = "https://www.googleapis.com/auth/adexchange.buyer"

# Combined scopes for full functionality
ALL_SCOPES = [AUTHORIZED_BUYERS_SCOPE, ADEXCHANGE_BUYER_SCOPE]

T = TypeVar("T")


class BaseAuthorizedBuyersClient:
    """Base async client for Google Authorized Buyers Real-Time Bidding API.

    This class handles service account authentication and provides common
    functionality for API interactions with proper rate limiting and error handling.

    Attributes:
        account_id: The Authorized Buyers bidder account ID.
        page_size: Number of results per API page (default: 100).
        max_retries: Maximum retry attempts for rate-limited requests.
        base_delay: Base delay in seconds for exponential backoff.

    Example:
        >>> class MyClient(BaseAuthorizedBuyersClient):
        ...     async def fetch_data(self):
        ...         service = self._get_service()
        ...         return await self._execute_with_retry(
        ...             lambda: service.bidders().get(name=self.parent)
        ...         )
    """

    DEFAULT_PAGE_SIZE = 100
    API_SERVICE_NAME = "realtimebidding"
    API_VERSION = "v1"
    MAX_RETRIES = 5
    BASE_DELAY = 1.0

    def __init__(
        self,
        credentials_path: str,
        account_id: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_retries: int = MAX_RETRIES,
        base_delay: float = BASE_DELAY,
    ) -> None:
        """Initialize the Authorized Buyers client.

        Args:
            credentials_path: Path to service account JSON credentials file.
            account_id: Authorized Buyers bidder account ID.
            page_size: Number of results per API page (1-100).
            max_retries: Maximum retry attempts for rate-limited requests.
            base_delay: Base delay in seconds for exponential backoff.

        Raises:
            ValueError: If account_id is empty.
        """
        if not account_id:
            raise ValueError("account_id is required")

        self.account_id = account_id
        self.page_size = min(max(1, page_size), 100)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._credentials_path = credentials_path
        self._service = None

    def _get_service(self):
        """Lazy initialization of the RTB API service.

        Returns:
            Google API client service object for realtimebidding v1.

        Raises:
            google.auth.exceptions.DefaultCredentialsError: If credentials invalid.
        """
        if self._service is None:
            credentials = service_account.Credentials.from_service_account_file(
                self._credentials_path,
                scopes=[AUTHORIZED_BUYERS_SCOPE],
            )
            self._service = build(
                self.API_SERVICE_NAME,
                self.API_VERSION,
                credentials=credentials,
                cache_discovery=False,
            )
        return self._service

    @property
    def parent(self) -> str:
        """The parent resource name for API calls.

        Returns:
            Resource name in format 'bidders/{account_id}'.
        """
        return f"bidders/{self.account_id}"

    async def _execute_with_retry(self, request_func: Callable) -> dict:
        """Execute an API request with exponential backoff for rate limits.

        Implements retry logic for HTTP 429 (rate limit) errors with
        exponential backoff and jitter.

        Args:
            request_func: A callable that returns an API request to execute.

        Returns:
            The API response dictionary.

        Raises:
            HttpError: If request fails after all retries or non-retryable error.
        """
        loop = asyncio.get_event_loop()
        last_error: Optional[HttpError] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: request_func().execute(),
                )
                return response

            except HttpError as ex:
                last_error = ex

                # Only retry on rate limit errors (429)
                if ex.resp.status != 429:
                    raise

                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    delay = self.base_delay * (2**attempt)
                    jitter = delay * 0.1 * (0.5 - time.time() % 1)
                    wait_time = delay + jitter

                    logger.warning(
                        f"Rate limited (429). Retry {attempt + 1}/{self.max_retries} "
                        f"after {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Rate limit exceeded after {self.max_retries} retries"
                    )
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected state in retry logic")

    async def get_bidder_info(self) -> dict:
        """Get information about the bidder account.

        Returns:
            Bidder account information dictionary.

        Raises:
            HttpError: If the API request fails.
        """
        service = self._get_service()

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: service.bidders().get(name=self.parent).execute(),
            )
            return response

        except HttpError as ex:
            logger.error(f"Failed to get bidder info: {ex}")
            raise
