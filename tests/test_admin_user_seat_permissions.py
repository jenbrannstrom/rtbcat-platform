import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from api import dependencies
from services.admin_service import AdminService
from services.auth_service import User, UserBuyerSeatPermission


def _admin_user() -> User:
    return User(id="admin-1", email="admin@example.com", role="sudo")


@pytest.mark.asyncio
async def test_admin_service_grant_buyer_seat_permission_audits():
    auth = MagicMock()
    auth.grant_user_buyer_seat_permission = AsyncMock(
        return_value=UserBuyerSeatPermission(
            id="perm-1",
            user_id="user-1",
            buyer_id="1487810529",
            access_level="admin",
            granted_by="admin-1",
            granted_at="2026-02-23T00:00:00",
            buyer_display_name="Amazing Design Tools",
            bidder_id="123",
            active=True,
        )
    )
    auth.log_audit = AsyncMock()

    svc = AdminService(auth_service=auth, repo=MagicMock())
    perm = await svc.grant_buyer_seat_permission(
        admin=_admin_user(),
        user_id="user-1",
        buyer_id="1487810529",
        access_level="admin",
        client_ip="127.0.0.1",
    )

    assert perm.buyer_id == "1487810529"
    auth.grant_user_buyer_seat_permission.assert_awaited_once()
    details = json.loads(auth.log_audit.await_args.kwargs["details"])
    assert details["buyer_id"] == "1487810529"
    assert details["access_level"] == "admin"


@pytest.mark.asyncio
async def test_admin_service_rejects_invalid_seat_access_level():
    auth = MagicMock()
    auth.grant_user_buyer_seat_permission = AsyncMock()
    auth.log_audit = AsyncMock()
    svc = AdminService(auth_service=auth, repo=MagicMock())

    with pytest.raises(Exception) as exc:
        await svc.grant_buyer_seat_permission(
            admin=_admin_user(),
            user_id="user-1",
            buyer_id="1487810529",
            access_level="write",
            client_ip=None,
        )

    assert "Seat access level" in str(exc.value)
    auth.grant_user_buyer_seat_permission.assert_not_called()


@pytest.mark.asyncio
async def test_get_allowed_buyer_ids_prefers_explicit_seat_permissions(monkeypatch):
    auth = MagicMock()
    auth.get_user_buyer_seat_ids = AsyncMock(return_value=["1487810529"])
    auth.get_user_service_account_ids = AsyncMock(return_value=["sa-1"])

    monkeypatch.setattr(dependencies, "get_auth_service", lambda: auth)

    store = MagicMock()
    store.get_buyer_ids_for_service_accounts = AsyncMock(return_value=["legacy-should-not-be-used"])

    user = User(id="user-1", email="user@example.com", role="read")
    allowed = await dependencies.get_allowed_buyer_ids(store=store, user=user)

    assert allowed == ["1487810529"]
    store.get_buyer_ids_for_service_accounts.assert_not_called()


@pytest.mark.asyncio
async def test_get_allowed_buyer_ids_no_longer_falls_back_to_legacy_service_accounts(monkeypatch):
    auth = MagicMock()
    auth.get_user_buyer_seat_ids = AsyncMock(return_value=[])
    auth.get_user_service_account_ids = AsyncMock(return_value=["sa-1", "sa-2"])

    monkeypatch.setattr(dependencies, "get_auth_service", lambda: auth)

    store = MagicMock()
    store.get_buyer_ids_for_service_accounts = AsyncMock(return_value=["111", "222"])

    user = User(id="user-1", email="user@example.com", role="admin")
    allowed = await dependencies.get_allowed_buyer_ids(store=store, user=user)

    assert allowed == []
    store.get_buyer_ids_for_service_accounts.assert_not_called()
