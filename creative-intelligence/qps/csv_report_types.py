"""CSV Report Type Detection and Configuration.

Google Authorized Buyers has field incompatibilities that require MULTIPLE CSV exports
to get complete QPS optimization data.

THE 3 REQUIRED REPORTS:
=======================

1. PERFORMANCE DETAIL (rtb_daily table)
   - Purpose: Creative/Size/App-level performance
   - What you CAN'T include: Bid requests, Bids, Bids in auction, Auctions won
   - Dimensions: Day, Billing ID, Creative ID, Creative size, Creative format,
                 Country, Publisher ID, Mobile app ID, Mobile app name
   - Metrics: Reached queries, Impressions, Clicks, Spend

2. RTB FUNNEL - GEO ONLY (rtb_funnel table)
   - Purpose: Full bid pipeline metrics by country
   - What you CAN'T include: Creative ID, Creative size, Mobile app ID, Publisher ID
   - Dimensions: Day, Country, Buyer account ID, Hour
   - Metrics: Bid requests, Inventory matches, Successful responses, Reached queries,
              Bids, Bids in auction, Auctions won, Impressions, Clicks

3. RTB FUNNEL - WITH PUBLISHERS (rtb_funnel table)
   - Purpose: Publisher-level bid pipeline (for publisher optimization)
   - What you CAN'T include: Creative ID, Creative size, Mobile app ID
   - Dimensions: Day, Country, Buyer account ID, Hour, Publisher ID, Publisher name
   - Metrics: Same as RTB Funnel Geo Only

WHY 3 REPORTS?
==============
Google's error: "Mobile app ID is not compatible with [Bid requests], [Inventory matches]..."

This means:
- To get App-level data → you lose Bid request metrics
- To get Bid request metrics → you lose App/Creative detail
- To get Publisher + Bid metrics → separate from App data

JOINING THE DATA:
=================
- rtb_daily + rtb_funnel JOIN ON (metric_date, country)
- For publisher analysis: JOIN ON (metric_date, country, publisher_id)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class ReportType(Enum):
    """The 3 CSV report types users must create."""
    PERFORMANCE_DETAIL = "performance_detail"      # rtb_daily - has creative/app/size
    RTB_FUNNEL_GEO = "rtb_funnel_geo"             # rtb_funnel - geo only, full pipeline
    RTB_FUNNEL_PUBLISHER = "rtb_funnel_publisher"  # rtb_funnel - with publisher, full pipeline
    UNKNOWN = "unknown"


# ============================================================================
# COLUMN DEFINITIONS FOR EACH REPORT TYPE
# ============================================================================

# Report 1: Performance Detail (goes to rtb_daily)
PERFORMANCE_DETAIL_REQUIRED = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "billing_id": ["Billing ID", "#Billing ID"],
    "creative_id": ["Creative ID", "#Creative ID"],
    "creative_size": ["Creative size", "#Creative size"],
    "country": ["Country", "#Country"],
    "reached_queries": ["Reached queries", "#Reached queries"],
    "impressions": ["Impressions", "#Impressions"],
}

PERFORMANCE_DETAIL_OPTIONAL = {
    "creative_format": ["Creative format", "#Creative format"],
    "platform": ["Platform", "#Platform"],
    "environment": ["Environment", "#Environment"],
    "app_id": ["Mobile app ID", "#Mobile app ID"],
    "app_name": ["Mobile app name", "#Mobile app name"],
    "publisher_id": ["Publisher ID", "#Publisher ID"],
    "publisher_name": ["Publisher name", "#Publisher name"],
    "publisher_domain": ["Publisher domain", "#Publisher domain"],
    "clicks": ["Clicks", "#Clicks"],
    "spend": ["Spend (bidder currency)", "Spend _buyer currency_",
              "Spend (buyer currency)", "#Spend"],
    "video_starts": ["Video starts", "#Video starts"],
    "video_completions": ["Video completions", "#Video completions"],
}

# Report 2 & 3: RTB Funnel (goes to rtb_funnel)
RTB_FUNNEL_REQUIRED = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "country": ["Country", "#Country"],
    "bid_requests": ["Bid requests", "#Bid requests"],
    "reached_queries": ["Reached queries", "#Reached queries"],
}

RTB_FUNNEL_PIPELINE_METRICS = {
    "inventory_matches": ["Inventory matches", "#Inventory matches"],
    "successful_responses": ["Successful responses", "#Successful responses"],
    "bids": ["Bids", "#Bids"],
    "bids_in_auction": ["Bids in auction", "#Bids in auction"],
    "auctions_won": ["Auctions won", "#Auctions won"],
    "impressions": ["Impressions", "#Impressions"],
    "clicks": ["Clicks", "#Clicks"],
}

RTB_FUNNEL_OPTIONAL = {
    "hour": ["Hour", "#Hour"],
    "buyer_account_id": ["Buyer account ID", "#Buyer account ID"],
    # Publisher fields - presence determines funnel subtype
    "publisher_id": ["Publisher ID", "#Publisher ID"],
    "publisher_name": ["Publisher name", "#Publisher name"],
}

# Fields that are MUTUALLY EXCLUSIVE with bid_requests (Google limitation)
INCOMPATIBLE_WITH_BID_REQUESTS = {
    "creative_id", "creative_size", "creative_format",
    "app_id", "app_name", "billing_id"
}


@dataclass
class ReportDetectionResult:
    """Result of detecting which report type a CSV is."""
    report_type: ReportType
    confidence: str  # "high", "medium", "low"
    target_table: str  # "rtb_daily" or "rtb_funnel"

    columns_found: List[str] = field(default_factory=list)
    columns_mapped: Dict[str, str] = field(default_factory=dict)
    required_missing: List[str] = field(default_factory=list)

    # For UI display
    report_name: str = ""
    description: str = ""

    def __post_init__(self):
        if self.report_type == ReportType.PERFORMANCE_DETAIL:
            self.report_name = "Performance Detail"
            self.description = "Creative/Size/App performance data"
            self.target_table = "rtb_daily"
        elif self.report_type == ReportType.RTB_FUNNEL_GEO:
            self.report_name = "RTB Funnel (Geo)"
            self.description = "Bid pipeline by country"
            self.target_table = "rtb_funnel"
        elif self.report_type == ReportType.RTB_FUNNEL_PUBLISHER:
            self.report_name = "RTB Funnel (Publisher)"
            self.description = "Bid pipeline by publisher"
            self.target_table = "rtb_funnel"


def detect_report_type(header: List[str]) -> ReportDetectionResult:
    """
    Detect which of the 3 report types a CSV is based on its header.

    Detection logic:
    1. Has "Bid requests" column? → RTB Funnel type
       - Also has Publisher ID? → RTB_FUNNEL_PUBLISHER
       - No Publisher? → RTB_FUNNEL_GEO
    2. Has "Creative ID" + "Billing ID"? → PERFORMANCE_DETAIL
    3. Otherwise → UNKNOWN
    """
    header_set = set(header)
    result = ReportDetectionResult(
        report_type=ReportType.UNKNOWN,
        confidence="low",
        target_table="",
        columns_found=header
    )

    # Helper to check if any variant of a column exists
    def has_column(possible_names: List[str]) -> Optional[str]:
        for name in possible_names:
            if name in header_set:
                return name
        return None

    # Check for bid_requests - this is THE distinguishing field
    bid_requests_col = has_column(["Bid requests", "#Bid requests"])
    creative_id_col = has_column(["Creative ID", "#Creative ID"])
    billing_id_col = has_column(["Billing ID", "#Billing ID"])
    publisher_id_col = has_column(["Publisher ID", "#Publisher ID"])

    if bid_requests_col:
        # This is an RTB Funnel report
        # Check if it has publisher data
        if publisher_id_col:
            result.report_type = ReportType.RTB_FUNNEL_PUBLISHER
        else:
            result.report_type = ReportType.RTB_FUNNEL_GEO

        result.target_table = "rtb_funnel"
        result.confidence = "high"

        # Map columns
        for our_name, possible_names in {**RTB_FUNNEL_REQUIRED, **RTB_FUNNEL_PIPELINE_METRICS, **RTB_FUNNEL_OPTIONAL}.items():
            col = has_column(possible_names)
            if col:
                result.columns_mapped[our_name] = col

        # Check required
        for our_name, possible_names in RTB_FUNNEL_REQUIRED.items():
            if not has_column(possible_names):
                result.required_missing.append(our_name)

    elif creative_id_col and billing_id_col:
        # This is a Performance Detail report
        result.report_type = ReportType.PERFORMANCE_DETAIL
        result.target_table = "rtb_daily"
        result.confidence = "high"

        # Map columns
        for our_name, possible_names in {**PERFORMANCE_DETAIL_REQUIRED, **PERFORMANCE_DETAIL_OPTIONAL}.items():
            col = has_column(possible_names)
            if col:
                result.columns_mapped[our_name] = col

        # Check required
        for our_name, possible_names in PERFORMANCE_DETAIL_REQUIRED.items():
            if not has_column(possible_names):
                result.required_missing.append(our_name)

    result.__post_init__()  # Update names/descriptions
    return result


# ============================================================================
# USER DOCUMENTATION - WHAT CSVS TO CREATE
# ============================================================================

REPORT_INSTRUCTIONS = """
================================================================================
CAT-SCAN REQUIRED CSV REPORTS
================================================================================

You need to create 3 DAILY scheduled reports in Google Authorized Buyers.
This is required because Google has field incompatibilities.

Go to: Authorized Buyers → Reporting → Scheduled Reports → New Report

--------------------------------------------------------------------------------
REPORT 1: "catscan-performance" (Creative/App detail)
--------------------------------------------------------------------------------
Purpose: See which creatives, sizes, and apps are performing

DIMENSIONS (in this order):
  1. Day
  2. Billing ID
  3. Creative ID
  4. Creative size
  5. Creative format
  6. Country
  7. Publisher ID        ← Can include this
  8. Mobile app ID       ← Can include this
  9. Mobile app name     ← Can include this

METRICS:
  ✓ Reached queries
  ✓ Impressions
  ✓ Clicks
  ✓ Spend (buyer currency)

Schedule: Daily, Yesterday
Filename: catscan-performance

--------------------------------------------------------------------------------
REPORT 2: "catscan-funnel-geo" (Bid pipeline by country)
--------------------------------------------------------------------------------
Purpose: Understand bid_requests → bids → wins conversion by geo

DIMENSIONS (in this order):
  1. Day
  2. Country
  3. Buyer account ID
  4. Hour (optional)

METRICS:
  ✓ Bid requests         ← THE KEY METRIC
  ✓ Inventory matches
  ✓ Successful responses
  ✓ Reached queries
  ✓ Bids
  ✓ Bids in auction
  ✓ Auctions won
  ✓ Impressions
  ✓ Clicks

Schedule: Daily, Yesterday
Filename: catscan-funnel-geo

⚠️  You CANNOT add Creative ID, Mobile app ID, or Billing ID to this report!
    Google will show: "Mobile app ID is not compatible with [Bid requests]"

--------------------------------------------------------------------------------
REPORT 3: "catscan-funnel-publishers" (Bid pipeline by publisher)
--------------------------------------------------------------------------------
Purpose: See which publishers have best bid→win conversion

DIMENSIONS (in this order):
  1. Day
  2. Country
  3. Buyer account ID
  4. Publisher ID         ← Can include this (but not apps)
  5. Publisher name
  6. Hour (optional)

METRICS:
  ✓ Bid requests
  ✓ Inventory matches
  ✓ Successful responses
  ✓ Reached queries
  ✓ Bids
  ✓ Bids in auction
  ✓ Auctions won
  ✓ Impressions
  ✓ Clicks

Schedule: Daily, Yesterday
Filename: catscan-funnel-publishers

⚠️  You CANNOT add Mobile app ID to this report!

================================================================================
WHY 3 REPORTS?
================================================================================

Google's API limitation:
  "Mobile app ID is not compatible with [Bid requests], [Inventory matches]..."

This means:
  • To see App performance → you lose "Bid requests" column
  • To see "Bid requests" → you lose App/Creative detail
  • Publisher CAN be combined with Bid requests (but not Apps)

HOW CAT-SCAN JOINS THEM:
  • Report 1 (performance) + Report 2 (funnel-geo) → JOIN ON date + country
  • Report 1 + Report 3 (funnel-publishers) → JOIN ON date + country + publisher

This gives AI the full picture:
  Total traffic (bid_requests) → What you bid on → What you won → Revenue
================================================================================
"""


def get_report_instructions() -> str:
    """Return the full instructions for creating CSV reports."""
    return REPORT_INSTRUCTIONS
