"""Pure parsing functions for pretargeting configuration API responses.

This module contains stateless functions for transforming raw API responses
into normalized PretargetingConfigDict structures.
"""

from datetime import datetime, timezone
from typing import Optional

from collectors.pretargeting.schemas import (
    AppTargeting,
    CreativeDimensions,
    GeoTargeting,
    NumericTargetingDimension,
    PretargetingConfigDict,
    StringTargetingDimension,
    UserListTargeting,
)


def _extract_numeric_targeting(data: Optional[dict]) -> Optional[NumericTargetingDimension]:
    """Extract numeric targeting dimension from raw data.

    Args:
        data: Raw targeting data with includedIds/excludedIds.

    Returns:
        NumericTargetingDimension if data exists, None otherwise.
    """
    if not data:
        return None

    return NumericTargetingDimension(
        includedIds=data.get("includedIds", []),
        excludedIds=data.get("excludedIds", []),
    )


def _extract_string_targeting(data: Optional[dict]) -> Optional[StringTargetingDimension]:
    """Extract string targeting dimension from raw data.

    Args:
        data: Raw targeting data with targetingMode/values.

    Returns:
        StringTargetingDimension if data exists, None otherwise.
    """
    if not data:
        return None

    return StringTargetingDimension(
        targetingMode=data.get("targetingMode"),
        values=data.get("values", []),
    )


def _extract_geo_targeting(data: Optional[dict]) -> Optional[GeoTargeting]:
    """Extract geographic targeting from raw data.

    Args:
        data: Raw geo targeting data.

    Returns:
        GeoTargeting if data exists, None otherwise.
    """
    if not data:
        return None

    return GeoTargeting(
        includedIds=data.get("includedIds", []),
        excludedIds=data.get("excludedIds", []),
    )


def _extract_user_list_targeting(data: Optional[dict]) -> Optional[UserListTargeting]:
    """Extract user list targeting from raw data.

    Args:
        data: Raw user list targeting data.

    Returns:
        UserListTargeting if data exists, None otherwise.
    """
    if not data:
        return None

    return UserListTargeting(
        includedIds=data.get("includedIds", []),
        excludedIds=data.get("excludedIds", []),
    )


def _extract_app_targeting(data: Optional[dict]) -> Optional[AppTargeting]:
    """Extract app targeting configuration from raw data.

    Args:
        data: Raw app targeting data.

    Returns:
        AppTargeting if data exists, None otherwise.
    """
    if not data:
        return None

    result = AppTargeting()

    mobile_app = data.get("mobileAppTargeting")
    if mobile_app:
        result["mobileAppTargeting"] = StringTargetingDimension(
            targetingMode=mobile_app.get("targetingMode"),
            values=mobile_app.get("values", []),
        )

    mobile_category = data.get("mobileAppCategoryTargeting")
    if mobile_category:
        result["mobileAppCategoryTargeting"] = NumericTargetingDimension(
            includedIds=mobile_category.get("includedIds", []),
            excludedIds=mobile_category.get("excludedIds", []),
        )

    return result if result else None


def _extract_creative_dimensions(
    dimensions_list: Optional[list],
) -> list[CreativeDimensions]:
    """Extract creative dimensions from raw data.

    Args:
        dimensions_list: List of raw dimension dictionaries.

    Returns:
        List of CreativeDimensions.
    """
    if not dimensions_list:
        return []

    return [
        CreativeDimensions(
            width=dim.get("width", 0),
            height=dim.get("height", 0),
        )
        for dim in dimensions_list
    ]


def parse_pretargeting_config(config_data: dict) -> PretargetingConfigDict:
    """Convert an API response to normalized PretargetingConfigDict.

    Transforms the raw API response into a consistent structure with
    all targeting dimensions properly extracted.

    Args:
        config_data: A pretargeting config resource from the API.

    Returns:
        PretargetingConfigDict with normalized data.

    Example:
        >>> raw = {"name": "bidders/123/pretargetingConfigs/456", ...}
        >>> config = parse_pretargeting_config(raw)
        >>> config["configId"]
        '456'
    """
    # Extract resource name components
    name = config_data.get("name", "")
    parts = name.split("/")
    config_id = parts[-1] if len(parts) >= 4 else ""

    # Determine state with fallback
    state = config_data.get("state", "SUSPENDED")
    if state not in ("ACTIVE", "SUSPENDED"):
        state = "SUSPENDED"

    result: PretargetingConfigDict = {
        "configId": config_id,
        "name": name,
        "displayName": config_data.get("displayName"),
        "billingId": config_data.get("billingId"),
        "state": state,  # type: ignore[typeddict-item]
        "includedFormats": config_data.get("includedFormats", []),
        "geoTargeting": _extract_geo_targeting(config_data.get("geoTargeting")),
        "userListTargeting": _extract_user_list_targeting(
            config_data.get("userListTargeting")
        ),
        "interstitialTargeting": config_data.get("interstitialTargeting"),
        "allowedUserTargetingModes": config_data.get("allowedUserTargetingModes", []),
        "excludedContentLabelIds": config_data.get("excludedContentLabelIds", []),
        "includedUserIdTypes": config_data.get("includedUserIdTypes", []),
        "includedLanguages": config_data.get("includedLanguages", []),
        "includedMobileOperatingSystemIds": config_data.get(
            "includedMobileOperatingSystemIds", []
        ),
        "verticalTargeting": _extract_numeric_targeting(
            config_data.get("verticalTargeting")
        ),
        "includedPlatforms": config_data.get("includedPlatforms", []),
        "includedCreativeDimensions": _extract_creative_dimensions(
            config_data.get("includedCreativeDimensions")
        ),
        "appTargeting": _extract_app_targeting(config_data.get("appTargeting")),
        "webTargeting": _extract_string_targeting(config_data.get("webTargeting")),
        "publisherTargeting": _extract_string_targeting(
            config_data.get("publisherTargeting")
        ),
        "minimumViewabilityDecile": config_data.get("minimumViewabilityDecile"),
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "source": "authorized_buyers_api",
    }

    return result
