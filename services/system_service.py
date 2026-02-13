"""Business logic for system status and utilities."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from storage.postgres_database import pg_query


@dataclass
class SystemStatus:
    """System status information."""

    python_version: str
    node_available: bool
    node_version: Optional[str]
    ffmpeg_available: bool
    ffmpeg_version: Optional[str]
    database_size_mb: float
    thumbnails_count: int
    disk_space_gb: float
    creatives_count: int
    videos_count: int


# Fallback geo ID mappings for common Google Ads criterion IDs
FALLBACK_GEO_NAMES = {
    # US Metro/DMA regions (21xxx series) - most common
    '21155': 'Los Angeles, CA', '21164': 'New York, NY', '21174': 'Chicago, IL',
    '21145': 'Atlanta, GA', '21147': 'Austin, TX', '21149': 'Baltimore, MD',
    '21159': 'Boston, MA', '21170': 'Charlotte, NC', '21176': 'Cincinnati, OH',
    '21178': 'Cleveland-Akron, OH', '21183': 'Columbus, OH', '21186': 'Dallas-Fort Worth, TX',
    '21189': 'Denver, CO', '21191': 'Detroit, MI', '21225': 'Houston, TX',
    '21228': 'Indianapolis, IN', '21231': 'Jacksonville, FL', '21236': 'Kansas City, MO',
    '21244': 'Las Vegas, NV', '21258': 'Miami-Fort Lauderdale, FL', '21260': 'Minneapolis-St. Paul, MN',
    '21267': 'Nashville, TN', '21268': 'New Orleans, LA', '21272': 'Oklahoma City, OK',
    '21274': 'Orlando-Daytona Beach, FL', '21281': 'Philadelphia, PA', '21282': 'Phoenix, AZ',
    '21283': 'Pittsburgh, PA', '21284': 'Portland, OR', '21289': 'Raleigh-Durham, NC',
    '21297': 'Sacramento-Stockton, CA', '21299': 'Saint Louis, MO', '21301': 'Salt Lake City, UT',
    '21303': 'San Antonio, TX', '21304': 'San Diego, CA', '21305': 'San Francisco-Oakland, CA',
    '21308': 'Seattle-Tacoma, WA', '21319': 'Tampa-St. Petersburg, FL', '21332': 'Washington, DC',
    '21152': 'Beaumont-Port Arthur, TX', '21171': 'Charlottesville, VA',
    # Country-level IDs
    '2840': 'United States', '2826': 'United Kingdom', '2124': 'Canada', '2036': 'Australia',
    '2276': 'Germany', '2250': 'France', '2392': 'Japan', '2076': 'Brazil', '2356': 'India',
    '2484': 'Mexico', '2724': 'Spain', '2380': 'Italy', '2528': 'Netherlands', '2586': 'Pakistan',
    '2360': 'Indonesia', '2608': 'Philippines', '2704': 'Vietnam', '2764': 'Thailand',
    '2458': 'Malaysia', '2702': 'Singapore', '2784': 'UAE', '2682': 'Saudi Arabia',
}


class SystemService:
    """Service layer for system status operations."""

    def __init__(self) -> None:
        self._thumbnails_dir = Path.home() / ".catscan" / "thumbnails"

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        if shutil.which("ffmpeg") is not None:
            return True
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return True
        return False

    def _get_ffmpeg_path(self) -> str:
        """Get the ffmpeg executable path."""
        path = shutil.which("ffmpeg")
        if path:
            return path
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return "ffmpeg"

    def _get_node_version(self) -> tuple[bool, Optional[str]]:
        """Check node availability and get version."""
        node_available = shutil.which("node") is not None
        node_version = None
        if node_available:
            try:
                result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
                node_version = result.stdout.strip()
            except Exception:
                pass
        return node_available, node_version

    def _get_ffmpeg_version(self) -> tuple[bool, Optional[str]]:
        """Check ffmpeg availability and get version."""
        ffmpeg_available = self._check_ffmpeg()
        ffmpeg_version = None
        if ffmpeg_available:
            try:
                result = subprocess.run([self._get_ffmpeg_path(), '-version'], capture_output=True, text=True, timeout=5)
                first_line = result.stdout.split('\n')[0]
                parts = first_line.split(' ')
                ffmpeg_version = parts[2] if len(parts) > 2 else 'Unknown'
            except Exception:
                pass
        return ffmpeg_available, ffmpeg_version

    async def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status."""
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        node_available, node_version = self._get_node_version()
        ffmpeg_available, ffmpeg_version = self._get_ffmpeg_version()

        # Database size not available for Postgres via file stat
        database_size_mb = 0.0

        # Thumbnails count
        thumbnails_count = len(list(self._thumbnails_dir.glob("*.jpg"))) if self._thumbnails_dir.exists() else 0

        # Disk space
        total, used, free = shutil.disk_usage(Path.home())
        disk_space_gb = free / (1024 ** 3)

        # Creative counts from database
        creatives_count = 0
        videos_count = 0
        try:
            rows = await pg_query("SELECT COUNT(*) as cnt FROM creatives")
            creatives_count = rows[0]["cnt"] if rows else 0
            video_rows = await pg_query("SELECT COUNT(*) as cnt FROM creatives WHERE format = 'VIDEO'")
            videos_count = video_rows[0]["cnt"] if video_rows else 0
        except Exception:
            pass

        return SystemStatus(
            python_version=python_version,
            node_available=node_available,
            node_version=node_version,
            ffmpeg_available=ffmpeg_available,
            ffmpeg_version=ffmpeg_version,
            database_size_mb=round(database_size_mb, 2),
            thumbnails_count=thumbnails_count,
            disk_space_gb=round(disk_space_gb, 1),
            creatives_count=creatives_count,
            videos_count=videos_count,
        )

    async def lookup_geo_names(self, geo_ids: list[str]) -> dict[str, str]:
        """Look up human-readable names for Google geo criterion IDs.

        Falls back to inline mapping or original ID if not found in database.
        """
        if not geo_ids:
            return {}

        # Try database lookup first
        rows = []
        try:
            rows = await pg_query(
                """
                SELECT google_geo_id, country_code, country_name, city_name
                FROM geographies
                WHERE google_geo_id = ANY(%s)
                """,
                (geo_ids,),
            )
        except Exception:
            # Table may not exist if migration not run
            pass

        # Build result mapping from database
        result = {}
        found_ids = set()

        for row in rows:
            geo_id = str(row['google_geo_id'])
            found_ids.add(geo_id)

            if row['city_name']:
                result[geo_id] = row['city_name']
            elif row['country_name']:
                from utils.country_codes import get_country_alpha3
                result[geo_id] = get_country_alpha3(row['country_code']) if row['country_code'] else row['country_name']
            elif row['country_code']:
                from utils.country_codes import get_country_alpha3
                result[geo_id] = get_country_alpha3(row['country_code'])

        # For any not found in DB, try fallback mapping
        for geo_id in geo_ids:
            if geo_id not in found_ids:
                if geo_id in FALLBACK_GEO_NAMES:
                    from utils.country_codes import get_country_alpha3_from_name
                    result[geo_id] = get_country_alpha3_from_name(FALLBACK_GEO_NAMES[geo_id])
                else:
                    result[geo_id] = geo_id

        return result

    async def search_geo_targets(
        self,
        query: str,
        limit: int = 20,
        target_type: str = "all",
    ) -> list[dict[str, str]]:
        """Search Google geo targets by country/city name or criterion ID."""
        normalized = (query or "").strip()
        if not normalized:
            return []

        safe_limit = max(1, min(limit, 50))
        text_pattern = f"%{normalized}%"
        type_filter_sql = ""
        if target_type == "country":
            type_filter_sql = "AND COALESCE(city_name, '') = ''"
        elif target_type == "city":
            type_filter_sql = "AND COALESCE(city_name, '') <> ''"

        rows = []
        try:
            rows = await pg_query(
                f"""
                SELECT google_geo_id, country_code, country_name, city_name
                FROM geographies
                WHERE (
                    google_geo_id::text = %s
                    OR country_name ILIKE %s
                    OR city_name ILIKE %s
                    OR country_code ILIKE %s
                )
                {type_filter_sql}
                ORDER BY
                    CASE WHEN google_geo_id::text = %s THEN 0 ELSE 1 END,
                    CASE WHEN city_name ILIKE %s THEN 0 ELSE 1 END,
                    CASE WHEN country_name ILIKE %s THEN 0 ELSE 1 END,
                    city_name NULLS LAST,
                    country_name
                LIMIT %s
                """,
                (
                    normalized,
                    text_pattern,
                    text_pattern,
                    text_pattern,
                    normalized,
                    text_pattern,
                    text_pattern,
                    safe_limit,
                ),
            )
        except Exception:
            # The geographies table may not exist in all environments.
            return []

        results: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for row in rows:
            geo_id = str(row.get("google_geo_id") or "").strip()
            if not geo_id or geo_id in seen_ids:
                continue
            seen_ids.add(geo_id)

            country_code = (row.get("country_code") or "").strip().upper()
            country_name = (row.get("country_name") or "").strip()
            city_name = (row.get("city_name") or "").strip()

            if city_name:
                suffix = country_code or country_name
                label = f"{city_name}, {suffix}" if suffix else city_name
                item_type = "city"
            else:
                label = country_name or country_code or geo_id
                item_type = "country"

            results.append(
                {
                    "geo_id": geo_id,
                    "label": label,
                    "country_code": country_code,
                    "country_name": country_name,
                    "city_name": city_name,
                    "type": item_type,
                }
            )

        return results
