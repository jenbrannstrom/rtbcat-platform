"""
App name extraction utilities for creative clustering.

Parses app store URLs and HTML snippets to extract app identifiers and names
for better creative clustering (e.g., "Temu" instead of "Google Com").
"""

import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

# Static lookup for known popular apps
# Maps package ID -> human-readable app name
KNOWN_APPS: dict[str, str] = {
    # Social & Entertainment
    "com.zhiliaoapp.musically": "TikTok",
    "com.ss.android.ugc.trill": "TikTok Lite",
    "com.ss.android.ugc.aweme": "Douyin",
    "com.facebook.katana": "Facebook",
    "com.facebook.lite": "Facebook Lite",
    "com.instagram.android": "Instagram",
    "com.whatsapp": "WhatsApp",
    "com.whatsapp.w4b": "WhatsApp Business",
    "com.snapchat.android": "Snapchat",
    "com.twitter.android": "X (Twitter)",
    "com.linkedin.android": "LinkedIn",
    "com.pinterest": "Pinterest",
    "com.reddit.frontpage": "Reddit",
    "com.discord": "Discord",
    "org.telegram.messenger": "Telegram",
    "com.viber.voip": "Viber",
    "jp.naver.line.android": "LINE",
    "com.tencent.mm": "WeChat",

    # E-commerce & Shopping
    "com.einnovation.temu": "Temu",
    "com.amazon.mShop.android.shopping": "Amazon Shopping",
    "com.amazon.avod.thirdpartyclient": "Amazon Prime Video",
    "com.shopee.app": "Shopee",
    "com.alibaba.aliexpresshd": "AliExpress",
    "com.shein.android": "SHEIN",
    "com.wish.android": "Wish",
    "com.ebay.mobile": "eBay",
    "com.walmart.android": "Walmart",
    "com.target.ui": "Target",
    "com.lazada.android": "Lazada",
    "com.jd.jdlite": "JD.com",
    "com.mercadolibre": "Mercado Libre",
    "com.etsy.android": "Etsy",

    # Gaming - Casual
    "com.king.candycrushsaga": "Candy Crush Saga",
    "com.king.candycrushsodasaga": "Candy Crush Soda Saga",
    "com.supercell.clashofclans": "Clash of Clans",
    "com.supercell.clashroyale": "Clash Royale",
    "com.supercell.brawlstars": "Brawl Stars",
    "com.rovio.angrybirds": "Angry Birds",
    "com.kiloo.subwaysurf": "Subway Surfers",
    "com.imangi.templerun2": "Temple Run 2",
    "com.outfit7.talkingtom2": "Talking Tom",
    "com.miniclip.eightballpool": "8 Ball Pool",
    "com.zynga.words3": "Words With Friends",
    "io.voodoo.crowdcity": "Crowd City",
    "com.crazylabs.tricky.puzzle.master": "Brain Test",

    # Gaming - Strategy/RPG
    "com.plarium.raidlegends": "RAID: Shadow Legends",
    "com.lilithgames.roc.gp": "Rise of Kingdoms",
    "com.lilithgames.afkglobal": "AFK Arena",
    "com.mojang.minecraftpe": "Minecraft",
    "com.activision.callofduty.shooter": "Call of Duty Mobile",
    "com.tencent.ig": "PUBG Mobile",
    "com.dts.freefireth": "Free Fire",
    "com.miHoYo.GenshinImpact": "Genshin Impact",
    "com.YoStarEN.Arknights": "Arknights",
    "com.garena.game.codm": "Garena COD Mobile",

    # Streaming & Media
    "com.spotify.music": "Spotify",
    "com.netflix.mediaclient": "Netflix",
    "com.google.android.youtube": "YouTube",
    "com.google.android.apps.youtube.music": "YouTube Music",
    "com.disney.disneyplus": "Disney+",
    "com.hbo.hbonow": "HBO Max",
    "com.hulu.plus": "Hulu",
    "com.amazon.avod": "Prime Video",
    "com.apple.android.music": "Apple Music",
    "com.pandora.android": "Pandora",
    "com.soundcloud.android": "SoundCloud",
    "tv.twitch.android.app": "Twitch",
    "com.crunchyroll.crunchyroid": "Crunchyroll",

    # Finance & Fintech
    "com.paypal.android.p2pmobile": "PayPal",
    "com.venmo": "Venmo",
    "com.squareup.cash": "Cash App",
    "com.revolut.revolut": "Revolut",
    "com.robinhood.android": "Robinhood",
    "com.coinbase.android": "Coinbase",
    "com.binance.dev": "Binance",
    "com.crypto.exchange": "Crypto.com",
    "com.chime.chmrwarern": "Chime",
    "com.zellepay.zelle": "Zelle",

    # Productivity & Utilities
    "com.google.android.gm": "Gmail",
    "com.microsoft.office.outlook": "Outlook",
    "com.google.android.apps.docs": "Google Docs",
    "com.dropbox.android": "Dropbox",
    "com.evernote": "Evernote",
    "com.notion.id": "Notion",
    "com.todoist": "Todoist",
    "com.slack": "Slack",
    "us.zoom.videomeetings": "Zoom",
    "com.microsoft.teams": "Microsoft Teams",

    # Travel & Transport
    "com.ubercab": "Uber",
    "com.ubercab.eats": "Uber Eats",
    "com.lyft.android": "Lyft",
    "com.grabhitch.passenger": "Grab",
    "com.gojek.app": "Gojek",
    "com.booking": "Booking.com",
    "com.airbnb.android": "Airbnb",
    "com.tripadvisor.tripadvisor": "Tripadvisor",
    "com.expedia.bookings": "Expedia",

    # Food Delivery
    "com.dd.doordash": "DoorDash",
    "com.grubhub.android": "Grubhub",
    "com.postmates.android": "Postmates",
    "com.deliveroo.orderapp": "Deliveroo",
    "com.mcdonalds.app": "McDonald's",
    "com.starbucks.mobilecard": "Starbucks",

    # Health & Fitness
    "com.calm.android": "Calm",
    "com.headspace.android": "Headspace",
    "com.fitbit.FitbitMobile": "Fitbit",
    "com.myfitnesspal.android": "MyFitnessPal",
    "com.nike.omega": "Nike Run Club",
    "com.strava": "Strava",
    "cc.forestapp": "Forest",

    # Dating
    "com.tinder": "Tinder",
    "com.bumble.app": "Bumble",
    "com.hinge.app": "Hinge",
    "com.match.android.matchmobile": "Match",
    "com.badoo.mobile": "Badoo",

    # News & Reading
    "com.cnn.mobile.android.phone": "CNN",
    "com.nytimes.android": "NY Times",
    "com.bbc.news": "BBC News",
    "com.medium.reader": "Medium",
    "com.readdle.documents": "Documents",
    "com.audible.application": "Audible",
    "com.amazon.kindle": "Kindle",

    # Education
    "com.duolingo": "Duolingo",
    "com.quizlet.quizletandroid": "Quizlet",
    "com.coursera.app": "Coursera",
    "com.udemy.android": "Udemy",
    "com.khan.academy": "Khan Academy",

    # Wallpapers & Customization
    "helectronsoft.com.grubl.live.wallpapers3d": "4D Wallpaper",
    "com.flavionet.android.camera.lite": "Zedge",
    "me.morirain.dev.iconpack.flavor": "Icon Pack",
}


def get_app_name(package_id: str) -> str:
    """
    Get app name from package ID.
    First checks lookup table, then auto-formats if unknown.

    Args:
        package_id: Android package ID (e.g., "com.example.app")

    Returns:
        Human-readable app name
    """
    if not package_id:
        return "Unknown"

    # Check lookup table first
    if package_id in KNOWN_APPS:
        return KNOWN_APPS[package_id]

    # Auto-format unknown package IDs
    return format_package_id_as_name(package_id)


def format_package_id_as_name(package_id: str) -> str:
    """
    Convert package ID to a readable name.
    Example: com.zhiliaoapp.musically -> "Zhiliaoapp Musically"

    Args:
        package_id: Android package ID

    Returns:
        Formatted name from package ID
    """
    if not package_id:
        return "Unknown"

    # Split by dots and take relevant parts (skip com/org/net prefixes)
    parts = package_id.split(".")

    # Skip common prefixes
    skip_prefixes = {"com", "org", "net", "io", "me", "app", "android", "google"}
    relevant_parts = [p for p in parts if p.lower() not in skip_prefixes]

    # If nothing left, use last 2 parts
    if not relevant_parts and len(parts) >= 2:
        relevant_parts = parts[-2:]
    elif not relevant_parts:
        relevant_parts = parts

    # Format each part: split camelCase, replace underscores, capitalize
    formatted_parts = []
    for part in relevant_parts:
        # Split camelCase
        formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', part)
        # Replace underscores and hyphens with spaces
        formatted = formatted.replace("_", " ").replace("-", " ")
        # Capitalize each word
        formatted = " ".join(word.capitalize() for word in formatted.split())
        formatted_parts.append(formatted)

    return " ".join(formatted_parts) if formatted_parts else "Unknown"


def parse_app_store_url(url: str) -> Optional[dict]:
    """
    Parse app store URLs and extract app info.

    Args:
        url: URL to parse

    Returns:
        Dict with app_id, app_name, store or None if not an app store URL
    """
    if not url:
        return None

    try:
        # Decode URL-encoded strings
        decoded = unquote(url)

        # Google Play Store
        # Example: https://play.google.com/store/apps/details?id=com.example.app
        play_match = re.search(
            r'play\.google\.com/store/apps/details\?id=([a-zA-Z0-9._-]+)',
            decoded
        )
        if play_match:
            app_id = play_match.group(1)
            return {
                "app_id": app_id,
                "app_name": get_app_name(app_id),
                "store": "play_store",
            }

        # Apple App Store
        # Example: https://apps.apple.com/us/app/app-name/id123456789
        appstore_match = re.search(
            r'apps\.apple\.com/[^/]+/app/([^/]+)/id(\d+)',
            decoded
        )
        if appstore_match:
            app_slug = appstore_match.group(1)
            app_id = f"id{appstore_match.group(2)}"
            # Format the slug as name (e.g., "candy-crush-saga" -> "Candy Crush Saga")
            app_name = app_slug.replace("-", " ").title()
            return {
                "app_id": app_id,
                "app_name": app_name,
                "store": "app_store",
            }

        # AppsFlyer tracking URLs
        # Example: https://app.appsflyer.com/com.example.app?pid=...
        appsflyer_match = re.search(
            r'app\.appsflyer\.com/([a-zA-Z0-9._-]+)',
            decoded
        )
        if appsflyer_match:
            app_id = appsflyer_match.group(1)
            return {
                "app_id": app_id,
                "app_name": get_app_name(app_id),
                "store": "appsflyer",
            }

        # Adjust tracking URLs
        # Example: https://app.adjust.com/abc123?campaign=MyApp
        adjust_match = re.search(
            r'adjust\.com.*[?&]campaign=([^&]+)',
            decoded,
            re.IGNORECASE
        )
        if adjust_match:
            campaign = unquote(adjust_match.group(1))
            # Clean up campaign name
            app_name = campaign.replace("_", " ").replace("-", " ").title()
            return {
                "app_id": campaign,
                "app_name": app_name,
                "store": "adjust",
            }

        # Firebase Dynamic Links - recurse into the actual link
        # Example: https://example.page.link?link=https://play.google.com/...
        firebase_match = re.search(
            r'\.page\.link.*[?&]link=([^&]+)',
            decoded
        )
        if firebase_match:
            inner_url = unquote(firebase_match.group(1))
            return parse_app_store_url(inner_url)

        # OneLink (AppsFlyer) - extract app from path or params
        onelink_match = re.search(
            r'onelink\.me/[^/]+/([a-zA-Z0-9._-]+)',
            decoded
        )
        if onelink_match:
            app_id = onelink_match.group(1)
            if app_id and len(app_id) > 3:  # Skip short tracking codes
                return {
                    "app_id": app_id,
                    "app_name": format_package_id_as_name(app_id),
                    "store": "onelink",
                }

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

    # Patterns to extract URLs from HTML
    patterns = [
        # Standard href
        r'href=["\']([^"\']+)["\']',
        # JavaScript escaped quotes (for document.write)
        r'href=\\["\']([^\\]+)\\["\']',
        # window.open calls
        r'window\.open\(["\']([^"\']+)["\']',
        r'window\.open\(\\["\']([^\\]+)\\["\']',
        # location.href assignments
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
        # Direct Play Store URLs in code
        r'(https?://play\.google\.com/store/apps/details\?id=[a-zA-Z0-9._-]+)',
        # Direct App Store URLs in code
        r'(https?://apps\.apple\.com/[^\s"\'<>]+)',
        # AppsFlyer URLs
        r'(https?://app\.appsflyer\.com/[^\s"\'<>]+)',
        # Adjust URLs
        r'(https?://[^/]*adjust\.com[^\s"\'<>]+)',
        # Firebase dynamic links
        r'(https?://[^/]+\.page\.link[^\s"\'<>]+)',
        # Generic URLs in JavaScript const/var
        r'(?:const|var|let)\s+(?:url|link|dest|click)\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        urls.extend(matches)

    # Clean and filter URLs
    cleaned_urls: list[str] = []
    seen: set[str] = set()

    for url in urls:
        # Skip if not a valid URL
        if not url or not url.startswith(("http://", "https://")):
            continue

        # Skip DFP/tracking macros
        if "%%" in url or "{{" in url:
            continue

        # Skip tracking pixels and beacons
        tracking_indicators = [
            "pixel", "track", "beacon", "1x1", "impression",
            "imp.", "pxl", "t.co", "bit.ly", "goo.gl",
            "clickserve", "doubleclick", "googlesyndication",
            "googleadservices", "facebook.com/tr", "analytics",
        ]
        url_lower = url.lower()
        if any(indicator in url_lower for indicator in tracking_indicators):
            continue

        # Deduplicate
        if url not in seen:
            seen.add(url)
            cleaned_urls.append(url)

    return cleaned_urls


def extract_app_info_from_creative(
    final_url: Optional[str] = None,
    declared_urls: Optional[list[str]] = None,
    html_snippet: Optional[str] = None,
    advertiser_name: Optional[str] = None,
) -> dict:
    """
    Extract app info from creative data using multiple sources.

    Priority order:
    1. Parse HTML snippet for embedded app store URLs
    2. Parse declaredClickThroughUrls
    3. Parse final_url
    4. Use advertiser domain as fallback

    Args:
        final_url: Primary destination URL
        declared_urls: List of declared click-through URLs
        html_snippet: HTML creative snippet content
        advertiser_name: Declared advertiser name

    Returns:
        Dict with app_id, app_name, app_store (may be empty)
    """
    result = {
        "app_id": None,
        "app_name": None,
        "app_store": None,
    }

    # 1. Try HTML snippet first (most accurate for HTML creatives)
    if html_snippet:
        urls = extract_urls_from_html_snippet(html_snippet)
        for url in urls:
            app_info = parse_app_store_url(url)
            if app_info:
                return app_info

    # 2. Try declared click-through URLs
    if declared_urls:
        for url in declared_urls:
            app_info = parse_app_store_url(url)
            if app_info:
                return app_info

    # 3. Try final_url
    if final_url:
        app_info = parse_app_store_url(final_url)
        if app_info:
            return app_info

    # 4. Fallback to advertiser name or domain
    if advertiser_name:
        result["app_name"] = advertiser_name
    elif final_url:
        try:
            parsed = urlparse(final_url)
            domain = parsed.netloc.replace("www.", "")
            # Clean domain to name
            domain_name = domain.split(".")[0]
            result["app_name"] = domain_name.replace("-", " ").replace("_", " ").title()
        except Exception:
            pass

    return result
