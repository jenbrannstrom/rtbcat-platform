"""
RTB Troubleshooting API Client

Uses Ad Exchange Buyer II API (v2beta1) to fetch:
- Filtered bid reasons (WHY bids were rejected)
- Bid metrics (funnel from bids to wins)
- Callout status metrics (how requests reached bidder)

This is the GOLD for understanding QPS waste - it tells you exactly
why your bids are being filtered before auction.
"""

from googleapiclient.discovery import build
from google.oauth2 import service_account
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from collectors.base import ADEXCHANGE_BUYER_SCOPE

logger = logging.getLogger(__name__)


# Reference: Creative Status Codes
CREATIVE_STATUS_CODES = {
    1: "CREATIVE_NOT_SUBMITTED",
    2: "CREATIVE_PENDING_REVIEW",
    3: "CREATIVE_APPROVED",
    4: "CREATIVE_DISAPPROVED",
    5: "CREATIVE_NOT_APPROVED",  # Different from disapproved - just not yet approved
    79: "CREATIVE_BLOCKED",
    80: "CREATIVE_PENDING_SUBMISSION",
}

# Reference: Callout Status Codes
CALLOUT_STATUS_CODES = {
    1: "SUCCESS",
    2: "NO_BID",
    3: "EMPTY_RESPONSE",
    4: "HTTP_ERROR",
    5: "RESPONSE_TOO_LARGE",
    6: "TIMEOUT",
    7: "BAD_REQUEST",
    8: "CONNECTION_ERROR",
    9: "NO_COOKIE_MATCH",
}


class TroubleshootingClient:
    """
    Client for Google Ad Exchange Buyer II API troubleshooting endpoints.

    Filter Sets are required containers for querying metrics.
    We create one filter set per query configuration.

    Example:
        >>> client = TroubleshootingClient(
        ...     credentials_path="/path/to/creds.json",
        ...     bidder_id="299038253"
        ... )
        >>> metrics = client.collect_all_metrics(days=7)
        >>> print(metrics["filtered_bids"])
    """

    def __init__(self, credentials_path: str, bidder_id: str):
        """
        Initialize the troubleshooting client.

        Args:
            credentials_path: Path to service account JSON
            bidder_id: Your bidder account ID (e.g., "299038253")
        """
        self.bidder_id = bidder_id

        # Load credentials with required scope
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[ADEXCHANGE_BUYER_SCOPE]
        )

        # Build the service client
        self.service = build(
            'adexchangebuyer2',
            'v2beta1',
            credentials=credentials,
            cache_discovery=False
        )

        # Parent path for API calls
        self.parent = f"bidders/{self.bidder_id}"

    def create_filter_set(
        self,
        name: str,
        environment: str = None,       # "APP" or "WEB"
        platforms: List[str] = None,   # ["DESKTOP", "MOBILE", "TABLET"]
        formats: List[str] = None,     # ["NATIVE_DISPLAY", "NATIVE_VIDEO", "NON_NATIVE_DISPLAY", "NON_NATIVE_VIDEO"]
        time_series_granularity: str = "DAILY",
        relative_date_range: Dict = None,  # {"offsetDays": 1, "durationDays": 7}
        absolute_date_range: Dict = None,  # {"startDate": {...}, "endDate": {...}}
        is_transient: bool = True
    ) -> Dict:
        """
        Create a filter set for querying troubleshooting metrics.

        Filter sets define the dimensions for metric queries.
        Transient filter sets are not persisted (use for ad-hoc queries).

        Args:
            name: Unique identifier for this filter set
            environment: Filter by APP or WEB
            platforms: Filter by device types
            formats: Filter by creative formats
            time_series_granularity: HOURLY or DAILY
            relative_date_range: Relative date range (preferred)
            absolute_date_range: Absolute date range
            is_transient: If True, filter set is not saved server-side

        Returns:
            Created filter set object
        """
        filter_set = {
            "name": f"{self.parent}/filterSets/{name}",
            "timeSeriesGranularity": time_series_granularity,
        }

        # Add optional filters
        if environment:
            filter_set["environment"] = environment
        if platforms:
            filter_set["platforms"] = platforms
        if formats:
            filter_set["formats"] = formats

        # Date range (one of these required)
        if relative_date_range:
            filter_set["relativeDateRange"] = relative_date_range
        elif absolute_date_range:
            filter_set["absoluteDateRange"] = absolute_date_range
        else:
            # Default: last 7 days
            filter_set["relativeDateRange"] = {
                "offsetDays": 1,  # Start from yesterday (today incomplete)
                "durationDays": 7
            }

        try:
            result = self.service.bidders().filterSets().create(
                ownerName=self.parent,
                isTransient=is_transient,
                body=filter_set
            ).execute()

            logger.info(f"Created filter set: {result.get('name')}")
            return result

        except Exception as e:
            logger.error(f"Failed to create filter set: {e}")
            raise

    def get_filtered_bid_requests(self, filter_set_name: str) -> List[Dict]:
        """
        Get filtered bid request metrics - shows WHY bids were filtered.

        This is the GOLD for understanding QPS waste.

        Returns list of:
        {
            "calloutStatusId": 1,  # Lookup in CALLOUT_STATUS_CODES
            "impressions": {"value": "12345"},
            "bids": {"value": "10000"},
            ...
        }

        Key status codes to watch:
        - 1: Successful response
        - 2: No bid
        - 6: Timeout
        - 7: Bad request
        """
        try:
            results = []
            request = self.service.bidders().filterSets().filteredBidRequests().list(
                filterSetName=filter_set_name
            )

            while request is not None:
                response = request.execute()
                results.extend(response.get('calloutStatusRows', []))
                request = self.service.bidders().filterSets().filteredBidRequests().list_next(
                    request, response
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get filtered bid requests: {e}")
            raise

    def get_filtered_bids(self, filter_set_name: str) -> List[Dict]:
        """
        Get filtered bids - bids that were submitted but rejected.

        Returns breakdown by creative status:
        - CREATIVE_NOT_APPROVED
        - CREATIVE_NOT_SUBMITTED
        - BID_BELOW_FLOOR
        - CREATIVE_DISAPPROVED
        - etc.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().filteredBids().list(
                filterSetName=filter_set_name
            )

            while request is not None:
                response = request.execute()
                results.extend(response.get('creativeStatusRows', []))
                request = self.service.bidders().filterSets().filteredBids().list_next(
                    request, response
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get filtered bids: {e}")
            raise

    def get_bid_metrics(self, filter_set_name: str) -> List[Dict]:
        """
        Get overall bid metrics - the funnel from requests to wins.

        Returns:
        {
            "bids": {"value": "1000000"},
            "bidsInAuction": {"value": "500000"},
            "impressionsWon": {"value": "50000"},
            "billedImpressions": {"value": "48000"},
            "measurableImpressions": {"value": "45000"},
            "viewableImpressions": {"value": "30000"}
        }
        """
        try:
            results = []
            request = self.service.bidders().filterSets().bidMetrics().list(
                filterSetName=filter_set_name
            )

            while request is not None:
                response = request.execute()
                results.extend(response.get('bidMetricsRows', []))
                request = self.service.bidders().filterSets().bidMetrics().list_next(
                    request, response
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get bid metrics: {e}")
            raise

    def get_impression_metrics(self, filter_set_name: str) -> List[Dict]:
        """
        Get impression-level metrics.

        Returns breakdown by inventory type, ad position, etc.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().impressionMetrics().list(
                filterSetName=filter_set_name
            )

            while request is not None:
                response = request.execute()
                results.extend(response.get('impressionMetricsRows', []))
                request = self.service.bidders().filterSets().impressionMetrics().list_next(
                    request, response
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get impression metrics: {e}")
            raise

    def get_loser_bids(self, filter_set_name: str) -> List[Dict]:
        """
        Get details on bids that lost in auction.

        Useful for understanding if you're being outbid.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().losingBids().list(
                filterSetName=filter_set_name
            )

            while request is not None:
                response = request.execute()
                results.extend(response.get('creativeStatusRows', []))
                request = self.service.bidders().filterSets().losingBids().list_next(
                    request, response
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get loser bids: {e}")
            raise

    def collect_all_metrics(
        self,
        days: int = 7,
        environment: str = None,
        granularity: str = "DAILY"
    ) -> Dict[str, Any]:
        """
        Convenience method to collect all troubleshooting metrics.

        Args:
            days: Number of days to look back
            environment: Optional filter for APP or WEB
            granularity: DAILY or HOURLY

        Returns:
            Dictionary with all metric types
        """
        # Create a transient filter set
        filter_set_name = f"catscan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        filter_set = self.create_filter_set(
            name=filter_set_name,
            environment=environment,
            time_series_granularity=granularity,
            relative_date_range={
                "offsetDays": 1,
                "durationDays": days
            },
            is_transient=True
        )

        full_name = filter_set["name"]

        return {
            "filter_set": filter_set,
            "filtered_bid_requests": self.get_filtered_bid_requests(full_name),
            "filtered_bids": self.get_filtered_bids(full_name),
            "bid_metrics": self.get_bid_metrics(full_name),
            "impression_metrics": self.get_impression_metrics(full_name),
            "loser_bids": self.get_loser_bids(full_name),
            "collected_at": datetime.utcnow().isoformat()
        }
