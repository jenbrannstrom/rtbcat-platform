import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.routing import APIRoute
from starlette.requests import Request

from api import auth_authing, session_middleware
from api.routers.admin import router
from api.session_middleware import SessionAuthMiddleware
from services.admin_service import AdminService
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


def _admin() -> User:
    return User(id="admin-1", email="admin@example.com", role="sudo")


def _target(*, active: bool = True) -> User:
    return User(
        id="user-1",
        email="user@example.com",
        display_name="Example User",
        role="read",
        is_active=active,
    )


@pytest.mark.asyncio
async def test_admin_can_set_local_password_and_existing_sessions_are_revoked():
    auth = MagicMock()
    auth.get_user_by_id = AsyncMock(return_value=_target())
    auth.delete_user_sessions = AsyncMock(return_value=2)
    auth.log_audit = AsyncMock()
    password_writer = AsyncMock()

    service = AdminService(
        auth_service=auth,
        repo=MagicMock(),
        password_hasher=lambda value: f"hashed::{value}",
        password_hash_writer=password_writer,
    )

    result = await service.reset_user_password(
        admin=_admin(),
        user_id="user-1",
        password="a-new-password",
        client_ip="127.0.0.1",
    )

    password_writer.assert_awaited_once_with("user-1", "hashed::a-new-password")
    auth.delete_user_sessions.assert_awaited_once_with("user-1")
    assert result["sessions_deleted"] == 2

    audit_call = auth.log_audit.await_args.kwargs
    assert audit_call["action"] == "reset_password"
    assert audit_call["resource_id"] == "user-1"
    details = json.loads(audit_call["details"])
    assert details == {"email": "user@example.com", "sessions_deleted": 2}
    assert "password" not in audit_call["details"]


@pytest.mark.asyncio
async def test_admin_password_reset_rejects_short_password_before_writing():
    auth = MagicMock()
    auth.get_user_by_id = AsyncMock(return_value=_target())
    auth.delete_user_sessions = AsyncMock()
    auth.log_audit = AsyncMock()
    password_writer = AsyncMock()
    service = AdminService(
        auth_service=auth,
        repo=MagicMock(),
        password_hasher=lambda value: f"hashed::{value}",
        password_hash_writer=password_writer,
    )

    with pytest.raises(HTTPException) as exc:
        await service.reset_user_password(
            admin=_admin(),
            user_id="user-1",
            password="short",
            client_ip=None,
        )

    assert exc.value.status_code == 400
    password_writer.assert_not_awaited()
    auth.delete_user_sessions.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_user_updates_status_and_revokes_sessions():
    auth = MagicMock()
    auth.get_user_by_id = AsyncMock(return_value=_target())
    auth.update_user = AsyncMock(return_value=True)
    auth.delete_user_sessions = AsyncMock(return_value=1)
    auth.log_audit = AsyncMock()
    service = AdminService(auth_service=auth, repo=MagicMock())

    result = await service.deactivate_user(
        admin=_admin(),
        user_id="user-1",
        client_ip="127.0.0.1",
    )

    auth.update_user.assert_awaited_once_with(user_id="user-1", is_active=False)
    auth.delete_user_sessions.assert_awaited_once_with("user-1")
    assert result["status"] == "success"


def test_deactivate_route_uses_documented_post_contract_and_keeps_legacy_delete():
    methods_by_path = {
        route.path: route.methods
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert "POST" in methods_by_path["/admin/users/{user_id}/deactivate"]
    assert "DELETE" in methods_by_path["/admin/users/{user_id}"]


def test_inactive_user_cannot_reauthenticate_through_oauth_proxy(monkeypatch):
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=_target(active=False))
    monkeypatch.setattr(session_middleware, "get_auth_service", lambda: auth)
    monkeypatch.setattr(session_middleware, "is_oauth2_proxy_enabled", lambda: True)
    monkeypatch.setattr(session_middleware, "_is_trusted_proxy_client", lambda _request: True)

    app = FastAPI()

    @app.get("/protected")
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(SessionAuthMiddleware)
    response = SyncASGIClient(app).get(
        "/protected",
        headers={"X-Email": "user@example.com"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated. Contact an administrator."


@pytest.mark.asyncio
async def test_inactive_user_cannot_reauthenticate_through_authing(monkeypatch):
    class FakeHttpResponse:
        status_code = 200

        def __init__(self, payload: dict[str, str]) -> None:
            self._payload = payload

        def json(self) -> dict[str, str]:
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeHttpResponse({"access_token": "token"})

        async def get(self, *_args, **_kwargs):
            return FakeHttpResponse({"email": "user@example.com"})

    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=_target(active=False))
    auth.update_last_login = AsyncMock()
    auth.create_session = AsyncMock()
    monkeypatch.setattr(auth_authing, "is_authing_login_enabled", lambda: True)
    monkeypatch.setattr(auth_authing, "get_auth_service", lambda: auth)
    monkeypatch.setattr(
        auth_authing,
        "get_authing_config",
        lambda: {
            "app_id": "app",
            "app_secret": "secret",
            "token_endpoint": "https://auth.example/token",
            "userinfo_endpoint": "https://auth.example/me",
        },
    )
    monkeypatch.setattr(auth_authing.httpx, "AsyncClient", FakeAsyncClient)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/auth/authing/callback",
        "raw_path": b"/auth/authing/callback",
        "query_string": b"",
        "headers": [
            (b"host", b"scan.rtb.cat"),
            (b"cookie", b"rtbcat_auth_state=state|/"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("scan.rtb.cat", 443),
    }

    result = await auth_authing.authing_callback(
        request=Request(scope),
        response=Response(),
        code="code",
        state="state",
    )

    assert result.status_code == 302
    assert "Account+is+deactivated" in result.headers["location"]
    auth.update_last_login.assert_not_awaited()
    auth.create_session.assert_not_awaited()
