"""RTBcat Creative Intelligence - Collectors Module.

This module provides data collection capabilities for Authorized Buyers
creatives, pretargeting configurations, RTB endpoints, and CSV report processing.

Example:
    >>> from collectors import CreativesClient, PretargetingClient, EndpointsClient
    >>>
    >>> # Fetch creatives
    >>> creative_client = CreativesClient(
    ...     credentials_path='~/.rtbcat/service-account.json',
    ...     account_id='12345'
    ... )
    >>> creatives = await creative_client.fetch_all_creatives()
    >>>
    >>> # Fetch pretargeting configs
    >>> pretargeting_client = PretargetingClient(
    ...     credentials_path='~/.rtbcat/service-account.json',
    ...     account_id='12345'
    ... )
    >>> configs = await pretargeting_client.fetch_all_pretargeting_configs()
    >>>
    >>> # Fetch RTB endpoints
    >>> endpoints_client = EndpointsClient(
    ...     credentials_path='~/.rtbcat/service-account.json',
    ...     account_id='12345'
    ... )
    >>> endpoints = await endpoints_client.list_endpoints()
"""

from collectors.base import BaseAuthorizedBuyersClient
from collectors.creatives.client import CreativesClient
from collectors.creatives.schemas import CreativeDict
from collectors.csv_reports import GmailCSVFetcher
from collectors.endpoints.client import EndpointsClient
from collectors.endpoints.schemas import EndpointDict
from collectors.pretargeting.client import PretargetingClient
from collectors.pretargeting.schemas import PretargetingConfigDict
from collectors.seats import BuyerSeatsClient

__all__ = [
    # Clients
    "CreativesClient",
    "PretargetingClient",
    "EndpointsClient",
    "BuyerSeatsClient",
    "BaseAuthorizedBuyersClient",
    "GmailCSVFetcher",
    # Schemas
    "CreativeDict",
    "PretargetingConfigDict",
    "EndpointDict",
]
