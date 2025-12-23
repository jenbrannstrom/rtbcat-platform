"""Pure parsing functions for creative API responses.

This module contains stateless functions for transforming raw API responses
into normalized CreativeDict structures. All functions are pure with no
side effects or API calls.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

from collectors.creatives.schemas import (
    ApprovalStatus,
    CreativeDict,
    CreativeFormat,
    HtmlCreativeData,
    ImageData,
    NativeCreativeData,
    UtmParams,
    VideoCreativeData,
)

logger = logging.getLogger(__name__)


def _parse_utm_params(url: Optional[str]) -> UtmParams:
    """Extract UTM parameters from a URL.

    Args:
        url: The URL to parse for UTM parameters.

    Returns:
        UtmParams dictionary with extracted values (None for missing params).

    Example:
        >>> _parse_utm_params("https://example.com?utm_source=google&utm_medium=cpc")
        {'utm_source': 'google', 'utm_medium': 'cpc', ...}
    """
    result: UtmParams = {
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
        "utm_term": None,
    }

    if not url:
        return result

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        for key in result:
            values = params.get(key, [])
            if values:
                result[key] = values[0]  # type: ignore[literal-required]
    except Exception as e:
        logger.warning(f"Failed to parse URL '{url}': {e}")

    return result


def _determine_format(creative_data: dict) -> CreativeFormat:
    """Determine the creative format from the API response.

    The API returns a union field 'content' where only one of html, video,
    or native exists. This function detects which one is present.

    Args:
        creative_data: The creative resource dictionary from API.

    Returns:
        CreativeFormat: 'HTML', 'VIDEO', 'NATIVE', or 'UNKNOWN'.
    """
    if creative_data.get("html"):
        return "HTML"
    elif creative_data.get("video"):
        return "VIDEO"
    elif creative_data.get("native"):
        return "NATIVE"
    return "UNKNOWN"


def _extract_html_data(creative_data: dict) -> Optional[HtmlCreativeData]:
    """Extract HTML creative-specific data.

    Args:
        creative_data: The creative resource dictionary from API.

    Returns:
        HtmlCreativeData if html content exists, None otherwise.
    """
    html = creative_data.get("html")
    if not html:
        return None

    return HtmlCreativeData(
        snippet=html.get("snippet", ""),
        width=html.get("width", 0),
        height=html.get("height", 0),
    )


def _extract_video_data(creative_data: dict) -> Optional[VideoCreativeData]:
    """Extract video creative-specific data.

    Args:
        creative_data: The creative resource dictionary from API.

    Returns:
        VideoCreativeData if video content exists, None otherwise.
    """
    video = creative_data.get("video")
    if not video:
        return None

    video_metadata = video.get("videoMetadata", {})
    return VideoCreativeData(
        videoUrl=video.get("videoUrl"),
        vastXml=video.get("videoVastXml"),
        duration=video_metadata.get("duration"),
    )


def _extract_native_data(creative_data: dict) -> Optional[NativeCreativeData]:
    """Extract native creative-specific data.

    Args:
        creative_data: The creative resource dictionary from API.

    Returns:
        NativeCreativeData if native content exists, None otherwise.
    """
    native = creative_data.get("native")
    if not native:
        return None

    result = NativeCreativeData(
        headline=native.get("headline"),
        body=native.get("body"),
        callToAction=native.get("callToAction"),
        clickLinkUrl=native.get("clickLinkUrl"),
    )

    # Extract image data if present
    image = native.get("image")
    if image:
        result["image"] = ImageData(
            url=image.get("url", ""),
            width=image.get("width", 0),
            height=image.get("height", 0),
        )

    # Extract logo data if present
    logo = native.get("logo")
    if logo:
        result["logo"] = ImageData(
            url=logo.get("url", ""),
            width=logo.get("width", 0),
            height=logo.get("height", 0),
        )

    return result


def _get_approval_status(creative_data: dict) -> ApprovalStatus:
    """Extract approval status from creativeServingDecision.

    Uses networkPolicyCompliance.status as per API documentation.

    Args:
        creative_data: The creative resource dictionary from API.

    Returns:
        ApprovalStatus: One of PENDING_REVIEW, APPROVED, DISAPPROVED,
                       CERTIFICATE_REQUIRED, or UNKNOWN.
    """
    serving_decision = creative_data.get("creativeServingDecision", {})
    network_compliance = serving_decision.get("networkPolicyCompliance", {})
    status = network_compliance.get("status", "UNKNOWN")

    valid_statuses: set[ApprovalStatus] = {
        "PENDING_REVIEW",
        "APPROVED",
        "DISAPPROVED",
        "CERTIFICATE_REQUIRED",
    }
    if status in valid_statuses:
        return status  # type: ignore[return-value]
    return "UNKNOWN"


def _get_dest_url(
    creative_data: dict, creative_format: CreativeFormat
) -> Optional[str]:
    """Determine the destination URL based on creative format.

    For native ads, uses native.clickLinkUrl. For other formats,
    uses the first declaredClickThroughUrls entry.

    Args:
        creative_data: The creative resource dictionary from API.
        creative_format: The detected creative format.

    Returns:
        The primary destination URL, or None if not available.
    """
    # For native ads, prefer clickLinkUrl
    if creative_format == "NATIVE":
        native = creative_data.get("native", {})
        click_link = native.get("clickLinkUrl")
        if click_link:
            return click_link

    # Fallback to declaredClickThroughUrls
    click_urls = creative_data.get("declaredClickThroughUrls", [])
    return click_urls[0] if click_urls else None


def parse_creative_response(
    creative_data: dict,
    default_account_id: str = "",
    buyer_id: Optional[str] = None,
) -> CreativeDict:
    """Convert an API response to normalized CreativeDict schema.

    Transforms the raw API response into a consistent structure with:
    - Core identification fields
    - Format-specific nested data (only one of html/video/native)
    - Extracted UTM parameters
    - Approval status from networkPolicyCompliance

    Args:
        creative_data: A creative resource from the API response.
        default_account_id: Fallback account ID if not in response.
        buyer_id: Optional buyer seat ID for multi-seat accounts.

    Returns:
        CreativeDict with normalized and extracted data.

    Example:
        >>> raw = {"name": "bidders/123/creatives/abc", "html": {...}}
        >>> creative = parse_creative_response(raw, "123", buyer_id="456")
        >>> creative["format"]
        'HTML'
        >>> creative["buyerId"]
        '456'
    """
    # Extract resource name components
    name = creative_data.get("name", "")
    parts = name.split("/")
    creative_id = parts[-1] if len(parts) >= 4 else ""
    account_id = parts[1] if len(parts) >= 2 else default_account_id

    # Determine format and get destination URL
    creative_format = _determine_format(creative_data)
    dest_url = _get_dest_url(creative_data, creative_format)

    # Extract UTM parameters from destination URL
    utm_params = _parse_utm_params(dest_url)

    # Get declared click-through URLs
    click_urls = creative_data.get("declaredClickThroughUrls", [])

    # Build the normalized response
    result: CreativeDict = {
        "creativeId": creative_id,
        "creativeName": name,
        "accountId": account_id,
        "buyerId": buyer_id,
        "format": creative_format,
        "destUrl": dest_url,
        "utmParams": utm_params,
        "approvalStatus": _get_approval_status(creative_data),
        "advertiserName": creative_data.get("advertiserName"),
        "declaredClickThroughUrls": click_urls,
        "apiUpdateTime": creative_data.get("apiUpdateTime"),
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "source": "authorized_buyers_api",
    }

    # Add format-specific data (only one will be non-None)
    result["html"] = _extract_html_data(creative_data)
    result["video"] = _extract_video_data(creative_data)
    result["native"] = _extract_native_data(creative_data)

    return result
