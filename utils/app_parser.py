"""
App name extraction utilities for creative clustering.

Fetches app names dynamically from app stores and websites.
No static lookup tables - always gets the real name from the source.
"""

import re
import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote
from functools import lru_cache
import aiohttp

logger = logging.getLogger(__name__)

# Cache timeout in seconds (1 hour)
CACHE_TTL = 3600

# Simple in-memory cache for app names
_app_name_cache: dict[str, tuple[str, float]] = {}


def _get_cached(key: str) -> Optional[str]:
    """Get value from cache if not expired."""
    import time
    if key in _app_name_cache:
        value, timestamp = _app_name_cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
    return None


def _set_cached(key: str, value: str) -> None:
    """Set value in cache with current timestamp."""
    import time
    _app_name_cache[key] = (value, time.time())


async def fetch_play_store_name(package_id: str) -> Optional[str]:
    """
    Fetch app name from Google Play Store.

    Args:
        package_id: Android package ID (e.g., "com.example.app")

    Returns:
        App name or None if not found
    """
    cache_key = f"play:{package_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    url = f"https://play.google.com/store/apps/details?id={package_id}&hl=en"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.debug(f"Play Store returned {response.status} for {package_id}")
                    return None

                html = await response.text()

                # Extract app name from the page title or meta tags
                # Page title format: "App Name - Apps on Google Play"
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1)
                    # Remove " - Apps on Google Play" suffix
                    app_name = re.sub(r'\s*[-–]\s*Apps on Google Play.*$', '', title).strip()
                    if app_name and app_name != "Google Play":
                        _set_cached(cache_key, app_name)
                        return app_name

                # Fallback: try og:title meta tag
                og_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if not og_match:
                    og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html, re.IGNORECASE)

                if og_match:
                    app_name = og_match.group(1).strip()
                    # Remove suffix if present
                    app_name = re.sub(r'\s*[-–]\s*Apps on Google Play.*$', '', app_name).strip()
                    if app_name:
                        _set_cached(cache_key, app_name)
                        return app_name

                return None

    except asyncio.TimeoutError:
        logger.debug(f"Timeout fetching Play Store name for {package_id}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching Play Store name for {package_id}: {e}")
        return None


async def fetch_app_store_name(app_id: str) -> Optional[str]:
    """
    Fetch app name from Apple App Store using iTunes Lookup API.

    Args:
        app_id: Apple App Store ID (numeric, e.g., "123456789")

    Returns:
        App name or None if not found
    """
    # Strip 'id' prefix if present
    numeric_id = app_id.lstrip('id')
    if not numeric_id.isdigit():
        return None

    cache_key = f"appstore:{numeric_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Use iTunes Lookup API - it's official and returns JSON
    url = f"https://itunes.apple.com/lookup?id={numeric_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.debug(f"iTunes API returned {response.status} for {app_id}")
                    return None

                # iTunes API returns text/javascript content-type, so we need to bypass content-type check
                data = await response.json(content_type=None)
                results = data.get("results", [])

                if results and len(results) > 0:
                    app_name = results[0].get("trackName")
                    if app_name:
                        _set_cached(cache_key, app_name)
                        return app_name

                return None

    except asyncio.TimeoutError:
        logger.debug(f"Timeout fetching App Store name for {app_id}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching App Store name for {app_id}: {e}")
        return None


async def fetch_website_title(url: str) -> Optional[str]:
    """
    Fetch page title from a website.

    Args:
        url: Full URL to fetch

    Returns:
        Page title or None if not found
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()
    except Exception:
        return None

    cache_key = f"web:{domain}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return None

                # Only read first 50KB to get title
                html = await response.content.read(50000)
                html = html.decode('utf-8', errors='ignore')

                # Try og:title first (usually cleaner)
                og_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if not og_match:
                    og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html, re.IGNORECASE)

                if og_match:
                    title = og_match.group(1).strip()
                    if title:
                        _set_cached(cache_key, title)
                        return title

                # Fallback to <title> tag
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                    # Clean up common suffixes
                    title = re.sub(r'\s*[-|–]\s*(Home|Official Site|Official Website).*$', '', title, flags=re.IGNORECASE).strip()
                    if title:
                        _set_cached(cache_key, title)
                        return title

                return None

    except asyncio.TimeoutError:
        logger.debug(f"Timeout fetching title for {url}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching title for {url}: {e}")
        return None


def parse_app_store_url(url: str) -> Optional[dict]:
    """
    Parse app store URLs and extract app info.
    Does NOT fetch names - just extracts IDs and store type.

    Args:
        url: URL to parse

    Returns:
        Dict with app_id, store, or None if not an app store URL
    """
    if not url:
        return None

    try:
        # Normalize URL - add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        decoded = unquote(url)

        # Google Play Store
        play_match = re.search(
            r'play\.google\.com/store/apps/details\?id=([a-zA-Z0-9._-]+)',
            decoded
        )
        if play_match:
            return {
                "app_id": play_match.group(1),
                "store": "play_store",
            }

        # Apple App Store
        appstore_match = re.search(
            r'apps\.apple\.com/[^/]+/app/[^/]+/id(\d+)',
            decoded
        )
        if appstore_match:
            return {
                "app_id": f"id{appstore_match.group(1)}",
                "store": "app_store",
            }

        # AppsFlyer tracking URLs
        appsflyer_match = re.search(
            r'app\.appsflyer\.com/([a-zA-Z0-9._-]+)',
            decoded
        )
        if appsflyer_match:
            app_id = appsflyer_match.group(1)
            # Check if it looks like an Android package
            if '.' in app_id and not app_id.startswith('id'):
                return {
                    "app_id": app_id,
                    "store": "play_store",  # AppsFlyer usually tracks Android
                }

        # Adjust tracking URLs - try to extract app info from deep link
        if 'adjust.com' in decoded or 'adj.st' in decoded:
            # Look for deep_link param which might contain app store URL
            deep_link_match = re.search(r'[?&]deep_link=([^&]+)', decoded)
            if deep_link_match:
                inner_url = unquote(deep_link_match.group(1))
                return parse_app_store_url(inner_url)

        # Firebase Dynamic Links
        firebase_match = re.search(r'\.page\.link.*[?&]link=([^&]+)', decoded)
        if firebase_match:
            inner_url = unquote(firebase_match.group(1))
            return parse_app_store_url(inner_url)

        return None

    except Exception:
        return None


def extract_urls_from_html_snippet(html: str) -> list[str]:
    """
    Extract all destination URLs from HTML creative snippet.

    Args:
        html: HTML snippet content

    Returns:
        List of extracted URLs (filtered to remove tracking pixels)
    """
    if not html:
        return []

    urls: list[str] = []

    patterns = [
        r'href=["\']([^"\']+)["\']',
        r'href=\\["\']([^\\]+)\\["\']',
        r'window\.open\(["\']([^"\']+)["\']',
        r'window\.open\(\\["\']([^\\]+)\\["\']',
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
        r'(https?://play\.google\.com/store/apps/details\?id=[a-zA-Z0-9._-]+)',
        r'(https?://apps\.apple\.com/[^\s"\'<>]+)',
        r'(https?://app\.appsflyer\.com/[^\s"\'<>]+)',
        r'(https?://[^/]*adjust\.com[^\s"\'<>]+)',
        r'(https?://[^/]+\.page\.link[^\s"\'<>]+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        urls.extend(matches)

    # Clean and filter URLs
    cleaned: list[str] = []
    seen: set[str] = set()

    tracking_indicators = [
        "pixel", "track", "beacon", "1x1", "impression",
        "imp.", "pxl", "t.co", "bit.ly", "goo.gl",
        "clickserve", "doubleclick", "googlesyndication",
        "googleadservices", "facebook.com/tr", "analytics",
    ]

    for url in urls:
        if not url or not url.startswith(("http://", "https://")):
            continue
        if "%%" in url or "{{" in url:
            continue
        url_lower = url.lower()
        if any(ind in url_lower for ind in tracking_indicators):
            continue
        if url not in seen:
            seen.add(url)
            cleaned.append(url)

    return cleaned


async def get_app_name(app_id: str, store: str) -> Optional[str]:
    """
    Get app name from the appropriate store.

    Args:
        app_id: App identifier
        store: Store type ("play_store" or "app_store")

    Returns:
        App name or None
    """
    if store == "play_store":
        return await fetch_play_store_name(app_id)
    elif store == "app_store":
        return await fetch_app_store_name(app_id)
    return None


def get_app_name_sync(app_id: str, store: str) -> Optional[str]:
    """
    Synchronous wrapper for get_app_name.
    Creates event loop if needed.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, can't use run_until_complete
            # Return None and let the caller handle async
            return None
        return loop.run_until_complete(get_app_name(app_id, store))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(get_app_name(app_id, store))


def _normalize_url(url: str) -> str:
    """Normalize URL by adding https:// if no protocol is present."""
    if not url:
        return url
    if not url.startswith(('http://', 'https://')):
        return 'https://' + url
    return url


def format_package_id_as_name(package_id: str) -> str:
    """
    Fallback: Format package ID as readable name.
    Only used when store fetch fails.

    Example: com.zhiliaoapp.musically -> "Zhiliaoapp Musically"
    """
    if not package_id:
        return "Unknown"

    parts = package_id.split(".")
    skip_prefixes = {"com", "org", "net", "io", "me", "app", "android", "google"}
    relevant_parts = [p for p in parts if p.lower() not in skip_prefixes]

    if not relevant_parts and len(parts) >= 2:
        relevant_parts = parts[-2:]
    elif not relevant_parts:
        relevant_parts = parts

    formatted_parts = []
    for part in relevant_parts:
        formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', part)
        formatted = formatted.replace("_", " ").replace("-", " ")
        formatted = " ".join(word.capitalize() for word in formatted.split())
        formatted_parts.append(formatted)

    return " ".join(formatted_parts) if formatted_parts else "Unknown"


async def extract_app_info_from_creative(
    final_url: Optional[str] = None,
    declared_urls: Optional[list[str]] = None,
    html_snippet: Optional[str] = None,
    advertiser_name: Optional[str] = None,
    fetch_names: bool = True,
) -> dict:
    """
    Extract app info from creative data using multiple sources.
    Fetches actual app names from stores when possible.

    Priority order:
    1. Parse HTML snippet for embedded app store URLs
    2. Parse declaredClickThroughUrls
    3. Parse final_url
    4. Fetch website title as fallback

    Args:
        final_url: Primary destination URL
        declared_urls: List of declared click-through URLs
        html_snippet: HTML creative snippet content
        advertiser_name: Declared advertiser name (not used, kept for compatibility)
        fetch_names: Whether to fetch names from stores (set False for sync contexts)

    Returns:
        Dict with app_id, app_name, app_store (may be empty)
    """
    result = {
        "app_id": None,
        "app_name": None,
        "app_store": None,
    }

    # Normalize final_url
    if final_url:
        final_url = _normalize_url(final_url)

    # Collect all URLs to check
    urls_to_check: list[str] = []

    if html_snippet:
        urls_to_check.extend(extract_urls_from_html_snippet(html_snippet))

    if declared_urls:
        urls_to_check.extend([_normalize_url(u) for u in declared_urls])

    if final_url:
        urls_to_check.append(final_url)

    # Try to find an app store URL
    for url in urls_to_check:
        app_info = parse_app_store_url(url)
        if app_info:
            result["app_id"] = app_info["app_id"]
            result["app_store"] = app_info["store"]

            # Fetch the actual name from the store
            if fetch_names:
                app_name = await get_app_name(app_info["app_id"], app_info["store"])
                if app_name:
                    result["app_name"] = app_name
                else:
                    # Fallback to formatted package ID
                    result["app_name"] = format_package_id_as_name(app_info["app_id"])
            else:
                result["app_name"] = format_package_id_as_name(app_info["app_id"])

            return result

    # No app store URL found - try to get website title
    if final_url and fetch_names:
        try:
            parsed = urlparse(final_url)
            # Skip tracking domains
            tracking_domains = ['appsflyer', 'adjust', 'branch', 'onelink', 'page.link']
            if not any(td in parsed.netloc.lower() for td in tracking_domains):
                title = await fetch_website_title(final_url)
                if title:
                    result["app_name"] = title
                    return result
        except Exception:
            pass

    # Final fallback: extract domain name
    if final_url:
        try:
            parsed = urlparse(final_url)
            domain = parsed.netloc.replace("www.", "")
            domain_name = domain.split(".")[0]
            result["app_name"] = domain_name.replace("-", " ").replace("_", " ").title()
        except Exception:
            pass

    return result


def extract_app_info_from_creative_sync(
    final_url: Optional[str] = None,
    declared_urls: Optional[list[str]] = None,
    html_snippet: Optional[str] = None,
    advertiser_name: Optional[str] = None,
) -> dict:
    """
    Synchronous version of extract_app_info_from_creative.
    Does not fetch names from stores - uses fallback formatting.
    """
    result = {
        "app_id": None,
        "app_name": None,
        "app_store": None,
    }

    # Normalize final_url
    if final_url:
        final_url = _normalize_url(final_url)

    urls_to_check: list[str] = []

    if html_snippet:
        urls_to_check.extend(extract_urls_from_html_snippet(html_snippet))

    if declared_urls:
        urls_to_check.extend([_normalize_url(u) for u in declared_urls])

    if final_url:
        urls_to_check.append(final_url)

    for url in urls_to_check:
        app_info = parse_app_store_url(url)
        if app_info:
            result["app_id"] = app_info["app_id"]
            result["app_store"] = app_info["store"]
            result["app_name"] = format_package_id_as_name(app_info["app_id"])
            return result

    # Fallback to domain name
    if final_url:
        try:
            parsed = urlparse(final_url)
            domain = parsed.netloc.replace("www.", "")
            domain_name = domain.split(".")[0]
            result["app_name"] = domain_name.replace("-", " ").replace("_", " ").title()
        except Exception:
            pass

    return result
