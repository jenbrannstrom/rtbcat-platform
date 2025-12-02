#!/usr/bin/env python3
"""Cat-Scan QPS Analyzer CLI - Unified Data Architecture

Command-line tool for QPS optimization analysis:
- Validate and import BigQuery CSV exports
- Analyze size coverage
- Track config performance
- Detect fraud signals
- Generate full reports
- Generate video thumbnails

Usage:
    python cli/qps_analyzer.py validate <csv_file>
    python cli/qps_analyzer.py import <csv_file>
    python cli/qps_analyzer.py coverage [--days N]
    python cli/qps_analyzer.py include-list
    python cli/qps_analyzer.py configs [--days N]
    python cli/qps_analyzer.py fraud [--days N]
    python cli/qps_analyzer.py full-report [--days N]
    python cli/qps_analyzer.py summary
    python cli/qps_analyzer.py generate-thumbnails [--limit N] [--force]

Examples:
    python cli/qps_analyzer.py validate ~/downloads/bigquery_export.csv
    python cli/qps_analyzer.py import ~/downloads/bigquery_export.csv
    python cli/qps_analyzer.py coverage --days 7
    python cli/qps_analyzer.py full-report --days 7 > qps_report.txt
    python cli/qps_analyzer.py generate-thumbnails --limit 10
"""

import sys
import os
import re
import json
import sqlite3
import argparse
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent.parent))

from qps.importer import validate_csv, import_csv, get_data_summary
from qps.size_analyzer import SizeCoverageAnalyzer
from qps.config_tracker import ConfigPerformanceTracker
from qps.fraud_detector import FraudSignalDetector
from qps.constants import ACCOUNT_NAME, ACCOUNT_ID, PRETARGETING_CONFIGS


def cmd_import(args):
    """Import a CSV file with validation."""
    csv_path = args.file

    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"File: {csv_path} ({file_size_mb:.1f} MB)")

    # Validate first
    print("\nValidating...")
    validation = validate_csv(csv_path)

    if not validation.is_valid:
        print(f"\n❌ VALIDATION FAILED")
        print(f"\nError: {validation.error_message}")
        print(validation.get_fix_instructions())
        sys.exit(1)

    print(f"✓ Validation passed")
    print(f"  Columns found: {len(validation.columns_found)}")
    print(f"  Columns mapped: {len(validation.columns_mapped)}")
    print(f"  Rows (estimated): {validation.row_count_estimate:,}")

    if validation.optional_missing:
        print(f"\n  Optional columns not found:")
        for col in validation.optional_missing[:10]:
            print(f"    - {col}")
        if len(validation.optional_missing) > 10:
            print(f"    ... and {len(validation.optional_missing) - 10} more")

    # Import
    print(f"\nImporting...")
    result = import_csv(csv_path)

    if result.success:
        print(f"\n{'='*60}")
        print("✅ IMPORT COMPLETE")
        print(f"{'='*60}")
        print(f"  Batch ID:         {result.batch_id}")
        print(f"  Rows read:        {result.rows_read:,}")
        print(f"  Rows imported:    {result.rows_imported:,}")
        print(f"  Rows duplicate:   {result.rows_duplicate:,}")
        print(f"  Rows skipped:     {result.rows_skipped:,}")
        print(f"  Date range:       {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique creatives: {result.unique_creatives:,}")
        print(f"  Unique sizes:     {len(result.unique_sizes)}")
        print(f"  Billing IDs:      {', '.join(result.unique_billing_ids[:5])}")
        print(f"  Total reached:    {result.total_reached:,}")
        print(f"  Total impressions:{result.total_impressions:,}")
        print(f"  Total spend:      ${result.total_spend_usd:,.2f}")

        if result.errors:
            print(f"\n  Warnings ({len(result.errors)}):")
            for err in result.errors[:5]:
                print(f"    - {err}")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)


def cmd_validate(args):
    """Validate a CSV file without importing."""
    csv_path = args.file

    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    print(f"Validating {csv_path}...")
    validation = validate_csv(csv_path)

    print(f"\n{'='*60}")
    if validation.is_valid:
        print("✅ VALID - Ready for import")
    else:
        print("❌ INVALID - Cannot import")
    print(f"{'='*60}")

    print(f"\nColumns in file: {len(validation.columns_found)}")
    print(f"Columns mapped:  {len(validation.columns_mapped)}")
    print(f"Rows (est.):     {validation.row_count_estimate:,}")

    if validation.columns_mapped:
        print(f"\nMapped columns:")
        for our_name, csv_name in sorted(validation.columns_mapped.items()):
            print(f"  ✓ {our_name} ← '{csv_name}'")

    if validation.required_missing:
        print(f"\n❌ MISSING REQUIRED:")
        for col in validation.required_missing:
            print(f"  ✗ {col}")

    if validation.optional_missing:
        print(f"\nOptional not found:")
        for col in validation.optional_missing[:10]:
            print(f"  - {col}")

    if not validation.is_valid:
        print(validation.get_fix_instructions())
        sys.exit(1)


def cmd_coverage(args):
    """Generate size coverage report."""
    days = args.days or 7

    analyzer = SizeCoverageAnalyzer()
    print(analyzer.generate_report(days))


def cmd_include_list(args):
    """Generate recommended pretargeting include list."""
    analyzer = SizeCoverageAnalyzer()
    report = analyzer.analyze_coverage(days=7)

    print("=" * 60)
    print("RECOMMENDED PRETARGETING INCLUDE LIST")
    print("=" * 60)
    print()
    print(f"Your creatives span {len(report.inventory_sizes)} unique sizes.")
    print(f"Of these, {len(report.include_list)} can be filtered in pretargeting.")
    print()
    print("WARNING: Adding these will EXCLUDE all other sizes!")
    print()

    if report.include_list:
        print("SIZES TO INCLUDE:")
        print()

        # Format for easy copy-paste
        for i in range(0, len(report.include_list), 5):
            chunk = report.include_list[i:i+5]
            print("  " + ", ".join(chunk))

        print()
        print("TO IMPLEMENT:")
        print("  1. Go to Authorized Buyers UI")
        print("  2. Navigate to Bidder Settings -> Pretargeting")
        print("  3. Edit the config you want to modify")
        print("  4. Under 'Creative dimensions', add the sizes above")
        print("  5. Click Save")
        print("  6. Monitor traffic for 24-48 hours")
    else:
        print("No sizes found. Make sure creatives are synced.")

    print()


def cmd_configs(args):
    """Generate config performance report."""
    days = args.days or 7

    tracker = ConfigPerformanceTracker()
    print(tracker.generate_report(days))


def cmd_fraud(args):
    """Generate fraud signals report."""
    days = args.days or 14

    detector = FraudSignalDetector()
    print(detector.generate_report(days))


def cmd_full_report(args):
    """Generate comprehensive QPS optimization report."""
    days = args.days or 7

    print()
    print("=" * 80)
    print("Cat-Scan QPS OPTIMIZATION FULL REPORT")
    print("=" * 80)
    print()
    print(f"Account: {ACCOUNT_NAME} (ID: {ACCOUNT_ID})")
    print(f"Generated: {datetime.now().isoformat()}")
    print(f"Analysis Period: {days} days")
    print()

    # Size Coverage
    print("-" * 80)
    print("SECTION 1: SIZE COVERAGE")
    print("-" * 80)
    try:
        analyzer = SizeCoverageAnalyzer()
        print(analyzer.generate_report(days))
    except Exception as e:
        print(f"Error generating size coverage: {e}")
    print()

    # Config Performance
    print("-" * 80)
    print("SECTION 2: CONFIG PERFORMANCE")
    print("-" * 80)
    try:
        tracker = ConfigPerformanceTracker()
        print(tracker.generate_report(days))
    except Exception as e:
        print(f"Error generating config performance: {e}")
    print()

    # Fraud Signals
    print("-" * 80)
    print("SECTION 3: FRAUD SIGNALS")
    print("-" * 80)
    try:
        detector = FraudSignalDetector()
        print(detector.generate_report(days * 2))  # Use 2x days for fraud
    except Exception as e:
        print(f"Error generating fraud signals: {e}")
    print()

    print("=" * 80)
    print("END OF FULL REPORT")
    print("=" * 80)


def cmd_summary(args):
    """Show summary of imported data."""
    summary = get_data_summary()

    print("=" * 60)
    print("QPS DATA SUMMARY")
    print("=" * 60)
    print()
    print(f"  Total rows:           {summary['total_rows']:,}")
    print(f"  Unique dates:         {summary['unique_dates']}")
    print(f"  Unique billing IDs:   {summary['unique_billing_ids']}")
    print(f"  Unique sizes:         {summary['unique_sizes']}")
    print(f"  Unique creatives:     {summary['unique_creatives']}")
    print()

    if summary['date_range']['start']:
        print(f"  Date range:           {summary['date_range']['start']} to {summary['date_range']['end']}")
    else:
        print("  Date range:           No data imported yet")

    print()
    print(f"  Total reached queries: {summary['total_reached_queries']:,}")
    print(f"  Total impressions:     {summary['total_impressions']:,}")
    print(f"  Total spend:           ${summary['total_spend_usd']:,.2f}")
    print()

    if summary['total_rows'] == 0:
        print("  WARNING: No data imported yet!")
        print("  Use: python cli/qps_analyzer.py import <csv_file>")

    print()


def cmd_help(args):
    """Show help message."""
    print(__doc__)


def _get_db_path() -> Path:
    """Get the Cat-Scan database path."""
    return Path.home() / ".catscan" / "catscan.db"


def _get_thumbnails_dir() -> Path:
    """Get the thumbnails directory, creating if needed."""
    thumb_dir = Path.home() / ".catscan" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir


def _extract_video_url_from_vast(vast_xml: str) -> str | None:
    """Extract video URL from VAST XML MediaFile element."""
    if not vast_xml:
        return None
    # Match MediaFile URL, with or without CDATA
    patterns = [
        r'<MediaFile[^>]*><!\[CDATA\[(https?://[^\]]+)\]\]></MediaFile>',
        r'<MediaFile[^>]*>(https?://[^<]+)</MediaFile>',
    ]
    for pattern in patterns:
        match = re.search(pattern, vast_xml, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _generate_thumbnail_ffmpeg(video_url: str, output_path: Path, timeout: int = 30) -> bool:
    """Generate thumbnail from video URL using ffmpeg."""
    try:
        # ffmpeg command to extract first frame
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-ss", "1",  # Seek to 1 second (skip potential black frames)
            "-i", video_url,
            "-vframes", "1",  # Extract 1 frame
            "-vf", "scale='min(480,iw)':'-1'",  # Scale to max 480px width
            "-q:v", "2",  # High quality JPEG
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )

        return result.returncode == 0 and output_path.exists()
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def _update_thumbnail_in_db(db_path: Path, creative_id: str, thumbnail_path: Path) -> bool:
    """Update the creative's raw_data with local thumbnail path."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get current raw_data
        cursor.execute("SELECT raw_data FROM creatives WHERE id = ?", (creative_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            conn.close()
            return False

        raw_data = json.loads(row[0])

        # Add or update thumbnail URL in video section
        if "video" not in raw_data:
            raw_data["video"] = {}
        raw_data["video"]["localThumbnailPath"] = str(thumbnail_path)

        # Update the database
        cursor.execute(
            "UPDATE creatives SET raw_data = ? WHERE id = ?",
            (json.dumps(raw_data), creative_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def cmd_generate_thumbnails(args):
    """Generate thumbnails for video creatives using ffmpeg."""
    # Check ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not in PATH")
        print("Install with: sudo apt install ffmpeg")
        sys.exit(1)

    db_path = _get_db_path()
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    thumb_dir = _get_thumbnails_dir()
    limit = args.limit or 100
    force = args.force

    print("=" * 60)
    print("THUMBNAIL GENERATION")
    print("=" * 60)
    print(f"Database:    {db_path}")
    print(f"Output dir:  {thumb_dir}")
    print(f"Limit:       {limit}")
    print(f"Force:       {force}")
    print()

    # Query video creatives
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get video creatives with VAST XML
    cursor.execute("""
        SELECT id, json_extract(raw_data, '$.video.vastXml') as vast_xml,
               json_extract(raw_data, '$.video.localThumbnailPath') as local_thumb
        FROM creatives
        WHERE format = 'VIDEO'
          AND json_extract(raw_data, '$.video.vastXml') IS NOT NULL
        ORDER BY id DESC
        LIMIT ?
    """, (limit * 3,))  # Get more to account for filtering

    rows = cursor.fetchall()
    conn.close()

    # Filter to those needing thumbnails
    to_process = []
    for creative_id, vast_xml, local_thumb in rows:
        thumb_path = thumb_dir / f"{creative_id}.jpg"

        # Skip if thumbnail exists and not forcing
        if not force and (thumb_path.exists() or local_thumb):
            continue

        video_url = _extract_video_url_from_vast(vast_xml)
        if video_url:
            to_process.append((creative_id, video_url, thumb_path))

        if len(to_process) >= limit:
            break

    if not to_process:
        print("No video creatives need thumbnails.")
        print("Use --force to regenerate existing thumbnails.")
        return

    print(f"Processing {len(to_process)} videos...")
    print()

    success_count = 0
    fail_count = 0

    for i, (creative_id, video_url, thumb_path) in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {creative_id}...", end=" ", flush=True)

        if _generate_thumbnail_ffmpeg(video_url, thumb_path):
            if _update_thumbnail_in_db(db_path, creative_id, thumb_path):
                print(f"OK ({thumb_path.stat().st_size // 1024}KB)")
                success_count += 1
            else:
                print("OK (file only, DB update failed)")
                success_count += 1
        else:
            print("FAILED")
            fail_count += 1

    print()
    print("=" * 60)
    print(f"COMPLETE: {success_count} generated, {fail_count} failed")
    print("=" * 60)

    if success_count > 0:
        print()
        print("Thumbnails saved to:", thumb_dir)
        print("Restart the API server to see updated thumbnails.")


def main():
    parser = argparse.ArgumentParser(
        description="Cat-Scan QPS Optimization Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate ~/downloads/bigquery.csv Validate CSV before import
  %(prog)s import ~/downloads/bigquery.csv   Import CSV data
  %(prog)s coverage --days 7                 Size coverage report
  %(prog)s include-list                      Generate pretargeting sizes
  %(prog)s configs --days 7                  Config performance report
  %(prog)s fraud --days 14                   Fraud signals report
  %(prog)s full-report --days 7              Full optimization report
  %(prog)s summary                           Show data summary
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate CSV without importing")
    validate_parser.add_argument("file", help="Path to CSV file")
    validate_parser.set_defaults(func=cmd_validate)

    # Import command
    import_parser = subparsers.add_parser("import", help="Import BigQuery CSV file")
    import_parser.add_argument("file", help="Path to CSV file")
    import_parser.set_defaults(func=cmd_import)

    # Coverage command
    coverage_parser = subparsers.add_parser("coverage", help="Size coverage analysis")
    coverage_parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    coverage_parser.set_defaults(func=cmd_coverage)

    # Include list command
    include_parser = subparsers.add_parser("include-list", help="Generate pretargeting include list")
    include_parser.set_defaults(func=cmd_include_list)

    # Configs command
    configs_parser = subparsers.add_parser("configs", help="Config performance tracking")
    configs_parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    configs_parser.set_defaults(func=cmd_configs)

    # Fraud command
    fraud_parser = subparsers.add_parser("fraud", help="Fraud signal detection")
    fraud_parser.add_argument("--days", type=int, default=14, help="Days to analyze (default: 14)")
    fraud_parser.set_defaults(func=cmd_fraud)

    # Full report command
    full_parser = subparsers.add_parser("full-report", help="Generate full optimization report")
    full_parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    full_parser.set_defaults(func=cmd_full_report)

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show data summary")
    summary_parser.set_defaults(func=cmd_summary)

    # Help command
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.set_defaults(func=cmd_help)

    # Generate thumbnails command
    thumb_parser = subparsers.add_parser("generate-thumbnails", help="Generate video thumbnails using ffmpeg")
    thumb_parser.add_argument("--limit", type=int, default=100, help="Max videos to process (default: 100)")
    thumb_parser.add_argument("--force", action="store_true", help="Regenerate existing thumbnails")
    thumb_parser.set_defaults(func=cmd_generate_thumbnails)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
