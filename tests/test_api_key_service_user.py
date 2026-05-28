"""API-key automation should have an authenticated service user context."""

from fastapi import Depends, FastAPI

from api.auth import APIKeyAuthMiddleware
from api.dependencies import require_admin
from api.session_middleware import SessionAuthMiddleware
from services.auth_service import User
from services.secrets_manager import get_secrets_manager
from tests.support.asgi_client import SyncASGIClient


def _app_with_auth(monkeypatch) -> FastAPI:
    monkeypatch.setenv("CATSCAN_API_KEY", "test-api-key")
    get_secrets_manager.cache_clear()

    async def multi_user_enabled(_self) -> bool:
        return True

    monkeypatch.setattr(
        SessionAuthMiddleware,
        "_check_multi_user_mode",
        multi_user_enabled,
    )

    app = FastAPI()

    @app.get("/admin-only")
    async def admin_only(user: User = Depends(require_admin)) -> dict[str, str]:
        return {"email": user.email, "role": user.role}

    @app.get("/precompute/health")
    async def precompute_health() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/auth/login")
    async def auth_login() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/agent/v1/probe")
    async def agent_probe() -> dict[str, str]:
        return {"ok": "true"}

    app.add_middleware(APIKeyAuthMiddleware)
    app.add_middleware(SessionAuthMiddleware)
    return app


def test_api_key_auth_attaches_sudo_service_user(monkeypatch) -> None:
    client = SyncASGIClient(_app_with_auth(monkeypatch))

    response = client.get(
        "/admin-only",
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": "api-key@automation.local",
        "role": "sudo",
    }


def test_invalid_api_key_still_rejected(monkeypatch) -> None:
    client = SyncASGIClient(_app_with_auth(monkeypatch))

    response = client.get(
        "/admin-only",
        headers={"Authorization": "Bearer wrong"},
    )

    assert response.status_code == 401


def test_secret_gated_scheduler_paths_bypass_api_key_middleware(monkeypatch) -> None:
    client = SyncASGIClient(_app_with_auth(monkeypatch))

    response = client.get("/precompute/health")

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_password_login_path_bypasses_api_key_middleware(monkeypatch) -> None:
    client = SyncASGIClient(_app_with_auth(monkeypatch))

    response = client.post("/auth/login")

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_agent_api_prefix_bypasses_global_api_key_middleware(monkeypatch) -> None:
    client = SyncASGIClient(_app_with_auth(monkeypatch))

    response = client.get(
        "/agent/v1/probe",
        headers={"Authorization": "Bearer cat_agent_not_global_api_key"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}
