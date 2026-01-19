"""Unified Flexible CSV Importer.

Imports ANY Cat-Scan CSV by:
1. Auto-mapping columns using synonyms and fuzzy matching
2. Detecting the best target table based on what columns exist
3. Using sensible defaults for missing fields

This is the recommended importer for all CSVs.
"""

import csv
import sqlite3
import os
import hashlib
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from qps.flexible_mapper import (
    map_columns, detect_best_report_type, get_default_value, MappingResult
)

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")
IMPORT_BATCH_SIZE = int(os.getenv("CATSCAN_IMPORT_BATCH_SIZE", "1000"))


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

    # Errors
    errors: List[str] = field(default_factory=list)


def parse_date(date_str: str) -> str:
    """Parse date from various formats to YYYY-MM-DD."""
    if not date_str:
        return ""
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def parse_int(value) -> int:
    """Parse integer, returning 0 for empty/invalid."""
    if value is None or value == "":
        return 0
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def parse_float(value) -> float:
    """Parse float, returning 0.0 for empty/invalid."""
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return 0.0


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


def parse_bidder_id_from_filename(csv_path: str) -> Optional[str]:
    """Try to extract a bidder/account ID from a Cat-Scan filename."""
    filename = os.path.basename(csv_path)
    for token in filename.split("-"):
        if token.isdigit() and len(token) >= 6:
            return token
    return None


def ensure_columns_exist(cursor, table_name: str, columns: List[Tuple[str, str]]):
    """Ensure columns exist in table, adding them if missing."""
    # Get existing columns
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in columns:
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to {table_name}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")


def ensure_table_exists(cursor, table_name: str):
    """Ensure the target table exists."""
    if table_name == "rtb_daily":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                spend_micros INTEGER DEFAULT 0,
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
        ensure_unique_index(cursor, "rtb_daily", "row_hash", "idx_rtb_daily_row_hash")

    elif table_name == "rtb_bidstream":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_bidstream (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        ensure_unique_index(cursor, "rtb_bidstream", "row_hash", "idx_rtb_bidstream_row_hash")

    elif table_name == "rtb_bid_filtering":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rtb_bid_filtering (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_date DATE NOT NULL,
                country TEXT,
                buyer_account_id TEXT,
                filtering_reason TEXT NOT NULL,
                creative_id TEXT,
                bids INTEGER DEFAULT 0,
                bids_in_auction INTEGER DEFAULT 0,
                opportunity_cost_micros INTEGER DEFAULT 0,
                bidder_id TEXT,
                row_hash TEXT UNIQUE,
                import_batch_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_date ON rtb_bid_filtering(metric_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_reason ON rtb_bid_filtering(filtering_reason)")
        ensure_unique_index(cursor, "rtb_bid_filtering", "row_hash", "idx_rtb_bid_filtering_row_hash")


def configure_import_connection(conn: sqlite3.Connection) -> None:
    """Apply SQLite pragmas tuned for bulk imports."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")


def ensure_unique_index(cursor, table_name: str, column_name: str, index_name: str) -> None:
    """Ensure a unique index exists, warn if duplicates prevent creation."""
    try:
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"
        )
    except sqlite3.IntegrityError as e:
        logger.warning(
            "Could not create unique index %s on %s.%s due to duplicates: %s",
            index_name,
            table_name,
            column_name,
            e,
        )
    except sqlite3.OperationalError as e:
        logger.warning(
            "Could not create unique index %s on %s.%s: %s",
            index_name,
            table_name,
            column_name,
            e,
        )


def import_to_rtb_daily(
    csv_path: str,
    mapping: MappingResult,
    db_path: str,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
):
    """Import data to rtb_daily table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    configure_import_connection(conn)
    ensure_table_exists(cursor, "rtb_daily")
    ensure_unique_index(cursor, "rtb_daily", "row_hash", "idx_rtb_daily_row_hash")

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

    hash_keys = [
        "metric_date", "hour", "billing_id", "creative_id", "creative_size",
        "country", "publisher_id", "buyer_account_id", "bidder_id",
    ]
    min_date, max_date = None, None

    insert_sql = """
        INSERT OR IGNORE INTO rtb_daily (
            metric_date, hour, billing_id, creative_id, creative_size, creative_format,
            country, platform, environment, publisher_id, publisher_name, publisher_domain,
            app_id, app_name, buyer_account_id, reached_queries, impressions, clicks, spend_micros,
            bids, bids_in_auction, auctions_won,
            video_starts, video_completions, viewable_impressions, measurable_impressions,
            bidder_id, row_hash, import_batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        if not rows_to_insert:
            return
        before = conn.total_changes
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = conn.total_changes - before
        result.rows_imported += inserted
        if inserted >= 0:
            result.rows_duplicate += len(rows_to_insert) - inserted
        rows_to_insert.clear()

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

                    # Build row data with defaults
                    row_data = {
                        "metric_date": metric_date,
                        "hour": parse_int(get_value(row, mapping, "hour", "0")),
                        "billing_id": get_value(row, mapping, "billing_id", "unknown"),
                        "creative_id": get_value(row, mapping, "creative_id", ""),
                        "creative_size": get_value(row, mapping, "creative_size", "unknown"),
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
                            from qps.account_mapper import get_bidder_id_for_billing_id
                            bidder_id = get_bidder_id_for_billing_id(row_data["billing_id"], db_path=db_path)
                        except Exception:
                            bidder_id = None
                    row_data["bidder_id"] = bidder_id

                    # If buyer_account_id missing from CSV, use bidder_id from filename
                    if not row_data["buyer_account_id"] and bidder_id:
                        row_data["buyer_account_id"] = bidder_id
                    if not row_data["buyer_account_id"]:
                        raise ValueError("buyer_account_id missing and no seat ID detected in filename")
                    if not row_data["buyer_account_id"]:
                        raise ValueError("buyer_account_id missing and no seat ID detected in filename")
                    if not row_data["buyer_account_id"]:
                        raise ValueError("buyer_account_id missing and no seat ID detected in filename")
                    if not row_data["buyer_account_id"]:
                        raise ValueError("buyer_account_id missing and no seat ID detected in filename")

                    # Parse spend (convert to micros)
                    spend = parse_float(get_value(row, mapping, "spend", "0"))
                    row_data["spend_micros"] = int(spend * 1_000_000) if spend < 1000 else int(spend)

                    # Compute hash
                    row_hash = compute_row_hash(row_data, hash_keys)

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
        result.date_range_start = min_date
        result.date_range_end = max_date

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def import_to_rtb_bidstream(
    csv_path: str,
    mapping: MappingResult,
    db_path: str,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
):
    """Import data to rtb_bidstream table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    configure_import_connection(conn)
    configure_import_connection(conn)

    # Check if table exists, if not create it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rtb_bidstream'")
    if not cursor.fetchone():
        ensure_table_exists(cursor, "rtb_bidstream")
    ensure_unique_index(cursor, "rtb_bidstream", "row_hash", "idx_rtb_bidstream_row_hash")
    ensure_columns_exist(cursor, "rtb_bidstream", [("bidder_id", "TEXT")])

    hash_keys = ["metric_date", "hour", "country", "buyer_account_id", "publisher_id", "bidder_id"]
    min_date, max_date = None, None

    insert_sql = """
        INSERT OR IGNORE INTO rtb_bidstream (
            metric_date, hour, country, buyer_account_id, publisher_id, publisher_name,
            inventory_matches, bid_requests, successful_responses, reached_queries,
            bids, bids_in_auction, auctions_won, impressions, clicks,
            bidder_id, row_hash, import_batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        if not rows_to_insert:
            return
        before = conn.total_changes
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = conn.total_changes - before
        result.rows_imported += inserted
        if inserted >= 0:
            result.rows_duplicate += len(rows_to_insert) - inserted
        rows_to_insert.clear()

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

                    row_data = {
                        "metric_date": metric_date,
                        "hour": parse_int(get_value(row, mapping, "hour", "0")),
                        "country": get_value(row, mapping, "country", ""),
                        "buyer_account_id": get_value(row, mapping, "buyer_account_id", ""),
                        "publisher_id": get_value(row, mapping, "publisher_id", ""),
                        "publisher_name": get_value(row, mapping, "publisher_name", ""),
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
        result.date_range_start = min_date
        result.date_range_end = max_date

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def import_to_rtb_bid_filtering(
    csv_path: str,
    mapping: MappingResult,
    db_path: str,
    batch_id: str,
    result: UnifiedImportResult,
    bidder_id: Optional[str] = None,
):
    """Import data to rtb_bid_filtering table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    configure_import_connection(conn)
    ensure_table_exists(cursor, "rtb_bid_filtering")
    ensure_unique_index(cursor, "rtb_bid_filtering", "row_hash", "idx_rtb_bid_filtering_row_hash")

    hash_keys = ["metric_date", "country", "filtering_reason", "creative_id", "bidder_id"]
    min_date, max_date = None, None

    insert_sql = """
        INSERT OR IGNORE INTO rtb_bid_filtering (
            metric_date, country, buyer_account_id, filtering_reason, creative_id,
            bids, bids_in_auction, opportunity_cost_micros,
            bidder_id, row_hash, import_batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows_to_insert: list[tuple] = []

    def flush_rows():
        if not rows_to_insert:
            return
        before = conn.total_changes
        cursor.executemany(insert_sql, rows_to_insert)
        inserted = conn.total_changes - before
        result.rows_imported += inserted
        if inserted >= 0:
            result.rows_duplicate += len(rows_to_insert) - inserted
        rows_to_insert.clear()

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
        result.date_range_start = min_date
        result.date_range_end = max_date

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")

    finally:
        conn.close()


def unified_import(
    csv_path: str,
    db_path: str = DB_PATH,
    bidder_id: Optional[str] = None,
) -> UnifiedImportResult:
    """
    Import any CSV using flexible column mapping.

    Args:
        csv_path: Path to CSV file
        db_path: Database path

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
        bidder_id = parse_bidder_id_from_filename(csv_path)
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

    # Import based on target table
    if target_table == "rtb_daily":
        import_to_rtb_daily(csv_path, mapping, db_path, result.batch_id, result, bidder_id=bidder_id)
    elif target_table == "rtb_bidstream":
        import_to_rtb_bidstream(csv_path, mapping, db_path, result.batch_id, result, bidder_id=bidder_id)
    elif target_table == "rtb_bid_filtering":
        import_to_rtb_bid_filtering(csv_path, mapping, db_path, result.batch_id, result, bidder_id=bidder_id)
    else:
        result.error_message = f"Unknown target table: {target_table}"

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
