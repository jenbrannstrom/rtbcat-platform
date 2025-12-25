"""
Size normalization utility for reducing 2000+ creative sizes to ~18 IAB standards.

This module provides functions to normalize arbitrary ad creative dimensions
to standard IAB (Interactive Advertising Bureau) size categories.

Example usage:
    >>> from size_normalization import canonical_size, get_size_category
    >>> canonical_size(300, 250)
    '300x250 (Medium Rectangle)'
    >>> get_size_category('300x250 (Medium Rectangle)')
    'IAB Standard'
"""

from typing import Dict, Tuple, Optional

# IAB Standard sizes mapping: (width, height) -> display name
IAB_STANDARD_SIZES: Dict[Tuple[int, int], str] = {
    (300, 250): "300x250 (Medium Rectangle)",
    (728, 90): "728x90 (Leaderboard)",
    (320, 50): "320x50 (Mobile Banner)",
    (160, 600): "160x600 (Wide Skyscraper)",
    (300, 600): "300x600 (Half Page)",
    (970, 250): "970x250 (Billboard)",
    (320, 100): "320x100 (Large Mobile Banner)",
    (468, 60): "468x60 (Banner)",
    (234, 60): "234x60 (Half Banner)",
    (120, 600): "120x600 (Skyscraper)",
    (970, 90): "970x90 (Super Leaderboard)",
    (336, 280): "336x280 (Large Rectangle)",
    (250, 250): "250x250 (Square)",
    (200, 200): "200x200 (Small Square)",
    (180, 150): "180x150 (Small Rectangle)",
}


def canonical_size(width: int, height: int) -> str:
    """
    Convert arbitrary creative dimensions to canonical IAB standard size.

    Reduces 2000+ possible creative sizes to approximately 18 standard categories
    including IAB standard sizes, video formats, and adaptive/fluid sizes.

    Args:
        width: The width of the creative in pixels.
        height: The height of the creative in pixels.

    Returns:
        A string representing the canonical size category.

    Examples:
        >>> canonical_size(300, 250)
        '300x250 (Medium Rectangle)'

        >>> canonical_size(728, 90)
        '728x90 (Leaderboard)'

        >>> canonical_size(0, 250)
        'Adaptive/Fluid'

        >>> canonical_size(1, 1)
        'Adaptive/Responsive'

        >>> canonical_size(1080, 1920)
        'Video 9:16 (Vertical)'

        >>> canonical_size(1920, 1080)
        'Video 16:9 (Horizontal)'

        >>> canonical_size(123, 456)
        'Non-Standard (123x456)'
    """
    # Special case: Adaptive/Fluid (zero dimension)
    if width == 0 or height == 0:
        return "Adaptive/Fluid"

    # Special case: Adaptive/Responsive (1x1)
    if width == 1 and height == 1:
        return "Adaptive/Responsive"

    # Check for exact IAB standard match
    size_key = (width, height)
    if size_key in IAB_STANDARD_SIZES:
        return IAB_STANDARD_SIZES[size_key]

    # Check video aspect ratios
    aspect_ratio = width / height

    # Video 9:16 (Vertical) - aspect ratio 0.5-0.6
    if 0.5 <= aspect_ratio <= 0.6:
        return "Video 9:16 (Vertical)"

    # Video 16:9 (Horizontal) - aspect ratio 1.7-1.8
    if 1.7 <= aspect_ratio <= 1.8:
        return "Video 16:9 (Horizontal)"

    # Video 1:1 (Square) - aspect ratio 0.9-1.1
    if 0.9 <= aspect_ratio <= 1.1:
        return "Video 1:1 (Square)"

    # Video 4:5 (Portrait) - aspect ratio 0.7-0.8
    if 0.7 <= aspect_ratio <= 0.8:
        return "Video 4:5 (Portrait)"

    # Non-standard size
    return f"Non-Standard ({width}x{height})"


def get_size_category(canonical: str) -> str:
    """
    Get the category of a canonical size string.

    Args:
        canonical: A canonical size string returned by canonical_size().

    Returns:
        One of: "IAB Standard", "Video", "Adaptive", or "Non-Standard".

    Examples:
        >>> get_size_category('300x250 (Medium Rectangle)')
        'IAB Standard'

        >>> get_size_category('Video 16:9 (Horizontal)')
        'Video'

        >>> get_size_category('Adaptive/Fluid')
        'Adaptive'

        >>> get_size_category('Non-Standard (123x456)')
        'Non-Standard'
    """
    if canonical.startswith("Video"):
        return "Video"

    if canonical.startswith("Adaptive"):
        return "Adaptive"

    if canonical.startswith("Non-Standard"):
        return "Non-Standard"

    return "IAB Standard"


def find_closest_iab_size(width: int, height: int, tolerance: int = 5) -> Optional[str]:
    """
    Find the closest IAB standard size within tolerance.

    Phase 22: Tolerance-based size normalization to map near-standard sizes
    like 298x250 → 300x250.

    Args:
        width: The width of the creative in pixels.
        height: The height of the creative in pixels.
        tolerance: Maximum pixel difference for each dimension (default 5).

    Returns:
        The canonical IAB size string if within tolerance, None otherwise.

    Examples:
        >>> find_closest_iab_size(300, 250)  # exact match
        '300x250 (Medium Rectangle)'

        >>> find_closest_iab_size(298, 250, tolerance=5)  # within tolerance
        '300x250 (Medium Rectangle)'

        >>> find_closest_iab_size(290, 250, tolerance=5)  # outside tolerance
        None
    """
    for (std_w, std_h), name in IAB_STANDARD_SIZES.items():
        if abs(width - std_w) <= tolerance and abs(height - std_h) <= tolerance:
            return name
    return None


def canonical_size_with_tolerance(width: int, height: int, tolerance: int = 5) -> str:
    """
    Convert arbitrary creative dimensions to canonical IAB standard size with tolerance.

    Phase 22: Enhanced version that maps near-standard sizes to standards.
    For example, 298x250 → 300x250 (Medium Rectangle) if within tolerance.

    Args:
        width: The width of the creative in pixels.
        height: The height of the creative in pixels.
        tolerance: Maximum pixel difference for each dimension (default 5).

    Returns:
        A string representing the canonical size category.

    Examples:
        >>> canonical_size_with_tolerance(298, 250)
        '300x250 (Medium Rectangle)'

        >>> canonical_size_with_tolerance(726, 92)
        '728x90 (Leaderboard)'

        >>> canonical_size_with_tolerance(123, 456)
        'Non-Standard (123x456)'
    """
    # Special case: Adaptive/Fluid (zero dimension)
    if width == 0 or height == 0:
        return "Adaptive/Fluid"

    # Special case: Adaptive/Responsive (1x1)
    if width == 1 and height == 1:
        return "Adaptive/Responsive"

    # Check for exact IAB standard match first
    size_key = (width, height)
    if size_key in IAB_STANDARD_SIZES:
        return IAB_STANDARD_SIZES[size_key]

    # Check for near-standard match with tolerance
    closest = find_closest_iab_size(width, height, tolerance)
    if closest:
        return closest

    # Check video aspect ratios
    aspect_ratio = width / height

    # Video 9:16 (Vertical) - aspect ratio 0.5-0.6
    if 0.5 <= aspect_ratio <= 0.6:
        return "Video 9:16 (Vertical)"

    # Video 16:9 (Horizontal) - aspect ratio 1.7-1.8
    if 1.7 <= aspect_ratio <= 1.8:
        return "Video 16:9 (Horizontal)"

    # Video 1:1 (Square) - aspect ratio 0.9-1.1
    if 0.9 <= aspect_ratio <= 1.1:
        return "Video 1:1 (Square)"

    # Video 4:5 (Portrait) - aspect ratio 0.7-0.8
    if 0.7 <= aspect_ratio <= 0.8:
        return "Video 4:5 (Portrait)"

    # Non-standard size
    return f"Non-Standard ({width}x{height})"


# Unit tests
if __name__ == "__main__":
    import unittest

    class TestCanonicalSize(unittest.TestCase):
        """Test cases for canonical_size function."""

        def test_iab_standard_sizes(self):
            """Test all IAB standard size mappings."""
            test_cases = [
                ((300, 250), "300x250 (Medium Rectangle)"),
                ((728, 90), "728x90 (Leaderboard)"),
                ((320, 50), "320x50 (Mobile Banner)"),
                ((160, 600), "160x600 (Wide Skyscraper)"),
                ((300, 600), "300x600 (Half Page)"),
                ((970, 250), "970x250 (Billboard)"),
                ((320, 100), "320x100 (Large Mobile Banner)"),
                ((468, 60), "468x60 (Banner)"),
                ((234, 60), "234x60 (Half Banner)"),
                ((120, 600), "120x600 (Skyscraper)"),
                ((970, 90), "970x90 (Super Leaderboard)"),
                ((336, 280), "336x280 (Large Rectangle)"),
                ((250, 250), "250x250 (Square)"),
                ((200, 200), "200x200 (Small Square)"),
                ((180, 150), "180x150 (Small Rectangle)"),
            ]
            for (width, height), expected in test_cases:
                with self.subTest(width=width, height=height):
                    self.assertEqual(canonical_size(width, height), expected)

        def test_adaptive_fluid(self):
            """Test adaptive/fluid sizes (zero dimension)."""
            self.assertEqual(canonical_size(0, 250), "Adaptive/Fluid")
            self.assertEqual(canonical_size(300, 0), "Adaptive/Fluid")
            self.assertEqual(canonical_size(0, 0), "Adaptive/Fluid")

        def test_adaptive_responsive(self):
            """Test adaptive/responsive size (1x1)."""
            self.assertEqual(canonical_size(1, 1), "Adaptive/Responsive")

        def test_video_vertical(self):
            """Test video 9:16 vertical detection (aspect 0.5-0.6)."""
            # 9:16 = 0.5625
            self.assertEqual(canonical_size(1080, 1920), "Video 9:16 (Vertical)")
            self.assertEqual(canonical_size(540, 960), "Video 9:16 (Vertical)")
            # Edge cases within range
            self.assertEqual(canonical_size(500, 1000), "Video 9:16 (Vertical)")  # 0.5
            self.assertEqual(canonical_size(600, 1000), "Video 9:16 (Vertical)")  # 0.6

        def test_video_horizontal(self):
            """Test video 16:9 horizontal detection (aspect 1.7-1.8)."""
            # 16:9 = 1.777...
            self.assertEqual(canonical_size(1920, 1080), "Video 16:9 (Horizontal)")
            self.assertEqual(canonical_size(1280, 720), "Video 16:9 (Horizontal)")
            # Edge cases within range
            self.assertEqual(canonical_size(1700, 1000), "Video 16:9 (Horizontal)")  # 1.7
            self.assertEqual(canonical_size(1800, 1000), "Video 16:9 (Horizontal)")  # 1.8

        def test_video_square(self):
            """Test video 1:1 square detection (aspect 0.9-1.1)."""
            self.assertEqual(canonical_size(1080, 1080), "Video 1:1 (Square)")
            self.assertEqual(canonical_size(500, 500), "Video 1:1 (Square)")
            # Edge cases within range
            self.assertEqual(canonical_size(900, 1000), "Video 1:1 (Square)")  # 0.9
            self.assertEqual(canonical_size(1100, 1000), "Video 1:1 (Square)")  # 1.1

        def test_video_portrait(self):
            """Test video 4:5 portrait detection (aspect 0.7-0.8)."""
            # 4:5 = 0.8
            self.assertEqual(canonical_size(1080, 1350), "Video 4:5 (Portrait)")
            self.assertEqual(canonical_size(800, 1000), "Video 4:5 (Portrait)")  # 0.8
            self.assertEqual(canonical_size(700, 1000), "Video 4:5 (Portrait)")  # 0.7

        def test_non_standard(self):
            """Test non-standard sizes."""
            self.assertEqual(canonical_size(123, 456), "Non-Standard (123x456)")
            self.assertEqual(canonical_size(999, 888), "Non-Standard (999x888)")
            # Size that doesn't match any video aspect ratio
            self.assertEqual(canonical_size(400, 300), "Non-Standard (400x300)")

        def test_iab_standard_exact_match_priority(self):
            """Test that IAB standards take priority over video aspect ratios."""
            # 250x250 is IAB Square, not Video 1:1 (Square)
            self.assertEqual(canonical_size(250, 250), "250x250 (Square)")
            # 200x200 is IAB Small Square, not Video 1:1 (Square)
            self.assertEqual(canonical_size(200, 200), "200x200 (Small Square)")

    class TestGetSizeCategory(unittest.TestCase):
        """Test cases for get_size_category function."""

        def test_iab_standard_category(self):
            """Test IAB Standard category detection."""
            self.assertEqual(get_size_category("300x250 (Medium Rectangle)"), "IAB Standard")
            self.assertEqual(get_size_category("728x90 (Leaderboard)"), "IAB Standard")
            self.assertEqual(get_size_category("320x50 (Mobile Banner)"), "IAB Standard")

        def test_video_category(self):
            """Test Video category detection."""
            self.assertEqual(get_size_category("Video 9:16 (Vertical)"), "Video")
            self.assertEqual(get_size_category("Video 16:9 (Horizontal)"), "Video")
            self.assertEqual(get_size_category("Video 1:1 (Square)"), "Video")
            self.assertEqual(get_size_category("Video 4:5 (Portrait)"), "Video")

        def test_adaptive_category(self):
            """Test Adaptive category detection."""
            self.assertEqual(get_size_category("Adaptive/Fluid"), "Adaptive")
            self.assertEqual(get_size_category("Adaptive/Responsive"), "Adaptive")

        def test_non_standard_category(self):
            """Test Non-Standard category detection."""
            self.assertEqual(get_size_category("Non-Standard (123x456)"), "Non-Standard")
            self.assertEqual(get_size_category("Non-Standard (999x888)"), "Non-Standard")

    # Run tests
    unittest.main(verbosity=2)
