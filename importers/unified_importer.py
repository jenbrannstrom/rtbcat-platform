"""Unified Flexible CSV Importer.

Imports ANY Cat-Scan CSV by:
1. Auto-mapping columns using synonyms and fuzzy matching
2. Detecting the best target table based on what columns exist
3. Using sensible defaults for missing fields

This is the recommended importer for all CSVs.
"""

import csv
import os
import hashlib
import re
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row

from datetime import date, timedelta

from importers.flexible_mapper import (
    map_columns, detect_best_report_type, get_default_value, MappingResult
)
from importers.domain_rollup import rollup_domains
from importers.parquet_pipeline import ParquetExportManager
from importers.utils import parse_date, parse_float, parse_int
from utils.size_normalization import canonical_size_with_tolerance

logger = logging.getLogger(__name__)

IMPORT_BATCH_SIZE = int(os.getenv("CATSCAN_IMPORT_BATCH_SIZE", "1000"))


def is_web_lane_enabled(buyer_id: str = "") -> bool:
    """Check if the web/domain lane is enabled globally and for a specific buyer."""
    if os.getenv("CATSCAN_WEB_LANE_ENABLED", "").lower() not in ("1", "true", "yes"):
        return False
    allowlist = os.getenv("CATSCAN_WEB_LANE_BUYERS", "")
    if not allowlist:
        return True  # global enabled, no per-buyer restriction
    return buyer_id in [b.strip() for b in allowlist.split(",")]


def get_postgres_connection() -> Any:
    """Get Postgres connection using POSTGRES_SERVING_DSN/POSTGRES_DSN/DATABASE_URL."""
    dsn = (
        os.getenv("POSTGRES_SERVING_DSN")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("DATABASE_URL")
        or ""
    )
    if not dsn:
        raise RuntimeError(
            "POSTGRES_SERVING_DSN, POSTGRES_DSN, or DATABASE_URL must be set"
        )
    return psycopg.connect(dsn, row_factory=dict_row)


@dataclass
class UnifiedImportResult:
    """Result from unified import."""
    success: bool = False
    error_message: str = ""

    # What was detected
    report_type: str = ""
    target_table: str = ""

    # Column mapping info
    columns_mapped: Dict[str, str] = field(default_factory=dict)  # db_field -> csv_column
    columns_unmapped: List[str] = field(default_factory=list)
    columns_defaulted: List[str] = field(default_factory=list)  # fields that used defaults

    # Counts
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0

    # Data summary
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None

    # Metadata
    batch_id: str = ""

    # Date continuity (IMPORT-002)
    date_gaps: List[str] = field(default_factory=list)
    date_gap_warning: Optional[str] = None

    # Errors
    errors: List[str] = field(default_factory=list)


def compute_row_hash(row_data: Dict, keys: List[str]) -> str:
    """Compute hash of specified keys for deduplication."""
    hash_input = "|".join(str(row_data.get(k, "")) for k in keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


def get_value(row: Dict, mapping: MappingResult, db_field: str, default: str = "") -> str:
    """Get value from row using mapping, or return default."""
    csv_col = mapping.get_csv_column(db_field)
    if csv_col and csv_col in row:
        return row[csv_col].strip()
    return default


_SIZE_SEPARATORS = re.compile(r"[xX×]")


def canonicalize_size_string(raw: str) -> str:
    """Parse a raw size string and return the canonical IAB category.

    Handles formats like ``"300x250"``, ``"300 x 250"``, ``"300X250"``,
    ``"Native"``, ``"Video/Overlay"``, etc.  Falls back to the original
    (stripped) string when parsing fails so existing behaviour is preserved.
    """
    stripped = raw.strip()
    if not stripped or stripped.lower() in ("unknown", "native", "video/overlay"):
        return stripped

    # Try WxH split
    parts = _SIZE_SEPARATORS.split(stripped)
    if len(parts) == 2:
        try:
            w = int(parts[0].strip())
            h = int(parts[1].strip())
            return canonical_size_with_tolerance(w, h)
        except (ValueError, TypeError):
            pass
    return stripped


def check_date_continuity(
    observed_dates: set,
    date_range_start: Optional[str],
    date_range_end: Optional[str],
) -> List[str]:
    """Return a sorted list of YYYY-MM-DD strings for missing days.

    ``observed_dates`` is a set of YYYY-MM-DD strings actually seen during
    import.  The function generates the expected contiguous range from
    *date_range_start* to *date_range_end* (inclusive) and returns any days
    that were expected but absent.  Returns an empty list when the range is
    invalid, absent, or fully covered.
    """
    if not date_range_start or not date_range_end:
        return []
    try:
        start = date.fromisoformat(date_range_start)
        end = date.fromisoformat(date_range_end)
    except (ValueError, TypeError):
        return []
    if start > end:
        return []

    expected = set()
    d = start
    while d <= end:
        expected.add(d.isoformat())
        d += timedelta(days=1)

    missing = sorted(expected - observed_dates)
    return missing


def _apply_date_continuity(
    result: "UnifiedImportResult",
    observed_dates: set,
    min_date: Optional[str],
    max_date: Optional[str],
) -> None:
    """Populate *result* with date range and any continuity gaps."""
    result.date_range_start = min_date
    result.date_range_end = max_date
    gaps = check_date_continuity(observed_dates, min_date, max_date)
    if gaps:
        result.date_gaps = gaps
        result.date_gap_warning = (
            f"Import covers {min_date} to {max_date} but is missing "
            f"{len(gaps)} expected day(s): {', '.join(gaps[:5])}"
            + (f" (and {len(gaps) - 5} more)" if len(gaps) > 5 else "")
        )
        logger.warning("Date continuity gap: %s", result.date_gap_warning)


def parse_bidder_id_from_filename(filename: str) -> Optional[str]:
    """Try to extract a bidder/account ID from a Cat-Scan filename."""
    base = os.path.basename(filename)
    for token in base.split("-"):
        if token.isdigit() and len(token) >= 6:
            return token
    return None


def ensure_columns_exist(cursor, table_name: str, columns: List[Tuple[str, str]]):
    """Ensure columns exist in table, adding them if missing."""
    # Get existing columns from Postgres information_schema
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table_name,))
    existing = {row["column_name"] for row in cursor.fetchall()}

    for col_name, col_type in columns:
        # Convert SQLite types to Postgres types
        pg_type = col_type.replace("INTEGER", "INTEGER").replace("TEXT", "TEXT")
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {pg_type}")
                logger.info(f"Added column {col_name} to {table_name}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")


def ensure_table_exists(cursor, table_name: str):
    """Ensure the target table exists (Postgres DDL)."""
    if table_name == "rtb_daily":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_daily (
                id SERIAL PRIMARY KEY,
                metric_date DATE NOT NULL,
                hour INTEGER DEFAULT 0,
                billing_id TEXT,
                creative_id TEXT,
                creative_size TEXT,
                creative_format TEXT,
                country TEXT,
                platform TEXT,
                environment TEXT,
                publisher_id TEXT,
                publisher_name TEXT,
                publisher_domain TEXT,
                app_id TEXT,
                app_name TEXT,
                buyer_account_id TEXT,
                reached_queries INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                spend_micros BIGINT DEFAULT 0,
                bids INTEGER DEFAULT 0,
                bids_in_auction INTEGER DEFAULT 0,
                auctions_won INTEGER DEFAULT 0,
                video_starts INTEGER DEFAULT 0,
                video_completions INTEGER DEFAULT 0,
                viewable_impressions INTEGER DEFAULT 0,
                measurable_impressions INTEGER DEFAULT 0,
                bidder_id TEXT,
                row_hash TEXT UNIQUE,
                import_batch_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_daily_date ON rtb_daily(metric_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_daily_billing ON rtb_daily(billing_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_daily_creative ON rtb_daily(creative_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_daily_bidder ON rtb_daily(bidder_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_buyer "
            "ON rtb_daily(metric_date, buyer_account_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_billing "
            "ON rtb_daily(metric_date, billing_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_app "
            "ON rtb_daily(metric_date, app_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_creative "
            "ON rtb_daily(metric_date, creative_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_country "
            "ON rtb_daily(metric_date, country)"
        )

    elif table_name == "rtb_bidstream":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_bidstream (
                id SERIAL PRIMARY KEY,
                metric_date DATE NOT NULL,
                hour INTEGER DEFAULT 0,
                country TEXT,
                buyer_account_id TEXT,
                publisher_id TEXT,
                publisher_name TEXT,
                platform TEXT,
                environment TEXT,
                transaction_type TEXT,
                inventory_matches INTEGER DEFAULT 0,
                bid_requests INTEGER DEFAULT 0,
                successful_responses INTEGER DEFAULT 0,
                reached_queries INTEGER DEFAULT 0,
                bids INTEGER DEFAULT 0,
                bids_in_auction INTEGER DEFAULT 0,
                auctions_won INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                row_hash TEXT UNIQUE,
                import_batch_id TEXT,
                bidder_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_date ON rtb_bidstream(metric_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_country ON rtb_bidstream(country)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_metric_buyer "
            "ON rtb_bidstream(metric_date, buyer_account_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_metric_publisher "
            "ON rtb_bidstream(metric_date, publisher_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_date_country "
            "ON rtb_bidstream(metric_date, country)"
        )

    elif table_name == "rtb_bid_filtering":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_bid_filtering (
                id SERIAL PRIMARY KEY,
                metric_date DATE NOT NULL,
                country TEXT,
                buyer_account_id TEXT,
                filtering_reason TEXT NOT NULL,
                creative_id TEXT,
                bids INTEGER DEFAULT 0,
                bids_in_auction INTEGER DEFAULT 0,
                opportunity_cost_micros BIGINT DEFAULT 0,
                bidder_id TEXT,
                row_hash TEXT UNIQUE,
                import_batch_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_date ON rtb_bid_filtering(metric_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_reason ON rtb_bid_filtering(filtering_reason)")

    elif table_name == "web_domain_daily":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_domain_daily (
                id              SERIAL PRIMARY KEY,
                metric_date     DATE NOT NULL,
                buyer_account_id TEXT NOT NULL,
                billing_id      TEXT NOT NULL,
                publisher_id    TEXT,
                publisher_domain TEXT NOT NULL,
                inventory_type  TEXT NOT NULL CHECK (inventory_type IN ('web', 'app', 'unknown')),
                impressions     BIGINT DEFAULT 0,
                reached_queries BIGINT DEFAULT 0,
                spend_micros    BIGINT DEFAULT 0,
                source_report   TEXT,
                row_hash        TEXT,
                import_batch_id TEXT,
                ingested_at     TIMESTAMPTZ DEFAULT now(),
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (metric_date, buyer_account_id, billing_id, publisher_domain)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_domain_daily_date "
            "ON web_domain_daily(metric_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_domain_daily_buyer "
            "ON web_domain_daily(metric_date, buyer_account_id)"
        )


def import_to_rtb_daily(
    csv_path: str,
    mapping: MappingResult,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
    parquet_exporter: Optional["ParquetExportManager"] = None,
    report_type: Optional[str] = None,
):
    """Import data to rtb_daily table (Postgres)."""
    conn = get_postgres_connection()
    cursor = conn.cursor()
    ensure_table_exists(cursor, "rtb_daily")
    conn.commit()

    # Ensure all potentially needed columns exist
    ensure_columns_exist(cursor, "rtb_daily", [
        ("bids", "INTEGER DEFAULT 0"),
        ("bids_in_auction", "INTEGER DEFAULT 0"),
        ("auctions_won", "INTEGER DEFAULT 0"),
        ("hour", "INTEGER DEFAULT 0"),
        ("viewable_impressions", "INTEGER DEFAULT 0"),
        ("measurable_impressions", "INTEGER DEFAULT 0"),
        ("buyer_account_id", "TEXT"),
        ("bidder_id", "TEXT"),
    ])
    conn.commit()

    hash_keys = [
        "metric_date", "hour", "billing_id", "creative_id", "creative_size",
        "country", "publisher_id", "buyer_account_id", "bidder_id",
    ]
    min_date, max_date = None, None
    observed_dates: set = set()

    insert_sql = """
        INSERT INTO rtb_daily (
            metric_date, hour, billing_id, creative_id, creative_size, creative_format,
            country, platform, environment, publisher_id, publisher_name, publisher_domain,
            app_id, app_name, buyer_account_id, reached_queries, impressions, clicks, spend_micros,
            bids, bids_in_auction, auctions_won,
            video_starts, video_completions, viewable_impressions, measurable_impressions,
            bidder_id, row_hash, import_batch_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (row_hash) DO NOTHING
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        nonlocal rows_to_insert
        if not rows_to_insert:
            return
        batch_count = len(rows_to_insert)
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = cursor.rowcount if cursor.rowcount >= 0 else batch_count
        result.rows_imported += inserted
        result.rows_duplicate += batch_count - inserted
        rows_to_insert = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1

                try:
                    # Parse date
                    metric_date = parse_date(get_value(row, mapping, "day"))
                    if not metric_date:
                        result.rows_skipped += 1
                        continue

                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    observed_dates.add(metric_date)

                    # Build row data with defaults
                    row_data = {
                        "metric_date": metric_date,
                        "hour": parse_int(get_value(row, mapping, "hour", "0")),
                        "billing_id": get_value(row, mapping, "billing_id", "unknown"),
                        "creative_id": get_value(row, mapping, "creative_id", ""),
                        "creative_size": canonicalize_size_string(
                            get_value(row, mapping, "creative_size", "unknown")
                        ),
                        "creative_format": get_value(row, mapping, "creative_format", ""),
                        "country": get_value(row, mapping, "country", ""),
                        "platform": get_value(row, mapping, "platform", ""),
                        "environment": get_value(row, mapping, "environment", ""),
                        "publisher_id": get_value(row, mapping, "publisher_id", ""),
                        "publisher_name": get_value(row, mapping, "publisher_name", ""),
                        "publisher_domain": get_value(row, mapping, "publisher_domain", ""),
                        "app_id": get_value(row, mapping, "app_id", ""),
                        "app_name": get_value(row, mapping, "app_name", ""),
                        "buyer_account_id": get_value(row, mapping, "buyer_account_id", ""),
                        "reached_queries": parse_int(get_value(row, mapping, "reached_queries", "0")),
                        "impressions": parse_int(get_value(row, mapping, "impressions", "0")),
                        "clicks": parse_int(get_value(row, mapping, "clicks", "0")),
                        "bids": parse_int(get_value(row, mapping, "bids", "0")),
                        "bids_in_auction": parse_int(get_value(row, mapping, "bids_in_auction", "0")),
                        "auctions_won": parse_int(get_value(row, mapping, "auctions_won", "0")),
                        "video_starts": parse_int(get_value(row, mapping, "video_starts", "0")),
                        "video_completions": parse_int(get_value(row, mapping, "video_completions", "0")),
                        "viewable_impressions": parse_int(get_value(row, mapping, "viewable_impressions", "0")),
                        "measurable_impressions": parse_int(get_value(row, mapping, "measurable_impressions", "0")),
                    }

                    if not bidder_id:
                        try:
                            from importers.account_mapper import get_bidder_id_for_billing_id
                            bidder_id = get_bidder_id_for_billing_id(row_data["billing_id"])
                        except Exception:
                            bidder_id = None
                    row_data["bidder_id"] = bidder_id

                    # If buyer_account_id missing from CSV, use bidder_id from filename
                    if not row_data["buyer_account_id"] and bidder_id:
                        row_data["buyer_account_id"] = bidder_id
                    if not row_data["buyer_account_id"]:
                        raise ValueError("buyer_account_id missing and no seat ID detected in filename")

                    # Parse spend (convert to micros)
                    spend = parse_float(get_value(row, mapping, "spend", "0"))
                    row_data["spend_micros"] = int(spend * 1_000_000) if spend < 1000 else int(spend)

                    # Compute hash
                    row_hash = compute_row_hash(row_data, hash_keys)

                    if parquet_exporter:
                        parquet_exporter.add_row(
                            metric_date,
                            {
                                **row_data,
                                "spend_micros": row_data["spend_micros"],
                                "bidder_id": row_data["bidder_id"],
                                "report_type": report_type,
                                "row_hash": row_hash,
                                "import_batch_id": batch_id,
                            },
                        )

                    rows_to_insert.append((
                        row_data["metric_date"], row_data["hour"], row_data["billing_id"],
                        row_data["creative_id"], row_data["creative_size"], row_data["creative_format"],
                        row_data["country"], row_data["platform"], row_data["environment"],
                        row_data["publisher_id"], row_data["publisher_name"], row_data["publisher_domain"],
                        row_data["app_id"], row_data["app_name"], row_data["buyer_account_id"],
                        row_data["reached_queries"], row_data["impressions"], row_data["clicks"],
                        row_data["spend_micros"], row_data["bids"], row_data["bids_in_auction"],
                        row_data["auctions_won"], row_data["video_starts"], row_data["video_completions"],
                        row_data["viewable_impressions"], row_data["measurable_impressions"],
                        row_data["bidder_id"], row_hash, batch_id
                    ))
                    if len(rows_to_insert) >= IMPORT_BATCH_SIZE:
                        flush_rows()

                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 10:
                        result.errors.append(f"Row {row_num}: {str(e)}")

        flush_rows()
        conn.commit()
        result.success = True
        _apply_date_continuity(result, observed_dates, min_date, max_date)

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def import_to_rtb_bidstream(
    csv_path: str,
    mapping: MappingResult,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
    parquet_exporter: Optional["ParquetExportManager"] = None,
    report_type: Optional[str] = None,
):
    """Import data to rtb_bidstream table (Postgres)."""
    conn = get_postgres_connection()
    cursor = conn.cursor()
    ensure_table_exists(cursor, "rtb_bidstream")
    ensure_columns_exist(cursor, "rtb_bidstream", [("bidder_id", "TEXT")])
    conn.commit()

    hash_keys = ["metric_date", "hour", "country", "buyer_account_id", "publisher_id", "bidder_id"]
    min_date, max_date = None, None
    observed_dates: set = set()

    insert_sql = """
        INSERT INTO rtb_bidstream (
            metric_date, hour, country, buyer_account_id, publisher_id, publisher_name,
            inventory_matches, bid_requests, successful_responses, reached_queries,
            bids, bids_in_auction, auctions_won, impressions, clicks,
            bidder_id, row_hash, import_batch_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (row_hash) DO NOTHING
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        nonlocal rows_to_insert
        if not rows_to_insert:
            return
        batch_count = len(rows_to_insert)
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = cursor.rowcount if cursor.rowcount >= 0 else batch_count
        result.rows_imported += inserted
        result.rows_duplicate += batch_count - inserted
        rows_to_insert = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1

                try:
                    metric_date = parse_date(get_value(row, mapping, "day"))
                    if not metric_date:
                        result.rows_skipped += 1
                        continue

                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    observed_dates.add(metric_date)

                    row_data = {
                        "metric_date": metric_date,
                        "hour": parse_int(get_value(row, mapping, "hour", "0")),
                        "country": get_value(row, mapping, "country", ""),
                        "buyer_account_id": get_value(row, mapping, "buyer_account_id", ""),
                        "publisher_id": get_value(row, mapping, "publisher_id", ""),
                        "publisher_name": get_value(row, mapping, "publisher_name", ""),
                        "platform": get_value(row, mapping, "platform", ""),
                        "environment": get_value(row, mapping, "environment", ""),
                        "transaction_type": get_value(row, mapping, "transaction_type", ""),
                        "inventory_matches": parse_int(get_value(row, mapping, "inventory_matches", "0")),
                        "bid_requests": parse_int(get_value(row, mapping, "bid_requests", "0")),
                        "successful_responses": parse_int(get_value(row, mapping, "successful_responses", "0")),
                        "reached_queries": parse_int(get_value(row, mapping, "reached_queries", "0")),
                        "bids": parse_int(get_value(row, mapping, "bids", "0")),
                        "bids_in_auction": parse_int(get_value(row, mapping, "bids_in_auction", "0")),
                        "auctions_won": parse_int(get_value(row, mapping, "auctions_won", "0")),
                        "impressions": parse_int(get_value(row, mapping, "impressions", "0")),
                        "clicks": parse_int(get_value(row, mapping, "clicks", "0")),
                    }

                    # If buyer_account_id missing from CSV, use bidder_id from filename
                    if not row_data["buyer_account_id"] and bidder_id:
                        row_data["buyer_account_id"] = bidder_id

                    row_data["bidder_id"] = bidder_id

                    row_hash = compute_row_hash(row_data, hash_keys)

                    if parquet_exporter:
                        parquet_exporter.add_row(
                            metric_date,
                            {
                                **row_data,
                                "bidder_id": row_data["bidder_id"],
                                "report_type": report_type,
                                "row_hash": row_hash,
                                "import_batch_id": batch_id,
                            },
                        )

                    rows_to_insert.append((
                        row_data["metric_date"], row_data["hour"], row_data["country"],
                        row_data["buyer_account_id"], row_data["publisher_id"], row_data["publisher_name"],
                        row_data["inventory_matches"], row_data["bid_requests"],
                        row_data["successful_responses"], row_data["reached_queries"],
                        row_data["bids"], row_data["bids_in_auction"], row_data["auctions_won"],
                        row_data["impressions"], row_data["clicks"],
                        row_data["bidder_id"], row_hash, batch_id
                    ))
                    if len(rows_to_insert) >= IMPORT_BATCH_SIZE:
                        flush_rows()

                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 10:
                        result.errors.append(f"Row {row_num}: {str(e)}")

        flush_rows()
        conn.commit()
        result.success = True
        _apply_date_continuity(result, observed_dates, min_date, max_date)

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def import_to_rtb_bid_filtering(
    csv_path: str,
    mapping: MappingResult,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
    parquet_exporter: Optional["ParquetExportManager"] = None,
    report_type: Optional[str] = None,
):
    """Import data to rtb_bid_filtering table (Postgres)."""
    conn = get_postgres_connection()
    cursor = conn.cursor()
    ensure_table_exists(cursor, "rtb_bid_filtering")
    conn.commit()

    hash_keys = ["metric_date", "country", "filtering_reason", "creative_id", "bidder_id"]
    min_date, max_date = None, None
    observed_dates: set = set()

    insert_sql = """
        INSERT INTO rtb_bid_filtering (
            metric_date, country, buyer_account_id, filtering_reason, creative_id,
            bids, bids_in_auction, opportunity_cost_micros,
            bidder_id, row_hash, import_batch_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (row_hash) DO NOTHING
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        nonlocal rows_to_insert
        if not rows_to_insert:
            return
        batch_count = len(rows_to_insert)
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = cursor.rowcount if cursor.rowcount >= 0 else batch_count
        result.rows_imported += inserted
        result.rows_duplicate += batch_count - inserted
        rows_to_insert = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1

                try:
                    metric_date = parse_date(get_value(row, mapping, "day"))
                    filtering_reason = get_value(row, mapping, "filtering_reason")

                    if not metric_date or not filtering_reason:
                        result.rows_skipped += 1
                        continue

                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    observed_dates.add(metric_date)

                    row_data = {
                        "metric_date": metric_date,
                        "country": get_value(row, mapping, "country", ""),
                        "buyer_account_id": get_value(row, mapping, "buyer_account_id", ""),
                        "filtering_reason": filtering_reason,
                        "creative_id": get_value(row, mapping, "creative_id", ""),
                        "bids": parse_int(get_value(row, mapping, "bids", "0")),
                        "bids_in_auction": parse_int(get_value(row, mapping, "bids_in_auction", "0")),
                    }

                    # If buyer_account_id missing from CSV, use bidder_id from filename
                    if not row_data["buyer_account_id"] and bidder_id:
                        row_data["buyer_account_id"] = bidder_id

                    row_data["bidder_id"] = bidder_id

                    # Parse opportunity cost
                    opp_cost = parse_float(get_value(row, mapping, "opportunity_cost", "0"))
                    row_data["opportunity_cost_micros"] = int(opp_cost * 1_000_000) if opp_cost < 1000 else int(opp_cost)

                    row_hash = compute_row_hash(row_data, hash_keys)

                    if parquet_exporter:
                        parquet_exporter.add_row(
                            metric_date,
                            {
                                **row_data,
                                "bidder_id": row_data["bidder_id"],
                                "row_hash": row_hash,
                                "import_batch_id": batch_id,
                            },
                        )

                    rows_to_insert.append((
                        row_data["metric_date"], row_data["country"], row_data["buyer_account_id"],
                        row_data["filtering_reason"], row_data["creative_id"],
                        row_data["bids"], row_data["bids_in_auction"], row_data["opportunity_cost_micros"],
                        bidder_id, row_hash, batch_id
                    ))
                    if len(rows_to_insert) >= IMPORT_BATCH_SIZE:
                        flush_rows()

                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 10:
                        result.errors.append(f"Row {row_num}: {str(e)}")

        flush_rows()
        conn.commit()
        result.success = True
        _apply_date_continuity(result, observed_dates, min_date, max_date)

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def derive_inventory_type(row_data: dict) -> str:
    """Derive inventory_type from row signals when not explicitly provided."""
    app_id = row_data.get("app_id", "")
    app_name = row_data.get("app_name", "")
    domain = row_data.get("publisher_domain", "")

    if app_id or app_name:
        return "app"
    if domain and domain != "__NO_DOMAIN__":
        return "web"
    return "unknown"


def import_to_web_domain_daily(
    csv_path: str,
    mapping: MappingResult,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
    parquet_exporter: Optional["ParquetExportManager"] = None,
    report_type: Optional[str] = None,
):
    """Import data to web_domain_daily table (Postgres)."""
    conn = get_postgres_connection()
    cursor = conn.cursor()
    ensure_table_exists(cursor, "web_domain_daily")
    conn.commit()

    has_domain_col = mapping.has_field("publisher_domain")
    if not has_domain_col:
        logger.warning(
            "Domain CSV missing publisher_domain column — no domain insight possible"
        )

    min_date, max_date = None, None
    observed_dates: set = set()
    all_rows: list[dict] = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1

                try:
                    metric_date = parse_date(get_value(row, mapping, "day"))
                    if not metric_date:
                        result.rows_skipped += 1
                        continue

                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    observed_dates.add(metric_date)

                    buyer_account_id = get_value(row, mapping, "buyer_account_id", "")
                    if not buyer_account_id and bidder_id:
                        buyer_account_id = bidder_id
                    if not buyer_account_id:
                        raise ValueError(
                            "buyer_account_id missing and no seat ID detected in filename"
                        )

                    # Buyer allowlist check
                    if not is_web_lane_enabled(buyer_account_id):
                        result.error_message = (
                            f"Buyer {buyer_account_id} not in domain lane allowlist"
                        )
                        return

                    domain = get_value(row, mapping, "publisher_domain", "")
                    if not domain:
                        domain = "__NO_DOMAIN__"

                    row_data = {
                        "metric_date": metric_date,
                        "buyer_account_id": buyer_account_id,
                        "billing_id": get_value(row, mapping, "billing_id", "unknown"),
                        "publisher_id": get_value(row, mapping, "publisher_id", ""),
                        "publisher_domain": domain,
                        "app_id": get_value(row, mapping, "app_id", ""),
                        "app_name": get_value(row, mapping, "app_name", ""),
                        "reached_queries": parse_int(
                            get_value(row, mapping, "reached_queries", "0")
                        ),
                        "impressions": parse_int(
                            get_value(row, mapping, "impressions", "0")
                        ),
                    }

                    # Parse spend (convert to micros)
                    spend = parse_float(get_value(row, mapping, "spend", "0"))
                    row_data["spend_micros"] = (
                        int(spend * 1_000_000) if spend < 1000 else int(spend)
                    )

                    # Inventory type: explicit or derived
                    explicit_inv = get_value(row, mapping, "inventory_type", "")
                    if explicit_inv and explicit_inv in ("web", "app", "unknown"):
                        row_data["inventory_type"] = explicit_inv
                    elif explicit_inv:
                        # Explicit but invalid value — fall back to derivation
                        row_data["inventory_type"] = derive_inventory_type(row_data)
                    else:
                        row_data["inventory_type"] = derive_inventory_type(row_data)

                    # Fix #3: if no domain column, force unknown
                    if not has_domain_col:
                        row_data["inventory_type"] = "unknown"

                    row_data["source_report"] = report_type or ""
                    row_data["import_batch_id"] = batch_id

                    # Compute hash
                    hash_keys = [
                        "metric_date", "buyer_account_id", "billing_id",
                        "publisher_domain",
                    ]
                    row_data["row_hash"] = compute_row_hash(row_data, hash_keys)

                    all_rows.append(row_data)

                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 10:
                        result.errors.append(f"Row {row_num}: {str(e)}")

        # Apply top-N rollup before insert
        rolled_up = rollup_domains(all_rows)

        # Batch insert
        insert_sql = """
            INSERT INTO web_domain_daily (
                metric_date, buyer_account_id, billing_id, publisher_id,
                publisher_domain, inventory_type, impressions, reached_queries,
                spend_micros, source_report, row_hash, import_batch_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (metric_date, buyer_account_id, billing_id, publisher_domain)
            DO NOTHING
        """
        rows_to_insert: list[tuple] = []

        def flush_rows():
            nonlocal rows_to_insert
            if not rows_to_insert:
                return
            batch_count = len(rows_to_insert)
            cursor.executemany(insert_sql, rows_to_insert)
            inserted = cursor.rowcount if cursor.rowcount >= 0 else batch_count
            result.rows_imported += inserted
            result.rows_duplicate += batch_count - inserted
            rows_to_insert = []

        for rd in rolled_up:
            rows_to_insert.append((
                rd["metric_date"], rd["buyer_account_id"], rd["billing_id"],
                rd.get("publisher_id", ""), rd["publisher_domain"],
                rd["inventory_type"], rd.get("impressions", 0),
                rd.get("reached_queries", 0), rd.get("spend_micros", 0),
                rd.get("source_report", ""), rd.get("row_hash", ""),
                rd.get("import_batch_id", ""),
            ))
            if len(rows_to_insert) >= IMPORT_BATCH_SIZE:
                flush_rows()

        flush_rows()
        conn.commit()
        result.success = True
        _apply_date_continuity(result, observed_dates, min_date, max_date)

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def unified_import(
    csv_path: str,
    bidder_id: Optional[str] = None,
    source_filename: Optional[str] = None,
) -> UnifiedImportResult:
    """
    Import any CSV using flexible column mapping (Postgres).

    Args:
        csv_path: Path to CSV file
        bidder_id: Optional bidder ID override

    Returns:
        UnifiedImportResult with success status and details
    """
    result = UnifiedImportResult()
    result.batch_id = str(uuid.uuid4())[:8]

    # Check file exists
    if not os.path.exists(csv_path):
        result.error_message = f"File not found: {csv_path}"
        return result

    # Read headers
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
    except Exception as e:
        result.error_message = f"Failed to read CSV: {e}"
        return result

    # Map columns
    mapping = map_columns(headers)

    # Store mapping info
    result.columns_mapped = {db: m.csv_column for db, m in mapping.mapped.items()}
    result.columns_unmapped = mapping.unmapped

    # Check for fields that will use defaults
    for db_field in ["billing_id", "creative_size", "reached_queries", "impressions"]:
        if not mapping.has_field(db_field) and get_default_value(db_field):
            result.columns_defaulted.append(db_field)

    # Detect best report type
    report_type, target_table, missing_critical = detect_best_report_type(mapping)

    # Filename-first routing for domain lane
    if source_filename and "catscan-domains-" in os.path.basename(source_filename or "").lower():
        report_type = "domains"
        target_table = "web_domain_daily"
        missing_critical = [] if mapping.has_field("day") else ["day"]

    result.report_type = report_type
    result.target_table = target_table

    # Check for critical missing fields
    if missing_critical:
        result.error_message = f"Missing critical columns that cannot be defaulted: {', '.join(missing_critical)}"
        return result

    if not target_table:
        result.error_message = (
            f"Could not determine target table. Mapped columns: {list(result.columns_mapped.keys())}"
        )
        return result

    if not bidder_id:
        bidder_id = parse_bidder_id_from_filename(source_filename or csv_path)
    if target_table == "rtb_bidstream" and not bidder_id and not mapping.has_field("buyer_account_id"):
        result.error_message = (
            "Missing Buyer account ID. Include the column in the report or ensure the filename "
            "contains the seat ID (e.g. catscan-pipeline-<seat>-yesterday-UTC.csv)."
        )
        return result
    if target_table == "rtb_daily" and not mapping.has_field("buyer_account_id") and not mapping.has_field("billing_id") and not bidder_id:
        result.error_message = (
            "Missing Billing ID and Buyer account ID. Include Billing ID in the report or "
            "ensure the filename contains the seat ID (e.g. catscan-quality-<seat>-yesterday-UTC.csv)."
        )
        return result

    parquet_exporter = ParquetExportManager.from_env(
        target_table, result.batch_id, result.errors
    )

    try:
        # Import based on target table
        if target_table == "rtb_daily":
            import_to_rtb_daily(
                csv_path,
                mapping,
                result.batch_id,
                result,
                bidder_id=bidder_id,
                parquet_exporter=parquet_exporter,
                report_type=report_type,
            )
        elif target_table == "rtb_bidstream":
            import_to_rtb_bidstream(
                csv_path,
                mapping,
                result.batch_id,
                result,
                bidder_id=bidder_id,
                parquet_exporter=parquet_exporter,
                report_type=report_type,
            )
        elif target_table == "rtb_bid_filtering":
            import_to_rtb_bid_filtering(
                csv_path,
                mapping,
                result.batch_id,
                result,
                bidder_id=bidder_id,
                parquet_exporter=parquet_exporter,
                report_type=report_type,
            )
        elif target_table == "web_domain_daily":
            import_to_web_domain_daily(
                csv_path,
                mapping,
                result.batch_id,
                result,
                bidder_id=bidder_id,
                parquet_exporter=parquet_exporter,
                report_type=report_type,
            )
        else:
            result.error_message = f"Unknown target table: {target_table}"
    finally:
        if parquet_exporter:
            parquet_exporter.finalize()

    return result


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m qps.unified_importer <csv_file>")
        sys.exit(1)

    csv_path = sys.argv[1]
    print(f"Importing: {csv_path}\n")

    result = unified_import(csv_path)

    print("=" * 60)
    if result.success:
        print("✅ IMPORT SUCCESSFUL")
    else:
        print("❌ IMPORT FAILED")
    print("=" * 60)

    print(f"\nReport Type:    {result.report_type}")
    print(f"Target Table:   {result.target_table}")
    print(f"Date Range:     {result.date_range_start} to {result.date_range_end}")

    print(f"\nRows read:      {result.rows_read:,}")
    print(f"Rows imported:  {result.rows_imported:,}")
    print(f"Rows duplicate: {result.rows_duplicate:,}")
    print(f"Rows skipped:   {result.rows_skipped:,}")

    print(f"\nMapped columns ({len(result.columns_mapped)}):")
    for db_field, csv_col in sorted(result.columns_mapped.items()):
        print(f"  {csv_col:30} → {db_field}")

    if result.columns_defaulted:
        print(f"\nDefaulted fields: {result.columns_defaulted}")

    if result.columns_unmapped:
        print(f"\nUnmapped columns: {result.columns_unmapped}")

    if result.error_message:
        print(f"\nError: {result.error_message}")

    if result.errors:
        print(f"\nRow errors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"  {err}")

    sys.exit(0 if result.success else 1)
