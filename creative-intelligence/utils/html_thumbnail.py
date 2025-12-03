"""HTML Thumbnail Extraction Utility.

Phase 22: Extract image URLs from HTML/JS snippets for thumbnail generation.

This module parses HTML creative snippets to find embedded image URLs that can
be used as thumbnail previews in the dashboard.
"""

import re
from typing import Optional, List
from urllib.parse import urlparse


def extract_image_urls_from_html(html_snippet: str) -> List[str]:
    """Extract all image URLs from an HTML snippet.

    Handles various patterns:
    - <img src="...">
    - <img src='...'>
    - JavaScript document.write with img tags
    - Background images in style attributes

    Args:
        html_snippet: The HTML/JS snippet to parse

    Returns:
        List of image URLs found, in order of appearance
    """
    if not html_snippet:
        return []

    urls = []

    # Pattern 1: Standard img src (handles both quotes)
    # <img src="https://example.com/image.png"
    # <img src='https://example.com/image.png'
    img_src_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    urls.extend(re.findall(img_src_pattern, html_snippet, re.IGNORECASE))

    # Pattern 2: JavaScript escaped quotes in document.write
    # src=\'https://example.com/image.png\'
    # src=\"https://example.com/image.png\"
    js_img_pattern = r"src=\\['\"]([^\\]+)\\['\"]"
    urls.extend(re.findall(js_img_pattern, html_snippet))

    # Pattern 3: Background image in style
    # background-image: url('https://example.com/image.png')
    # background: url("https://example.com/image.png")
    bg_pattern = r'url\(["\']?([^"\')\s]+)["\']?\)'
    bg_urls = re.findall(bg_pattern, html_snippet, re.IGNORECASE)
    # Filter to only image extensions
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
    urls.extend([u for u in bg_urls if any(u.lower().endswith(ext) for ext in image_extensions)])

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen and _is_valid_image_url(url):
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def extract_primary_image_url(html_snippet: str) -> Optional[str]:
    """Extract the primary/best image URL from an HTML snippet.

    Returns the first valid image URL found, which is typically the main
    creative image in most ad formats.

    Args:
        html_snippet: The HTML/JS snippet to parse

    Returns:
        The primary image URL, or None if no valid images found
    """
    urls = extract_image_urls_from_html(html_snippet)

    if not urls:
        return None

    # Prefer larger/main images over tracking pixels
    # Filter out common tracking/pixel patterns
    tracking_patterns = [
        'pixel', 'track', '1x1', '0x0', 'beacon', 'impression',
        'imp.gif', 'imp.png', 'count', 'log'
    ]

    for url in urls:
        url_lower = url.lower()
        is_tracking = any(p in url_lower for p in tracking_patterns)
        if not is_tracking:
            return url

    # If all URLs look like tracking, return the first one anyway
    return urls[0] if urls else None


def _is_valid_image_url(url: str) -> bool:
    """Check if URL is a valid image URL.

    Args:
        url: The URL to validate

    Returns:
        True if URL appears to be a valid image URL
    """
    if not url:
        return False

    # Must start with http:// or https://
    if not url.startswith(('http://', 'https://')):
        return False

    try:
        parsed = urlparse(url)
        # Must have a valid host
        if not parsed.netloc:
            return False
        # Should not be a data URL
        if parsed.scheme == 'data':
            return False
        return True
    except Exception:
        return False


def get_image_dimensions_from_html(html_snippet: str) -> tuple[Optional[int], Optional[int]]:
    """Try to extract image dimensions from HTML snippet.

    Looks for width/height attributes on img tags.

    Args:
        html_snippet: The HTML/JS snippet to parse

    Returns:
        Tuple of (width, height), either may be None if not found
    """
    if not html_snippet:
        return None, None

    # Look for width="300" height="250" patterns
    width_match = re.search(r'width=["\']?(\d+)', html_snippet, re.IGNORECASE)
    height_match = re.search(r'height=["\']?(\d+)', html_snippet, re.IGNORECASE)

    width = int(width_match.group(1)) if width_match else None
    height = int(height_match.group(1)) if height_match else None

    return width, height


# Test function
if __name__ == "__main__":
    # Test with the actual snippet from creative 99878
    test_snippet = '''<script type="text/javascript"> document.write("<a href='%%CLICK_URL_UNESC%%...' style='display:inline-block;width:100%;' id='clickTracker' adCode='{AdCode}'><img src='https://s1.novabeyond.com/creatives/uploads/20241120/43VK6xgFeWaC1PI0mly8O9cXZU1TgB5V.png' impurl='...' onload='isshow.call(this)'/></a>"); </script>'''

    urls = extract_image_urls_from_html(test_snippet)
    print(f"Found {len(urls)} image URLs:")
    for url in urls:
        print(f"  - {url}")

    primary = extract_primary_image_url(test_snippet)
    print(f"\nPrimary image: {primary}")
