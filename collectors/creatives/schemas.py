"""Type definitions for creative data structures.

This module contains all TypedDict definitions for creative data,
including format-specific data structures and UTM parameters.
"""

from typing import Literal, Optional, TypedDict


# Type aliases for creative formats and approval statuses
CreativeFormat = Literal["HTML", "VIDEO", "NATIVE", "UNKNOWN"]
ApprovalStatus = Literal[
    "PENDING_REVIEW", "APPROVED", "DISAPPROVED", "CERTIFICATE_REQUIRED", "UNKNOWN"
]


class UtmParams(TypedDict, total=False):
    """UTM tracking parameters extracted from destination URLs.

    Attributes:
        utm_source: Traffic source (e.g., 'google', 'facebook').
        utm_medium: Marketing medium (e.g., 'cpc', 'display').
        utm_campaign: Campaign name or ID.
        utm_content: Content variant for A/B testing.
        utm_term: Paid search keywords.
    """

    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    utm_content: Optional[str]
    utm_term: Optional[str]


class HtmlCreativeData(TypedDict, total=False):
    """HTML creative-specific fields.

    Attributes:
        snippet: The HTML markup for the creative.
        width: Creative width in pixels.
        height: Creative height in pixels.
    """

    snippet: str
    width: int
    height: int


class ImageData(TypedDict, total=False):
    """Image data for native creatives.

    Attributes:
        url: URL of the image asset.
        width: Image width in pixels.
        height: Image height in pixels.
    """

    url: str
    width: int
    height: int


class VideoCreativeData(TypedDict, total=False):
    """Video creative-specific fields.

    Attributes:
        videoUrl: URL to the video asset (mutually exclusive with vastXml).
        vastXml: VAST XML content (mutually exclusive with videoUrl).
        duration: Video duration as ISO 8601 duration string (e.g., 'PT30S').
    """

    videoUrl: Optional[str]
    vastXml: Optional[str]
    duration: Optional[str]


class NativeCreativeData(TypedDict, total=False):
    """Native creative-specific fields.

    Attributes:
        headline: Main headline text.
        body: Body/description text.
        callToAction: CTA button text.
        image: Main image asset data.
        logo: Logo image asset data.
        clickLinkUrl: Destination URL for native ad clicks.
    """

    headline: Optional[str]
    body: Optional[str]
    callToAction: Optional[str]
    image: Optional[ImageData]
    logo: Optional[ImageData]
    clickLinkUrl: Optional[str]


class CreativeDict(TypedDict, total=False):
    """Normalized creative data returned by the client.

    This schema provides a consistent structure for all creative types,
    with format-specific fields populated based on the creative format.

    Attributes:
        creativeId: Unique creative identifier.
        creativeName: Full resource name (bidders/{account}/creatives/{id}).
        accountId: Bidder account ID.
        buyerId: Buyer seat ID (for multi-seat accounts).
        format: Creative format (HTML, VIDEO, NATIVE, UNKNOWN).
        destUrl: Primary destination URL.
        utmParams: Extracted UTM tracking parameters.
        approvalStatus: Network policy compliance status.
        html: HTML-specific data (only present for HTML creatives).
        video: Video-specific data (only present for VIDEO creatives).
        native: Native-specific data (only present for NATIVE creatives).
        advertiserName: Declared advertiser name.
        declaredClickThroughUrls: All declared click-through URLs.
        apiUpdateTime: Last API update timestamp.
        collectedAt: Timestamp when this data was collected.
        source: Data source identifier (always 'authorized_buyers_api').
        canonical_size: Normalized IAB standard size (e.g., "300x250 (Medium Rectangle)").
        size_category: Size category ("IAB Standard", "Video", "Adaptive", "Non-Standard").
    """

    creativeId: str
    creativeName: str
    accountId: str
    buyerId: Optional[str]
    format: CreativeFormat
    destUrl: Optional[str]
    utmParams: UtmParams
    approvalStatus: ApprovalStatus
    html: Optional[HtmlCreativeData]
    video: Optional[VideoCreativeData]
    native: Optional[NativeCreativeData]
    advertiserName: Optional[str]
    declaredClickThroughUrls: list[str]
    apiUpdateTime: Optional[str]
    collectedAt: str
    source: Literal["authorized_buyers_api"]
    canonical_size: str
    size_category: str
