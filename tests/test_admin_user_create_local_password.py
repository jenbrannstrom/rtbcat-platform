import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from services.admin_service import AdminService
from services.auth_service import User


def _make_admin() -> User:
    return User(id="admin-1", email="admin@example.com", role="admin")


def _make_created_user(email: str = "new@example.com", role: str = "user") -> User:
    return User(id="created-user", email=email, role=role, display_name="New User", default_language="en")


@pytest.mark.asyncio
async def test_create_user_with_local_password_stores_hash_and_audits_method():
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=None)
    auth.create_user = AsyncMock(return_value=_make_created_user())
    auth.log_audit = AsyncMock()
    auth.set_user_password_hash = AsyncMock()

    password_writer = AsyncMock()
    svc = AdminService(
        auth_service=auth,
        repo=MagicMock(),
        password_hasher=lambda value: f"hashed::{value}",
        password_hash_writer=password_writer,
    )

    result = await svc.create_user(
        admin=_make_admin(),
        email="New@Example.com",
        display_name="New User",
        role="user",
        default_language="en",
        auth_method="local-password",
        password="password123",
        client_ip="127.0.0.1",
    )

    created_user_id = auth.create_user.await_args.kwargs["user_id"]
    password_writer.assert_awaited_once_with(created_user_id, "hashed::password123")
    assert "local password" in result["message"].lower()

    audit_details = json.loads(auth.log_audit.await_args.kwargs["details"])
    assert audit_details["auth_method"] == "local-password"


@pytest.mark.asyncio
async def test_create_user_rejects_local_password_when_missing():
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=None)
    auth.create_user = AsyncMock()
    auth.log_audit = AsyncMock()

    svc = AdminService(auth_service=auth, repo=MagicMock())

    with pytest.raises(HTTPException) as exc:
        await svc.create_user(
            admin=_make_admin(),
            email="new@example.com",
            display_name=None,
            role="user",
            default_language="en",
            auth_method="local-password",
            password=None,
            client_ip=None,
        )

    assert exc.value.status_code == 400
    assert "Password is required" in exc.value.detail
    auth.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_rejects_short_local_password():
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=None)
    auth.create_user = AsyncMock()
    auth.log_audit = AsyncMock()

    svc = AdminService(auth_service=auth, repo=MagicMock())

    with pytest.raises(HTTPException) as exc:
        await svc.create_user(
            admin=_make_admin(),
            email="new@example.com",
            display_name=None,
            role="user",
            default_language="en",
            auth_method="local-password",
            password="short",
            client_ip=None,
        )

    assert exc.value.status_code == 400
    assert "at least 8 characters" in exc.value.detail
    auth.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_legacy_default_remains_oauth_precreate():
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=None)
    auth.create_user = AsyncMock(return_value=_make_created_user())
    auth.log_audit = AsyncMock()

    svc = AdminService(auth_service=auth, repo=MagicMock())

    result = await svc.create_user(
        admin=_make_admin(),
        email="legacy@example.com",
        display_name=None,
        role="user",
        default_language="en",
        auth_method=None,
        password=None,
        client_ip=None,
    )

    assert "external authentication" in result["message"].lower()
    audit_details = json.loads(auth.log_audit.await_args.kwargs["details"])
    assert audit_details["auth_method"] == "oauth-precreate"


@pytest.mark.asyncio
async def test_create_user_rejects_password_for_oauth_precreate():
    auth = MagicMock()
    auth.get_user_by_email = AsyncMock(return_value=None)
    auth.create_user = AsyncMock()
    auth.log_audit = AsyncMock()

    svc = AdminService(auth_service=auth, repo=MagicMock())

    with pytest.raises(HTTPException) as exc:
        await svc.create_user(
            admin=_make_admin(),
            email="legacy@example.com",
            display_name=None,
            role="user",
            default_language="en",
            auth_method="oauth-precreate",
            password="password123",
            client_ip=None,
        )

    assert exc.value.status_code == 400
    assert "Password is only allowed" in exc.value.detail
