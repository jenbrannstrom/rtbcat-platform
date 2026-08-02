"""Cross-seat authorization regression tests.

Covers the defect where administering any one buyer seat was accepted as
authorization to act on every other seat. Each test here pins a caller to seat
2222222222 and asserts they are refused against seat 1111111111.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException

from api.campaigns_router import require_campaign_access, require_creative_access
from api.dependencies import (
    get_admin_bidder_ids,
    get_admin_buyer_ids,
    require_bidder_admin,
    require_billing_id_admin,
    resolve_admin_buyer_id,
)
from services.auth_service import User


OWN_SEAT = "2222222222"
OTHER_SEAT = "1111111111"


def _sudo_user() -> User:
    return User(id="sudo-1", email="sudo@example.com", role="sudo")


def _seat_admin_user() -> User:
    """Admin of OWN_SEAT only."""
    return User(id="admin-1", email="admin@example.com", role="admin")


def _readonly_user() -> User:
    return User(id="ro-1", email="ro@example.com", role="read")


def _auth_svc(admin_seats: list[str], read_seats: list[str] | None = None):
    """Auth service whose admin/read seat sets can differ."""
    read_seats = read_seats if read_seats is not None else list(admin_seats)
    svc = MagicMock()
    svc.get_user_buyer_seat_ids = AsyncMock(
        side_effect=lambda uid, min_access_level="read": (
            list(admin_seats) if min_access_level == "admin" else list(read_seats)
        )
    )
    return svc


def _store(bidder_ids_by_buyer: dict[str, str]):
    store = MagicMock()
    store.get_bidder_ids_for_buyer_ids = AsyncMock(
        side_effect=lambda buyer_ids: sorted(
            {bidder_ids_by_buyer[b] for b in buyer_ids if b in bidder_ids_by_buyer}
        )
    )
    return store


# ==================== get_admin_buyer_ids ====================


@pytest.mark.asyncio
async def test_admin_buyer_ids_is_none_for_sudo():
    assert await get_admin_buyer_ids(_sudo_user()) is None


@pytest.mark.asyncio
async def test_admin_buyer_ids_excludes_read_only_seats():
    """A read grant on another seat must not appear in the admin set."""
    svc = _auth_svc(admin_seats=[OWN_SEAT], read_seats=[OWN_SEAT, OTHER_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        assert await get_admin_buyer_ids(_seat_admin_user()) == [OWN_SEAT]


# ==================== resolve_admin_buyer_id ====================


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_denies_other_seat():
    svc = _auth_svc([OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await resolve_admin_buyer_id(OTHER_SEAT, user=_seat_admin_user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_allows_own_seat():
    svc = _auth_svc([OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        assert await resolve_admin_buyer_id(OWN_SEAT, user=_seat_admin_user()) == OWN_SEAT


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_denies_read_only_user_on_own_seat():
    """Read access to a seat is not admin access to it."""
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await resolve_admin_buyer_id(OWN_SEAT, user=_readonly_user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_defaults_to_sole_admin_seat():
    """Omitting buyer_id pins to the caller's own seat, never widens scope."""
    svc = _auth_svc([OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        assert await resolve_admin_buyer_id(None, user=_seat_admin_user()) == OWN_SEAT


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_requires_explicit_id_when_multi_seat():
    svc = _auth_svc([OWN_SEAT, "3333333333"])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await resolve_admin_buyer_id(None, user=_seat_admin_user())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_admin_buyer_id_passes_through_for_sudo():
    assert await resolve_admin_buyer_id(OTHER_SEAT, user=_sudo_user()) == OTHER_SEAT


# ==================== bidder-scoped checks ====================


@pytest.mark.asyncio
async def test_admin_bidder_ids_derive_from_admin_seats_only():
    svc = _auth_svc(admin_seats=[OWN_SEAT], read_seats=[OWN_SEAT, OTHER_SEAT])
    store = _store({OWN_SEAT: "bidder-own", OTHER_SEAT: "bidder-other"})
    with patch("api.dependencies.get_auth_service", return_value=svc):
        assert await get_admin_bidder_ids(store=store, user=_seat_admin_user()) == ["bidder-own"]


@pytest.mark.asyncio
async def test_require_bidder_admin_denies_foreign_bidder():
    svc = _auth_svc([OWN_SEAT])
    store = _store({OWN_SEAT: "bidder-own", OTHER_SEAT: "bidder-other"})
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await require_bidder_admin("bidder-other", store=store, user=_seat_admin_user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_bidder_admin_denies_missing_bidder():
    """An unresolved bidder must fail closed rather than pass the check."""
    svc = _auth_svc([OWN_SEAT])
    store = _store({OWN_SEAT: "bidder-own"})
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await require_bidder_admin(None, store=store, user=_seat_admin_user())
    assert exc.value.status_code == 403


# ==================== require_billing_id_admin ====================


def _pretargeting_repo(config: dict | None):
    repo = MagicMock()
    repo.get_config_by_billing_id = AsyncMock(return_value=config)
    return MagicMock(return_value=repo)


@pytest.mark.asyncio
async def test_require_billing_id_admin_denies_config_of_other_bidder():
    """The live-pretargeting escalation: seat admin acting on a foreign config."""
    svc = _auth_svc([OWN_SEAT])
    store = _store({OWN_SEAT: "bidder-own", OTHER_SEAT: "bidder-other"})
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.dependencies.PretargetingRepository",
        _pretargeting_repo({"billing_id": "cfg-other", "bidder_id": "bidder-other"}),
    ):
        with pytest.raises(HTTPException) as exc:
            await require_billing_id_admin("cfg-other", store=store, user=_seat_admin_user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_billing_id_admin_allows_own_config():
    svc = _auth_svc([OWN_SEAT])
    store = _store({OWN_SEAT: "bidder-own"})
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.dependencies.PretargetingRepository",
        _pretargeting_repo({"billing_id": "cfg-own", "bidder_id": "bidder-own"}),
    ):
        assert await require_billing_id_admin("cfg-own", store=store, user=_seat_admin_user()) == "cfg-own"


@pytest.mark.asyncio
async def test_require_billing_id_admin_404s_on_unknown_config():
    svc = _auth_svc([OWN_SEAT])
    store = _store({OWN_SEAT: "bidder-own"})
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.dependencies.PretargetingRepository", _pretargeting_repo(None)
    ):
        with pytest.raises(HTTPException) as exc:
            await require_billing_id_admin("cfg-missing", store=store, user=_seat_admin_user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_billing_id_admin_skips_lookup_for_sudo():
    """Sudo must not require the config to exist locally."""
    repo_factory = _pretargeting_repo(None)
    with patch("api.dependencies.PretargetingRepository", repo_factory):
        assert await require_billing_id_admin("cfg-any", store=None, user=_sudo_user()) == "cfg-any"
    repo_factory.assert_not_called()


# ==================== campaign / creative object access ====================


def _campaigns_service(owner_buyer_ids: list[str]):
    svc = MagicMock()
    svc.get_campaign_buyer_ids = AsyncMock(return_value=owner_buyer_ids)
    return MagicMock(return_value=svc)


def _store_with_creative(buyer_id: str | None):
    store = MagicMock()
    store.get_creative = AsyncMock(
        return_value=(MagicMock(buyer_id=buyer_id) if buyer_id is not None else None)
    )
    return store


@pytest.mark.asyncio
async def test_require_campaign_access_denies_other_buyers_campaign():
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.campaigns_router.get_campaigns_service", _campaigns_service([OTHER_SEAT])
    ):
        with pytest.raises(HTTPException) as exc:
            await require_campaign_access("camp-other", store=MagicMock(), user=_readonly_user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_campaign_access_allows_own_campaign():
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.campaigns_router.get_campaigns_service", _campaigns_service([OWN_SEAT])
    ):
        await require_campaign_access("camp-own", store=MagicMock(), user=_readonly_user())


@pytest.mark.asyncio
async def test_require_campaign_access_denies_unattributable_campaign():
    """A campaign resolving to no buyer is sudo-only, not open to everyone."""
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc), patch(
        "api.campaigns_router.get_campaigns_service", _campaigns_service([])
    ):
        with pytest.raises(HTTPException) as exc:
            await require_campaign_access("camp-orphan", store=MagicMock(), user=_readonly_user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_creative_access_denies_other_buyers_creative():
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await require_creative_access(
                "cr-other", store=_store_with_creative(OTHER_SEAT), user=_readonly_user()
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_creative_access_denies_missing_creative():
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await require_creative_access(
                "cr-missing", store=_store_with_creative(None), user=_readonly_user()
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_creative_access_allows_own_creative():
    svc = _auth_svc(admin_seats=[], read_seats=[OWN_SEAT])
    with patch("api.dependencies.get_auth_service", return_value=svc):
        await require_creative_access(
            "cr-own", store=_store_with_creative(OWN_SEAT), user=_readonly_user()
        )
