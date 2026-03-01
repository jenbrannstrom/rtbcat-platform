"""Cache behavior tests for SeatsService buyer->bidder lookup path."""

from __future__ import annotations

import pytest

from services.seats_service import BuyerSeat, SeatsService


class _StubSeatsRepo:
    def __init__(self) -> None:
        self.get_with_bidder_calls = 0
        self.get_with_bidder_row: dict[str, object] | None = {
            "bidder_id": "bidder-1",
            "display_name": "Seat One",
            "service_account_id": None,
        }

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
    SeatsService._invalidate_buyer_seat_with_bidder_cache()
    repo = _StubSeatsRepo()
    service = SeatsService(repo=repo)

    first = await service.get_buyer_seat_with_bidder("buyer-1")
    first["bidder_id"] = "mutated-locally"
    second = await service.get_buyer_seat_with_bidder("buyer-1")

    assert repo.get_with_bidder_calls == 1
    assert second["bidder_id"] == "bidder-1"


@pytest.mark.asyncio
async def test_save_buyer_seat_invalidates_buyer_lookup_cache() -> None:
    SeatsService._invalidate_buyer_seat_with_bidder_cache()
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
