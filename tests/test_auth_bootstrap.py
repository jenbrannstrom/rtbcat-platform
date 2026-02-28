"""Tests for bootstrap guard and /auth/bootstrap endpoint."""

import os
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth_bootstrap import (
    is_bootstrap_token_required,
    is_bootstrap_completed,
    _auto_heal_bootstrap_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_user(user_id="u1", email="admin@test.com", role="sudo"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.display_name = "Admin"
    user.role = role
    return user


def _make_auth_service(user_count=0, existing_user=None, bootstrap_completed="0"):
    """Build a mock AuthService."""
    svc = AsyncMock()
    svc.count_users = AsyncMock(return_value=user_count)
    svc.get_user_by_email = AsyncMock(return_value=existing_user)
    svc.create_user = AsyncMock(side_effect=lambda **kw: _make_fake_user(
        user_id=kw.get("user_id", "u1"),
        email=kw.get("email", "admin@test.com"),
        role=kw.get("role", "sudo"),
    ))
    svc.create_session = AsyncMock()
    svc.log_audit = AsyncMock()
    svc.get_setting = AsyncMock(return_value=bootstrap_completed)
    svc.set_setting = AsyncMock()

    return svc


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestIsBootstrapTokenRequired:
    def test_returns_true_when_set(self):
        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "abc123"}):
            assert is_bootstrap_token_required() is True

    def test_returns_false_when_empty(self):
        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": ""}):
            assert is_bootstrap_token_required() is False

    def test_returns_false_when_unset(self):
        env = os.environ.copy()
        env.pop("CATSCAN_BOOTSTRAP_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_bootstrap_token_required() is False


class TestIsBootstrapCompleted:
    @pytest.mark.asyncio
    async def test_completed(self):
        svc = _make_auth_service(bootstrap_completed="1")
        with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
            assert await is_bootstrap_completed() is True

    @pytest.mark.asyncio
    async def test_not_completed(self):
        svc = _make_auth_service(bootstrap_completed="0")
        with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
            assert await is_bootstrap_completed() is False


class TestAutoHealBootstrapStatus:
    @pytest.mark.asyncio
    async def test_heals_when_users_exist_and_not_completed(self):
        svc = _make_auth_service(user_count=3, bootstrap_completed="0")
        with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
            await _auto_heal_bootstrap_status()
            svc.set_setting.assert_called_once_with(
                "bootstrap_completed", "1", updated_by="auto_heal"
            )

    @pytest.mark.asyncio
    async def test_no_op_when_already_completed(self):
        svc = _make_auth_service(user_count=3, bootstrap_completed="1")
        with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
            await _auto_heal_bootstrap_status()
            svc.set_setting.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_op_when_no_users(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
            await _auto_heal_bootstrap_status()
            svc.set_setting.assert_not_called()


# ---------------------------------------------------------------------------
# Integration-style tests for /auth/bootstrap endpoint
# ---------------------------------------------------------------------------


def _build_test_client(auth_svc):
    """Build a minimal FastAPI test client with the bootstrap router."""
    from fastapi import FastAPI
    from api.auth_bootstrap import router

    app = FastAPI()
    app.include_router(router)

    with patch("api.auth_bootstrap._get_auth_service", return_value=auth_svc):
        yield TestClient(app)


class TestBootstrapEndpoint:
    def test_creates_admin_with_valid_token(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        token = "valid-token-abc"

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": token}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                from fastapi import FastAPI
                from api.auth_bootstrap import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post("/auth/bootstrap", json={
                    "bootstrap_token": token,
                    "email": "admin@test.com",
                    "password": "securepassword123",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user"]["role"] == "sudo"
        svc.create_user.assert_called_once()
        svc.set_setting.assert_called_once_with(
            "bootstrap_completed", "1", updated_by=ANY,
        )

    def test_wrong_token_returns_403(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "correct-token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                from fastapi import FastAPI
                from api.auth_bootstrap import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post("/auth/bootstrap", json={
                    "bootstrap_token": "wrong-token",
                    "email": "admin@test.com",
                })

        assert resp.status_code == 403
        assert "Invalid bootstrap token" in resp.json()["detail"]
        svc.create_user.assert_not_called()

    def test_already_bootstrapped_returns_403(self):
        svc = _make_auth_service(user_count=1, bootstrap_completed="1")

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                from fastapi import FastAPI
                from api.auth_bootstrap import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post("/auth/bootstrap", json={
                    "bootstrap_token": "token",
                    "email": "admin@test.com",
                })

        assert resp.status_code == 403
        assert "already completed" in resp.json()["detail"]

    def test_users_exist_returns_403(self):
        svc = _make_auth_service(user_count=5, bootstrap_completed="0")

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                from fastapi import FastAPI
                from api.auth_bootstrap import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post("/auth/bootstrap", json={
                    "bootstrap_token": "token",
                    "email": "admin@test.com",
                })

        assert resp.status_code == 403
        assert "Users already exist" in resp.json()["detail"]

    def test_no_token_configured_returns_403(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        env = os.environ.copy()
        env.pop("CATSCAN_BOOTSTRAP_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                from fastapi import FastAPI
                from api.auth_bootstrap import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post("/auth/bootstrap", json={
                    "bootstrap_token": "anything",
                    "email": "admin@test.com",
                })

        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Guard integration tests (OAuth2 Proxy path)
# ---------------------------------------------------------------------------


class TestOAuth2ProxyBootstrapGuard:
    @pytest.mark.asyncio
    async def test_first_user_blocked_when_token_set(self):
        """OAuth2 auto-create should be blocked when bootstrap token is set."""
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                assert is_bootstrap_token_required() is True
                assert await is_bootstrap_completed() is False
                # The guard logic: if count==0 and token required and not completed -> block
                user_count = await svc.count_users()
                assert user_count == 0
                should_block = (
                    user_count == 0
                    and is_bootstrap_token_required()
                    and not await is_bootstrap_completed()
                )
                assert should_block is True

    @pytest.mark.asyncio
    async def test_first_user_allowed_when_no_token(self):
        """OAuth2 auto-create should work normally when no bootstrap token."""
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        env = os.environ.copy()
        env.pop("CATSCAN_BOOTSTRAP_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                assert is_bootstrap_token_required() is False
                # No guard: first user can auto-create
                should_block = (
                    (await svc.count_users()) == 0
                    and is_bootstrap_token_required()
                    and not await is_bootstrap_completed()
                )
                assert should_block is False
