"""Type definitions for RTB endpoint data structures.

This module contains TypedDict definitions for RTB endpoints
from the Google Authorized Buyers API.

API Reference:
    https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/bidders.endpoints
"""

from typing import Literal, Optional, TypedDict


# Bid protocol types supported by the API
BidProtocol = Literal[
    "BID_PROTOCOL_UNSPECIFIED",
    "GOOGLE_RTB",
    "OPENRTB_2_2",
    "OPENRTB_2_3",
    "OPENRTB_2_4",
    "OPENRTB_2_5",
    "OPENRTB_PROTOBUF_2_3",
    "OPENRTB_PROTOBUF_2_4",
    "OPENRTB_PROTOBUF_2_5",
]

# Trading location types
TradingLocation = Literal[
    "TRADING_LOCATION_UNSPECIFIED",
    "US_WEST",
    "US_EAST",
    "EUROPE",
    "ASIA",
]


class EndpointDict(TypedDict, total=False):
    """Normalized RTB endpoint configuration data.

    This schema represents an RTB endpoint with its configuration
    as returned by the bidders.endpoints API.

    Attributes:
        endpointId: Unique endpoint identifier (extracted from resource name).
        name: Full resource name (bidders/{bidder_id}/endpoints/{endpoint_id}).
        url: The URL that bid requests are sent to.
        maximumQps: Maximum queries per second (optional, can be unlimited).
        tradingLocation: Geographic location for trading.
        bidProtocol: Protocol used for bid requests.
        collectedAt: Timestamp when this data was collected.
        source: Data source identifier.
    """

    endpointId: str
    name: str
    url: str
    maximumQps: Optional[int]
    tradingLocation: TradingLocation
    bidProtocol: BidProtocol
    collectedAt: str
    source: Literal["authorized_buyers_api"]
