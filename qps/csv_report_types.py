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
    """The 5 CSV report types for QPS optimization."""
    PERFORMANCE_DETAIL = "performance_detail"      # rtb_daily - has creative/app/size
    RTB_FUNNEL_GEO = "rtb_funnel_geo"             # rtb_funnel - geo only, full pipeline
    RTB_FUNNEL_PUBLISHER = "rtb_funnel_publisher"  # rtb_funnel - with publisher, full pipeline
    BID_FILTERING = "bid_filtering"                # rtb_bid_filtering - why bids fail
    QUALITY_SIGNALS = "quality_signals"            # rtb_quality - fraud/viewability signals
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
    "hour": ["Hour", "#Hour"],  # NEW: Hourly granularity
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
    # NEW: Viewability metrics
    "viewable_impressions": ["Active View viewable", "Active view viewable", "#Active View viewable"],
    "measurable_impressions": ["Active View measurable", "Active view measurable", "#Active View measurable"],
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
    # NEW: Platform/Environment/Transaction type
    "platform": ["Platform", "#Platform"],
    "environment": ["Environment", "#Environment"],
    "transaction_type": ["Transaction type", "#Transaction type"],
}

# Fields that are MUTUALLY EXCLUSIVE with bid_requests (Google limitation)
INCOMPATIBLE_WITH_BID_REQUESTS = {
    "creative_id", "creative_size", "creative_format",
    "app_id", "app_name", "billing_id"
}

# ============================================================================
# Report 4: Bid Filtering (goes to rtb_bid_filtering)
# ============================================================================
# This report answers: "WHY are bids being filtered?"
# Detected by presence of "Bid filtering reason" column

BID_FILTERING_REQUIRED = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "filtering_reason": ["Bid filtering reason", "#Bid filtering reason",
                         "Filtering reason", "#Filtering reason"],
}

BID_FILTERING_METRICS = {
    "bids": ["Bids", "#Bids"],
    "bids_in_auction": ["Bids in auction", "#Bids in auction"],
}

BID_FILTERING_OPTIONAL = {
    "country": ["Country", "#Country"],
    "buyer_account_id": ["Buyer account ID", "#Buyer account ID"],
    "creative_id": ["Creative ID", "#Creative ID"],  # May not be available due to incompatibilities
    "opportunity_cost": ["Opportunity cost", "#Opportunity cost", "Lost spend", "#Lost spend"],
}

# ============================================================================
# Report 5: Quality Signals (goes to rtb_quality)
# ============================================================================
# This report answers: "Which publishers have fraud or low viewability?"
# Detected by presence of "IVT credited impressions" or "Pre-filtered impressions"

QUALITY_SIGNALS_REQUIRED = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "publisher_id": ["Publisher ID", "#Publisher ID"],
}

QUALITY_SIGNALS_METRICS = {
    "impressions": ["Impressions", "#Impressions"],
    "pre_filtered_impressions": ["Pre-filtered impressions", "#Pre-filtered impressions",
                                  "Pre filtered impressions"],
    "ivt_credited_impressions": ["IVT credited impressions", "#IVT credited impressions",
                                  "IVT credited", "Invalid traffic credited impressions"],
    "billed_impressions": ["Billed impressions", "#Billed impressions"],
    "measurable_impressions": ["Active View measurable", "Active view measurable",
                               "Measurable impressions", "#Active View measurable"],
    "viewable_impressions": ["Active View viewable", "Active view viewable",
                             "Viewable impressions", "#Active View viewable"],
}

QUALITY_SIGNALS_OPTIONAL = {
    "publisher_name": ["Publisher name", "#Publisher name"],
    "country": ["Country", "#Country"],
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
        elif self.report_type == ReportType.BID_FILTERING:
            self.report_name = "Bid Filtering"
            self.description = "Bid filtering reasons (why bids fail)"
            self.target_table = "rtb_bid_filtering"
        elif self.report_type == ReportType.QUALITY_SIGNALS:
            self.report_name = "Quality Signals"
            self.description = "Fraud and viewability signals by publisher"
            self.target_table = "rtb_quality"


def detect_report_type(header: List[str]) -> ReportDetectionResult:
    """
    Detect which of the 5 report types a CSV is based on its header.

    Detection logic:
    1. Has "Bid filtering reason" column? → BID_FILTERING
    2. Has "IVT credited impressions" or "Pre-filtered impressions"? → QUALITY_SIGNALS
    3. Has "Bid requests" column? → RTB Funnel type
       - Also has Publisher ID? → RTB_FUNNEL_PUBLISHER
       - No Publisher? → RTB_FUNNEL_GEO
    4. Has "Creative ID" + "Billing ID"? → PERFORMANCE_DETAIL
    5. Otherwise → UNKNOWN
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

    # Check for distinguishing columns
    bid_requests_col = has_column(["Bid requests", "#Bid requests"])
    creative_id_col = has_column(["Creative ID", "#Creative ID"])
    billing_id_col = has_column(["Billing ID", "#Billing ID"])
    publisher_id_col = has_column(["Publisher ID", "#Publisher ID"])

    # NEW: Check for bid filtering reason (Report 4)
    filtering_reason_col = has_column(["Bid filtering reason", "#Bid filtering reason",
                                        "Filtering reason", "#Filtering reason"])

    # NEW: Check for quality signal columns (Report 5)
    ivt_credited_col = has_column(["IVT credited impressions", "#IVT credited impressions",
                                   "IVT credited", "Invalid traffic credited impressions"])
    pre_filtered_col = has_column(["Pre-filtered impressions", "#Pre-filtered impressions",
                                   "Pre filtered impressions"])

    # Detection order matters - check most specific first

    # 1. Check for Bid Filtering report (has filtering reason)
    if filtering_reason_col:
        result.report_type = ReportType.BID_FILTERING
        result.target_table = "rtb_bid_filtering"
        result.confidence = "high"

        # Map columns
        for our_name, possible_names in {**BID_FILTERING_REQUIRED, **BID_FILTERING_METRICS, **BID_FILTERING_OPTIONAL}.items():
            col = has_column(possible_names)
            if col:
                result.columns_mapped[our_name] = col

        # Check required
        for our_name, possible_names in BID_FILTERING_REQUIRED.items():
            if not has_column(possible_names):
                result.required_missing.append(our_name)

    # 2. Check for Quality Signals report (has IVT or pre-filtered)
    elif ivt_credited_col or pre_filtered_col:
        result.report_type = ReportType.QUALITY_SIGNALS
        result.target_table = "rtb_quality"
        result.confidence = "high"

        # Map columns
        for our_name, possible_names in {**QUALITY_SIGNALS_REQUIRED, **QUALITY_SIGNALS_METRICS, **QUALITY_SIGNALS_OPTIONAL}.items():
            col = has_column(possible_names)
            if col:
                result.columns_mapped[our_name] = col

        # Check required
        for our_name, possible_names in QUALITY_SIGNALS_REQUIRED.items():
            if not has_column(possible_names):
                result.required_missing.append(our_name)

    # 3. Check for RTB Funnel report (has bid_requests)
    elif bid_requests_col:
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

    # 4. Check for Performance Detail report (has Creative ID + Billing ID)
    elif creative_id_col and billing_id_col:
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
