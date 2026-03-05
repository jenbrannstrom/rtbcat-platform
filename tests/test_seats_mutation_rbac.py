"""RBAC guards for seats mutation routes."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from fastapi import BackgroundTasks, HTTPException

# Avoid optional Google API dependency while importing seats router.
if "collectors" not in sys.modules:
    fake_collectors = types.ModuleType("collectors")
    fake_collectors.BuyerSeatsClient = object
    fake_collectors.CreativesClient = object
    fake_collectors.EndpointsClient = object
    fake_collectors.PretargetingClient = object
    sys.modules["collectors"] = fake_collectors

from api.routers import seats as seats_router
from services.auth_service import User
from services.seats_service import BuyerSeat


def _readonly_user() -> User:
    return User(id="read-1", email="read@example.com", role="read")


class _StubSeatsService:
    def __init__(self) -> None:
        self.get_buyer_seat_calls = 0
        self.update_display_name_calls = 0
        self.populate_calls = 0

    async def get_buyer_seat(self, _buyer_id: str) -> BuyerSeat | None:
        self.get_buyer_seat_calls += 1
        return None

    async def update_display_name(self, _buyer_id: str, _display_name: str) -> bool:
        self.update_display_name_calls += 1
        return True

    async def populate_from_creatives(self) -> int:
        self.populate_calls += 1
        return 1


@pytest.mark.asyncio
async def test_sync_seat_creatives_requires_buyer_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubSeatsService()
    monkeypatch.setattr(
        seats_router,
        "require_buyer_admin_access",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="forbidden")),
    )

    with pytest.raises(HTTPException) as exc:
        await seats_router.sync_seat_creatives(
            buyer_id="2222222222",
            filter_query=None,
            background_tasks=BackgroundTasks(),
            config=object(),
            seats_service=service,
            store=object(),
            user=_readonly_user(),
        )

    assert exc.value.status_code == 403
    assert service.get_buyer_seat_calls == 0


@pytest.mark.asyncio
async def test_update_seat_requires_buyer_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubSeatsService()
    monkeypatch.setattr(
        seats_router,
        "require_buyer_admin_access",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="forbidden")),
    )

    with pytest.raises(HTTPException) as exc:
        await seats_router.update_seat(
            buyer_id="2222222222",
            request=seats_router.UpdateSeatRequest(display_name="Customer Delta"),
            seats_service=service,
            store=object(),
            user=_readonly_user(),
        )

    assert exc.value.status_code == 403
    assert service.update_display_name_calls == 0


@pytest.mark.asyncio
async def test_discover_seats_requires_seat_admin_or_sudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        seats_router,
        "require_seat_admin_or_sudo",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="admin required")),
    )

    with pytest.raises(HTTPException) as exc:
        await seats_router.discover_seats(
            request=seats_router.DiscoverSeatsRequest(
                bidder_id="1111111111",
                auto_sync=False,
            ),
            config=object(),
            seats_service=_StubSeatsService(),
            store=object(),
            user=_readonly_user(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_sync_all_requires_seat_admin_or_sudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        seats_router,
        "require_seat_admin_or_sudo",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="admin required")),
    )

    with pytest.raises(HTTPException) as exc:
        await seats_router.sync_all_data(
            seats_service=_StubSeatsService(),
            store=object(),
            config=object(),
            user=_readonly_user(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_populate_seats_requires_sudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubSeatsService()
    monkeypatch.setattr(
        seats_router,
        "require_admin",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="sudo required")),
    )

    with pytest.raises(HTTPException) as exc:
        await seats_router.populate_seats_from_creatives(
            seats_service=service,
            user=_readonly_user(),
        )

    assert exc.value.status_code == 403
    assert service.populate_calls == 0
