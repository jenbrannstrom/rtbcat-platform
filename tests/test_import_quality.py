"""Tests for B4 import quality controls: IMPORT-001 + IMPORT-002.

IMPORT-001: Size canonicalization before persistence.
IMPORT-002: Date continuity gap detection.
"""

import pytest
from unittest.mock import MagicMock

from importers.unified_importer import (
    canonicalize_size_string,
    check_date_continuity,
    _apply_date_continuity,
    UnifiedImportResult,
    sync_performance_metrics_from_rtb_daily_batch,
)


# =========================================================================
# IMPORT-001 — canonicalize_size_string
# =========================================================================

class TestCanonicalizeSizeString:
    """Verify that raw CSV size strings are normalised to IAB categories."""

    def test_standard_iab_size(self):
        assert canonicalize_size_string("300x250") == "300x250 (Medium Rectangle)"

    def test_uppercase_separator(self):
        assert canonicalize_size_string("728X90") == "728x90 (Leaderboard)"

    def test_spaced_separator(self):
        assert canonicalize_size_string("320 x 50") == "320x50 (Mobile Banner)"

    def test_tolerance_near_standard(self):
        # 298x250 is within 5px tolerance of 300x250
        assert canonicalize_size_string("298x250") == "300x250 (Medium Rectangle)"

    def test_non_standard_size(self):
        result = canonicalize_size_string("123x456")
        assert result == "Non-Standard (123x456)"

    def test_video_aspect_ratio(self):
        result = canonicalize_size_string("1920x1080")
        assert result == "Video 16:9 (Horizontal)"

    def test_adaptive_fluid(self):
        assert canonicalize_size_string("0x250") == "Adaptive/Fluid"

    def test_adaptive_responsive(self):
        assert canonicalize_size_string("1x1") == "Adaptive/Responsive"

    def test_native_passthrough(self):
        assert canonicalize_size_string("Native") == "Native"

    def test_video_overlay_passthrough(self):
        assert canonicalize_size_string("Video/Overlay") == "Video/Overlay"

    def test_unknown_passthrough(self):
        assert canonicalize_size_string("unknown") == "unknown"

    def test_empty_passthrough(self):
        assert canonicalize_size_string("") == ""

    def test_whitespace_stripping(self):
        assert canonicalize_size_string("  300x250  ") == "300x250 (Medium Rectangle)"

    def test_unparseable_falls_back(self):
        assert canonicalize_size_string("interstitial") == "interstitial"

    def test_unicode_multiplication_sign(self):
        # × (U+00D7) multiplication sign
        assert canonicalize_size_string("320×50") == "320x50 (Mobile Banner)"


# =========================================================================
# IMPORT-002 — check_date_continuity
# =========================================================================

class TestCheckDateContinuity:
    """Verify gap detection for imported date ranges."""

    def test_no_gap_contiguous(self):
        observed = {"2026-02-10", "2026-02-11", "2026-02-12"}
        gaps = check_date_continuity(observed, "2026-02-10", "2026-02-12")
        assert gaps == []

    def test_single_missing_day(self):
        observed = {"2026-02-10", "2026-02-12"}
        gaps = check_date_continuity(observed, "2026-02-10", "2026-02-12")
        assert gaps == ["2026-02-11"]

    def test_multiple_missing_days(self):
        observed = {"2026-02-10", "2026-02-15"}
        gaps = check_date_continuity(observed, "2026-02-10", "2026-02-15")
        assert gaps == [
            "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-14",
        ]

    def test_single_day_range_no_gap(self):
        observed = {"2026-02-10"}
        gaps = check_date_continuity(observed, "2026-02-10", "2026-02-10")
        assert gaps == []

    def test_empty_observed(self):
        gaps = check_date_continuity(set(), "2026-02-10", "2026-02-12")
        assert gaps == ["2026-02-10", "2026-02-11", "2026-02-12"]

    def test_none_range(self):
        gaps = check_date_continuity({"2026-02-10"}, None, None)
        assert gaps == []

    def test_inverted_range(self):
        gaps = check_date_continuity(set(), "2026-02-12", "2026-02-10")
        assert gaps == []

    def test_cross_month_boundary(self):
        observed = {"2026-01-30", "2026-02-01"}
        gaps = check_date_continuity(observed, "2026-01-30", "2026-02-01")
        assert gaps == ["2026-01-31"]


class TestApplyDateContinuity:
    """Verify _apply_date_continuity populates result fields."""

    def test_populates_result_with_gap_warning(self):
        result = UnifiedImportResult()
        observed = {"2026-02-10", "2026-02-12"}
        _apply_date_continuity(result, observed, "2026-02-10", "2026-02-12")

        assert result.date_range_start == "2026-02-10"
        assert result.date_range_end == "2026-02-12"
        assert result.date_gaps == ["2026-02-11"]
        assert "missing 1 expected day" in result.date_gap_warning

    def test_no_warning_when_contiguous(self):
        result = UnifiedImportResult()
        observed = {"2026-02-10", "2026-02-11", "2026-02-12"}
        _apply_date_continuity(result, observed, "2026-02-10", "2026-02-12")

        assert result.date_gaps == []
        assert result.date_gap_warning is None

    def test_truncates_long_gap_list(self):
        result = UnifiedImportResult()
        observed = {"2026-02-01", "2026-02-15"}
        _apply_date_continuity(result, observed, "2026-02-01", "2026-02-15")

        assert len(result.date_gaps) == 13
        # Warning should mention "and N more"
        assert "more" in result.date_gap_warning


# =========================================================================
# IMPORT-003 — rtb_daily -> performance_metrics hydration
# =========================================================================

class TestPerformanceMetricsHydration:
    """Verify legacy performance_metrics sync SQL is executed for imported batches."""

    def test_sync_executes_expected_sql(self):
        cursor = MagicMock()

        sync_performance_metrics_from_rtb_daily_batch(cursor, "batch-123")

        # ensure_performance_metrics_table emits CREATE TABLE + CREATE INDEX
        assert cursor.execute.call_count >= 3

        insert_call = cursor.execute.call_args_list[-1]
        sql = insert_call.args[0]
        params = insert_call.args[1]

        assert "INSERT INTO performance_metrics" in sql
        assert "FROM rtb_daily" in sql
        assert "import_batch_id = %s" in sql
        assert params == ("batch-123",)
