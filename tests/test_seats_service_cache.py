"""Cache behavior tests for SeatsService seat-list and buyer->bidder paths."""

from __future__ import annotations

import pytest

from services.seats_service import BuyerSeat, SeatsService


class _StubSeatsRepo:
    def __init__(self) -> None:
        self.get_seats_calls = 0
        self.get_seats_by_ids_calls = 0
        self.seat_rows: list[dict[str, object]] = [
            {
                "buyer_id": "buyer-1",
                "bidder_id": "bidder-1",
                "display_name": "Seat One",
                "active": True,
                "creative_count": 0,
                "last_synced": None,
                "created_at": None,
                "service_account_id": None,
            },
            {
                "buyer_id": "buyer-2",
                "bidder_id": "bidder-1",
                "display_name": "Seat Two",
                "active": True,
                "creative_count": 0,
                "last_synced": None,
                "created_at": None,
                "service_account_id": None,
            },
        ]
        self.get_with_bidder_calls = 0
        self.get_with_bidder_row: dict[str, object] | None = {
            "bidder_id": "bidder-1",
            "display_name": "Seat One",
            "service_account_id": None,
        }

    async def get_buyer_seats(
        self,
        bidder_id: str | None,
        active_only: bool,
    ) -> list[dict[str, object]]:
        self.get_seats_calls += 1
        rows = self.seat_rows
        if bidder_id:
            rows = [row for row in rows if row["bidder_id"] == bidder_id]
        if active_only:
            rows = [row for row in rows if bool(row.get("active", True))]
        return [dict(row) for row in rows]

    async def get_buyer_seats_by_ids(
        self,
        buyer_ids: list[str],
        bidder_id: str | None,
        active_only: bool,
    ) -> list[dict[str, object]]:
        self.get_seats_by_ids_calls += 1
        allowed = set(buyer_ids)
        rows = [row for row in self.seat_rows if str(row["buyer_id"]) in allowed]
        if bidder_id:
            rows = [row for row in rows if row["bidder_id"] == bidder_id]
        if active_only:
            rows = [row for row in rows if bool(row.get("active", True))]
        return [dict(row) for row in rows]

    async def get_buyer_seat_with_bidder(self, buyer_id: str):
        self.get_with_bidder_calls += 1
        return dict(self.get_with_bidder_row) if self.get_with_bidder_row else None

    async def save_buyer_seat(
        self,
        buyer_id: str,
        bidder_id: str,
        display_name: str | None,
        active: bool,
        service_account_id: str | None,
    ) -> None:
        return None

    async def update_buyer_seat_display_name(self, buyer_id: str, display_name: str) -> bool:
        return True

    async def link_buyer_seat_to_service_account(self, buyer_id: str, service_account_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_get_buyer_seat_with_bidder_uses_ttl_cache() -> None:
    SeatsService.clear_caches()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    first = await service.get_buyer_seat_with_bidder("buyer-1")
    first["bidder_id"] = "mutated-locally"
    second = await service.get_buyer_seat_with_bidder("buyer-1")

    assert repo.get_with_bidder_calls == 1
    assert second["bidder_id"] == "bidder-1"


@pytest.mark.asyncio
async def test_save_buyer_seat_invalidates_buyer_lookup_cache() -> None:
    SeatsService.clear_caches()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    await service.get_buyer_seat_with_bidder("buyer-1")
    assert repo.get_with_bidder_calls == 1

    repo.get_with_bidder_row = {
        "bidder_id": "bidder-2",
        "display_name": "Seat Two",
        "service_account_id": None,
    }
    await service.save_buyer_seat(
        BuyerSeat(
            buyer_id="buyer-1",
            bidder_id="bidder-2",
            display_name="Seat Two",
            active=True,
        )
    )
    refreshed = await service.get_buyer_seat_with_bidder("buyer-1")

    assert repo.get_with_bidder_calls == 2
    assert refreshed["bidder_id"] == "bidder-2"


@pytest.mark.asyncio
async def test_get_buyer_seats_uses_ttl_cache() -> None:
    SeatsService.clear_caches()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    first = await service.get_buyer_seats(active_only=True)
    first[0].buyer_id = "mutated-locally"
    second = await service.get_buyer_seats(active_only=True)

    assert repo.get_seats_calls == 1
    assert second[0].buyer_id == "buyer-1"


@pytest.mark.asyncio
async def test_get_buyer_seats_by_ids_cache_scopes_by_allow_list() -> None:
    SeatsService.clear_caches()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    first = await service.get_buyer_seats_by_ids(
        buyer_ids=["buyer-2", "buyer-1"],
        bidder_id="bidder-1",
        active_only=True,
    )
    second = await service.get_buyer_seats_by_ids(
        buyer_ids=["buyer-1", "buyer-2"],
        bidder_id="bidder-1",
        active_only=True,
    )

    assert repo.get_seats_by_ids_calls == 1
    assert [seat.buyer_id for seat in first] == [seat.buyer_id for seat in second]


@pytest.mark.asyncio
async def test_save_buyer_seat_invalidates_buyer_seats_list_cache() -> None:
    SeatsService.clear_caches()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    await service.get_buyer_seats(active_only=True)
    assert repo.get_seats_calls == 1

    await service.save_buyer_seat(
        BuyerSeat(
            buyer_id="buyer-3",
            bidder_id="bidder-1",
            display_name="Seat Three",
            active=True,
        )
    )
    await service.get_buyer_seats(active_only=True)

    assert repo.get_seats_calls == 2
