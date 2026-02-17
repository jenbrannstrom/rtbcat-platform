#!/usr/bin/env python3
"""B4 runtime validation script for VM2.

Exercises IMPORT-001 (size canonicalization) and IMPORT-002 (date continuity)
against the live Postgres database.

Usage:
    python3 tests/b4_runtime_validation.py
"""

import json
import os
import sys

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from importers.unified_importer import unified_import


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def run_test(name: str, csv_name: str, bidder_id: str = "999999999"):
    """Run a single import test and return the result."""
    csv_path = os.path.join(FIXTURES_DIR, csv_name)
    if not os.path.exists(csv_path):
        print(f"  SKIP: {csv_path} not found")
        return None

    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"CSV:  {csv_name}")
    print(f"{'='*60}")

    result = unified_import(csv_path, bidder_id=bidder_id, source_filename=csv_name)

    print(f"  success:          {result.success}")
    print(f"  report_type:      {result.report_type}")
    print(f"  target_table:     {result.target_table}")
    print(f"  rows_read:        {result.rows_read}")
    print(f"  rows_imported:    {result.rows_imported}")
    print(f"  rows_duplicate:   {result.rows_duplicate}")
    print(f"  rows_skipped:     {result.rows_skipped}")
    print(f"  date_range:       {result.date_range_start} to {result.date_range_end}")
    print(f"  date_gaps:        {result.date_gaps}")
    print(f"  date_gap_warning: {result.date_gap_warning}")
    print(f"  batch_id:         {result.batch_id}")
    if result.errors:
        print(f"  errors:           {result.errors[:5]}")
    if result.error_message:
        print(f"  error_message:    {result.error_message}")

    return result


def query_persisted_sizes(batch_id: str):
    """Query the DB for persisted creative_size values from a specific batch."""
    try:
        from importers.unified_importer import get_postgres_connection
        conn = get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT creative_id, creative_size FROM rtb_daily "
            "WHERE import_batch_id = %s ORDER BY creative_id",
            (batch_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"  DB query error: {e}")
        return []


def main():
    print("=" * 60)
    print("B4 RUNTIME VALIDATION")
    print("=" * 60)

    # ---------------------------------------------------------------
    # TEST 1: IMPORT-001 — Size canonicalization
    # ---------------------------------------------------------------
    r1 = run_test(
        "IMPORT-001: Size canonicalization",
        "b4_size_canonicalization.csv",
    )

    if r1 and r1.success:
        print("\n  --- Persisted sizes in DB ---")
        rows = query_persisted_sizes(r1.batch_id)
        for row in rows:
            print(f"    {row['creative_id']:12s} -> {row['creative_size']}")

        # Verify expected canonicalization
        expected = {
            "cr_001": "300x250 (Medium Rectangle)",   # 300x250
            "cr_002": "300x250 (Medium Rectangle)",   # 300 X 250
            "cr_003": "320x50 (Mobile Banner)",        # 320×50
            "cr_004": "300x250 (Medium Rectangle)",   # 298x250 (tolerance)
            "cr_005": "Non-Standard (123x456)",        # 123x456
            "cr_006": "Native",                        # passthrough
            "cr_007": "Video/Overlay",                 # passthrough
            "cr_008": "interstitial",                  # passthrough
        }
        db_map = {r["creative_id"]: r["creative_size"] for r in rows}
        all_ok = True
        for cid, exp in expected.items():
            actual = db_map.get(cid, "<missing>")
            status = "OK" if actual == exp else "FAIL"
            if status == "FAIL":
                all_ok = False
            print(f"    {status}: {cid} expected={exp!r} actual={actual!r}")

        print(f"\n  IMPORT-001 RESULT: {'PASS' if all_ok else 'FAIL'}")
    elif r1:
        print(f"\n  IMPORT-001 RESULT: FAIL (import failed: {r1.error_message})")
    else:
        print("\n  IMPORT-001 RESULT: SKIP")

    # ---------------------------------------------------------------
    # TEST 2: IMPORT-002 — Date gap detection
    # ---------------------------------------------------------------
    r2 = run_test(
        "IMPORT-002: Date gap detection",
        "b4_date_gap.csv",
    )

    if r2 and r2.success:
        has_gaps = len(r2.date_gaps) > 0
        expected_gaps = {"2026-02-11", "2026-02-13"}
        actual_gaps = set(r2.date_gaps)
        gaps_correct = expected_gaps == actual_gaps
        has_warning = r2.date_gap_warning is not None

        print(f"\n  gaps detected:    {has_gaps}")
        print(f"  expected gaps:    {sorted(expected_gaps)}")
        print(f"  actual gaps:      {sorted(actual_gaps)}")
        print(f"  gaps match:       {gaps_correct}")
        print(f"  warning present:  {has_warning}")
        print(f"\n  IMPORT-002 (gap) RESULT: {'PASS' if gaps_correct and has_warning else 'FAIL'}")
    elif r2:
        print(f"\n  IMPORT-002 (gap) RESULT: FAIL (import failed: {r2.error_message})")
    else:
        print("\n  IMPORT-002 (gap) RESULT: SKIP")

    # ---------------------------------------------------------------
    # TEST 3: IMPORT-002 — No-gap control
    # ---------------------------------------------------------------
    r3 = run_test(
        "IMPORT-002: No-gap control",
        "b4_date_contiguous.csv",
    )

    if r3 and r3.success:
        no_gaps = len(r3.date_gaps) == 0
        no_warning = r3.date_gap_warning is None

        print(f"\n  gaps detected:    {not no_gaps}")
        print(f"  warning present:  {not no_warning}")
        print(f"\n  IMPORT-002 (no-gap) RESULT: {'PASS' if no_gaps and no_warning else 'FAIL'}")
    elif r3:
        print(f"\n  IMPORT-002 (no-gap) RESULT: FAIL (import failed: {r3.error_message})")
    else:
        print("\n  IMPORT-002 (no-gap) RESULT: SKIP")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    results = {
        "import_001": r1 and r1.success,
        "import_002_gap": r2 and r2.success and len(r2.date_gaps) > 0 if r2 else False,
        "import_002_nogap": r3 and r3.success and len(r3.date_gaps) == 0 if r3 else False,
    }
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")

    all_pass = all(results.values())
    print(f"\n  OVERALL: {'GO' if all_pass else 'NO-GO'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
