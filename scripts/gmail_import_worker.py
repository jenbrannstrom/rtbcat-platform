#!/usr/bin/env python3
"""Detached Gmail import worker.

Runs Gmail import and refreshes home/config precompute after successful imports.
Designed to be launched from API and continue running independently.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime

from scripts.gmail_import import run_import
from services.config_precompute import refresh_config_breakdowns
from services.home_precompute import refresh_home_summaries


def _print(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detached Gmail import worker")
    parser.add_argument("--job-id", required=True, help="Job ID to track in status")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose importer output")
    parser.add_argument("--refresh-days", type=int, default=30, help="Precompute refresh window")
    parser.add_argument(
        "--import-trigger",
        choices=["gmail-auto", "gmail-manual"],
        default="gmail-manual",
        help="Source label for ingestion tracking",
    )
    args = parser.parse_args()

    _print(f"Starting Gmail import job {args.job_id}")
    result = run_import(
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

    try:
        _print(f"Refreshing home precompute (days={args.refresh_days})")
        asyncio.run(refresh_home_summaries(days=args.refresh_days))
        _print(f"Refreshing config precompute (days={args.refresh_days})")
        asyncio.run(refresh_config_breakdowns(days=args.refresh_days))
        _print("Worker finished successfully")
        return 0
    except Exception as exc:
        _print(f"Precompute refresh failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
