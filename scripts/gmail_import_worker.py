#!/usr/bin/env python3
"""Detached Gmail import worker.

Runs Gmail import and refreshes serving-side caches after successful imports.
Designed to be launched from API and continue running independently.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime


def _print(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] {msg}", flush=True)


def _run_import(*, verbose: bool, job_id: str, import_trigger: str) -> dict:
    from scripts.gmail_import import run_import

    return run_import(
        verbose=verbose,
        job_id=job_id,
        import_trigger=import_trigger,
    )


def _enqueue_refresh(*, start_date: str, end_date: str, job_id: str) -> dict:
    """Queue the post-import refresh for the API's precompute worker.

    Running the multi-hour refresh chain inline here competed with scheduled
    refreshes for database capacity; the durable queue serializes them.
    """
    from services.precompute_queue import enqueue_precompute_job

    return asyncio.run(
        enqueue_precompute_job(
            source="gmail-import",
            start_date=start_date,
            end_date=end_date,
            dedupe_key=f"gmail-import:{job_id}",
            include_legacy_performance=True,
            run_validation=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Detached Gmail import worker")
    parser.add_argument("--job-id", required=True, help="Job ID to track in status")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose importer output")
    parser.add_argument(
        "--refresh-days",
        type=int,
        default=2,
        help="Fallback precompute window when imported file dates are unavailable",
    )
    parser.add_argument(
        "--import-trigger",
        choices=["gmail-auto", "gmail-manual"],
        default="gmail-manual",
        help="Source label for ingestion tracking",
    )
    args = parser.parse_args()

    _print(f"Starting Gmail import job {args.job_id}")
    result = _run_import(
        verbose=not args.quiet,
        job_id=args.job_id,
        import_trigger=args.import_trigger,
    )
    _print(f"Import result: {json.dumps(result, default=str)}")

    if not result.get("success"):
        _print("Import failed, skipping precompute refresh")
        return 1
    if int(result.get("files_imported", 0)) <= 0:
        _print("No files imported, skipping precompute refresh")
        return 0
    if int(result.get("duplicate_downstream_skip_count", 0)) >= int(
        result.get("files_imported", 0)
    ):
        _print("All imported files were exact duplicates, skipping precompute refresh")
        return 0

    try:
        start_date = result.get("imported_date_start")
        end_date = result.get("imported_date_end")
        if not start_date or not end_date:
            from services.precompute_utils import normalize_refresh_dates, refresh_window

            start_date, end_date = refresh_window(
                normalize_refresh_dates(days=args.refresh_days)
            )
        _print(f"Enqueueing precompute refresh ({start_date} to {end_date})")
        enqueue_result = _enqueue_refresh(
            start_date=start_date, end_date=end_date, job_id=args.job_id
        )
        _print(
            "Refresh queued as precompute job "
            f"{enqueue_result['job_id']} (deduplicated={enqueue_result['deduplicated']})"
        )
        _print("Worker finished successfully")
        return 0
    except Exception as exc:
        _print(f"Precompute refresh enqueue failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
