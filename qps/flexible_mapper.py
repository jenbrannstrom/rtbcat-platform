"""Flexible Column Mapper for CSV Imports.

Maps CSV columns to database fields using:
1. Exact matches
2. Case-insensitive matches
3. Synonym matching
4. Fuzzy matching (Levenshtein distance)

This allows importing CSVs with varied column naming conventions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from difflib import SequenceMatcher


# =============================================================================
# COLUMN SYNONYMS - All possible names for each database field
# =============================================================================

COLUMN_SYNONYMS: Dict[str, List[str]] = {
    # Time dimensions
    "day": ["day", "date", "#day", "#date", "metric_date", "report_date"],
    "hour": ["hour", "#hour", "time", "hour_of_day"],

    # Account/Config dimensions
    "billing_id": [
        "billing id", "billing_id", "#billing id", "billingid",
        "pretargeting", "pretargeting id", "config", "config_id",
        "buyer billing id", "account"
    ],
    "buyer_account_id": [
        "buyer account id", "buyer_account_id", "#buyer account id",
        "account id", "buyer id", "buyerid", "bidder id"
    ],

    # Creative dimensions
    "creative_id": [
        "creative id", "creative_id", "#creative id", "creativeid",
        "creative", "ad id", "ad_id", "banner id"
    ],
    "creative_size": [
        "creative size", "creative_size", "#creative size", "size",
        "ad size", "banner size", "dimensions", "format size"
    ],
    "creative_format": [
        "creative format", "creative_format", "#creative format", "format",
        "ad format", "ad type", "creative type"
    ],

    # Geo dimensions
    "country": [
        "country", "#country", "geo", "geography", "region",
        "country code", "country_code", "location"
    ],

    # Publisher/Inventory dimensions
    "publisher_id": [
        "publisher id", "publisher_id", "#publisher id", "publisherid",
        "pub id", "pub_id", "seller id", "seller_id"
    ],
    "publisher_name": [
        "publisher name", "publisher_name", "#publisher name",
        "publisher", "pub name", "seller name", "seller"
    ],
    "publisher_domain": [
        "publisher domain", "publisher_domain", "#publisher domain",
        "domain", "site", "website"
    ],
    "app_id": [
        "mobile app id", "mobile_app_id", "#mobile app id", "app id",
        "app_id", "appid", "application id", "bundle id", "bundle"
    ],
    "app_name": [
        "mobile app name", "mobile_app_name", "#mobile app name",
        "app name", "app_name", "appname", "application name", "app"
    ],
    "platform": [
        "platform", "#platform", "device type", "device", "os"
    ],
    "environment": [
        "environment", "#environment", "env", "inventory type"
    ],

    # Bid funnel metrics
    "inventory_matches": [
        "inventory matches", "inventory_matches", "#inventory matches",
        "matches", "matched queries"
    ],
    "bid_requests": [
        "bid requests", "bid_requests", "#bid requests", "requests",
        "bid request", "callouts", "queries"
    ],
    "successful_responses": [
        "successful responses", "successful_responses", "#successful responses",
        "responses", "valid responses"
    ],
    "bids": [
        "bids", "#bids", "bid count", "total bids", "submitted bids"
    ],
    "bids_in_auction": [
        "bids in auction", "bids_in_auction", "#bids in auction",
        "auction bids", "eligible bids", "qualified bids", "bids in auctions"
    ],
    "auctions_won": [
        "auctions won", "auctions_won", "#auctions won", "wins",
        "won", "auction wins", "victories"
    ],
    "reached_queries": [
        "reached queries", "reached_queries", "#reached queries",
        "reached", "reach", "queries reached"
    ],

    # Performance metrics
    "impressions": [
        "impressions", "#impressions", "imps", "imp", "views",
        "ad impressions", "served"
    ],
    "clicks": [
        "clicks", "#clicks", "click", "taps", "interactions"
    ],
    "spend": [
        "spend", "#spend", "cost", "revenue", "spend (bidder currency)",
        "spend (buyer currency)", "spend_buyer_currency", "spend_micros",
        "total spend", "amount"
    ],

    # Video metrics
    "video_starts": [
        "video starts", "video_starts", "#video starts", "starts",
        "video plays", "plays"
    ],
    "video_completions": [
        "video completions", "video_completions", "#video completions",
        "completions", "complete views", "100% viewed"
    ],

    # Viewability metrics
    "viewable_impressions": [
        "active view viewable", "viewable impressions", "viewable",
        "viewable_impressions", "#active view viewable", "viewed"
    ],
    "measurable_impressions": [
        "active view measurable", "measurable impressions", "measurable",
        "measurable_impressions", "#active view measurable"
    ],

    # Bid filtering
    "filtering_reason": [
        "bid filtering reason", "filtering reason", "filter reason",
        "#bid filtering reason", "reason", "block reason", "rejection reason"
    ],
    "opportunity_cost": [
        "opportunity cost", "bid filtering opportunity cost",
        "lost spend", "missed revenue", "opportunity_cost"
    ],

    # Quality signals
    "pre_filtered_impressions": [
        "pre-filtered impressions", "pre_filtered_impressions",
        "prefiltered", "pre filtered", "filtered impressions"
    ],
    "ivt_credited_impressions": [
        "ivt credited impressions", "ivt_credited_impressions",
        "ivt credited", "invalid traffic", "fraud impressions"
    ],
    "billed_impressions": [
        "billed impressions", "billed_impressions", "billed",
        "billable impressions", "charged impressions"
    ],
}


@dataclass
class ColumnMapping:
    """Result of mapping a CSV column to a database field."""
    csv_column: str
    db_field: str
    match_type: str  # "exact", "case_insensitive", "synonym", "fuzzy"
    confidence: float  # 0.0 to 1.0


@dataclass
class MappingResult:
    """Result of mapping all columns in a CSV."""
    mapped: Dict[str, ColumnMapping] = field(default_factory=dict)  # db_field -> mapping
    unmapped: List[str] = field(default_factory=list)  # CSV columns that couldn't be mapped
    csv_to_db: Dict[str, str] = field(default_factory=dict)  # csv_column -> db_field

    def get_csv_column(self, db_field: str) -> Optional[str]:
        """Get the CSV column name for a database field."""
        if db_field in self.mapped:
            return self.mapped[db_field].csv_column
        return None

    def has_field(self, db_field: str) -> bool:
        """Check if a database field was mapped."""
        return db_field in self.mapped


def normalize_column_name(name: str) -> str:
    """Normalize a column name for comparison."""
    return name.lower().strip().replace("_", " ").replace("-", " ").replace("#", "")


def fuzzy_match_score(s1: str, s2: str) -> float:
    """Calculate similarity score between two strings."""
    return SequenceMatcher(None, normalize_column_name(s1), normalize_column_name(s2)).ratio()


def map_columns(csv_headers: List[str], min_fuzzy_score: float = 0.8) -> MappingResult:
    """
    Map CSV column headers to database fields.

    Args:
        csv_headers: List of column names from CSV
        min_fuzzy_score: Minimum similarity score for fuzzy matching (0.0-1.0)

    Returns:
        MappingResult with all mappings
    """
    result = MappingResult()
    used_csv_columns: Set[str] = set()

    # Build reverse lookup: normalized synonym -> (db_field, original_synonym)
    synonym_lookup: Dict[str, Tuple[str, str]] = {}
    for db_field, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            synonym_lookup[normalize_column_name(synonym)] = (db_field, synonym)

    # Pass 1: Exact matches and case-insensitive matches
    for csv_col in csv_headers:
        normalized = normalize_column_name(csv_col)

        if normalized in synonym_lookup:
            db_field, _ = synonym_lookup[normalized]
            if db_field not in result.mapped:  # Don't overwrite existing mappings
                result.mapped[db_field] = ColumnMapping(
                    csv_column=csv_col,
                    db_field=db_field,
                    match_type="synonym",
                    confidence=1.0
                )
                result.csv_to_db[csv_col] = db_field
                used_csv_columns.add(csv_col)

    # Pass 2: Fuzzy matching for unmapped columns
    for csv_col in csv_headers:
        if csv_col in used_csv_columns:
            continue

        best_match: Optional[Tuple[str, float]] = None

        for db_field, synonyms in COLUMN_SYNONYMS.items():
            if db_field in result.mapped:
                continue

            for synonym in synonyms:
                score = fuzzy_match_score(csv_col, synonym)
                if score >= min_fuzzy_score:
                    if best_match is None or score > best_match[1]:
                        best_match = (db_field, score)

        if best_match:
            db_field, score = best_match
            result.mapped[db_field] = ColumnMapping(
                csv_column=csv_col,
                db_field=db_field,
                match_type="fuzzy",
                confidence=score
            )
            result.csv_to_db[csv_col] = db_field
            used_csv_columns.add(csv_col)

    # Track unmapped columns
    result.unmapped = [col for col in csv_headers if col not in used_csv_columns]

    return result


def detect_best_report_type(mapping: MappingResult) -> Tuple[str, str, List[str]]:
    """
    Detect the best report type based on mapped columns.

    Priority order:
    1. Bid Filtering (has filtering_reason)
    2. Quality Signals (has IVT metrics)
    3. Performance Detail (has creative_id - even with bid metrics, creative-level wins)
    4. RTB Funnel (has bid_requests without creative_id)
    5. Unknown

    Returns:
        (report_type, target_table, missing_critical_fields)
    """
    has_day = mapping.has_field("day")
    has_country = mapping.has_field("country")
    has_creative_id = mapping.has_field("creative_id")
    has_billing_id = mapping.has_field("billing_id")
    has_bid_requests = mapping.has_field("bid_requests")
    has_bids_in_auction = mapping.has_field("bids_in_auction")
    has_filtering_reason = mapping.has_field("filtering_reason")
    has_publisher_id = mapping.has_field("publisher_id")
    has_ivt = mapping.has_field("ivt_credited_impressions") or mapping.has_field("pre_filtered_impressions")
    has_impressions = mapping.has_field("impressions")
    has_auctions_won = mapping.has_field("auctions_won")

    # Check for Bid Filtering report
    if has_filtering_reason:
        missing = []
        if not has_day:
            missing.append("day")
        return ("bid_filtering", "rtb_bid_filtering", missing)

    # Check for Quality Signals report
    if has_ivt:
        missing = []
        if not has_day:
            missing.append("day")
        if not has_publisher_id:
            missing.append("publisher_id")
        return ("quality_signals", "rtb_quality", missing)

    # Check for Performance Detail (has creative_id)
    # This takes priority over funnel because creative-level data should go to rtb_daily
    # Even if it has bid metrics (bids_in_auction, auctions_won), creative_id wins
    if has_creative_id:
        missing = []
        if not has_day:
            missing.append("day")
        return ("performance_detail", "rtb_daily", missing)

    # Check for RTB Funnel report (has bid pipeline metrics WITHOUT creative_id)
    if has_bid_requests or has_bids_in_auction or has_auctions_won:
        missing = []
        if not has_day:
            missing.append("day")
        if not has_country:
            missing.append("country")

        if has_publisher_id:
            return ("rtb_bidstream_publisher", "rtb_bidstream", missing)
        else:
            return ("rtb_bidstream_geo", "rtb_bidstream", missing)

    # Check for Performance Detail without creative_id (has impressions)
    if has_impressions:
        missing = []
        if not has_day:
            missing.append("day")
        return ("performance_detail", "rtb_daily", missing)

    # Unknown
    return ("unknown", "", ["day"])


def get_default_value(db_field: str) -> Optional[str]:
    """Get a sensible default value for a missing field."""
    defaults = {
        "billing_id": "unknown",
        "creative_size": "unknown",
        "creative_format": "unknown",
        "publisher_name": "",
        "app_name": "",
        "platform": "unknown",
        "environment": "unknown",
        "hour": "0",
        "clicks": "0",
        "spend": "0",
        "video_starts": "0",
        "video_completions": "0",
        "viewable_impressions": "0",
        "measurable_impressions": "0",
        "reached_queries": "0",
        "impressions": "0",
        "bids": "0",
        "bids_in_auction": "0",
        "auctions_won": "0",
        "inventory_matches": "0",
        "successful_responses": "0",
        "bid_requests": "0",
        "opportunity_cost": "0",
    }
    return defaults.get(db_field)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import sys
    import csv

    if len(sys.argv) < 2:
        print("Usage: python -m qps.flexible_mapper <csv_file>")
        sys.exit(1)

    csv_path = sys.argv[1]

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)

    print(f"\nCSV Columns: {headers}\n")

    mapping = map_columns(headers)

    print("=" * 60)
    print("COLUMN MAPPING RESULTS")
    print("=" * 60)

    print("\nMapped columns:")
    for db_field, m in sorted(mapping.mapped.items()):
        print(f"  {m.csv_column:30} → {db_field:20} ({m.match_type}, {m.confidence:.0%})")

    if mapping.unmapped:
        print(f"\nUnmapped columns: {mapping.unmapped}")

    report_type, table, missing = detect_best_report_type(mapping)
    print(f"\nDetected report type: {report_type}")
    print(f"Target table: {table}")
    if missing:
        print(f"Missing critical fields: {missing}")
