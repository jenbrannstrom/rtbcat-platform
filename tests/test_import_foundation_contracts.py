"""Foundation hardening import contract tests (E0)."""

from __future__ import annotations

import csv
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from importers.flexible_mapper import map_columns
from importers.unified_importer import unified_import


def _write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _mock_conn() -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = [
        {"column_name": "bidder_id"},
        {"column_name": "buyer_account_id"},
        {"column_name": "platform"},
        {"column_name": "environment"},
        {"column_name": "transaction_type"},
    ]
    cursor.rowcount = 1
    return conn, cursor


def test_map_columns_supports_transaction_type_synonym():
    mapping = map_columns(["Day", "Country", "Transaction Type"])
    assert mapping.has_field("transaction_type")
    assert mapping.get_csv_column("transaction_type") == "Transaction Type"


def test_quality_signals_import_routes_and_writes_rtb_quality():
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "quality.csv")
    _write_csv(
        csv_path,
        [
            "Day",
            "Publisher ID",
            "Publisher Name",
            "Country",
            "Impressions",
            "Pre-filtered Impressions",
            "IVT Credited Impressions",
            "Billed Impressions",
            "Active View Measurable",
            "Active View Viewable",
        ],
        [
            [
                "2026-02-20",
                "pub-1",
                "Publisher One",
                "US",
                "100",
                "95",
                "20",
                "80",
                "80",
                "60",
            ]
        ],
    )

    mock_conn, mock_cursor = _mock_conn()
    with (
        patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn),
        patch("importers.unified_importer.ParquetExportManager") as mock_pem,
    ):
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-ivt-1234567890-yesterday-UTC.csv",
        )

    assert result.success
    assert result.report_type == "quality_signals"
    assert result.target_table == "rtb_quality"
    assert mock_cursor.executemany.called

    sql, batch_rows = mock_cursor.executemany.call_args[0]
    assert "INSERT INTO rtb_quality" in sql
    assert "source_report" in sql
    assert len(batch_rows) == 1
    row = batch_rows[0]
    assert row[4] == "1234567890"  # buyer_account_id fallback from filename
    assert row[11] == pytest.approx(20.0)  # ivt_rate_pct
    assert row[12] == pytest.approx(75.0)  # viewability_pct
    assert row[13] == "1234567890"  # bidder_id
    assert row[14] == result.report_type  # lineage to source report


def test_bidstream_import_persists_optional_dimensions():
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "bidstream.csv")
    _write_csv(
        csv_path,
        [
            "Day",
            "Country",
            "Buyer Account ID",
            "Publisher ID",
            "Publisher Name",
            "Platform",
            "Environment",
            "Transaction Type",
            "Inventory Matches",
            "Bid Requests",
            "Successful Responses",
            "Reached Queries",
            "Bids",
            "Bids in Auction",
            "Auctions Won",
            "Impressions",
            "Clicks",
        ],
        [
            [
                "2026-02-20",
                "US",
                "2222222222",
                "pub-2",
                "Publisher Two",
                "ANDROID",
                "APP",
                "PMP",
                "1000",
                "900",
                "700",
                "650",
                "500",
                "450",
                "100",
                "80",
                "7",
            ]
        ],
    )

    mock_conn, mock_cursor = _mock_conn()
    with (
        patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn),
        patch("importers.unified_importer.ParquetExportManager") as mock_pem,
    ):
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-pipeline-1111111111-yesterday-UTC.csv",
        )

    assert result.success
    assert result.target_table == "rtb_bidstream"
    assert mock_cursor.executemany.called

    sql, batch_rows = mock_cursor.executemany.call_args[0]
    assert "INSERT INTO rtb_bidstream" in sql
    assert "platform, environment, transaction_type" in sql
    assert "source_report" in sql
    row = batch_rows[0]
    assert row[6] == "ANDROID"
    assert row[7] == "APP"
    assert row[8] == "PMP"
    assert row[19] == result.report_type  # lineage to source report


def test_bidstream_missing_metric_columns_are_null_not_zero():
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "bidstream_missing_cols.csv")
    _write_csv(
        csv_path,
        [
            "Day",
            "Country",
            "Buyer Account ID",
            "Publisher ID",
            "Bids in Auction",
        ],
        [
            [
                "2026-02-20",
                "US",
                "2222222222",
                "pub-3",
                "25",
            ]
        ],
    )

    mock_conn, mock_cursor = _mock_conn()
    with (
        patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn),
        patch("importers.unified_importer.ParquetExportManager") as mock_pem,
    ):
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-pipeline-1111111111-yesterday-UTC.csv",
        )

    assert result.success
    sql, batch_rows = mock_cursor.executemany.call_args[0]
    assert "INSERT INTO rtb_bidstream" in sql
    row = batch_rows[0]
    assert row[9] is None  # inventory_matches absent from report
    assert row[10] is None  # bid_requests absent from report
    assert row[14] == 25  # mapped metric remains numeric
    assert row[19] == result.report_type  # lineage to source report


def test_rtb_daily_missing_metric_columns_are_null_not_zero():
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "daily_missing_cols.csv")
    _write_csv(
        csv_path,
        [
            "Day",
            "Buyer Account ID",
            "Billing ID",
            "Creative ID",
            "Creative Size",
            "Impressions",
        ],
        [
            [
                "2026-02-20",
                "3333333333",
                "cfg-1",
                "creative-1",
                "300x250",
                "100",
            ]
        ],
    )

    mock_conn, mock_cursor = _mock_conn()
    with (
        patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn),
        patch("importers.unified_importer.ParquetExportManager") as mock_pem,
    ):
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-quality-3333333333-yesterday-UTC.csv",
        )

    assert result.success
    sql, batch_rows = mock_cursor.executemany.call_args[0]
    assert "INSERT INTO rtb_daily" in sql
    row = batch_rows[0]
    assert row[16] == 100  # impressions present in report
    assert row[17] is None  # clicks column absent from report
    assert row[18] is None  # spend column absent from report
    assert row[19] is None  # bids column absent from report
    assert row[27] == result.report_type  # lineage to source report


def test_bid_filtering_missing_metric_columns_are_null_not_zero():
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "filtering_missing_cols.csv")
    _write_csv(
        csv_path,
        [
            "Day",
            "Buyer Account ID",
            "Bid Filtering Reason",
            "Bids in Auction",
        ],
        [
            [
                "2026-02-20",
                "4444444444",
                "Creative disapproved",
                "12",
            ]
        ],
    )

    mock_conn, mock_cursor = _mock_conn()
    with (
        patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn),
        patch("importers.unified_importer.ParquetExportManager") as mock_pem,
    ):
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-bid-filtering-4444444444-yesterday-UTC.csv",
        )

    assert result.success
    sql, batch_rows = mock_cursor.executemany.call_args[0]
    assert "INSERT INTO rtb_bid_filtering" in sql
    row = batch_rows[0]
    assert row[5] is None  # bids column absent from report
    assert row[6] == 12  # bids_in_auction present in report
    assert row[7] is None  # opportunity_cost column absent from report
    assert row[9] == result.report_type  # lineage to source report
