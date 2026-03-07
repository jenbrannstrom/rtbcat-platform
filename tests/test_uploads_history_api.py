"""Uploads history route tests for buyer-aware import history."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import uploads as uploads_router
from services.auth_service import User
from services.uploads_service import ImportHistoryEntry


class _StubUploadsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def get_import_history(
        self,
        *,
        limit: int,
        offset: int,
        buyer_id: str | None = None,
        bidder_id: str | None = None,
        allowed_bidder_ids,
    ) -> list[ImportHistoryEntry]:
        self.calls.append(
            {
                "limit": limit,
                "offset": offset,
                "buyer_id": buyer_id,
                "bidder_id": bidder_id,
                "allowed_bidder_ids": allowed_bidder_ids,
            }
        )
        return [
            ImportHistoryEntry(
                batch_id="batch-1",
                filename="catscan-quality-299038253.csv",
                imported_at="2026-03-06T08:14:00Z",
                rows_read=10,
                rows_imported=0,
                rows_skipped=0,
                rows_duplicate=10,
                date_range_start="2026-03-05",
                date_range_end="2026-03-05",
                total_spend_usd=0.0,
                file_size_mb=0.1,
                status="complete",
                error_message=None,
                buyer_id=buyer_id,
                buyer_display_name="Tuky Display",
                bidder_id="299038253",
                billing_ids_found=["123"],
                columns_found=["Day", "Buyer account ID"],
                columns_missing=[],
                date_gaps=[],
                date_gap_warning=None,
                import_trigger="gmail-auto",
            )
        ]


def _user() -> User:
    return User(id="user-1", email="user@example.com", role="read")


@pytest.mark.asyncio
async def test_uploads_history_accepts_buyer_id_and_returns_display_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubUploadsService()

    async def _allow_buyer_ids(*, user):
        _ = user
        return ["299038253"]

    async def _allow_bidder_ids(*, user):
        _ = user
        return ["299038253"]

    monkeypatch.setattr(uploads_router, "get_allowed_buyer_ids", _allow_buyer_ids)
    monkeypatch.setattr(uploads_router, "get_allowed_bidder_ids", _allow_bidder_ids)

    payload = await uploads_router.get_import_history(
        limit=50,
        offset=0,
        buyer_id="299038253",
        bidder_id=None,
        user=_user(),
        service=service,
    )

    assert payload[0].buyer_id == "299038253"
    assert payload[0].buyer_display_name == "Tuky Display"
    assert service.calls[0]["buyer_id"] == "299038253"


@pytest.mark.asyncio
async def test_uploads_history_rejects_disallowed_buyer_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubUploadsService()

    async def _allow_buyer_ids(*, user):
        _ = user
        return ["299038253"]

    async def _allow_bidder_ids(*, user):
        _ = user
        return ["299038253"]

    monkeypatch.setattr(uploads_router, "get_allowed_buyer_ids", _allow_buyer_ids)
    monkeypatch.setattr(uploads_router, "get_allowed_bidder_ids", _allow_bidder_ids)

    with pytest.raises(HTTPException) as exc_info:
        await uploads_router.get_import_history(
            limit=50,
            offset=0,
            buyer_id="1487810529",
            bidder_id=None,
            user=_user(),
            service=service,
        )

    assert exc_info.value.status_code == 403
    assert "buyer seat" in str(exc_info.value.detail).lower()
    assert service.calls == []
