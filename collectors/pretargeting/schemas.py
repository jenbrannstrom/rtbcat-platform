"""Type definitions for pretargeting configuration data structures.

This module contains all TypedDict definitions for pretargeting configurations
and their nested targeting data.
"""

from typing import Literal, Optional, TypedDict


# Status types for pretargeting configs
PretargetingState = Literal["ACTIVE", "SUSPENDED"]


class NumericTargetingDimension(TypedDict, total=False):
    """Numeric targeting values (e.g., vertical IDs, vendor IDs).

    Attributes:
        includedIds: List of IDs to include.
        excludedIds: List of IDs to exclude.
    """

    includedIds: list[str]
    excludedIds: list[str]


class StringTargetingDimension(TypedDict, total=False):
    """String targeting values (e.g., URLs, app IDs).

    Attributes:
        targetingMode: How to apply targeting ('INCLUSIVE' or 'EXCLUSIVE').
        values: List of string values to target.
    """

    targetingMode: Optional[str]
    values: list[str]


class AppTargeting(TypedDict, total=False):
    """App targeting configuration.

    Attributes:
        mobileAppTargeting: Targeting for mobile app IDs.
        mobileAppCategoryTargeting: Targeting for app category IDs.
    """

    mobileAppTargeting: StringTargetingDimension
    mobileAppCategoryTargeting: NumericTargetingDimension


class GeoTargeting(TypedDict, total=False):
    """Geographic targeting configuration.

    Attributes:
        includedIds: List of geo criterion IDs to include.
        excludedIds: List of geo criterion IDs to exclude.
    """

    includedIds: list[str]
    excludedIds: list[str]


class UserListTargeting(TypedDict, total=False):
    """User list targeting configuration.

    Attributes:
        includedIds: List of user list IDs to include.
        excludedIds: List of user list IDs to exclude.
    """

    includedIds: list[str]
    excludedIds: list[str]


class CreativeDimensions(TypedDict, total=False):
    """Creative size dimensions.

    Attributes:
        width: Width in pixels.
        height: Height in pixels.
    """

    width: int
    height: int


class PretargetingConfigDict(TypedDict, total=False):
    """Normalized pretargeting configuration data.

    This schema represents a pretargeting configuration with all
    its targeting dimensions and settings.

    Attributes:
        configId: Unique configuration identifier.
        name: Full resource name.
        displayName: Human-readable configuration name.
        billingId: Associated billing ID.
        state: Configuration state (ACTIVE or SUSPENDED).
        includedFormats: List of ad formats to include.
        geoTargeting: Geographic targeting settings.
        userListTargeting: User list targeting settings.
        interstitialTargeting: Whether interstitials are targeted.
        allowedUserTargetingModes: Allowed user targeting modes.
        excludedContentLabelIds: Content labels to exclude.
        includedUserIdTypes: User ID types to include.
        includedLanguages: Language codes to include.
        includedMobileOperatingSystemIds: Mobile OS IDs to include.
        verticalTargeting: Vertical/industry targeting.
        includedPlatforms: Platforms to include.
        includedCreativeDimensions: Creative sizes to include.
        appTargeting: App targeting configuration.
        webTargeting: Web targeting configuration.
        publisherTargeting: Publisher targeting configuration.
        minimumViewabilityDecile: Minimum viewability threshold.
        collectedAt: Timestamp when this data was collected.
        source: Data source identifier.
    """

    configId: str
    name: str
    displayName: Optional[str]
    billingId: Optional[str]
    state: PretargetingState
    includedFormats: list[str]
    geoTargeting: Optional[GeoTargeting]
    userListTargeting: Optional[UserListTargeting]
    interstitialTargeting: Optional[str]
    allowedUserTargetingModes: list[str]
    excludedContentLabelIds: list[str]
    includedUserIdTypes: list[str]
    includedLanguages: list[str]
    includedMobileOperatingSystemIds: list[str]
    verticalTargeting: Optional[NumericTargetingDimension]
    includedPlatforms: list[str]
    includedCreativeDimensions: list[CreativeDimensions]
    appTargeting: Optional[AppTargeting]
    webTargeting: Optional[StringTargetingDimension]
    publisherTargeting: Optional[StringTargetingDimension]
    minimumViewabilityDecile: Optional[int]
    collectedAt: str
    source: Literal["authorized_buyers_api"]
