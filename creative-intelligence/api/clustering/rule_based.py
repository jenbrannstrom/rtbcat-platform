"""Rule-Based Pre-Clustering for Creatives.

This module provides deterministic clustering based on domain, URL patterns,
and temporal proximity before AI refinement.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.lower() if domain else None
    except Exception:
        return None


def extract_campaign_hint(url: str) -> Optional[str]:
    """Extract campaign-like patterns from URL.

    Examples:
      /holiday-sale-2025 -> holiday-sale
      /promo/summer -> summer
      /campaigns/abc123 -> abc123
      /landing/black-friday -> black-friday
    """
    if not url:
        return None

    url_lower = url.lower()

    patterns = [
        r"/campaigns?/([^/?#]+)",
        r"/promo/([^/?#]+)",
        r"/landing/([^/?#]+)",
        r"/(holiday|summer|winter|spring|black-friday|cyber-monday)[^/?#]*",
        r"/([a-z]+-sale)",
        r"/offer/([^/?#]+)",
        r"/deal/([^/?#]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_lower)
        if match:
            hint = match.group(1)
            # Clean up the hint
            hint = re.sub(r"[-_]+", "-", hint)
            hint = hint.strip("-")
            if len(hint) >= 3:
                return hint

    return None


def get_week_key(created_at: Optional[str | datetime]) -> str:
    """Get week key from timestamp for temporal clustering."""
    if not created_at:
        return "unknown"

    if isinstance(created_at, str):
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(created_at.split(".")[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return "unknown"
        except Exception:
            return "unknown"
    else:
        dt = created_at

    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def pre_cluster_creatives(creatives: list[dict]) -> dict[str, list[dict]]:
    """Group creatives by obvious signals.

    Uses a priority-based approach:
    1. Domain - creatives pointing to same advertiser domain
    2. URL patterns - campaign hints in URL paths
    3. Week created - temporal proximity as fallback

    Args:
        creatives: List of creative dicts with keys:
            - id: Creative ID
            - final_url or detected_url: Landing page URL
            - detected_domain: Extracted domain (optional)
            - created_at: Creation timestamp

    Returns:
        Dict mapping cluster keys to lists of creatives.
        Keys are prefixed with clustering method:
        - "domain:example.com"
        - "url:holiday-sale"
        - "week:2025-W45"
    """
    clusters: dict[str, list[dict]] = defaultdict(list)

    for creative in creatives:
        creative_id = creative.get("id")
        if not creative_id:
            continue

        # Get URL and domain
        url = creative.get("final_url") or creative.get("detected_url") or ""
        domain = creative.get("detected_domain") or extract_domain(url)

        # Priority 1: Group by domain
        if domain and len(domain) >= 3:
            key = f"domain:{domain}"
            clusters[key].append(creative)
            continue

        # Priority 2: Group by URL path patterns
        url_hint = extract_campaign_hint(url)
        if url_hint:
            key = f"url:{url_hint}"
            clusters[key].append(creative)
            continue

        # Priority 3: Fallback to week created
        week_key = get_week_key(creative.get("created_at"))
        key = f"week:{week_key}"
        clusters[key].append(creative)

    return dict(clusters)


def merge_small_clusters(
    clusters: dict[str, list[dict]],
    min_size: int = 3,
) -> dict[str, list[dict]]:
    """Merge clusters smaller than min_size into 'uncategorized'.

    Args:
        clusters: Dict of cluster_key -> creative list
        min_size: Minimum cluster size to keep separate

    Returns:
        Updated clusters dict with small clusters merged.
    """
    result: dict[str, list[dict]] = {}
    uncategorized: list[dict] = []

    for key, creatives in clusters.items():
        if len(creatives) >= min_size:
            result[key] = creatives
        else:
            uncategorized.extend(creatives)

    if uncategorized:
        result["uncategorized"] = uncategorized

    return result


def get_cluster_summary(cluster_key: str, creatives: list[dict]) -> dict:
    """Generate summary of a cluster for AI analysis.

    Args:
        cluster_key: The cluster key (e.g., "domain:example.com")
        creatives: List of creatives in the cluster

    Returns:
        Summary dict for AI analysis.
    """
    # Extract unique domains
    domains = set()
    for c in creatives:
        domain = c.get("detected_domain") or extract_domain(
            c.get("final_url") or c.get("detected_url") or ""
        )
        if domain:
            domains.add(domain)

    # Sample URLs (first 5)
    urls_sample = []
    for c in creatives[:5]:
        url = c.get("final_url") or c.get("detected_url")
        if url:
            urls_sample.append(url)

    # Get formats
    formats = set(c.get("format") for c in creatives if c.get("format"))

    # Date range
    dates = []
    for c in creatives:
        if c.get("created_at"):
            dates.append(str(c["created_at"]))
    dates.sort()

    return {
        "key": cluster_key,
        "count": len(creatives),
        "domains": list(domains)[:10],
        "urls_sample": urls_sample,
        "formats": list(formats),
        "date_range": {
            "earliest": dates[0] if dates else None,
            "latest": dates[-1] if dates else None,
        },
        "creative_ids": [c["id"] for c in creatives],
    }


def generate_cluster_name(cluster_key: str, creatives: list[dict]) -> str:
    """Generate a human-readable name for a cluster.

    This is a simple rule-based name generator. AI refinement
    will provide better names.

    Args:
        cluster_key: The cluster key
        creatives: List of creatives in cluster

    Returns:
        Human-readable cluster name
    """
    parts = cluster_key.split(":", 1)
    if len(parts) != 2:
        return f"Campaign ({len(creatives)} creatives)"

    method, value = parts

    if method == "domain":
        # Clean up domain for display
        name = value.replace(".", " ").title()
        return f"{name} Campaign"

    elif method == "url":
        # Convert URL hint to readable name
        name = value.replace("-", " ").replace("_", " ").title()
        return f"{name} Campaign"

    elif method == "week":
        return f"Week {value} Creatives"

    else:
        return f"Campaign ({len(creatives)} creatives)"
