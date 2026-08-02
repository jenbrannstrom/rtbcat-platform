"""Row-level buyer authorization tests for unified CSV imports."""

from __future__ import annotations

import csv
from unittest.mock import MagicMock, patch

import pytest

from importers.unified_importer import ImportBuyerScope, unified_import


ALLOWED_BUYER = "2222222222"
OTHER_BUYER = "1111111111"


def _write_csv(path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _mock_connection() -> tuple[MagicMock, MagicMock]:
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {"is_partitioned": False}
    cursor.rowcount = 1
    return connection, cursor


@pytest.mark.parametrize(
    ("expected_table", "filename", "headers", "row"),
    [
        (
            "rtb_daily",
            f"catscan-quality-{OTHER_BUYER}-yesterday-UTC.csv",
            [
                "Day",
                "Buyer Account ID",
                "Billing ID",
                "Creative ID",
                "Creative Size",
                "Impressions",
            ],
            ["2026-08-01", OTHER_BUYER, "cfg-1", "creative-1", "300x250", "10"],
        ),
        (
            "rtb_bidstream",
            f"catscan-pipeline-{OTHER_BUYER}-yesterday-UTC.csv",
            ["Day", "Country", "Buyer Account ID", "Publisher ID", "Bid Requests"],
            ["2026-08-01", "ZA", OTHER_BUYER, "pub-1", "10"],
        ),
        (
            "rtb_bid_filtering",
            f"catscan-bid-filtering-{OTHER_BUYER}-yesterday-UTC.csv",
            ["Day", "Buyer Account ID", "Bid Filtering Reason", "Bids"],
            ["2026-08-01", OTHER_BUYER, "Creative disapproved", "10"],
        ),
        (
            "rtb_quality",
            f"catscan-ivt-{OTHER_BUYER}-yesterday-UTC.csv",
            [
                "Day",
                "Buyer Account ID",
                "Publisher ID",
                "Impressions",
                "IVT Credited Impressions",
            ],
            ["2026-08-01", OTHER_BUYER, "pub-1", "10", "1"],
        ),
        (
            "web_domain_daily",
            f"catscan-domains-{OTHER_BUYER}-yesterday-UTC.csv",
            [
                "Day",
                "Buyer Account ID",
                "Billing ID",
                "Publisher Domain",
                "Impressions",
            ],
            ["2026-08-01", OTHER_BUYER, "cfg-1", "example.com", "10"],
        ),
    ],
)
def test_restricted_scope_rejects_cross_buyer_rows_for_every_report_family(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    expected_table: str,
    filename: str,
    headers: list[str],
    row: list[str],
) -> None:
    csv_path = tmp_path / "report.csv"
    _write_csv(csv_path, headers, [row])
    connection, cursor = _mock_connection()
    exporter = MagicMock()
    monkeypatch.setenv("CATSCAN_WEB_LANE_ENABLED", "true")
    monkeypatch.delenv("CATSCAN_WEB_LANE_BUYERS", raising=False)

    with (
        patch(
            "importers.unified_importer.get_postgres_connection",
            return_value=connection,
        ),
        patch("importers.unified_importer.ParquetExportManager") as manager,
    ):
        manager.from_env.return_value = exporter
        result = unified_import(
            str(csv_path),
            buyer_scope=ImportBuyerScope.restricted([ALLOWED_BUYER]),
            source_filename=filename,
        )

    assert result.target_table == expected_table
    assert result.success is False
    assert "outside the authorized import scope" in result.error_message
    assert result.rows_imported == 0
    cursor.executemany.assert_not_called()
    connection.rollback.assert_called_once_with()
    exporter.discard.assert_called_once_with()
    exporter.finalize.assert_not_called()


def test_scope_violation_rolls_back_rows_flushed_earlier_in_same_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "mixed.csv"
    headers = [
        "Day",
        "Buyer Account ID",
        "Billing ID",
        "Creative ID",
        "Creative Size",
        "Impressions",
    ]
    _write_csv(
        csv_path,
        headers,
        [
            ["2026-08-01", ALLOWED_BUYER, "cfg-1", "creative-1", "300x250", "10"],
            ["2026-08-01", OTHER_BUYER, "cfg-2", "creative-2", "300x250", "20"],
        ],
    )
    connection, cursor = _mock_connection()
    exporter = MagicMock()
    monkeypatch.setattr("importers.unified_importer.IMPORT_BATCH_SIZE", 1)

    with (
        patch(
            "importers.unified_importer.get_postgres_connection",
            return_value=connection,
        ),
        patch("importers.unified_importer.ParquetExportManager") as manager,
    ):
        manager.from_env.return_value = exporter
        result = unified_import(
            str(csv_path),
            buyer_scope=ImportBuyerScope.restricted([ALLOWED_BUYER]),
            source_filename=f"catscan-quality-{ALLOWED_BUYER}-yesterday-UTC.csv",
        )

    assert result.success is False
    assert result.rows_read == 2
    assert result.rows_imported == 0
    assert result.rows_duplicate == 0
    cursor.executemany.assert_called_once()
    connection.rollback.assert_called_once_with()
    exporter.add_row.assert_called_once()
    exporter.discard.assert_called_once_with()
    exporter.finalize.assert_not_called()


def test_restricted_scope_also_checks_filename_bidder_identity(
    tmp_path,
) -> None:
    csv_path = tmp_path / "filename-mismatch.csv"
    _write_csv(
        csv_path,
        ["Day", "Buyer Account ID", "Billing ID", "Creative ID", "Impressions"],
        [["2026-08-01", ALLOWED_BUYER, "cfg-1", "creative-1", "10"]],
    )
    connection, _cursor = _mock_connection()

    with (
        patch(
            "importers.unified_importer.get_postgres_connection",
            return_value=connection,
        ),
        patch("importers.unified_importer.ParquetExportManager") as manager,
    ):
        manager.from_env.return_value = None
        result = unified_import(
            str(csv_path),
            buyer_scope=ImportBuyerScope.restricted([ALLOWED_BUYER]),
            source_filename=f"catscan-quality-{OTHER_BUYER}-yesterday-UTC.csv",
        )

    assert result.success is False
    assert "outside the authorized import scope" in result.error_message
    connection.rollback.assert_called_once_with()
