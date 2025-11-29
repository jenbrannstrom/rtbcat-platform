"""Adapters for converting between collector schemas and storage models.

This module provides conversion functions between the TypedDict schemas
returned by API collectors and the dataclass models used for storage.
"""

from typing import TYPE_CHECKING, Optional, Tuple

from storage.sqlite_store import Creative
from utils.size_normalization import canonical_size as compute_canonical_size
from utils.size_normalization import get_size_category

if TYPE_CHECKING:
    from collectors.creatives.schemas import CreativeDict


def creative_dict_to_storage(data: "CreativeDict") -> Creative:
    """Convert a CreativeDict from the API collector to a storage Creative.

    Maps fields from the normalized API response schema to the storage
    dataclass, extracting nested UTM parameters and dimensions.

    Args:
        data: CreativeDict from CreativesClient.fetch_all_creatives()

    Returns:
        Creative dataclass ready for SQLite storage.

    Example:
        >>> from collectors import CreativesClient
        >>> from storage.adapters import creative_dict_to_storage
        >>>
        >>> client = CreativesClient(credentials_path="...", account_id="123")
        >>> api_creatives = await client.fetch_all_creatives()
        >>>
        >>> storage_creatives = [
        ...     creative_dict_to_storage(c) for c in api_creatives
        ... ]
        >>> await store.save_creatives(storage_creatives)
    """
    # Extract UTM parameters from nested dict
    utm_params = data.get("utmParams", {})

    # Extract dimensions based on format
    width = None
    height = None

    html_data = data.get("html")
    if html_data:
        width = html_data.get("width")
        height = html_data.get("height")

    native_data = data.get("native")
    if native_data and not width:
        image = native_data.get("image")
        if image:
            width = image.get("width")
            height = image.get("height")

    # Compute canonical size from dimensions
    canonical_size_str: Optional[str] = None
    size_category_str: Optional[str] = None
    if width is not None and height is not None:
        canonical_size_str = compute_canonical_size(width, height)
        size_category_str = get_size_category(canonical_size_str)

    return Creative(
        id=data.get("creativeId", ""),
        name=data.get("creativeName", ""),
        format=data.get("format", "UNKNOWN"),
        account_id=data.get("accountId"),
        buyer_id=data.get("buyerId"),  # For multi-seat support
        approval_status=data.get("approvalStatus"),
        width=width,
        height=height,
        canonical_size=canonical_size_str,
        size_category=size_category_str,
        final_url=data.get("destUrl"),
        display_url=data.get("destUrl"),  # Same as final_url for now
        utm_source=utm_params.get("utm_source"),
        utm_medium=utm_params.get("utm_medium"),
        utm_campaign=utm_params.get("utm_campaign"),
        utm_content=utm_params.get("utm_content"),
        utm_term=utm_params.get("utm_term"),
        advertiser_name=data.get("advertiserName"),
        campaign_id=None,  # Set later by clustering
        cluster_id=None,  # Set later by clustering
        raw_data={
            "declaredClickThroughUrls": data.get("declaredClickThroughUrls", []),
            "apiUpdateTime": data.get("apiUpdateTime"),
            "collectedAt": data.get("collectedAt"),
            "source": data.get("source"),
            "html": data.get("html"),
            "video": data.get("video"),
            "native": data.get("native"),
        },
    )


def creative_dicts_to_storage(data_list: list["CreativeDict"]) -> list[Creative]:
    """Convert a list of CreativeDict objects to storage Creative objects.

    Convenience function for batch conversion.

    Args:
        data_list: List of CreativeDict from API collector.

    Returns:
        List of Creative dataclasses ready for storage.

    Example:
        >>> api_creatives = await client.fetch_all_creatives()
        >>> storage_creatives = creative_dicts_to_storage(api_creatives)
        >>> count = await store.save_creatives(storage_creatives)
    """
    return [creative_dict_to_storage(d) for d in data_list]
