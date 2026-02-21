"""Unit tests for UploadsService import coverage matrix."""

import pytest

from services.uploads_service import UploadsService


class StubUploadsRepo:
    def __init__(self, has_ingestion_runs: bool = True):
        self.has_ingestion_runs = has_ingestion_runs

    async def table_exists(self, table_name: str) -> bool:
        if table_name == "ingestion_runs":
            return self.has_ingestion_runs
        return True

    async def get_active_import_accounts(self, allowed_bidder_ids=None, buyer_id=None):
        rows = [
            {"buyer_id": "111", "bidder_id": "111", "display_name": "Seat 111"},
            {"buyer_id": "222", "bidder_id": "222", "display_name": "Seat 222"},
        ]
        if buyer_id:
            rows = [row for row in rows if row["buyer_id"] == buyer_id]
        return rows

    async def get_latest_import_matrix_runs(self, start_date: str, buyer_ids: list[str]):
        _ = start_date
        rows = [
            {
                "account_id": "111",
                "csv_type": "quality",
                "status": "success",
                "import_trigger": "manual",
                "started_at": "2026-02-21T00:00:00Z",
                "finished_at": "2026-02-21T00:01:00Z",
                "error_summary": None,
            },
            {
                "account_id": "111",
                "csv_type": "pipeline-geo",
                "status": "failed",
                "import_trigger": "gmail-auto",
                "started_at": "2026-02-21T01:00:00Z",
                "finished_at": "2026-02-21T01:01:00Z",
                "error_summary": "bad header",
            },
            {
                "account_id": "222",
                "csv_type": "bidsinauction",
                "status": "success",
                "import_trigger": "gmail-manual",
                "started_at": "2026-02-21T02:00:00Z",
                "finished_at": "2026-02-21T02:01:00Z",
                "error_summary": None,
            },
        ]
        return [row for row in rows if row["account_id"] in set(buyer_ids)]


@pytest.mark.asyncio
async def test_import_matrix_returns_pass_fail_not_imported():
    svc = UploadsService(repo=StubUploadsRepo())

    result = await svc.get_import_tracking_matrix(days=30)

    assert result["total_accounts"] == 2
    assert result["pass_count"] == 2
    assert result["fail_count"] == 1
    assert result["not_imported_count"] == 7
    assert result["expected_csv_types"] == [
        "quality",
        "bidsinauction",
        "pipeline-geo",
        "pipeline-publisher",
        "bid-filtering",
    ]

    seat_111 = next(acc for acc in result["accounts"] if acc.buyer_id == "111")
    quality = next(cell for cell in seat_111.csv_types if cell.csv_type == "quality")
    pipe_geo = next(cell for cell in seat_111.csv_types if cell.csv_type == "pipeline-geo")
    pipe_pub = next(cell for cell in seat_111.csv_types if cell.csv_type == "pipeline-publisher")

    assert quality.status == "pass"
    assert quality.source == "manual"
    assert pipe_geo.status == "fail"
    assert pipe_geo.source == "gmail-auto"
    assert pipe_geo.error_summary == "bad header"
    assert pipe_pub.status == "not_imported"
    assert pipe_pub.source is None


@pytest.mark.asyncio
async def test_import_matrix_empty_when_ingestion_table_missing():
    svc = UploadsService(repo=StubUploadsRepo(has_ingestion_runs=False))

    result = await svc.get_import_tracking_matrix(days=30)

    assert result["accounts"] == []
    assert result["total_accounts"] == 0
    assert result["pass_count"] == 0
    assert result["fail_count"] == 0
    assert result["not_imported_count"] == 0
    assert "quality" in result["expected_csv_types"]
