from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response

from api import auth_password
from services.auth_service import User


def _legacy_hash(password: str, salt_hex: str = "11" * 32) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000).hex()
    return f"{salt_hex}:{digest}"


def _request() -> SimpleNamespace:
    return SimpleNamespace(headers={"User-Agent": "pytest"}, state=SimpleNamespace())


@pytest.mark.asyncio
async def test_login_accepts_legacy_pbkdf2_hash_and_upgrades_to_bcrypt(monkeypatch: pytest.MonkeyPatch):
    auth = MagicMock()
    user = User(id="user-1", email="cat-scan@rtb.cat", role="sudo", is_active=True)
    auth.get_user_by_email = AsyncMock(return_value=user)
    auth.update_last_login = AsyncMock()
    auth.create_session = AsyncMock()
    auth.log_audit = AsyncMock()

    stored_hash = _legacy_hash("password123!")
    upgraded_hashes: list[str] = []

    async def fake_set_password_hash(user_id: str, password_hash: str) -> None:
        assert user_id == user.id
        upgraded_hashes.append(password_hash)

    monkeypatch.setattr(auth_password, "get_auth_service", lambda: auth)
    monkeypatch.setattr(auth_password, "_get_user_password_hash", AsyncMock(return_value=stored_hash))
    monkeypatch.setattr(auth_password, "_set_user_password_hash", fake_set_password_hash)
    monkeypatch.setattr(auth_password, "_get_client_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(auth_password, "_is_secure_request", lambda request: True)
    monkeypatch.setattr(auth_password, "is_password_login_enabled", lambda: True)
    monkeypatch.setattr(auth_password, "hash_password", lambda value: f"$2stub${value}")

    response = Response()
    result = await auth_password.login(
        _request(),
        response,
        auth_password.LoginRequest(email="cat-scan@rtb.cat", password="password123!"),
    )

    assert result.status == "success"
    assert upgraded_hashes
    assert upgraded_hashes[0].startswith("$2stub$")
    auth.update_last_login.assert_awaited_once_with(user.id)
    auth.create_session.assert_awaited_once()
    assert "rtbcat_session=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_login_accepts_long_legacy_password_and_upgrades_to_bcrypt_sha256(
    monkeypatch: pytest.MonkeyPatch,
):
    auth = MagicMock()
    user = User(id="user-1", email="cat-scan@rtb.cat", role="sudo", is_active=True)
    auth.get_user_by_email = AsyncMock(return_value=user)
    auth.update_last_login = AsyncMock()
    auth.create_session = AsyncMock()
    auth.log_audit = AsyncMock()

    long_password = "L" * 80 + "!correct"
    stored_hash = _legacy_hash(long_password)
    upgraded_hashes: list[str] = []

    async def fake_set_password_hash(user_id: str, password_hash: str) -> None:
        assert user_id == user.id
        upgraded_hashes.append(password_hash)

    monkeypatch.setattr(auth_password, "get_auth_service", lambda: auth)
    monkeypatch.setattr(auth_password, "_get_user_password_hash", AsyncMock(return_value=stored_hash))
    monkeypatch.setattr(auth_password, "_set_user_password_hash", fake_set_password_hash)
    monkeypatch.setattr(auth_password, "_get_client_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(auth_password, "_is_secure_request", lambda request: True)
    monkeypatch.setattr(auth_password, "is_password_login_enabled", lambda: True)

    response = Response()
    result = await auth_password.login(
        _request(),
        response,
        auth_password.LoginRequest(email="cat-scan@rtb.cat", password=long_password),
    )

    assert result.status == "success"
    assert upgraded_hashes
    valid, needs_upgrade = auth_password.verify_password(long_password, upgraded_hashes[0])
    assert valid is True
    assert needs_upgrade is False
    auth.update_last_login.assert_awaited_once_with(user.id)
    auth.create_session.assert_awaited_once()
    assert "rtbcat_session=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_legacy_hash_without_500(monkeypatch: pytest.MonkeyPatch):
    auth = MagicMock()
    user = User(id="user-1", email="cat-scan@rtb.cat", role="sudo", is_active=True)
    auth.get_user_by_email = AsyncMock(return_value=user)
    auth.log_audit = AsyncMock()

    monkeypatch.setattr(auth_password, "get_auth_service", lambda: auth)
    monkeypatch.setattr(auth_password, "_get_user_password_hash", AsyncMock(return_value=_legacy_hash("correct-password")))
    monkeypatch.setattr(auth_password, "_set_user_password_hash", AsyncMock())
    monkeypatch.setattr(auth_password, "_get_client_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(auth_password, "_is_secure_request", lambda request: True)
    monkeypatch.setattr(auth_password, "is_password_login_enabled", lambda: True)

    with pytest.raises(HTTPException) as exc:
        await auth_password.login(
            _request(),
            Response(),
            auth_password.LoginRequest(email="cat-scan@rtb.cat", password="wrong-password"),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"
    auth.log_audit.assert_awaited_once()


def test_verify_password_handles_unknown_hash_without_raising() -> None:
    valid, needs_upgrade = auth_password.verify_password("password123!", _legacy_hash("password123!"))
    assert valid is True
    assert needs_upgrade is True

    valid, needs_upgrade = auth_password.verify_password("password123!", "not-a-real-hash")
    assert valid is False
    assert needs_upgrade is False
