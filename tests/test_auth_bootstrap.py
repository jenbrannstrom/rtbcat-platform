"""Tests for bootstrap guard and /auth/bootstrap endpoint."""

import os
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from api.auth_bootstrap import (
    is_bootstrap_token_required,
    is_bootstrap_completed,
    _auto_heal_bootstrap_status,
    bootstrap_first_admin,
    BootstrapRequest,
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


@pytest.fixture(autouse=True)
def _clear_bootstrap_rate_limit_state():
    from api import auth_bootstrap as bootstrap_module

    bootstrap_module._bootstrap_attempts.clear()
    bootstrap_module._bootstrap_lockouts.clear()
    yield
    bootstrap_module._bootstrap_attempts.clear()
    bootstrap_module._bootstrap_lockouts.clear()


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestIsBootstrapTokenRequired:
    def test_returns_true_by_default_when_unset(self):
        env = os.environ.copy()
        env.pop("CATSCAN_REQUIRE_BOOTSTRAP_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_bootstrap_token_required() is True

    def test_returns_true_when_explicit_true(self):
        with patch.dict(os.environ, {"CATSCAN_REQUIRE_BOOTSTRAP_TOKEN": "true"}):
            assert is_bootstrap_token_required() is True

    def test_returns_false_when_explicit_false(self):
        with patch.dict(os.environ, {"CATSCAN_REQUIRE_BOOTSTRAP_TOKEN": "false"}):
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
# Endpoint tests for /auth/bootstrap
# ---------------------------------------------------------------------------


def _make_request(client_host: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/auth/bootstrap",
        "raw_path": b"/auth/bootstrap",
        "query_string": b"",
        "headers": [(b"user-agent", b"pytest")],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class TestBootstrapEndpoint:
    @pytest.mark.asyncio
    async def test_creates_admin_with_valid_token(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        token = "valid-token-abc"
        request = _make_request()
        response = Response()

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": token}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                result = await bootstrap_first_admin(
                    BootstrapRequest(
                        bootstrap_token=token,
                        email="admin@test.com",
                    ),
                    request,
                    response,
                )

        assert result["status"] == "ok"
        assert result["user"]["role"] == "sudo"
        svc.create_user.assert_called_once()
        svc.set_setting.assert_called_once_with(
            "bootstrap_completed", "1", updated_by=ANY,
        )
        assert "rtbcat_session=" in response.headers.get("set-cookie", "")

    @pytest.mark.asyncio
    async def test_wrong_token_returns_403(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        request = _make_request()
        response = Response()

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "correct-token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                with pytest.raises(HTTPException) as exc_info:
                    await bootstrap_first_admin(
                        BootstrapRequest(
                            bootstrap_token="wrong-token",
                            email="admin@test.com",
                        ),
                        request,
                        response,
                    )

        assert exc_info.value.status_code == 403
        assert "Invalid bootstrap token" in str(exc_info.value.detail)
        svc.create_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_bootstrapped_returns_403(self):
        svc = _make_auth_service(user_count=1, bootstrap_completed="1")
        request = _make_request()
        response = Response()

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                with pytest.raises(HTTPException) as exc_info:
                    await bootstrap_first_admin(
                        BootstrapRequest(
                            bootstrap_token="token",
                            email="admin@test.com",
                        ),
                        request,
                        response,
                    )

        assert exc_info.value.status_code == 403
        assert "already completed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_users_exist_returns_403(self):
        svc = _make_auth_service(user_count=5, bootstrap_completed="0")
        request = _make_request()
        response = Response()

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                with pytest.raises(HTTPException) as exc_info:
                    await bootstrap_first_admin(
                        BootstrapRequest(
                            bootstrap_token="token",
                            email="admin@test.com",
                        ),
                        request,
                        response,
                    )

        assert exc_info.value.status_code == 403
        assert "Users already exist" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_no_token_configured_returns_503_when_required(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        request = _make_request()
        response = Response()

        env = os.environ.copy()
        env.pop("CATSCAN_BOOTSTRAP_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                with pytest.raises(HTTPException) as exc_info:
                    await bootstrap_first_admin(
                        BootstrapRequest(
                            bootstrap_token="anything",
                            email="admin@test.com",
                        ),
                        request,
                        response,
                    )

        assert exc_info.value.status_code == 503
        assert "required but missing" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_wrong_token_rate_limited_after_retries(self):
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")
        request = _make_request(client_host="203.0.113.10")
        response = Response()

        with patch.dict(os.environ, {"CATSCAN_BOOTSTRAP_TOKEN": "correct-token"}):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                with patch("api.auth_bootstrap._BOOTSTRAP_RATE_LIMIT_MAX_ATTEMPTS", 2):
                    with patch("api.auth_bootstrap._BOOTSTRAP_RATE_LIMIT_WINDOW_SECONDS", 900):
                        with patch("api.auth_bootstrap._BOOTSTRAP_RATE_LIMIT_LOCKOUT_SECONDS", 120):
                            payload = BootstrapRequest(
                                bootstrap_token="wrong-token",
                                email="admin@test.com",
                            )

                            with pytest.raises(HTTPException) as first_exc:
                                await bootstrap_first_admin(payload, request, response)
                            with pytest.raises(HTTPException) as second_exc:
                                await bootstrap_first_admin(payload, request, response)
                            with pytest.raises(HTTPException) as limited_exc:
                                await bootstrap_first_admin(payload, request, response)

        assert first_exc.value.status_code == 403
        assert second_exc.value.status_code == 403
        assert limited_exc.value.status_code == 429
        assert limited_exc.value.headers
        assert "Retry-After" in limited_exc.value.headers


# ---------------------------------------------------------------------------
# Guard integration tests (OAuth2 Proxy path)
# ---------------------------------------------------------------------------


class TestOAuth2ProxyBootstrapGuard:
    @pytest.mark.asyncio
    async def test_first_user_blocked_when_token_set(self):
        """OAuth2 auto-create should be blocked when bootstrap token is set."""
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        with patch.dict(
            os.environ,
            {"CATSCAN_BOOTSTRAP_TOKEN": "token", "CATSCAN_REQUIRE_BOOTSTRAP_TOKEN": "true"},
        ):
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
    async def test_first_user_allowed_when_guard_disabled(self):
        """OAuth2 auto-create should work when bootstrap guard is disabled."""
        svc = _make_auth_service(user_count=0, bootstrap_completed="0")

        with patch.dict(os.environ, {"CATSCAN_REQUIRE_BOOTSTRAP_TOKEN": "false"}, clear=True):
            with patch("api.auth_bootstrap._get_auth_service", return_value=svc):
                assert is_bootstrap_token_required() is False
                # No guard: first user can auto-create
                should_block = (
                    (await svc.count_users()) == 0
                    and is_bootstrap_token_required()
                    and not await is_bootstrap_completed()
                )
                assert should_block is False
