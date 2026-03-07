"""Unit tests for seats list routing behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from api.routers import seats as seats_router
from services.auth_service import User
from services.seats_service import BuyerSeat


class _StubSeatsService:
    def __init__(self) -> None:
        self.get_all_calls: list[dict[str, object]] = []
        self.get_by_ids_calls: list[dict[str, object]] = []

    async def get_buyer_seats(
        self,
        bidder_id: str | None = None,
        active_only: bool = True,
    ) -> list[BuyerSeat]:
        self.get_all_calls.append(
            {"bidder_id": bidder_id, "active_only": active_only}
        )
        return [
            BuyerSeat(
                buyer_id="buyer-all",
                bidder_id="bidder-all",
                display_name="All Seat",
                active=True,
            )
        ]

    async def get_buyer_seats_by_ids(
        self,
        buyer_ids: list[str],
        bidder_id: str | None = None,
        active_only: bool = True,
    ) -> list[BuyerSeat]:
        self.get_by_ids_calls.append(
            {
                "buyer_ids": buyer_ids,
                "bidder_id": bidder_id,
                "active_only": active_only,
            }
        )
        return [
            BuyerSeat(
                buyer_id=buyer_ids[0],
                bidder_id=bidder_id or "bidder-1",
                display_name="Allowed Seat",
                active=True,
            )
        ]


def _user() -> User:
    return User(id="user-1", email="user@example.com", role="read")


@pytest.mark.asyncio
async def test_list_seats_uses_allow_list_query_path(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _StubSeatsService()
    allowed_mock = AsyncMock(return_value=["buyer-allowed"])
    monkeypatch.setattr(seats_router, "get_allowed_buyer_ids", allowed_mock)

    rows = await seats_router.list_seats(
        bidder_id="bidder-1",
        active_only=True,
        seats_service=service,
        store=object(),
        user=_user(),
    )

    assert len(rows) == 1
    assert rows[0].buyer_id == "buyer-allowed"
    assert service.get_all_calls == []
    assert service.get_by_ids_calls == [
        {
            "buyer_ids": ["buyer-allowed"],
            "bidder_id": "bidder-1",
            "active_only": True,
        }
    ]
    allowed_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_seats_returns_empty_when_allow_list_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubSeatsService()
    monkeypatch.setattr(seats_router, "get_allowed_buyer_ids", AsyncMock(return_value=[]))

    rows = await seats_router.list_seats(
        bidder_id=None,
        active_only=True,
        seats_service=service,
        store=object(),
        user=_user(),
    )

    assert rows == []
    assert service.get_all_calls == []
    assert service.get_by_ids_calls == []


@pytest.mark.asyncio
async def test_list_seats_uses_unfiltered_query_for_sudo(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _StubSeatsService()
    monkeypatch.setattr(seats_router, "get_allowed_buyer_ids", AsyncMock(return_value=None))

    rows = await seats_router.list_seats(
        bidder_id=None,
        active_only=False,
        seats_service=service,
        store=object(),
        user=_user(),
    )

    assert len(rows) == 1
    assert rows[0].buyer_id == "buyer-all"
    assert service.get_all_calls == [{"bidder_id": None, "active_only": False}]
    assert service.get_by_ids_calls == []
