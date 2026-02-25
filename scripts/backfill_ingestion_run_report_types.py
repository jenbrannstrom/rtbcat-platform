#!/usr/bin/env python3
"""Reclassify historical ingestion_runs.report_type values for import tracking.

Why this exists:
- Older Gmail imports (especially GCS-downloaded reports) were recorded with generic
  local filenames like ``catscan-report-<seat>-<timestamp>.csv``.
- report_type in ingestion_runs was inferred from the local filename, which produced
  many ``unknown`` values and caused the Import matrix UI to underreport imported CSVs.
- A later patch also briefly stored unified importer parser types directly
  (e.g. ``performance_detail``, ``rtb_bidstream_publisher``), which the Import matrix
  does not canonicalize.

This script backfills ingestion_runs.report_type into canonical values used by the UI:
  - catscan-quality
  - catscan-bidsinauction
  - catscan-pipeline-geo
  - catscan-pipeline
  - catscan-bid-filtering

It uses:
1) filename (best signal when canonical filename preserved)
2) current parser-type values
3) import_history.columns_found (CSV header names) via nearest-row join

Usage:
  python scripts/backfill_ingestion_run_report_types.py --dry-run
  python scripts/backfill_ingestion_run_report_types.py --apply --since 2026-02-01
  python scripts/backfill_ingestion_run_report_types.py --apply --buyer-id 299038253
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Optional

import psycopg
from psycopg.rows import dict_row


CANONICAL_TARGETS = {
    "catscan-quality",
    "catscan-bidsinauction",
    "catscan-pipeline-geo",
    "catscan-pipeline",
    "catscan-bid-filtering",
}

PARSER_TYPES_TO_RECLASSIFY = {
    "performance_detail",
    "rtb_bidstream_geo",
    "rtb_bidstream_publisher",
    "bid_filtering",
    # quality_signals intentionally excluded from UI 5-type matrix; keep as-is.
}


def get_dsn() -> str:
    dsn = (
        os.getenv("POSTGRES_SERVING_DSN")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("DATABASE_URL")
        or ""
    )
    if not dsn:
        raise RuntimeError("POSTGRES_SERVING_DSN, POSTGRES_DSN, or DATABASE_URL must be set")
    return dsn


def detect_report_kind_from_filename(filename: Optional[str]) -> str:
    if not filename:
        return "unknown"
    name = filename.lower()
    if "catscan-bid-filtering" in name:
        return "catscan-bid-filtering"
    if "catscan-bidsinauction" in name:
        return "catscan-bidsinauction"
    if "catscan-pipeline-geo" in name:
        return "catscan-pipeline-geo"
    # Keep geo check first; this is publisher-level pipeline.
    if "catscan-pipeline" in name or "catscan-rtb-pipeline" in name:
        return "catscan-pipeline"
    if "catscan-quality" in name:
        return "catscan-quality"
    return "unknown"


def parse_columns(columns_found: Optional[str]) -> set[str]:
    return {
        col.strip().lower()
        for col in (columns_found or "").split(",")
        if col and col.strip()
    }


def classify_from_parser_type(
    parser_type: Optional[str],
    *,
    columns_found: Optional[str] = None,
) -> str:
    rt = (parser_type or "").strip().lower()
    cols = parse_columns(columns_found)

    if rt == "rtb_bidstream_geo":
        return "catscan-pipeline-geo"
    if rt == "rtb_bidstream_publisher":
        return "catscan-pipeline"
    if rt == "bid_filtering":
        return "catscan-bid-filtering"
    if rt == "performance_detail":
        # catscan-quality carries billing_id / Active View metrics.
        if any("billing id" in c for c in cols) or any("active view" in c for c in cols):
            return "catscan-quality"
        # catscan-bidsinauction carries bid-pipeline metrics.
        if any(c in cols for c in ("bids in auction", "auctions won", "bids")):
            return "catscan-bidsinauction"
        # If columns are missing, leave unresolved rather than guessing.
        return "unknown"
    # Preserve anything else by default (script only updates canonical targets).
    return "unknown"


def canonicalize_report_type(
    *,
    current_report_type: Optional[str],
    filename: Optional[str],
    columns_found: Optional[str],
) -> str:
    # If filename still has the canonical token, that is the best signal.
    by_filename = detect_report_kind_from_filename(filename)
    if by_filename != "unknown":
        return by_filename

    # Fallback to parser-type conversion + columns heuristics.
    by_parser = classify_from_parser_type(
        current_report_type,
        columns_found=columns_found,
    )
    return by_parser


@dataclass
class Candidate:
    run_id: str
    current_report_type: Optional[str]
    filename: Optional[str]
    account_id: Optional[str]
    import_trigger: Optional[str]
    row_count: int
    event_ts: str
    columns_found: Optional[str]
    imported_at: Optional[str]
    new_report_type: str


def build_candidate_query(limit: Optional[int]) -> str:
    limit_sql = f"LIMIT {int(limit)}" if limit is not None else ""
    return f"""
    SELECT
        ir.run_id,
        ir.report_type AS current_report_type,
        ir.filename,
        COALESCE(NULLIF(ir.buyer_id, ''), NULLIF(ir.bidder_id, '')) AS account_id,
        COALESCE(NULLIF(ir.import_trigger, ''), 'manual') AS import_trigger,
        ir.row_count,
        COALESCE(ir.finished_at, ir.started_at) AS event_ts,
        ih.columns_found,
        ih.imported_at
    FROM ingestion_runs ir
    LEFT JOIN LATERAL (
        SELECT ih.columns_found, ih.imported_at
        FROM import_history ih
        WHERE COALESCE(NULLIF(ih.buyer_id, ''), NULLIF(ih.bidder_id, ''))
              = COALESCE(NULLIF(ir.buyer_id, ''), NULLIF(ir.bidder_id, ''))
          AND COALESCE(NULLIF(ih.import_trigger, ''), 'manual')
              = COALESCE(NULLIF(ir.import_trigger, ''), 'manual')
          AND (
                (ir.filename IS NOT NULL AND ih.filename = ir.filename)
                OR (ir.filename IS NULL AND ih.filename IS NULL)
              )
          AND ABS(EXTRACT(EPOCH FROM (ih.imported_at - COALESCE(ir.finished_at, ir.started_at)))) <= 900
        ORDER BY
          ABS(EXTRACT(EPOCH FROM (ih.imported_at - COALESCE(ir.finished_at, ir.started_at)))) ASC,
          ih.imported_at DESC
        LIMIT 1
    ) ih ON TRUE
    WHERE ir.source_type = 'csv'
      AND (
            ir.report_type IS NULL
            OR ir.report_type = 'unknown'
            OR ir.report_type = ANY(%(parser_types)s)
          )
      AND (%(buyer_id)s IS NULL OR COALESCE(NULLIF(ir.buyer_id, ''), NULLIF(ir.bidder_id, '')) = %(buyer_id)s)
      AND (%(since)s IS NULL OR COALESCE(ir.finished_at, ir.started_at) >= %(since)s::timestamptz)
    ORDER BY COALESCE(ir.finished_at, ir.started_at) DESC
    {limit_sql}
    """


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill ingestion_runs.report_type classifications")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run output")
    parser.add_argument("--buyer-id", help="Limit to one buyer/account ID")
    parser.add_argument("--since", help="Only inspect rows on/after this timestamp/date (e.g. 2026-02-01)")
    parser.add_argument("--limit", type=int, help="Limit candidate rows scanned (for debugging)")
    parser.add_argument("--sample", type=int, default=20, help="Sample rows to print in dry-run")
    args = parser.parse_args()

    dry_run = not args.apply or args.dry_run

    dsn = get_dsn()
    conn = psycopg.connect(dsn, row_factory=dict_row)
    updated = 0
    skipped_unresolved = 0
    skipped_already_canonical = 0
    samples: list[Candidate] = []

    try:
        with conn:
            rows = conn.execute(
                build_candidate_query(args.limit),
                {
                    "parser_types": list(PARSER_TYPES_TO_RECLASSIFY),
                    "buyer_id": args.buyer_id,
                    "since": args.since,
                },
            ).fetchall()

            print(f"Scanned candidates: {len(rows)}")
            print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")

            for row in rows:
                current_report_type = row.get("current_report_type")
                filename = row.get("filename")
                columns_found = row.get("columns_found")
                new_report_type = canonicalize_report_type(
                    current_report_type=current_report_type,
                    filename=filename,
                    columns_found=columns_found,
                )

                if new_report_type not in CANONICAL_TARGETS:
                    skipped_unresolved += 1
                    continue

                if current_report_type == new_report_type:
                    skipped_already_canonical += 1
                    continue

                candidate = Candidate(
                    run_id=str(row["run_id"]),
                    current_report_type=current_report_type,
                    filename=filename,
                    account_id=row.get("account_id"),
                    import_trigger=row.get("import_trigger"),
                    row_count=int(row.get("row_count") or 0),
                    event_ts=str(row.get("event_ts")),
                    columns_found=columns_found,
                    imported_at=str(row.get("imported_at")) if row.get("imported_at") else None,
                    new_report_type=new_report_type,
                )

                if len(samples) < max(args.sample, 0):
                    samples.append(candidate)

                if not dry_run:
                    conn.execute(
                        """
                        UPDATE ingestion_runs
                        SET report_type = %s
                        WHERE run_id = %s
                        """,
                        (new_report_type, candidate.run_id),
                    )
                updated += 1

    finally:
        conn.close()

    print("")
    print("Summary")
    print("-------")
    print(f"Would update / Updated: {updated}")
    print(f"Skipped unresolved: {skipped_unresolved}")
    print(f"Skipped already canonical: {skipped_already_canonical}")

    if samples:
        print("")
        print("Sample changes")
        print("--------------")
        for c in samples:
            print(
                f"{c.run_id} account={c.account_id} trigger={c.import_trigger} "
                f"{c.current_report_type!r} -> {c.new_report_type!r} "
                f"row_count={c.row_count} file={c.filename!r}"
            )
            if c.columns_found:
                print(f"  columns_found={c.columns_found}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

