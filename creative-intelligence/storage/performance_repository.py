"""
Performance Repository with lookup-on-insert pattern.

This module provides optimized batch inserts for performance data using
normalized lookup tables for repeated strings (geographies, apps, etc).

The lookup-on-insert pattern:
1. Check if value exists in lookup table
2. If yes, use cached ID
3. If no, insert and cache the new ID
4. Use integer FK in performance_metrics

Benefits:
- 5x storage reduction for large datasets
- 10-100x faster queries (integer vs string comparison)
- Better index performance
"""

import sqlite3
from typing import Optional
from datetime import datetime


# Country name to ISO code mapping
COUNTRY_NAME_TO_CODE = {
    'united states': 'US',
    'united kingdom': 'GB',
    'canada': 'CA',
    'australia': 'AU',
    'germany': 'DE',
    'france': 'FR',
    'japan': 'JP',
    'brazil': 'BR',
    'india': 'IN',
    'mexico': 'MX',
    'spain': 'ES',
    'italy': 'IT',
    'netherlands': 'NL',
    'sweden': 'SE',
    'norway': 'NO',
    'denmark': 'DK',
    'finland': 'FI',
    'poland': 'PL',
    'russia': 'RU',
    'china': 'CN',
    'south korea': 'KR',
    'singapore': 'SG',
    'indonesia': 'ID',
    'thailand': 'TH',
    'malaysia': 'MY',
    'philippines': 'PH',
    'vietnam': 'VN',
    'argentina': 'AR',
    'chile': 'CL',
    'colombia': 'CO',
    'peru': 'PE',
    'south africa': 'ZA',
    'nigeria': 'NG',
    'egypt': 'EG',
    'united arab emirates': 'AE',
    'saudi arabia': 'SA',
    'israel': 'IL',
    'turkey': 'TR',
    'ireland': 'IE',
    'portugal': 'PT',
    'austria': 'AT',
    'switzerland': 'CH',
    'belgium': 'BE',
    'czech republic': 'CZ',
    'hungary': 'HU',
    'romania': 'RO',
    'ukraine': 'UA',
    'greece': 'GR',
    'new zealand': 'NZ',
    'hong kong': 'HK',
    'taiwan': 'TW',
}


def country_to_code(name: str) -> str:
    """Convert country name to ISO 3166-1 alpha-2 code."""
    if not name:
        return ''

    # Already a code
    if len(name) == 2 and name.isalpha():
        return name.upper()

    # Try lookup
    code = COUNTRY_NAME_TO_CODE.get(name.lower().strip())
    if code:
        return code

    # Fallback: first two letters uppercase
    return name[:2].upper() if len(name) >= 2 else name.upper()


class PerformanceRepository:
    """
    Repository for performance metrics with optimized batch inserts.

    Uses lookup tables to normalize repeated string values into integer FKs,
    reducing storage and improving query performance.
    """

    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize repository with database connection.

        Args:
            db_connection: SQLite database connection
        """
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

        # In-memory caches for lookup tables
        self._geo_cache: dict[tuple[str, Optional[str]], int] = {}
        self._app_cache: dict[str, int] = {}
        self._billing_cache: dict[str, int] = {}
        self._publisher_cache: dict[str, int] = {}

        # Pre-load existing lookups into cache
        self._load_caches()

    def _load_caches(self) -> None:
        """Load existing lookup table entries into memory caches."""
        cursor = self.db.cursor()

        # Load geographies
        cursor.execute("SELECT id, country_code, city_name FROM geographies")
        for row in cursor.fetchall():
            key = (row['country_code'], row['city_name'])
            self._geo_cache[key] = row['id']

        # Load apps
        cursor.execute("SELECT id, app_id FROM apps WHERE app_id IS NOT NULL")
        for row in cursor.fetchall():
            self._app_cache[row['app_id']] = row['id']

        # Load billing accounts
        cursor.execute("SELECT id, billing_id FROM billing_accounts")
        for row in cursor.fetchall():
            self._billing_cache[row['billing_id']] = row['id']

        # Load publishers
        cursor.execute("SELECT id, publisher_id FROM publishers WHERE publisher_id IS NOT NULL")
        for row in cursor.fetchall():
            self._publisher_cache[row['publisher_id']] = row['id']

    def get_or_create_geo_id(
        self,
        country: Optional[str],
        city: Optional[str] = None
    ) -> Optional[int]:
        """
        Get existing geography ID or create new entry.

        Args:
            country: Country name or ISO code
            city: Optional city name

        Returns:
            Geography ID or None if no country provided
        """
        if not country:
            return None

        # Normalize country to code
        country_code = country_to_code(country)
        cache_key = (country_code, city)

        # Check cache
        if cache_key in self._geo_cache:
            return self._geo_cache[cache_key]

        cursor = self.db.cursor()

        # Try to find existing
        if city:
            cursor.execute(
                "SELECT id FROM geographies WHERE country_code = ? AND city_name = ?",
                (country_code, city)
            )
        else:
            cursor.execute(
                "SELECT id FROM geographies WHERE country_code = ? AND city_name IS NULL",
                (country_code,)
            )

        row = cursor.fetchone()
        if row:
            self._geo_cache[cache_key] = row['id']
            return row['id']

        # Create new entry
        country_name = country if len(country) > 2 else None
        cursor.execute(
            "INSERT INTO geographies (country_code, country_name, city_name) VALUES (?, ?, ?)",
            (country_code, country_name, city)
        )

        geo_id = cursor.lastrowid
        self._geo_cache[cache_key] = geo_id
        return geo_id

    def get_or_create_app_id(
        self,
        app_id: Optional[str],
        app_name: Optional[str] = None,
        platform: Optional[str] = None
    ) -> Optional[int]:
        """
        Get existing app ID or create new entry.

        Args:
            app_id: External app identifier
            app_name: Human-readable app name
            platform: App platform (iOS, Android, Web)

        Returns:
            Internal app ID or None if no app_id provided
        """
        if not app_id:
            return None

        # Check cache
        if app_id in self._app_cache:
            return self._app_cache[app_id]

        cursor = self.db.cursor()

        # Try to find existing
        cursor.execute("SELECT id FROM apps WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()

        if row:
            self._app_cache[app_id] = row['id']
            return row['id']

        # Create new entry
        cursor.execute(
            "INSERT INTO apps (app_id, app_name, platform) VALUES (?, ?, ?)",
            (app_id, app_name, platform)
        )

        internal_id = cursor.lastrowid
        self._app_cache[app_id] = internal_id
        return internal_id

    def get_or_create_billing_id(
        self,
        billing_id: Optional[str],
        name: Optional[str] = None
    ) -> Optional[int]:
        """
        Get existing billing account ID or create new entry.

        Args:
            billing_id: External billing account identifier
            name: Human-readable account name

        Returns:
            Internal billing account ID or None if no billing_id provided
        """
        if not billing_id:
            return None

        # Check cache
        if billing_id in self._billing_cache:
            return self._billing_cache[billing_id]

        cursor = self.db.cursor()

        # Try to find existing
        cursor.execute("SELECT id FROM billing_accounts WHERE billing_id = ?", (billing_id,))
        row = cursor.fetchone()

        if row:
            self._billing_cache[billing_id] = row['id']
            return row['id']

        # Create new entry
        cursor.execute(
            "INSERT INTO billing_accounts (billing_id, name) VALUES (?, ?)",
            (billing_id, name)
        )

        internal_id = cursor.lastrowid
        self._billing_cache[billing_id] = internal_id
        return internal_id

    def get_or_create_publisher_id(
        self,
        publisher_id: Optional[str],
        publisher_name: Optional[str] = None
    ) -> Optional[int]:
        """
        Get existing publisher ID or create new entry.

        Args:
            publisher_id: External publisher identifier
            publisher_name: Human-readable publisher name

        Returns:
            Internal publisher ID or None if no publisher_id provided
        """
        if not publisher_id:
            return None

        # Check cache
        if publisher_id in self._publisher_cache:
            return self._publisher_cache[publisher_id]

        cursor = self.db.cursor()

        # Try to find existing
        cursor.execute("SELECT id FROM publishers WHERE publisher_id = ?", (publisher_id,))
        row = cursor.fetchone()

        if row:
            self._publisher_cache[publisher_id] = row['id']
            return row['id']

        # Create new entry
        cursor.execute(
            "INSERT INTO publishers (publisher_id, publisher_name) VALUES (?, ?)",
            (publisher_id, publisher_name)
        )

        internal_id = cursor.lastrowid
        self._publisher_cache[publisher_id] = internal_id
        return internal_id

    def insert_batch(
        self,
        rows: list[dict],
        seat_id: Optional[int] = None,
        commit: bool = True
    ) -> int:
        """
        Insert batch of performance rows with lookup resolution.

        Args:
            rows: List of row dicts with keys:
                - creative_id (required)
                - date (required)
                - impressions, clicks, spend
                - reached_queries (for QPS analysis)
                - geography/country, city
                - app_id, app_name, platform
                - billing_id, billing_name
                - publisher_id, publisher_name
                - device_type, placement, campaign_id
            seat_id: Optional seat ID to associate with all rows
            commit: Whether to commit after insert

        Returns:
            Number of rows inserted/updated
        """
        if not rows:
            return 0

        cursor = self.db.cursor()
        values = []

        for row in rows:
            # Resolve lookups
            geo_id = self.get_or_create_geo_id(
                row.get('geography') or row.get('country'),
                row.get('city')
            )
            app_id_fk = self.get_or_create_app_id(
                row.get('app_id'),
                row.get('app_name'),
                row.get('platform')
            )
            billing_id = self.get_or_create_billing_id(
                row.get('billing_id'),
                row.get('billing_name')
            )
            publisher_id_fk = self.get_or_create_publisher_id(
                row.get('publisher_id'),
                row.get('publisher_name')
            )

            # Parse spend - handle both USD and micros
            spend = row.get('spend', 0)
            if isinstance(spend, str):
                spend = float(spend.replace('$', '').replace(',', ''))
            spend_micros = row.get('spend_micros')
            if spend_micros is None:
                # Convert USD to micros
                spend_micros = int(float(spend) * 1_000_000)

            # Calculate CPM and CPC
            impressions = int(row.get('impressions', 0))
            clicks = int(row.get('clicks', 0))
            reached_queries = int(row.get('reached_queries', 0))
            cpm_micros = None
            cpc_micros = None

            if impressions > 0:
                cpm_micros = int((spend_micros / impressions) * 1000)
            if clicks > 0:
                cpc_micros = int(spend_micros / clicks)

            values.append((
                seat_id,
                row['creative_id'],
                row.get('date') or row.get('metric_date'),
                geo_id,
                app_id_fk,
                billing_id,
                publisher_id_fk,
                reached_queries,
                impressions,
                clicks,
                spend_micros,
                cpm_micros,
                cpc_micros,
                row.get('geography') or row.get('country'),  # Keep original for backward compat
                row.get('device_type'),
                row.get('placement'),
                row.get('campaign_id'),
            ))

        # Use UPSERT to handle duplicates
        cursor.executemany("""
            INSERT INTO performance_metrics (
                seat_id, creative_id, metric_date, geo_id, app_id_fk, billing_account_id,
                publisher_id_fk, reached_queries, impressions, clicks, spend_micros, cpm_micros,
                cpc_micros, geography, device_type, placement, campaign_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creative_id, metric_date, geography, device_type, placement)
            DO UPDATE SET
                seat_id = COALESCE(excluded.seat_id, seat_id),
                reached_queries = reached_queries + excluded.reached_queries,
                impressions = impressions + excluded.impressions,
                clicks = clicks + excluded.clicks,
                spend_micros = spend_micros + excluded.spend_micros,
                geo_id = excluded.geo_id,
                app_id_fk = excluded.app_id_fk,
                billing_account_id = excluded.billing_account_id,
                publisher_id_fk = excluded.publisher_id_fk,
                updated_at = CURRENT_TIMESTAMP
        """, values)

        if commit:
            self.db.commit()

        return len(values)

    def insert_video_metrics(
        self,
        performance_id: int,
        video_starts: int = 0,
        video_q1: int = 0,
        video_q2: int = 0,
        video_q3: int = 0,
        video_completions: int = 0,
        vast_errors: int = 0,
        engaged_views: int = 0,
        commit: bool = True
    ) -> int:
        """
        Insert video metrics for a performance row.

        Args:
            performance_id: ID of the related performance_metrics row
            video_starts: Number of video starts
            video_q1: Reached 25%
            video_q2: Reached 50%
            video_q3: Reached 75%
            video_completions: Completed video plays
            vast_errors: VAST error count
            engaged_views: Engaged view count
            commit: Whether to commit after insert

        Returns:
            1 if inserted, 0 if failed
        """
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO video_metrics (
                performance_id, video_starts, video_q1, video_q2, video_q3,
                video_completions, vast_errors, engaged_views
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            performance_id, video_starts, video_q1, video_q2, video_q3,
            video_completions, vast_errors, engaged_views
        ))

        if commit:
            self.db.commit()

        return 1 if cursor.rowcount > 0 else 0

    def insert_batch_with_video(
        self,
        rows: list[dict],
        seat_id: Optional[int] = None,
        commit: bool = True
    ) -> dict:
        """
        Insert batch of performance rows that include video metrics.

        Args:
            rows: List of row dicts with performance + video keys:
                - All standard performance fields
                - video_starts, video_q1, video_q2, video_q3, video_completions
                - vast_errors, engaged_views
            seat_id: Optional seat ID to associate with all rows
            commit: Whether to commit after insert

        Returns:
            Dict with 'performance_count' and 'video_count'
        """
        if not rows:
            return {'performance_count': 0, 'video_count': 0}

        cursor = self.db.cursor()
        perf_count = 0
        video_count = 0

        for row in rows:
            # Insert performance row first
            geo_id = self.get_or_create_geo_id(
                row.get('geography') or row.get('country'),
                row.get('city')
            )
            app_id_fk = self.get_or_create_app_id(
                row.get('app_id'),
                row.get('app_name'),
                row.get('platform')
            )

            spend = row.get('spend', 0)
            if isinstance(spend, str):
                spend = float(spend.replace('$', '').replace(',', ''))
            spend_micros = int(float(spend) * 1_000_000)

            impressions = int(row.get('impressions', 0))
            clicks = int(row.get('clicks', 0))
            reached_queries = int(row.get('reached_queries', 0))

            cpm_micros = int((spend_micros / impressions) * 1000) if impressions > 0 else None
            cpc_micros = int(spend_micros / clicks) if clicks > 0 else None

            cursor.execute("""
                INSERT INTO performance_metrics (
                    seat_id, creative_id, metric_date, geo_id, app_id_fk,
                    reached_queries, impressions, clicks, spend_micros, cpm_micros,
                    cpc_micros, geography, device_type, placement, campaign_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(creative_id, metric_date, geography, device_type, placement)
                DO UPDATE SET
                    seat_id = COALESCE(excluded.seat_id, seat_id),
                    reached_queries = reached_queries + excluded.reached_queries,
                    impressions = impressions + excluded.impressions,
                    clicks = clicks + excluded.clicks,
                    spend_micros = spend_micros + excluded.spend_micros,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                seat_id,
                row['creative_id'],
                row.get('date') or row.get('metric_date'),
                geo_id,
                app_id_fk,
                reached_queries,
                impressions,
                clicks,
                spend_micros,
                cpm_micros,
                cpc_micros,
                row.get('geography') or row.get('country'),
                row.get('device_type'),
                row.get('placement'),
                row.get('campaign_id'),
            ))

            result = cursor.fetchone()
            if result:
                perf_count += 1
                perf_id = result[0]

                # Insert video metrics if present
                if any(row.get(k) for k in ['video_starts', 'video_completions', 'video_q1']):
                    cursor.execute("""
                        INSERT OR REPLACE INTO video_metrics (
                            performance_id, video_starts, video_q1, video_q2, video_q3,
                            video_completions, vast_errors, engaged_views
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        perf_id,
                        int(row.get('video_starts', 0)),
                        int(row.get('video_q1') or row.get('video_first_quartile', 0)),
                        int(row.get('video_q2') or row.get('video_midpoint', 0)),
                        int(row.get('video_q3') or row.get('video_third_quartile', 0)),
                        int(row.get('video_completions', 0)),
                        int(row.get('vast_errors') or row.get('vast_error_count', 0)),
                        int(row.get('engaged_views', 0)),
                    ))
                    video_count += 1

        if commit:
            self.db.commit()

        return {'performance_count': perf_count, 'video_count': video_count}

    def clear_caches(self) -> None:
        """Clear all lookup caches (use if tables are modified externally)."""
        self._geo_cache.clear()
        self._app_cache.clear()
        self._billing_cache.clear()
        self._publisher_cache.clear()
