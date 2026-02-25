#!/usr/bin/env python3
"""
Resilient Gmail Import - Batch processing with checkpointing.

Features:
  - Checkpointing: Tracks processed message IDs, resumes on restart
  - Batch processing: Configurable batch size with delays
  - Background-safe: Designed for nohup/screen-less operation
  - Detailed logging: All output to timestamped log file

Usage:
  # On SG VM:
  cd /opt/catscan
  nohup python3 scripts/gmail_import_batch.py --batch-size 10 >> ~/.catscan/logs/gmail_batch.log 2>&1 &

  # Check progress:
  tail -f ~/.catscan/logs/gmail_batch.log
  cat ~/.catscan/gmail_batch_checkpoint.json

  # Resume after interruption (automatic - just run again):
  nohup python3 scripts/gmail_import_batch.py >> ~/.catscan/logs/gmail_batch.log 2>&1 &
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gmail_import import (
    get_gmail_service,
    find_report_emails,
    process_message,
    mark_as_read,
    import_to_catscan,
    archive_to_s3,
    detect_report_kind,
    record_import_run,
    run_pipeline_for_file,
    SEAT_ID_ALLOWLIST,
    CATSCAN_DIR,
    LOGS_DIR,
)

# Checkpoint configuration
CHECKPOINT_PATH = CATSCAN_DIR / "gmail_batch_checkpoint.json"
DEFAULT_BATCH_SIZE = 10
DEFAULT_DELAY_SECONDS = 2


def log(msg: str):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def load_checkpoint() -> Dict[str, Any]:
    """Load checkpoint from disk."""
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "processed_ids": [],
        "failed_ids": [],
        "started_at": None,
        "last_update": None,
        "total_found": 0,
        "total_processed": 0,
        "total_imported": 0,
        "total_errors": 0,
    }


def save_checkpoint(checkpoint: Dict[str, Any]):
    """Save checkpoint to disk."""
    checkpoint["last_update"] = datetime.now().isoformat()
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, indent=2))


def get_processed_ids(checkpoint: Dict[str, Any]) -> Set[str]:
    """Get set of already processed message IDs."""
    return set(checkpoint.get("processed_ids", []) + checkpoint.get("failed_ids", []))


def run_batch_import(
    batch_size: int = DEFAULT_BATCH_SIZE,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    max_emails: Optional[int] = None,
    reset: bool = False,
) -> Dict[str, Any]:
    """
    Run Gmail import with checkpointing and batching.

    Args:
        batch_size: Number of emails to process before saving checkpoint
        delay_seconds: Delay between emails (rate limiting)
        max_emails: Maximum emails to process (None = all)
        reset: If True, clear checkpoint and start fresh
    """
    log("=" * 60)
    log("Gmail Batch Import - Starting")
    log("=" * 60)

    # Load or reset checkpoint
    if reset and CHECKPOINT_PATH.exists():
        log("Resetting checkpoint...")
        CHECKPOINT_PATH.unlink()

    checkpoint = load_checkpoint()
    processed_ids = get_processed_ids(checkpoint)

    if checkpoint.get("started_at") is None:
        checkpoint["started_at"] = datetime.now().isoformat()

    log(f"Checkpoint: {len(processed_ids)} already processed")

    # Authenticate
    try:
        service, creds = get_gmail_service()
        access_token = creds.token
        log("Gmail authentication successful")
    except Exception as e:
        log(f"ERROR: Gmail authentication failed: {e}")
        return {"success": False, "error": str(e)}

    # Find all report emails
    log("Fetching report emails...")
    messages = find_report_emails(service)
    total_found = len(messages)
    checkpoint["total_found"] = total_found
    log(f"Found {total_found} total report emails")

    # Filter out already processed
    pending_messages = [m for m in messages if m["id"] not in processed_ids]
    log(f"Pending: {len(pending_messages)} emails to process")

    if not pending_messages:
        log("No new emails to process. Done!")
        save_checkpoint(checkpoint)
        return {"success": True, "processed": 0, "imported": 0}

    # Apply max_emails limit
    if max_emails and len(pending_messages) > max_emails:
        pending_messages = pending_messages[:max_emails]
        log(f"Limited to {max_emails} emails")

    # Process in batches
    batch_count = 0
    session_processed = 0
    session_imported = 0
    session_errors = 0

    for i, msg in enumerate(pending_messages, 1):
        message_id = msg["id"]
        log(f"[{i}/{len(pending_messages)}] Processing: {message_id}")

        try:
            downloaded_files, seat_id, subject, skipped = process_message(
                service,
                message_id,
                access_token,
                SEAT_ID_ALLOWLIST or None,
            )

            if skipped:
                log(f"  Skipped: seat_id={seat_id or 'unknown'}")
                checkpoint["processed_ids"].append(message_id)
                mark_as_read(service, message_id)
                session_processed += 1

            elif not downloaded_files:
                log("  No CSV found")
                checkpoint["processed_ids"].append(message_id)
                mark_as_read(service, message_id)  # Prevent reprocessing
                session_processed += 1

            else:
                for filepath in downloaded_files:
                    # Archive to S3
                    archive_to_s3(filepath, verbose=False)

                    # Import to database
                    imp = import_to_catscan(filepath)
                    report_kind = imp.report_type if imp.report_type else detect_report_kind(filepath.name)

                    record_import_run(
                        seat_id=seat_id,
                        report_kind=report_kind,
                        filename=filepath.name,
                        success=imp.success,
                        rows_imported=imp.rows_imported,
                        rows_duplicate=imp.rows_duplicate,
                        rows_read=imp.rows_read,
                        file_size_bytes=imp.file_size_bytes,
                        batch_id=imp.batch_id,
                        date_range_start=imp.date_range_start,
                        date_range_end=imp.date_range_end,
                        columns_found=imp.columns_found,
                        error=imp.error,
                    )

                    if imp.success:
                        log(f"  Imported: {imp.rows_imported} rows ({report_kind})")
                        session_imported += 1
                        # Run pipeline
                        run_pipeline_for_file(filepath, seat_id, verbose=False)
                    else:
                        log(f"  Import failed: {imp.error}")
                        session_errors += 1

                mark_as_read(service, message_id)
                checkpoint["processed_ids"].append(message_id)
                session_processed += 1

        except Exception as e:
            log(f"  ERROR: {e}")
            checkpoint["failed_ids"].append(message_id)
            session_errors += 1

        # Update checkpoint every batch
        batch_count += 1
        if batch_count >= batch_size:
            checkpoint["total_processed"] = len(checkpoint["processed_ids"])
            checkpoint["total_imported"] += session_imported
            checkpoint["total_errors"] += session_errors
            save_checkpoint(checkpoint)
            log(f"  Checkpoint saved ({session_processed} processed this session)")
            batch_count = 0
            # Reset session counters after checkpoint to avoid double-counting
            session_imported = 0
            session_errors = 0

        # Rate limiting delay
        if delay_seconds > 0 and i < len(pending_messages):
            time.sleep(delay_seconds)

    # Final checkpoint save (only adds remaining unsaved counts)
    checkpoint["total_processed"] = len(checkpoint["processed_ids"])
    checkpoint["total_imported"] += session_imported
    checkpoint["total_errors"] += session_errors
    checkpoint["completed_at"] = datetime.now().isoformat()
    save_checkpoint(checkpoint)

    log("=" * 60)
    log(f"Batch import complete!")
    log(f"  Processed this session: {session_processed}")
    log(f"  Imported this session: {session_imported}")
    log(f"  Errors this session: {session_errors}")
    log(f"  Total processed (all sessions): {checkpoint['total_processed']}")
    log("=" * 60)

    return {
        "success": True,
        "processed": session_processed,
        "imported": session_imported,
        "errors": session_errors,
    }


def show_status():
    """Show current checkpoint status."""
    checkpoint = load_checkpoint()
    print(json.dumps(checkpoint, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Resilient Gmail import with checkpointing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full import (resumes from checkpoint):
  python3 scripts/gmail_import_batch.py

  # Run in background on VM:
  nohup python3 scripts/gmail_import_batch.py >> ~/.catscan/logs/gmail_batch.log 2>&1 &

  # Process max 50 emails with larger batches:
  python3 scripts/gmail_import_batch.py --max-emails 50 --batch-size 20

  # Reset and start fresh:
  python3 scripts/gmail_import_batch.py --reset

  # Check progress:
  python3 scripts/gmail_import_batch.py --status
""",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Save checkpoint every N emails (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay between emails in seconds (default: {DEFAULT_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--max-emails",
        type=int,
        default=None,
        help="Maximum emails to process (default: all)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear checkpoint and start fresh",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show checkpoint status and exit",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Ensure log directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    result = run_batch_import(
        batch_size=args.batch_size,
        delay_seconds=args.delay,
        max_emails=args.max_emails,
        reset=args.reset,
    )

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
