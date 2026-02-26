"""Tests for three-tier RBAC: sudo / local-admin / read-only.

Validates:
- Permission primitives (is_sudo, require_buyer_access_level, etc.)
- Sudo bypass behavior
- Local-admin can admin-mutate for owned seat, denied on other seat
- Read-only user can read, cannot admin-mutate
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.dependencies import (
    is_sudo,
    require_buyer_access_level,
    require_buyer_admin_access,
    require_seat_admin_or_sudo,
)
from services.auth_service import User, UserBuyerSeatPermission


def _sudo_user() -> User:
    return User(id="sudo-1", email="cat-scan@rtb.cat", role="admin")


def _local_admin_user() -> User:
    """User with admin access to buyer 299038253 (TUKY) only."""
    return User(id="dea-1", email="dea@rtb.cat", role="user")


def _readonly_user() -> User:
    """User with read access to buyer 299038253 (TUKY) only."""
    return User(id="ro-1", email="readonly@rtb.cat", role="user")


def _tuky_admin_perm() -> UserBuyerSeatPermission:
    return UserBuyerSeatPermission(
        id="perm-1", user_id="dea-1", buyer_id="299038253", access_level="admin"
    )


def _tuky_read_perm() -> UserBuyerSeatPermission:
    return UserBuyerSeatPermission(
        id="perm-2", user_id="ro-1", buyer_id="299038253", access_level="read"
    )


# ==================== is_sudo ====================


def test_is_sudo_admin():
    assert is_sudo(_sudo_user()) is True


def test_is_sudo_regular_user():
    assert is_sudo(_local_admin_user()) is False
    assert is_sudo(_readonly_user()) is False


# ==================== require_buyer_access_level ====================


def _mock_auth_svc(perms: list[UserBuyerSeatPermission]):
    svc = MagicMock()
    svc.get_user_buyer_seat_permissions = AsyncMock(return_value=perms)
    svc.get_user_buyer_seat_ids = AsyncMock(
        side_effect=lambda uid, min_access_level="read": [
            p.buyer_id for p in perms if (
                ["read", "admin"].index(p.access_level) >= ["read", "admin"].index(min_access_level)
            )
        ]
    )
    return svc


@pytest.mark.asyncio
async def test_sudo_bypasses_all_access_checks():
    """Sudo user bypasses buyer access level checks."""
    # Should not raise for any buyer or level
    await require_buyer_access_level("299038253", "admin", _sudo_user())
    await require_buyer_access_level("999999", "admin", _sudo_user())
    await require_buyer_access_level("000000", "read", _sudo_user())


@pytest.mark.asyncio
async def test_local_admin_can_admin_own_seat():
    """Local-admin can access their seat at admin level."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_admin_perm()])):
        await require_buyer_access_level("299038253", "admin", _local_admin_user())


@pytest.mark.asyncio
async def test_local_admin_can_read_own_seat():
    """Local-admin can also read their seat (admin implies read)."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_admin_perm()])):
        await require_buyer_access_level("299038253", "read", _local_admin_user())


@pytest.mark.asyncio
async def test_local_admin_denied_other_seat():
    """Local-admin cannot access a seat they don't have permission for."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_admin_perm()])):
        with pytest.raises(HTTPException) as exc_info:
            await require_buyer_access_level("999999", "admin", _local_admin_user())
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_readonly_can_read_own_seat():
    """Read-only user can read their seat."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_read_perm()])):
        await require_buyer_access_level("299038253", "read", _readonly_user())


@pytest.mark.asyncio
async def test_readonly_denied_admin_own_seat():
    """Read-only user cannot admin-mutate their seat."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_read_perm()])):
        with pytest.raises(HTTPException) as exc_info:
            await require_buyer_access_level("299038253", "admin", _readonly_user())
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_readonly_denied_other_seat():
    """Read-only user cannot access a seat they don't have permission for."""
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_read_perm()])):
        with pytest.raises(HTTPException) as exc_info:
            await require_buyer_access_level("999999", "read", _readonly_user())
        assert exc_info.value.status_code == 403


# ==================== require_buyer_admin_access ====================


@pytest.mark.asyncio
async def test_require_buyer_admin_access_sudo():
    await require_buyer_admin_access("anything", _sudo_user())


@pytest.mark.asyncio
async def test_require_buyer_admin_access_local_admin():
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_admin_perm()])):
        await require_buyer_admin_access("299038253", _local_admin_user())


@pytest.mark.asyncio
async def test_require_buyer_admin_access_readonly_denied():
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_read_perm()])):
        with pytest.raises(HTTPException) as exc_info:
            await require_buyer_admin_access("299038253", _readonly_user())
        assert exc_info.value.status_code == 403


# ==================== require_seat_admin_or_sudo ====================


@pytest.mark.asyncio
async def test_require_seat_admin_or_sudo_for_sudo():
    result = await require_seat_admin_or_sudo(_sudo_user())
    assert result.role == "admin"


@pytest.mark.asyncio
async def test_require_seat_admin_or_sudo_for_local_admin():
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_admin_perm()])):
        result = await require_seat_admin_or_sudo(_local_admin_user())
        assert result.role == "user"


@pytest.mark.asyncio
async def test_require_seat_admin_or_sudo_denied_for_readonly():
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([_tuky_read_perm()])):
        with pytest.raises(HTTPException) as exc_info:
            await require_seat_admin_or_sudo(_readonly_user())
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_seat_admin_or_sudo_denied_for_no_perms():
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc([])):
        with pytest.raises(HTTPException) as exc_info:
            await require_seat_admin_or_sudo(_readonly_user())
        assert exc_info.value.status_code == 403
