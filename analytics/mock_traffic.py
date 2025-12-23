"""Mock RTB traffic data generator for development and testing.

This module generates synthetic bid request data that simulates real RTB traffic
patterns, including realistic size distributions and volume variations.

Example:
    >>> from analytics.mock_traffic import generate_mock_traffic
    >>> traffic = generate_mock_traffic(days=7)
    >>> print(f"Generated {len(traffic)} traffic records")
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from analytics.waste_models import TrafficRecord

# Realistic RTB traffic distributions
# Format: (raw_size, canonical_size, relative_weight)
# Weights represent relative frequency in real RTB traffic

TRAFFIC_DISTRIBUTIONS = {
    # High-volume IAB standard sizes (these should have creatives)
    "iab_standard": [
        ("300x250", "300x250 (Medium Rectangle)", 100),  # Most common
        ("728x90", "728x90 (Leaderboard)", 45),
        ("320x50", "320x50 (Mobile Banner)", 60),
        ("300x600", "300x600 (Half Page)", 25),
        ("160x600", "160x600 (Wide Skyscraper)", 20),
        ("970x250", "970x250 (Billboard)", 15),
        ("320x100", "320x100 (Large Mobile Banner)", 35),
        ("336x280", "336x280 (Large Rectangle)", 18),
        ("970x90", "970x90 (Super Leaderboard)", 8),
        ("468x60", "468x60 (Banner)", 5),
    ],
    # Non-standard sizes that are close to IAB (±1-2 pixels) - often waste
    "near_standard": [
        ("301x250", "Non-Standard (301x250)", 15),  # Off-by-one
        ("300x251", "Non-Standard (300x251)", 12),
        ("729x90", "Non-Standard (729x90)", 8),
        ("728x91", "Non-Standard (728x91)", 7),
        ("319x50", "Non-Standard (319x50)", 10),
        ("321x50", "Non-Standard (321x50)", 9),
        ("299x250", "Non-Standard (299x250)", 6),
    ],
    # Completely non-standard sizes - usually waste
    "non_standard": [
        ("320x480", "Non-Standard (320x480)", 25),  # Common mobile interstitial
        ("320x481", "Non-Standard (320x481)", 18),  # Off-by-one variant
        ("480x320", "Non-Standard (480x320)", 12),
        ("300x100", "Non-Standard (300x100)", 8),
        ("250x300", "Non-Standard (250x300)", 6),
        ("640x100", "Non-Standard (640x100)", 5),
        ("120x240", "Non-Standard (120x240)", 4),
        ("234x90", "Non-Standard (234x90)", 3),
        ("300x1050", "Non-Standard (300x1050)", 7),  # Portrait half-page
        ("580x400", "Non-Standard (580x400)", 4),
    ],
    # Video sizes
    "video": [
        ("1920x1080", "Video 16:9 (Horizontal)", 30),
        ("1280x720", "Video 16:9 (Horizontal)", 25),
        ("640x360", "Video 16:9 (Horizontal)", 20),
        ("1080x1920", "Video 9:16 (Vertical)", 15),
        ("1080x1080", "Video 1:1 (Square)", 12),
        ("640x640", "Video 1:1 (Square)", 8),
        ("1080x1350", "Video 4:5 (Portrait)", 10),
    ],
    # Adaptive/responsive
    "adaptive": [
        ("0x250", "Adaptive/Fluid", 5),
        ("300x0", "Adaptive/Fluid", 4),
        ("1x1", "Adaptive/Responsive", 8),
    ],
}


def generate_mock_traffic(
    days: int = 7,
    buyer_id: Optional[str] = None,
    base_daily_requests: int = 100000,
    include_weekday_variance: bool = True,
    waste_bias: float = 0.3,
) -> List[TrafficRecord]:
    """Generate mock RTB bid request traffic data.

    Generates realistic bid request data with:
    - IAB standard sizes (high volume)
    - Non-standard sizes (medium volume, often waste)
    - Video sizes (medium volume)
    - Day-over-day variance (weekdays vs weekends)

    Args:
        days: Number of days of traffic to generate.
        buyer_id: Optional buyer seat ID to associate with traffic.
        base_daily_requests: Base number of daily requests to generate.
        include_weekday_variance: Whether to vary traffic by day of week.
        waste_bias: Bias factor for non-standard sizes (0.0-1.0).
            Higher values generate more waste traffic.

    Returns:
        List of TrafficRecord objects with generated data.

    Example:
        >>> traffic = generate_mock_traffic(days=7)
        >>> for record in traffic[:5]:
        ...     print(f"{record.date}: {record.raw_size} - {record.request_count}")
    """
    records: List[TrafficRecord] = []
    today = datetime.now().date()

    # Flatten all size distributions
    all_sizes = []
    for category, sizes in TRAFFIC_DISTRIBUTIONS.items():
        weight_multiplier = 1.0
        if category in ["non_standard", "near_standard"]:
            weight_multiplier = waste_bias * 2  # Bias towards waste
        elif category == "iab_standard":
            weight_multiplier = 1.0 - waste_bias * 0.5

        for raw_size, canonical_size, weight in sizes:
            all_sizes.append((raw_size, canonical_size, weight * weight_multiplier))

    # Calculate total weight for normalization
    total_weight = sum(w for _, _, w in all_sizes)

    for day_offset in range(days):
        date = today - timedelta(days=day_offset)
        date_str = date.isoformat()

        # Apply day-of-week variance
        daily_multiplier = 1.0
        if include_weekday_variance:
            weekday = date.weekday()
            if weekday == 5:  # Saturday
                daily_multiplier = 0.7
            elif weekday == 6:  # Sunday
                daily_multiplier = 0.6
            elif weekday == 0:  # Monday
                daily_multiplier = 1.1
            elif weekday in [1, 2, 3]:  # Tue-Thu
                daily_multiplier = 1.05

        # Add some random daily variance
        daily_multiplier *= random.uniform(0.85, 1.15)

        daily_requests = int(base_daily_requests * daily_multiplier)

        # Distribute requests across sizes
        for raw_size, canonical_size, weight in all_sizes:
            # Calculate base count from weight
            size_ratio = weight / total_weight
            base_count = int(daily_requests * size_ratio)

            # Add random variance per size (±20%)
            variance = random.uniform(0.8, 1.2)
            count = max(1, int(base_count * variance))

            # Skip very low counts sometimes
            if count < 10 and random.random() < 0.3:
                continue

            records.append(
                TrafficRecord(
                    canonical_size=canonical_size,
                    raw_size=raw_size,
                    request_count=count,
                    date=date_str,
                    buyer_id=buyer_id,
                )
            )

    return records


def generate_traffic_with_gaps(
    days: int = 7,
    buyer_id: Optional[str] = None,
    gap_sizes: Optional[List[str]] = None,
) -> List[TrafficRecord]:
    """Generate traffic specifically designed to show waste gaps.

    This is useful for demos and testing - it generates traffic
    for sizes that are commonly NOT in creative inventory.

    Args:
        days: Number of days of traffic to generate.
        buyer_id: Optional buyer seat ID.
        gap_sizes: Specific sizes to include as gaps. If None,
            uses common problematic sizes.

    Returns:
        List of TrafficRecord objects emphasizing waste gaps.
    """
    if gap_sizes is None:
        gap_sizes = [
            # High-volume non-standard mobile sizes
            ("320x480", "Non-Standard (320x480)", 50000),
            ("320x481", "Non-Standard (320x481)", 35000),
            # Off-by-one sizes
            ("301x250", "Non-Standard (301x250)", 12000),
            ("728x91", "Non-Standard (728x91)", 8000),
            # Random non-standard
            ("480x320", "Non-Standard (480x320)", 6000),
            ("300x1050", "Non-Standard (300x1050)", 5000),
        ]
    else:
        # Convert simple size strings to full tuples
        gap_sizes = [
            (size, f"Non-Standard ({size})", 10000)
            for size in gap_sizes
        ]

    records: List[TrafficRecord] = []
    today = datetime.now().date()

    for day_offset in range(days):
        date = today - timedelta(days=day_offset)
        date_str = date.isoformat()

        for raw_size, canonical_size, daily_count in gap_sizes:
            # Add daily variance
            count = int(daily_count * random.uniform(0.7, 1.3))

            records.append(
                TrafficRecord(
                    canonical_size=canonical_size,
                    raw_size=raw_size,
                    request_count=count,
                    date=date_str,
                    buyer_id=buyer_id,
                )
            )

    return records


def get_size_from_raw(raw_size: str) -> tuple:
    """Parse a raw size string into width and height.

    Args:
        raw_size: Size string like "300x250" or "300x0".

    Returns:
        Tuple of (width, height) as integers.

    Example:
        >>> get_size_from_raw("300x250")
        (300, 250)
    """
    parts = raw_size.lower().split("x")
    if len(parts) != 2:
        return (0, 0)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (0, 0)
