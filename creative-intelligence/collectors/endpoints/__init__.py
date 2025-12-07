"""RTB Endpoints collector module.

This module provides the EndpointsClient for fetching RTB endpoint
configurations from the Google Authorized Buyers API.

Example:
    >>> from collectors.endpoints import EndpointsClient
    >>>
    >>> client = EndpointsClient(
    ...     credentials_path='~/.catscan/service-account.json',
    ...     account_id='12345'
    ... )
    >>> endpoints = await client.list_endpoints()
"""

from collectors.endpoints.client import EndpointsClient
from collectors.endpoints.schemas import EndpointDict

__all__ = [
    "EndpointsClient",
    "EndpointDict",
]
