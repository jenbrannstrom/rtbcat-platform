"""RBAC behavior tests for /uploads/tracking route helper."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from api.routers import uploads as uploads_router
from services.auth_service import User
from services.uploads_service import DailyUploadSummary


class _StubUploadsService:
    def __init__(self) -> None:
        self.calls = 0

    async def get_tracking_summary(self, days: int):
        self.calls += 1
        return {
            "daily_summaries": [
                DailyUploadSummary(
                    upload_date="2026-03-04",
                    total_uploads=3,
                    successful_uploads=3,
                    failed_uploads=0,
                    total_rows_written=1200,
                    total_file_size_mb=1.7,
                    avg_rows_per_upload=400.0,
                    min_rows=200,
                    max_rows=600,
                    has_anomaly=False,
                    anomaly_reason=None,
                )
            ],
            "total_days": 1,
            "total_uploads": 3,
            "total_rows": 1200,
            "days_with_anomalies": 0,
        }


@pytest.mark.asyncio
async def test_get_upload_tracking_returns_empty_for_non_sudo() -> None:
    svc = _StubUploadsService()
    user = User(id="read-1", email="read@example.com", role="read")

    payload = await uploads_router.get_upload_tracking(
        days=30,
        user=user,
        service=svc,
    )

    assert payload.total_days == 0
    assert payload.total_uploads == 0
    assert payload.total_rows == 0
    assert payload.daily_summaries == []
    assert svc.calls == 0


@pytest.mark.asyncio
async def test_get_upload_tracking_returns_data_for_sudo() -> None:
    svc = _StubUploadsService()
    user = User(id="sudo-1", email="sudo@example.com", role="sudo")

    payload = await uploads_router.get_upload_tracking(
        days=30,
        user=user,
        service=svc,
    )

    assert payload.total_days == 1
    assert payload.total_uploads == 3
    assert payload.total_rows == 1200
    assert len(payload.daily_summaries) == 1
    assert payload.daily_summaries[0].upload_date == "2026-03-04"
    assert svc.calls == 1
