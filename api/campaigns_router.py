"""FastAPI router for Campaign Clustering endpoints.

This module provides REST API endpoints for:
- Auto-clustering creatives into campaigns
- Managing campaigns
- Campaign performance aggregation
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from services.campaigns_service import CampaignsService, AICampaign
from utils.app_parser import (
    fetch_website_title,
    format_package_id_as_name,
    get_app_name,
    parse_app_store_url,
)
from api.dependencies import get_store, get_current_user, resolve_buyer_id
from storage.postgres_store import PostgresStore
from services.auth_service import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


CLICK_MACRO_PATTERNS = [
    r"%%Click_Url_Unesc%%",
    r"%%Click_Url%%",
    r"%%CLICK_URL_UNESC%%",
    r"%%CLICK_URL%%",
    r"\$\{CLICK_URL\}",
    r"\[CLICK_URL\]",
]

NAME_GARBAGE_TOKENS = [
    "click_url",
    "click url",
    "%%",
    "%3a",
    "%2f",
    "http%",
    "https%",
    "{click",
    "[click",
]

TRACKING_DOMAIN_TOKENS = [
    "appsflyer",
    "adjust",
    "branch",
    "onelink",
    "page.link",
    "doubleclick",
    "googleadservices",
]


# Singleton CampaignsService instance
_campaigns_service: Optional[CampaignsService] = None


def get_campaigns_service() -> CampaignsService:
    """Get or create the CampaignsService instance."""
    global _campaigns_service
    if _campaigns_service is None:
        _campaigns_service = CampaignsService()
    return _campaigns_service


# ============================================
# Request/Response Models
# ============================================

class CountryBreakdownEntry(BaseModel):
    """Country breakdown entry for a campaign."""
    creative_ids: list[str] = []
    spend_micros: int = 0
    impressions: int = 0


class AICampaignResponse(BaseModel):
    """Response model for AI campaign."""
    id: str
    seat_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    ai_generated: bool = True
    ai_confidence: Optional[float] = None
    clustering_method: Optional[str] = None
    status: str = "active"
    creative_count: int = 0
    creative_ids: list[str] = []  # Added for frontend compatibility
    country_breakdown: Optional[dict[str, CountryBreakdownEntry]] = None  # Phase 22
    performance: Optional[dict] = None
    # Phase 29: Disapproval tracking
    disapproved_count: int = 0
    has_disapproved: bool = False


class AutoClusterRequest(BaseModel):
    """Request body for auto-clustering."""
    by_url: bool = True
    by_country: bool = False
    buyer_id: Optional[str] = None  # Filter by buyer_id for multi-account support


class ClusterSuggestion(BaseModel):
    """A suggested campaign cluster."""
    suggested_name: str
    creative_ids: list[str]
    domain: Optional[str] = None
    country: Optional[str] = None


class AutoClusterResponse(BaseModel):
    """Response model for auto-cluster suggestions."""
    suggestions: list[ClusterSuggestion]
    unclustered_count: int


class CampaignCreateRequest(BaseModel):
    """Request for creating a new campaign."""
    name: str
    creative_ids: list[str] = []
    description: Optional[str] = None


class CampaignUpdateRequest(BaseModel):
    """Request for updating campaign."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CampaignPatchRequest(BaseModel):
    """Request for patching campaign (add/remove creatives)."""
    name: Optional[str] = None
    add_creative_ids: Optional[list[str]] = None
    remove_creative_ids: Optional[list[str]] = None


class AssignCreativesRequest(BaseModel):
    """Request for assigning creatives."""
    creative_ids: list[str]


class MoveCreativeRequest(BaseModel):
    """Request for moving a creative."""
    to_campaign_id: str


class CampaignPerformanceResponse(BaseModel):
    """Response for campaign performance."""
    impressions: int = 0
    clicks: int = 0
    spend: float = 0
    queries: int = 0
    win_rate: Optional[float] = None
    ctr: Optional[float] = None
    cpm: Optional[float] = None


# ============================================
# Helper Functions
# ============================================

# All endpoints now use CampaignsService for database access


# ============================================
# Clustering Endpoints
# ============================================

async def _get_creative_countries(creative_ids: list[str], days: int = 30) -> dict[str, str]:
    """Get the primary country (by spend) for each creative."""
    svc = get_campaigns_service()
    return await svc.get_creative_countries(creative_ids, days)


def _split_clusters_by_country(
    clusters: dict[str, list[dict]],
    creative_countries: dict[str, str],
) -> dict[str, list[dict]]:
    """Split clusters by country, creating 'domain:example.com:US' style keys."""
    result: dict[str, list[dict]] = {}

    for cluster_key, creatives in clusters.items():
        # Group by country within this cluster
        by_country: dict[str, list[dict]] = {}
        for creative in creatives:
            country = creative_countries.get(creative["id"], "UNKNOWN")
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(creative)

        # Create new cluster keys with country suffix
        for country, country_creatives in by_country.items():
            new_key = f"{cluster_key}:{country}"
            result[new_key] = country_creatives

    return result


def _normalize_whitespace(value: str) -> str:
    return " ".join((value or "").strip().split())


def _slugify_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return slug[:80] if slug else "unknown"


def _is_name_garbage(value: Optional[str]) -> bool:
    if value is None:
        return True
    normalized = _normalize_whitespace(value)
    if not normalized:
        return True

    lower = normalized.lower()
    if lower in {"unknown", "none", "null", "untitled", "campaign"}:
        return True
    if re.fullmatch(r"(?:id)?\d{6,}", lower):
        return True
    if re.match(r"^(https?://|www\.)", lower):
        return True

    percent_count = normalized.count("%")
    if percent_count >= 3 or (len(normalized) > 0 and percent_count / len(normalized) > 0.15):
        return True

    if len(normalized) > 140:
        return True

    return any(token in lower for token in NAME_GARBAGE_TOKENS)


def _is_usable_name(value: Optional[str]) -> bool:
    return not _is_name_garbage(value)


def _sanitize_destination_url(url: Optional[str]) -> str:
    if not url:
        return ""

    cleaned = url.strip().strip("'").strip('"')

    for macro in CLICK_MACRO_PATTERNS:
        cleaned = re.sub(macro, "", cleaned, flags=re.IGNORECASE)

    decoded = cleaned
    for _ in range(3):
        if "%" not in decoded:
            break
        candidate = unquote(decoded)
        if candidate == decoded:
            break
        decoded = candidate

    decoded = _normalize_whitespace(decoded).strip().strip("'").strip('"')
    for macro in CLICK_MACRO_PATTERNS:
        decoded = re.sub(macro, "", decoded, flags=re.IGNORECASE)

    embedded_match = re.search(r"(https?://[^\s\"'<>]+)", decoded, re.IGNORECASE)
    if embedded_match:
        decoded = embedded_match.group(1)
    elif decoded.startswith("//"):
        decoded = f"https:{decoded}"
    elif decoded and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", decoded):
        decoded = f"https://{decoded.lstrip('/')}"

    decoded = re.sub(
        r"^(https?)://",
        lambda match: f"{match.group(1).lower()}://",
        decoded,
        flags=re.IGNORECASE,
    )

    return decoded.strip()


def _extract_reference_domain(url: Optional[str]) -> Optional[str]:
    cleaned_url = _sanitize_destination_url(url)
    if not cleaned_url:
        return None

    try:
        parsed = urlparse(cleaned_url)
        domain = (parsed.netloc or "").strip().lower()
        if not domain and parsed.path:
            first_part = parsed.path.split("/")[0]
            if "." in first_part and " " not in first_part:
                domain = first_part.strip().lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain or _is_name_garbage(domain):
            return None
        return domain
    except Exception:
        return None


async def _resolve_cluster_display_name(
    *,
    cluster_key: str,
    app_name: Optional[str],
    app_id: Optional[str],
    app_store: Optional[str],
    final_url: Optional[str],
    advertiser_name: Optional[str],
) -> str:
    if _is_usable_name(app_name):
        return _normalize_whitespace(app_name or "")

    cleaned_url = _sanitize_destination_url(final_url)

    if app_id and app_store in {"play_store", "app_store"}:
        try:
            store_name = await get_app_name(app_id, app_store)
            if _is_usable_name(store_name):
                return _normalize_whitespace(store_name or "")
        except Exception as e:
            logger.debug("App store name lookup failed for %s (%s): %s", app_id, app_store, e)

        fallback_name = format_package_id_as_name(app_id)
        if _is_usable_name(fallback_name):
            return fallback_name

    if cleaned_url:
        try:
            parsed_store_info = parse_app_store_url(cleaned_url)
        except Exception:
            parsed_store_info = None

        if parsed_store_info:
            parsed_app_id = parsed_store_info.get("app_id")
            parsed_store = parsed_store_info.get("store")
            if parsed_app_id and parsed_store:
                try:
                    store_name = await get_app_name(parsed_app_id, parsed_store)
                    if _is_usable_name(store_name):
                        return _normalize_whitespace(store_name or "")
                except Exception as e:
                    logger.debug(
                        "Parsed app store name lookup failed for %s (%s): %s",
                        parsed_app_id,
                        parsed_store,
                        e,
                    )

                fallback_name = format_package_id_as_name(parsed_app_id)
                if _is_usable_name(fallback_name):
                    return fallback_name

        domain_for_title = _extract_reference_domain(cleaned_url) or ""
        is_tracking_domain = any(token in domain_for_title for token in TRACKING_DOMAIN_TOKENS)
        if not is_tracking_domain:
            try:
                website_title = await fetch_website_title(cleaned_url)
                if _is_usable_name(website_title):
                    return _normalize_whitespace(website_title or "")
            except Exception as e:
                logger.debug("Website title lookup failed for %s: %s", cleaned_url, e)

    if _is_usable_name(advertiser_name):
        return _normalize_whitespace(advertiser_name or "")

    if cluster_key.startswith("name:"):
        candidate = cluster_key.split(":", 1)[1].replace("_", " ").strip()
        candidate = " ".join(word.capitalize() for word in candidate.split())
        if _is_usable_name(candidate):
            return candidate

    if cluster_key.startswith("advertiser:"):
        candidate = cluster_key.split(":", 1)[1].replace("_", " ").strip()
        candidate = " ".join(word.capitalize() for word in candidate.split())
        if _is_usable_name(candidate):
            return candidate

    if cluster_key.startswith("app:"):
        candidate = cluster_key.split(":", 1)[1]
        fallback_name = format_package_id_as_name(candidate)
        if _is_usable_name(fallback_name):
            return fallback_name

    fallback_domain = _extract_reference_domain(cleaned_url)
    if not fallback_domain and ":" not in cluster_key and "." in cluster_key:
        fallback_domain = cluster_key.strip().lower()

    if fallback_domain:
        fallback_name = _generate_name_from_domain(fallback_domain)
        if _is_usable_name(fallback_name):
            return fallback_name

    return "Unknown Campaign"


@router.post("/auto-cluster", response_model=AutoClusterResponse)
async def auto_cluster_creatives(
    request: AutoClusterRequest,
    store: PostgresStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Auto-cluster unclustered creatives by destination URL (and optionally country).

    Returns suggested clusters without saving them. User must confirm to create.
    Supports buyer_id filtering for multi-account scenarios.
    """
    try:
        buyer_id = await resolve_buyer_id(request.buyer_id, store=store, user=user)
        svc = get_campaigns_service()
        rows = await svc.get_unclustered_creatives(buyer_id)
        unclustered_count = len(rows)

        if not rows:
            return AutoClusterResponse(suggestions=[], unclustered_count=0)

        logger.info(f"Found {unclustered_count} unclustered creatives for buyer_id={buyer_id}")

        # Group by cluster key (app ID for app stores, domain/brand for others)
        from collections import defaultdict

        # Maps cluster_key -> metadata + creative IDs
        cluster_data: dict[str, dict] = defaultdict(
            lambda: {
                "name": "",
                "domain": "",
                "creative_ids": [],
                "sample_url": "",
                "app_id": None,
                "app_store": None,
                "advertiser_name": None,
            }
        )

        for row in rows:
            row_dict = dict(row)
            creative_id = str(row_dict['creative_id'])
            final_url = row_dict.get('final_url') or ''
            app_id = row_dict.get('app_id')
            app_name = row_dict.get('app_name')
            app_store = row_dict.get('app_store')
            advertiser_name = row_dict.get('advertiser_name')

            # Cluster by stable ID when possible.
            if app_id:
                cluster_key = f"app:{app_id}"
            elif _is_usable_name(app_name):
                cluster_key = f"name:{_slugify_name(app_name or '')}"
            else:
                cluster_key, _ = _extract_cluster_key_and_name(final_url)
                if cluster_key == "unknown" and _is_usable_name(advertiser_name):
                    cluster_key = f"advertiser:{_slugify_name(advertiser_name or '')}"

            entry = cluster_data[cluster_key]
            entry["creative_ids"].append(creative_id)

            if not entry["sample_url"] and final_url:
                entry["sample_url"] = final_url
            if not entry["app_id"] and app_id:
                entry["app_id"] = app_id
            if not entry["app_store"] and app_store:
                entry["app_store"] = app_store
            if not entry["advertiser_name"] and advertiser_name:
                entry["advertiser_name"] = advertiser_name
            if not entry["name"] and _is_usable_name(app_name):
                entry["name"] = _normalize_whitespace(app_name or "")
            if not entry["domain"]:
                entry["domain"] = _extract_reference_domain(final_url) or ""

        # Resolve best display names per cluster (store lookup / website title / safe fallback).
        semaphore = asyncio.Semaphore(8)

        async def _resolve_one(cluster_key: str, metadata: dict) -> tuple[str, str]:
            async with semaphore:
                resolved_name = await _resolve_cluster_display_name(
                    cluster_key=cluster_key,
                    app_name=metadata.get("name"),
                    app_id=metadata.get("app_id"),
                    app_store=metadata.get("app_store"),
                    final_url=metadata.get("sample_url"),
                    advertiser_name=metadata.get("advertiser_name"),
                )
                return cluster_key, resolved_name

        resolve_tasks = [_resolve_one(cluster_key, metadata) for cluster_key, metadata in cluster_data.items()]
        resolve_results = await asyncio.gather(*resolve_tasks, return_exceptions=True)
        for result in resolve_results:
            if isinstance(result, Exception):
                logger.warning("Cluster display-name resolution failed: %s", result)
                continue
            cluster_key, resolved_name = result
            cluster_data[cluster_key]["name"] = resolved_name

        # Generate cluster suggestions
        suggestions: list[ClusterSuggestion] = []

        for cluster_key, data in cluster_data.items():
            if len(data['creative_ids']) < 1:
                continue

            suggestion_name = data["name"]
            if not _is_usable_name(suggestion_name):
                suggestion_name = _generate_name_from_domain(data.get("domain") or cluster_key)
            if not _is_usable_name(suggestion_name):
                suggestion_name = "Unknown Campaign"

            suggestions.append(ClusterSuggestion(
                suggested_name=suggestion_name,
                creative_ids=data['creative_ids'],
                domain=data['domain'] or _extract_reference_domain(data.get("sample_url")) or cluster_key,
                country=None,  # Could be populated if by_country is True
            ))

        # Sort by number of creatives (largest first)
        suggestions.sort(key=lambda s: len(s.creative_ids), reverse=True)

        return AutoClusterResponse(
            suggestions=suggestions,
            unclustered_count=unclustered_count,
        )

    except Exception as e:
        logger.error(f"Auto-clustering failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.get("/unclustered")
async def get_unclustered_creatives(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer_id"),
    store: PostgresStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get all creatives that are not assigned to any campaign.

    Returns:
        creative_ids: List of creative IDs not in any campaign
        count: Total number of unclustered creatives
    """
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        svc = get_campaigns_service()
        creative_ids = await svc.get_unclustered_creative_ids(buyer_id)

        return {
            "creative_ids": creative_ids,
            "count": len(creative_ids),
        }

    except Exception as e:
        logger.error(f"Failed to get unclustered creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_cluster_key_and_name(url: str) -> tuple[str, str]:
    """
    Extract a unique cluster key and display name from a URL.

    For app store URLs, extracts the app identifier.
    For other URLs, uses the domain.

    Returns:
        (cluster_key, display_name) tuple
    """
    if not url:
        return ('unknown', 'Unknown Campaign')

    try:
        cleaned_url = _sanitize_destination_url(url)
        if not cleaned_url:
            return ('unknown', 'Unknown Campaign')

        parsed = urlparse(cleaned_url)
        domain = (parsed.netloc or '').replace('www.', '').lower()
        path = parsed.path or ''
        query = parsed.query or ''

        if _is_name_garbage(domain):
            domain = ""

        # Google Play Store: play.google.com/store/apps/details?id=com.example.app
        if 'play.google.com' in domain and '/store/apps/details' in path:
            params = parse_qs(query)
            app_id = params.get('id', [''])[0]
            if app_id:
                name = _format_bundle_id(app_id)
                return (f'play:{app_id}', name)

        # Apple App Store: apps.apple.com/us/app/app-name/id123456789
        if 'apps.apple.com' in domain or 'itunes.apple.com' in domain:
            # Extract app name and ID from path like /us/app/app-name/id123456789
            parts = path.strip('/').split('/')
            app_name = None
            app_id = None
            for i, part in enumerate(parts):
                if part == 'app' and i + 2 < len(parts):
                    app_name = parts[i + 1]
                    app_id = parts[i + 2]
                    break
                elif part.startswith('id') and part[2:].isdigit():
                    app_id = part

            if app_id:
                if app_name:
                    name = app_name.replace('-', ' ').title()
                    return (f'appstore:{app_id}', name)
                return (f'appstore:{app_id}', _format_bundle_id(app_id))

        # Apple Music: music.apple.com/us/album/album-name/123456789
        if 'music.apple.com' in domain:
            parts = path.strip('/').split('/')
            content_type = None
            content_name = None
            content_id = None
            for i, part in enumerate(parts):
                if part in ('album', 'artist', 'playlist') and i + 2 < len(parts):
                    content_type = part
                    content_name = parts[i + 1]
                    content_id = parts[i + 2]
                    break

            if content_id:
                name = content_name.replace('-', ' ').title() if content_name else content_id
                return (f'applemusic:{content_type}:{content_id}', name)

        # AppsFlyer tracking URLs: app.appsflyer.com/com.example.app?...
        if 'appsflyer.com' in domain:
            # App ID is often in the path
            parts = path.strip('/').split('/')
            for part in parts:
                if '.' in part and (part.startswith('com.') or part.startswith('org.') or part.startswith('io.')):
                    name = _format_bundle_id(part)
                    return (f'appsflyer:{part}', name)
            # Fallback - check for bundle ID in query params
            params = parse_qs(query)
            for key in ['app_id', 'af_dp', 'pid']:
                if key in params and params[key][0]:
                    val = params[key][0]
                    if '.' in val:
                        name = _format_bundle_id(val)
                        return (f'appsflyer:{val}', name)

        # Adjust tracking URLs
        if 'adjust.com' in domain or 'adj.st' in domain:
            params = parse_qs(query)
            # Try to find campaign or app identifier
            for key in ['campaign', 'adgroup', 'label']:
                if key in params and params[key][0]:
                    name = params[key][0].replace('_', ' ').replace('-', ' ').title()
                    if _is_usable_name(name):
                        return (f'adjust:{params[key][0]}', name)
            # Fallback to path-based extraction
            if path and len(path) > 1:
                tracker = path.strip('/').split('/')[0]
                if _is_usable_name(tracker):
                    return (f'adjust:{tracker}', f'Adjust {tracker[:8]}')

        # Firebase Dynamic Links: *.page.link
        if '.page.link' in domain:
            params = parse_qs(query)
            link = params.get('link', [''])[0]
            if link:
                # Recursively extract from the actual destination
                return _extract_cluster_key_and_name(link)
            # Use the subdomain as identifier
            subdomain = domain.split('.page.link')[0]
            return (f'firebase:{subdomain}', f'{subdomain.title()} (Firebase)')

        # Default: domain-based clustering
        if not domain:
            return ('unknown', 'Unknown Campaign')
        return (domain, _generate_name_from_domain(domain))

    except Exception as e:
        logger.warning(f"Failed to parse URL '{url[:100]}': {e}")
        return ('unknown', 'Unknown Campaign')


def _format_bundle_id(bundle_id: str) -> str:
    """Format a bundle ID like com.example.myapp into 'Example Myapp'.

    Uses centralized formatting from app_parser.
    """
    if not bundle_id:
        return 'Unknown'

    # Phase 29: Use centralized package ID formatting
    return format_package_id_as_name(bundle_id)


def _generate_name_from_domain(domain: str) -> str:
    """Generate a clean campaign name from a domain."""
    if not domain or domain == 'unknown' or _is_name_garbage(domain):
        return 'Unknown Campaign'

    # Handle bundle IDs (com.example.app)
    if domain.startswith('com.') or domain.startswith('org.') or domain.startswith('io.'):
        return _format_bundle_id(domain)

    # Clean up domain - remove common TLDs
    clean_domain = domain
    for tld in ['.com', '.io', '.app', '.net', '.org', '.co', '.me', '.tv', '.gg']:
        if clean_domain.endswith(tld):
            clean_domain = clean_domain[:-len(tld)]
            break

    # Convert to title case, replace separators with spaces
    name = clean_domain.replace('.', ' ').replace('-', ' ').replace('_', ' ')
    name = ' '.join(word.capitalize() for word in name.split() if word)

    candidate = name or domain
    if _is_name_garbage(candidate):
        return "Unknown Campaign"
    return candidate


# ============================================
# Campaign CRUD Endpoints
# ============================================

@router.get("", response_model=list[AICampaignResponse])
async def list_campaigns(
    seat_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    include_performance: bool = Query(True),
    include_country_breakdown: bool = Query(False, description="Include country breakdown per campaign"),
    period: str = Query("7d"),
):
    """
    List all AI campaigns with optional performance data.

    Phase 22: Country-aware clustering support via include_country_breakdown.
    """
    try:
        days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)
        svc = get_campaigns_service()

        campaigns = await svc.list_campaigns(seat_id=seat_id, status=status)

        result = []
        for campaign in campaigns:
            # Get creative IDs for this campaign
            creative_ids = await svc.get_campaign_creatives(campaign.id)

            # Phase 29: Count disapproved creatives in this campaign
            disapproved_count = await svc.count_disapproved_creatives(creative_ids)

            campaign_data = {
                "id": campaign.id,
                "seat_id": campaign.seat_id,
                "name": campaign.name,
                "description": campaign.description,
                "ai_generated": campaign.ai_generated,
                "ai_confidence": campaign.ai_confidence,
                "clustering_method": campaign.clustering_method,
                "status": campaign.status,
                "creative_count": campaign.creative_count,
                "creative_ids": creative_ids,
                "performance": None,
                "country_breakdown": None,
                # Phase 29: Disapproval tracking
                "disapproved_count": disapproved_count,
                "has_disapproved": disapproved_count > 0,
            }

            if include_performance:
                perf = await svc.get_campaign_performance(campaign.id, days=days)
                campaign_data["performance"] = perf

            if include_country_breakdown:
                breakdown_raw = await svc.get_campaign_country_breakdown(campaign.id, days=days)
                campaign_data["country_breakdown"] = {
                    country: {
                        "creative_ids": data['creative_ids'],
                        "spend_micros": data['spend_micros'],
                        "impressions": data['impressions'],
                    }
                    for country, data in breakdown_raw.items()
                }

            result.append(campaign_data)

        return [AICampaignResponse(**c) for c in result]

    except Exception as e:
        logger.error(f"Failed to list campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=AICampaignResponse)
async def create_campaign(request: CampaignCreateRequest):
    """
    Create a new campaign and optionally assign creatives to it.
    """
    try:
        svc = get_campaigns_service()

        # Create the campaign
        campaign_id = await svc.create_campaign(
            name=request.name,
            seat_id=None,  # Could be added to request if needed
            description=request.description,
            ai_generated=False,
            ai_confidence=None,
            clustering_method="manual",
        )

        # Assign creatives if provided
        if request.creative_ids:
            await svc.assign_creatives_batch(
                creative_ids=request.creative_ids,
                campaign_id=campaign_id,
                assigned_by="user",
                manually_assigned=True,
            )

        # Fetch the created campaign
        campaign = await svc.get_campaign(campaign_id)
        creative_ids = await svc.get_campaign_creatives(campaign_id)

        campaign_data = {
            "id": campaign.id,
            "seat_id": campaign.seat_id,
            "name": campaign.name,
            "description": campaign.description,
            "ai_generated": campaign.ai_generated,
            "ai_confidence": campaign.ai_confidence,
            "clustering_method": campaign.clustering_method,
            "status": campaign.status,
            "creative_count": len(creative_ids),
            "creative_ids": creative_ids,
        }

        return AICampaignResponse(**campaign_data)

    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}", response_model=AICampaignResponse)
async def get_campaign(
    campaign_id: str,
    include_creatives: bool = Query(False),
):
    """
    Get campaign details.
    """
    try:
        svc = get_campaigns_service()
        campaign = await svc.get_campaign(campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Get creative IDs for this campaign
        creative_ids = await svc.get_campaign_creatives(campaign_id)

        # Phase 29: Count disapproved creatives
        disapproved_count = await svc.count_disapproved_creatives(creative_ids)

        campaign_data = {
            "id": campaign.id,
            "seat_id": campaign.seat_id,
            "name": campaign.name,
            "description": campaign.description,
            "ai_generated": campaign.ai_generated,
            "ai_confidence": campaign.ai_confidence,
            "clustering_method": campaign.clustering_method,
            "status": campaign.status,
            "creative_count": campaign.creative_count,
            "creative_ids": creative_ids,
            # Phase 29: Disapproval tracking
            "disapproved_count": disapproved_count,
            "has_disapproved": disapproved_count > 0,
        }

        return AICampaignResponse(**campaign_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: str, request: CampaignUpdateRequest):
    """
    Update campaign name or description.
    """
    try:
        svc = get_campaigns_service()
        success = await svc.update_campaign(
            campaign_id=campaign_id,
            name=request.name,
            description=request.description,
            status=request.status,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{campaign_id}", response_model=AICampaignResponse)
async def patch_campaign(campaign_id: str, request: CampaignPatchRequest):
    """
    Patch campaign: update name, add creatives, or remove creatives.

    This is the main endpoint used by the drag-and-drop UI for moving creatives.
    """
    try:
        svc = get_campaigns_service()

        # Check campaign exists
        campaign = await svc.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Update name if provided
        if request.name is not None:
            await svc.update_campaign(campaign_id=campaign_id, name=request.name)

        # Remove creatives if provided
        if request.remove_creative_ids:
            for creative_id in request.remove_creative_ids:
                await svc.remove_creative(creative_id)

        # Add creatives if provided
        if request.add_creative_ids:
            await svc.assign_creatives_batch(
                creative_ids=request.add_creative_ids,
                campaign_id=campaign_id,
                assigned_by="user",
                manually_assigned=True,
            )

        # Fetch updated campaign
        campaign = await svc.get_campaign(campaign_id)
        creative_ids = await svc.get_campaign_creatives(campaign_id)

        campaign_data = {
            "id": campaign.id,
            "seat_id": campaign.seat_id,
            "name": campaign.name,
            "description": campaign.description,
            "ai_generated": campaign.ai_generated,
            "ai_confidence": campaign.ai_confidence,
            "clustering_method": campaign.clustering_method,
            "status": campaign.status,
            "creative_count": len(creative_ids),
            "creative_ids": creative_ids,
        }

        return AICampaignResponse(**campaign_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to patch campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """
    Delete a campaign and unassign all its creatives.
    """
    try:
        svc = get_campaigns_service()
        success = await svc.delete_campaign(campaign_id)

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Creative Assignment Endpoints
# ============================================

@router.get("/{campaign_id}/creatives")
async def get_campaign_creatives(campaign_id: str):
    """
    Get all creative IDs in a campaign.
    """
    try:
        svc = get_campaigns_service()
        creative_ids = await svc.get_campaign_creatives(campaign_id)
        return {"creative_ids": creative_ids, "count": len(creative_ids)}

    except Exception as e:
        logger.error(f"Failed to get campaign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/creatives")
async def add_creatives_to_campaign(campaign_id: str, request: AssignCreativesRequest):
    """
    Manually assign creatives to a campaign.
    """
    try:
        svc = get_campaigns_service()
        count = await svc.assign_creatives_batch(
            creative_ids=request.creative_ids,
            campaign_id=campaign_id,
            assigned_by="user",
            manually_assigned=True,
        )
        return {"status": "assigned", "count": count}

    except Exception as e:
        logger.error(f"Failed to assign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}/creatives/{creative_id}")
async def remove_creative_from_campaign(campaign_id: str, creative_id: str):
    """
    Remove a creative from a campaign.
    """
    try:
        svc = get_campaigns_service()
        success = await svc.remove_creative(creative_id)

        if not success:
            raise HTTPException(status_code=404, detail="Creative not in campaign")

        return {"status": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creatives/{creative_id}/move")
async def move_creative(creative_id: str, request: MoveCreativeRequest):
    """
    Move a creative from one campaign to another.
    """
    try:
        svc = get_campaigns_service()
        await svc.assign_creative(
            creative_id=creative_id,
            campaign_id=request.to_campaign_id,
            assigned_by="user",
            manually_assigned=True,
        )
        return {"status": "moved"}

    except Exception as e:
        logger.error(f"Failed to move creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Performance Endpoints
# ============================================

@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: str,
    period: str = Query("7d"),
):
    """
    Get performance metrics for a campaign.
    """
    try:
        days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)
        svc = get_campaigns_service()
        perf = await svc.get_campaign_performance(campaign_id, days=days)
        return CampaignPerformanceResponse(**perf)

    except Exception as e:
        logger.error(f"Failed to get campaign performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/performance/daily")
async def get_campaign_daily_trend(
    campaign_id: str,
    days: int = Query(30),
):
    """
    Get daily performance trend for a campaign.
    """
    try:
        svc = get_campaigns_service()
        trend = await svc.get_campaign_daily_trend(campaign_id, days=days)
        return {"trend": trend}

    except Exception as e:
        logger.error(f"Failed to get campaign trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-summaries")
async def refresh_campaign_summaries(seat_id: Optional[int] = None):
    """
    Recalculate campaign_daily_summary from performance_metrics.
    Run this after importing new data.
    """
    try:
        svc = get_campaigns_service()
        result = await svc.refresh_all_summaries(seat_id=seat_id)
        return {"status": "refreshed", "campaigns_updated": result["campaigns"], "dates_processed": result["dates"]}

    except Exception as e:
        logger.error(f"Failed to refresh summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
