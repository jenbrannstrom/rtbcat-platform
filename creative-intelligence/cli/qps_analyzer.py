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

# Troubleshooting imports (lazy loaded to avoid auth issues when not needed)
def _get_troubleshooting_client():
    """Lazy load troubleshooting client to avoid auth issues on import."""
    from collectors.troubleshooting.client import TroubleshootingClient
    return TroubleshootingClient()


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


def _classify_ffmpeg_error(returncode: int, stderr: str, video_url: str, timed_out: bool = False) -> str:
    """Classify the ffmpeg error into a user-friendly reason.

    Returns one of: 'url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format', 'unknown'
    """
    if timed_out:
        return 'timeout'

    stderr_lower = stderr.lower() if stderr else ''

    # URL expiration errors
    if 'server returned 403' in stderr_lower or 'server returned 404' in stderr_lower:
        return 'url_expired'
    if 'server returned 410' in stderr_lower:
        return 'url_expired'
    if '403 forbidden' in stderr_lower or '404 not found' in stderr_lower:
        return 'url_expired'

    # Network errors
    if 'connection refused' in stderr_lower or 'network is unreachable' in stderr_lower:
        return 'network_error'
    if 'could not open' in stderr_lower and 'http' in stderr_lower:
        return 'network_error'
    if 'connection timed out' in stderr_lower:
        return 'network_error'

    # Format errors
    if 'invalid data found' in stderr_lower or 'does not contain' in stderr_lower:
        return 'invalid_format'
    if 'unsupported codec' in stderr_lower or 'decoder not found' in stderr_lower:
        return 'invalid_format'

    # Timeout (signal 9)
    if returncode == -9:
        return 'timeout'

    return 'unknown'


def _generate_thumbnail_ffmpeg(video_url: str, output_path: Path, timeout: int = 30) -> dict:
    """Generate thumbnail from video URL using ffmpeg.

    Returns:
        dict with keys: success (bool), error_reason (str|None), stderr (str|None)
    """
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

        if result.returncode == 0 and output_path.exists():
            return {'success': True, 'error_reason': None, 'stderr': None}
        else:
            error_reason = _classify_ffmpeg_error(result.returncode, result.stderr, video_url)
            return {'success': False, 'error_reason': error_reason, 'stderr': result.stderr}

    except subprocess.TimeoutExpired as e:
        return {'success': False, 'error_reason': 'timeout', 'stderr': str(e)}
    except Exception as e:
        return {'success': False, 'error_reason': 'unknown', 'stderr': str(e)}


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


def _record_thumbnail_status(db_path: Path, creative_id: str, status: str,
                             error_reason: str | None = None, video_url: str | None = None) -> bool:
    """Record thumbnail generation status in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = excluded.status,
                error_reason = excluded.error_reason,
                video_url = excluded.video_url,
                attempted_at = CURRENT_TIMESTAMP
        """, (creative_id, status, error_reason, video_url))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Warning: Failed to record status: {e}")
        return False


def _get_videos_needing_thumbnails(db_path: Path, limit: int, force: bool) -> list:
    """Get video creatives that need thumbnail generation.

    Args:
        db_path: Path to database
        limit: Maximum number to return
        force: If True, include failed status for retry

    Returns:
        List of (creative_id, vast_xml, video_url) tuples
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if force:
        # Retry failed ones, skip successful
        query = """
            SELECT c.id,
                   json_extract(c.raw_data, '$.video.vastXml') as vast_xml,
                   json_extract(c.raw_data, '$.video.videoUrl') as video_url
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND (ts.status IS NULL OR ts.status = 'failed')
            ORDER BY c.id DESC
            LIMIT ?
        """
    else:
        # Skip any that already have a status
        query = """
            SELECT c.id,
                   json_extract(c.raw_data, '$.video.vastXml') as vast_xml,
                   json_extract(c.raw_data, '$.video.videoUrl') as video_url
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND ts.status IS NULL
            ORDER BY c.id DESC
            LIMIT ?
        """

    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def _get_thumbnail_summary(db_path: Path) -> dict:
    """Get summary statistics for thumbnail generation."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Total video creatives
    cursor.execute("SELECT COUNT(*) FROM creatives WHERE format = 'VIDEO'")
    total_videos = cursor.fetchone()[0]

    # Count by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM thumbnail_status
        GROUP BY status
    """)
    status_counts = {row[0]: row[1] for row in cursor.fetchall()}

    # Count by error_reason (for failed)
    cursor.execute("""
        SELECT error_reason, COUNT(*) as count
        FROM thumbnail_status
        WHERE status = 'failed'
        GROUP BY error_reason
    """)
    error_counts = {row[0] or 'unknown': row[1] for row in cursor.fetchall()}

    conn.close()

    return {
        'total_videos': total_videos,
        'success': status_counts.get('success', 0),
        'failed': status_counts.get('failed', 0),
        'unprocessed': total_videos - sum(status_counts.values()),
        'error_counts': error_counts,
    }


def cmd_generate_thumbnails(args):
    """Generate thumbnails for video creatives using ffmpeg.

    Records status in thumbnail_status table:
    - 'success': Thumbnail generated successfully
    - 'failed': Generation failed (with error_reason)

    Error reasons:
    - 'no_url': No video URL found in creative data
    - 'url_expired': URL returned 403/404/410
    - 'timeout': ffmpeg timed out
    - 'network_error': Connection failed
    - 'invalid_format': ffmpeg couldn't decode the video
    """
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
    timeout = getattr(args, 'timeout', 30) or 30

    # Show current status before starting
    summary = _get_thumbnail_summary(db_path)

    print("=" * 60)
    print("THUMBNAIL GENERATION (Phase 10.4)")
    print("=" * 60)
    print(f"Database:    {db_path}")
    print(f"Output dir:  {thumb_dir}")
    print(f"Limit:       {limit}")
    print(f"Timeout:     {timeout}s")
    print(f"Force retry: {force}")
    print()
    print("Current Status:")
    print(f"  Total videos:  {summary['total_videos']}")
    print(f"  Success:       {summary['success']}")
    print(f"  Failed:        {summary['failed']}")
    print(f"  Unprocessed:   {summary['unprocessed']}")
    print()

    # Get videos needing thumbnails using new status-aware query
    rows = _get_videos_needing_thumbnails(db_path, limit, force)

    # Build list to process
    to_process = []
    no_url_count = 0

    for creative_id, vast_xml, direct_video_url in rows:
        thumb_path = thumb_dir / f"{creative_id}.jpg"

        # Try to get video URL from VAST or direct URL
        video_url = None
        if vast_xml:
            video_url = _extract_video_url_from_vast(vast_xml)
        if not video_url and direct_video_url:
            video_url = direct_video_url

        if video_url:
            to_process.append((creative_id, video_url, thumb_path))
        else:
            # Record no_url failure immediately
            _record_thumbnail_status(db_path, creative_id, 'failed', 'no_url', None)
            no_url_count += 1

        if len(to_process) >= limit:
            break

    if no_url_count > 0:
        print(f"Skipped {no_url_count} creatives with no video URL (recorded as failed)")
        print()

    if not to_process:
        print("No video creatives need thumbnails.")
        if not force:
            print("Use --force to retry failed thumbnails.")
        return

    print(f"Processing {len(to_process)} videos...")
    print()

    # Track results by error reason
    success_count = 0
    errors_by_reason = {}

    for i, (creative_id, video_url, thumb_path) in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {creative_id}...", end=" ", flush=True)

        result = _generate_thumbnail_ffmpeg(video_url, thumb_path, timeout)

        if result['success']:
            # Update raw_data with local path
            _update_thumbnail_in_db(db_path, creative_id, thumb_path)
            # Record success status
            _record_thumbnail_status(db_path, creative_id, 'success', None, video_url)
            file_size = thumb_path.stat().st_size // 1024 if thumb_path.exists() else 0
            print(f"OK ({file_size}KB)")
            success_count += 1
        else:
            error_reason = result['error_reason']
            # Record failure status with reason
            _record_thumbnail_status(db_path, creative_id, 'failed', error_reason, video_url)
            errors_by_reason[error_reason] = errors_by_reason.get(error_reason, 0) + 1
            print(f"FAILED ({error_reason})")

    # Final summary
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"New successes: {success_count}")

    if errors_by_reason:
        print(f"New failures:  {sum(errors_by_reason.values())}")
        print()
        print("Failures by reason:")
        for reason, count in sorted(errors_by_reason.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    # Show updated totals
    print()
    updated_summary = _get_thumbnail_summary(db_path)
    coverage_pct = (updated_summary['success'] / updated_summary['total_videos'] * 100
                   if updated_summary['total_videos'] > 0 else 0)
    print(f"Total coverage: {updated_summary['success']} of {updated_summary['total_videos']} "
          f"videos have thumbnails ({coverage_pct:.1f}%)")

    if updated_summary['error_counts']:
        print()
        print("All failures by reason:")
        for reason, count in sorted(updated_summary['error_counts'].items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    print("=" * 60)

    if success_count > 0:
        print()
        print("Thumbnails saved to:", thumb_dir)
        print("Restart the API server to see updated thumbnails.")


def cmd_troubleshoot_collect(args):
    """Collect troubleshooting data from RTB Troubleshooting API."""
    days = args.days or 7
    environment = args.environment

    print("=" * 60)
    print("RTB TROUBLESHOOTING DATA COLLECTION")
    print("=" * 60)
    print(f"Days: {days}")
    print(f"Environment: {environment or 'all'}")
    print()

    try:
        client = _get_troubleshooting_client()
        print("Collecting metrics from Ad Exchange Buyer II API...")
        print()

        data = client.collect_all_metrics(days=days, environment=environment)

        # Display results
        print("=" * 60)
        print("COLLECTION RESULTS")
        print("=" * 60)

        if "filtered_bid_requests" in data:
            fbr = data["filtered_bid_requests"]
            print(f"\nFiltered Bid Requests: {len(fbr)} reasons")
            for item in fbr[:5]:
                print(f"  - {item.get('status', 'unknown')}: {item.get('filtered_bid_request_count', 0):,} requests")
            if len(fbr) > 5:
                print(f"  ... and {len(fbr) - 5} more")

        if "filtered_bids" in data:
            fb = data["filtered_bids"]
            print(f"\nFiltered Bids: {len(fb)} reasons")
            for item in fb[:5]:
                print(f"  - {item.get('status', 'unknown')}: {item.get('bid_count', 0):,} bids")
            if len(fb) > 5:
                print(f"  ... and {len(fb) - 5} more")

        if "bid_metrics" in data:
            bm = data["bid_metrics"]
            print(f"\nBid Metrics: {len(bm)} rows")

        if "callout_status" in data:
            cs = data["callout_status"]
            print(f"\nCallout Status: {len(cs)} statuses")

        if "impression_metrics" in data:
            im = data["impression_metrics"]
            print(f"\nImpression Metrics: {len(im)} rows")

        if "loser_bids" in data:
            lb = data["loser_bids"]
            print(f"\nLoser Bids: {len(lb)} reasons")

        print()
        print("=" * 60)
        print("Collection complete. Use 'troubleshoot report' to analyze.")
        print("=" * 60)

    except Exception as e:
        print(f"Error collecting troubleshooting data: {e}")
        sys.exit(1)


def cmd_troubleshoot_report(args):
    """Generate a troubleshooting report from collected data."""
    days = args.days or 7

    print("=" * 60)
    print("RTB TROUBLESHOOTING REPORT")
    print("=" * 60)
    print(f"Analysis Period: {days} days")
    print()

    try:
        client = _get_troubleshooting_client()
        data = client.collect_all_metrics(days=days)

        # Analyze filtered bids
        if "filtered_bids" in data and data["filtered_bids"]:
            print("-" * 60)
            print("FILTERED BIDS ANALYSIS")
            print("-" * 60)
            print()

            total_filtered = sum(item.get("bid_count", 0) for item in data["filtered_bids"])
            print(f"Total filtered bids: {total_filtered:,}")
            print()

            # Top reasons
            sorted_reasons = sorted(data["filtered_bids"],
                                   key=lambda x: x.get("bid_count", 0), reverse=True)
            print("Top 10 filter reasons:")
            for i, item in enumerate(sorted_reasons[:10], 1):
                status = item.get("status", "unknown")
                count = item.get("bid_count", 0)
                pct = (count / total_filtered * 100) if total_filtered > 0 else 0
                print(f"  {i:2}. {status}: {count:,} ({pct:.1f}%)")

            print()

        # Analyze callout status
        if "callout_status" in data and data["callout_status"]:
            print("-" * 60)
            print("CALLOUT STATUS ANALYSIS")
            print("-" * 60)
            print()

            for item in data["callout_status"]:
                status = item.get("status", "unknown")
                imp_count = item.get("impression_count", 0)
                print(f"  {status}: {imp_count:,} impressions")

            print()

        # Analyze impression metrics
        if "impression_metrics" in data and data["impression_metrics"]:
            print("-" * 60)
            print("IMPRESSION METRICS")
            print("-" * 60)
            print()

            for item in data["impression_metrics"]:
                print(f"  Impressions available: {item.get('available_impressions', 0):,}")
                print(f"  Impressions bid on: {item.get('bid_impressions', 0):,}")
                print(f"  Successful bids: {item.get('successful_http_requests', 0):,}")

            print()

        # Summary recommendations
        print("-" * 60)
        print("RECOMMENDATIONS")
        print("-" * 60)
        print()

        if "filtered_bids" in data and data["filtered_bids"]:
            # Look for creative-related filters
            creative_filters = [f for f in data["filtered_bids"]
                              if "creative" in f.get("status", "").lower()]
            if creative_filters:
                print("Creative Issues Found:")
                for f in creative_filters[:3]:
                    print(f"  - {f.get('status')}: {f.get('bid_count', 0):,} bids filtered")
                print()

            # Look for pretargeting filters
            pt_filters = [f for f in data["filtered_bids"]
                        if "pretargeting" in f.get("status", "").lower()]
            if pt_filters:
                print("Pretargeting Issues Found:")
                for f in pt_filters[:3]:
                    print(f"  - {f.get('status')}: {f.get('bid_count', 0):,} bids filtered")
                print()

        print("=" * 60)
        print("END OF TROUBLESHOOTING REPORT")
        print("=" * 60)

    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)


def cmd_troubleshoot_status(args):
    """Show status of troubleshooting data collection."""
    db_path = _get_db_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 60)
    print("TROUBLESHOOTING DATA STATUS")
    print("=" * 60)
    print()

    # Check if tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('troubleshooting_data', 'troubleshooting_collections')
    """)
    tables = [row[0] for row in cursor.fetchall()]

    if "troubleshooting_data" not in tables:
        print("Troubleshooting tables not found.")
        print("Run: python scripts/reset_database.py to create them.")
        conn.close()
        return

    # Get collection history
    cursor.execute("""
        SELECT collection_date, status, filtered_bids_count, bid_metrics_count, collected_at
        FROM troubleshooting_collections
        ORDER BY collected_at DESC
        LIMIT 10
    """)
    collections = cursor.fetchall()

    if collections:
        print("Recent Collections:")
        print()
        for row in collections:
            date, status, fb_count, bm_count, collected_at = row
            print(f"  {date}: {status} - Filtered: {fb_count or 0}, Metrics: {bm_count or 0}")
            print(f"          Collected: {collected_at}")
        print()
    else:
        print("No collections recorded yet.")
        print("Run: python cli/qps_analyzer.py troubleshoot collect")
        print()

    # Get data summary
    cursor.execute("""
        SELECT metric_type, COUNT(*) as count, MIN(collection_date), MAX(collection_date)
        FROM troubleshooting_data
        GROUP BY metric_type
    """)
    summaries = cursor.fetchall()

    if summaries:
        print("Data Summary:")
        print()
        for metric_type, count, min_date, max_date in summaries:
            print(f"  {metric_type}: {count} rows ({min_date} to {max_date})")
    else:
        print("No troubleshooting data stored yet.")

    conn.close()
    print()
    print("=" * 60)


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
    thumb_parser.add_argument("--force", action="store_true", help="Retry failed thumbnails (skips successful)")
    thumb_parser.add_argument("--timeout", type=int, default=30, help="Timeout per video in seconds (default: 30)")
    thumb_parser.set_defaults(func=cmd_generate_thumbnails)

    # Troubleshoot command group
    troubleshoot_parser = subparsers.add_parser("troubleshoot", help="RTB Troubleshooting API commands")
    troubleshoot_subparsers = troubleshoot_parser.add_subparsers(dest="troubleshoot_command", help="Troubleshoot action")

    # troubleshoot collect
    ts_collect = troubleshoot_subparsers.add_parser("collect", help="Collect troubleshooting data from API")
    ts_collect.add_argument("--days", type=int, default=7, help="Days of data to collect (default: 7)")
    ts_collect.add_argument("--environment", type=str, choices=["APP", "WEB"], help="Filter by environment")
    ts_collect.set_defaults(func=cmd_troubleshoot_collect)

    # troubleshoot report
    ts_report = troubleshoot_subparsers.add_parser("report", help="Generate troubleshooting report")
    ts_report.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    ts_report.set_defaults(func=cmd_troubleshoot_report)

    # troubleshoot status
    ts_status = troubleshoot_subparsers.add_parser("status", help="Show troubleshooting data status")
    ts_status.set_defaults(func=cmd_troubleshoot_status)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Handle troubleshoot subcommands
    if args.command == "troubleshoot":
        if not hasattr(args, 'troubleshoot_command') or args.troubleshoot_command is None:
            troubleshoot_parser.print_help()
            sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
