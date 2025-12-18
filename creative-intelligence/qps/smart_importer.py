"""Smart CSV Importer - Auto-detects report type and routes to correct handler.

This is the RECOMMENDED entry point for importing any Cat-Scan CSV.

Usage:
    from qps.smart_importer import smart_import

    result = smart_import("/path/to/any-catscan-report.csv")
    print(f"Imported to: {result.target_table}")
"""

import csv
import os
from dataclasses import dataclass
from typing import Optional, Union

from qps.csv_report_types import (
    ReportType, detect_report_type, get_report_instructions
)
from qps.importer import import_csv, ImportResult
from qps.funnel_importer import import_funnel_csv, FunnelImportResult
from qps.bid_filtering_importer import import_bid_filtering_csv, BidFilteringImportResult
from qps.quality_importer import import_quality_csv, QualityImportResult


@dataclass
class SmartImportResult:
    """Result from smart import - wraps underlying result."""
    success: bool
    report_type: ReportType
    target_table: str
    report_name: str

    # Pass through key stats
    rows_imported: int = 0
    rows_read: int = 0
    error_message: str = ""

    # The underlying result object
    detail: Union[ImportResult, FunnelImportResult, BidFilteringImportResult, QualityImportResult, None] = None


def smart_import(
    csv_path: str,
    db_path: Optional[str] = None,
    bidder_id: Optional[str] = None,
) -> SmartImportResult:
    """
    Import a CSV by auto-detecting its type and routing to the correct handler.

    Detects:
    - Performance Detail CSVs → rtb_daily table (via importer.py)
    - RTB Funnel CSVs → rtb_funnel table (via funnel_importer.py)

    Args:
        csv_path: Path to CSV file
        db_path: Optional custom database path
        bidder_id: Optional account ID to associate

    Returns:
        SmartImportResult with success status and details
    """
    # Check file exists
    if not os.path.exists(csv_path):
        return SmartImportResult(
            success=False,
            report_type=ReportType.UNKNOWN,
            target_table="",
            report_name="Unknown",
            error_message=f"File not found: {csv_path}"
        )

    # Read header and detect type
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
    except Exception as e:
        return SmartImportResult(
            success=False,
            report_type=ReportType.UNKNOWN,
            target_table="",
            report_name="Unknown",
            error_message=f"Failed to read CSV header: {e}"
        )

    detection = detect_report_type(header)

    # Route based on detected type
    if detection.report_type == ReportType.PERFORMANCE_DETAIL:
        # Use existing importer for rtb_daily
        kwargs = {"csv_path": csv_path}
        if db_path:
            kwargs["db_path"] = db_path
        if bidder_id:
            kwargs["bidder_id"] = bidder_id

        result = import_csv(**kwargs)

        return SmartImportResult(
            success=result.success,
            report_type=ReportType.PERFORMANCE_DETAIL,
            target_table="rtb_daily",
            report_name="Performance Detail",
            rows_imported=result.rows_imported,
            rows_read=result.rows_read,
            error_message=result.error_message,
            detail=result
        )

    elif detection.report_type in [ReportType.RTB_FUNNEL_GEO, ReportType.RTB_FUNNEL_PUBLISHER]:
        # Use funnel importer for rtb_funnel
        kwargs = {"csv_path": csv_path}
        if db_path:
            kwargs["db_path"] = db_path
        if bidder_id:
            kwargs["bidder_id"] = bidder_id

        result = import_funnel_csv(**kwargs)

        report_name = "RTB Funnel (Geo)" if detection.report_type == ReportType.RTB_FUNNEL_GEO else "RTB Funnel (Publisher)"

        return SmartImportResult(
            success=result.success,
            report_type=detection.report_type,
            target_table="rtb_funnel",
            report_name=report_name,
            rows_imported=result.rows_imported,
            rows_read=result.rows_read,
            error_message=result.error_message,
            detail=result
        )

    elif detection.report_type == ReportType.BID_FILTERING:
        # Use bid filtering importer for rtb_bid_filtering
        kwargs = {"csv_path": csv_path}
        if db_path:
            kwargs["db_path"] = db_path
        if bidder_id:
            kwargs["bidder_id"] = bidder_id

        result = import_bid_filtering_csv(**kwargs)

        return SmartImportResult(
            success=result.success,
            report_type=ReportType.BID_FILTERING,
            target_table="rtb_bid_filtering",
            report_name="Bid Filtering",
            rows_imported=result.rows_imported,
            rows_read=result.rows_read,
            error_message=result.error_message,
            detail=result
        )

    elif detection.report_type == ReportType.QUALITY_SIGNALS:
        # Use quality importer for rtb_quality
        kwargs = {"csv_path": csv_path}
        if db_path:
            kwargs["db_path"] = db_path
        if bidder_id:
            kwargs["bidder_id"] = bidder_id

        result = import_quality_csv(**kwargs)

        return SmartImportResult(
            success=result.success,
            report_type=ReportType.QUALITY_SIGNALS,
            target_table="rtb_quality",
            report_name="Quality Signals",
            rows_imported=result.rows_imported,
            rows_read=result.rows_read,
            error_message=result.error_message,
            detail=result
        )

    else:
        # Unknown report type
        return SmartImportResult(
            success=False,
            report_type=ReportType.UNKNOWN,
            target_table="",
            report_name="Unknown",
            error_message=(
                "Could not detect report type from CSV columns.\n\n"
                "Expected one of:\n"
                "  1. Performance Detail: must have 'Creative ID' + 'Billing ID'\n"
                "  2. RTB Funnel: must have 'Bid requests'\n"
                "  3. Bid Filtering: must have 'Bid filtering reason'\n"
                "  4. Quality Signals: must have 'IVT credited impressions' or 'Pre-filtered impressions'\n\n"
                f"Columns found: {', '.join(header[:10])}...\n\n"
                "See: python -m qps.csv_report_types for required CSV formats"
            )
        )


def print_report_instructions():
    """Print the full CSV report creation instructions."""
    print(get_report_instructions())


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m qps.smart_importer <csv_file>")
        print("       python -m qps.smart_importer --help")
        print("\nAuto-detects CSV type and imports to correct table.")
        sys.exit(1)

    if sys.argv[1] == "--help":
        print_report_instructions()
        sys.exit(0)

    csv_path = sys.argv[1]

    print(f"Analyzing CSV: {csv_path}")
    result = smart_import(csv_path)

    if result.success:
        print(f"\n✅ IMPORT COMPLETE")
        print(f"  Report type:    {result.report_name}")
        print(f"  Target table:   {result.target_table}")
        print(f"  Rows read:      {result.rows_read:,}")
        print(f"  Rows imported:  {result.rows_imported:,}")
    else:
        print(f"\n❌ IMPORT FAILED")
        print(f"  Report type:    {result.report_name}")
        print(f"  Error: {result.error_message}")
        sys.exit(1)
