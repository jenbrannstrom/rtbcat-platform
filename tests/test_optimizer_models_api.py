"""API tests for BYOM optimizer model registry endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_models as optimizer_models_router


def _model_row(model_id: str = "mdl_1", is_active: bool = True) -> dict:
    return {
        "model_id": model_id,
        "buyer_id": "1111111111",
        "name": "Model A",
        "description": "desc",
        "model_type": "api",
        "endpoint_url": "https://example.com/score",
        "has_auth_header": True,
        "input_schema": {"features": ["spend_usd"]},
        "output_schema": {"score": "float"},
        "is_active": is_active,
        "created_at": "2026-02-28T00:00:00+00:00",
        "updated_at": "2026-02-28T00:00:00+00:00",
    }


class _StubOptimizerModelsService:
    def __init__(self):
        self.list_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.validate_calls: list[dict] = []
        self.not_found_ids: set[str] = {"missing"}

    async def list_models(self, **kwargs):
        self.list_calls.append(kwargs)
        return {
            "rows": [_model_row()],
            "meta": {
                "total": 1,
                "returned": 1,
                "limit": kwargs.get("limit", 100),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def create_model(self, **kwargs):
        self.create_calls.append(kwargs)
        return _model_row(model_id="mdl_created", is_active=kwargs.get("is_active", True))

    async def get_model(self, **kwargs):
        self.get_calls.append(kwargs)
        if kwargs.get("model_id") in self.not_found_ids:
            return None
        return _model_row(model_id=kwargs.get("model_id", "mdl_1"))

    async def update_model(self, **kwargs):
        self.update_calls.append(kwargs)
        if kwargs.get("model_id") in self.not_found_ids:
            return None
        updates = kwargs.get("updates") or {}
        row = _model_row(model_id=kwargs.get("model_id", "mdl_1"))
        row.update({k: v for k, v in updates.items() if k in row})
        return row

    async def validate_model_endpoint(self, **kwargs):
        self.validate_calls.append(kwargs)
        if kwargs.get("model_id") in self.not_found_ids:
            raise ValueError("Model not found")
        return {
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs.get("buyer_id"),
            "valid": True,
            "skipped": False,
            "http_status": 200,
            "message": "Model endpoint validated",
            "response_preview": '{"scores":[]}',
        }


def _build_client(
    stub_service: _StubOptimizerModelsService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(optimizer_models_router.router, prefix="/api")
    app.dependency_overrides[optimizer_models_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_models_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id or "1111111111"

    monkeypatch.setattr(optimizer_models_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_models_router, "OptimizerModelsService", lambda: stub_service)
    return TestClient(app)


def test_list_optimizer_models(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/optimizer/models",
        params={
            "buyer_id": "1111111111",
            "include_inactive": True,
            "limit": 20,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    assert len(stub.list_calls) == 1
    call = stub.list_calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["include_inactive"] is True
    assert call["limit"] == 20
    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert payload["rows"][0]["model_id"] == "mdl_1"


def test_create_optimizer_model(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    response = client.post(
        "/api/optimizer/models",
        json={
            "buyer_id": "1111111111",
            "name": "Model A",
            "description": "desc",
            "model_type": "api",
            "endpoint_url": "https://example.com/score",
            "auth_header_encrypted": "enc",
            "input_schema": {"features": ["spend_usd"]},
            "output_schema": {"score": "float"},
            "is_active": True,
        },
    )

    assert response.status_code == 200
    assert len(stub.create_calls) == 1
    call = stub.create_calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["model_type"] == "api"
    assert call["endpoint_url"] == "https://example.com/score"
    payload = response.json()
    assert payload["model_id"] == "mdl_created"


def test_get_optimizer_model_not_found(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    response = client.get("/api/optimizer/models/missing", params={"buyer_id": "1111111111"})

    assert response.status_code == 404


def test_update_optimizer_model(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    response = client.patch(
        "/api/optimizer/models/mdl_1",
        params={"buyer_id": "1111111111"},
        json={
            "name": "Updated Model",
            "is_active": False,
        },
    )

    assert response.status_code == 200
    assert len(stub.update_calls) == 1
    call = stub.update_calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["updates"]["name"] == "Updated Model"
    payload = response.json()
    assert payload["name"] == "Updated Model"
    assert payload["is_active"] is False


def test_activate_and_deactivate_optimizer_model(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    activate = client.post("/api/optimizer/models/mdl_1/activate", params={"buyer_id": "1111111111"})
    deactivate = client.post(
        "/api/optimizer/models/mdl_1/deactivate",
        params={"buyer_id": "1111111111"},
    )

    assert activate.status_code == 200
    assert deactivate.status_code == 200
    assert len(stub.update_calls) == 2
    assert stub.update_calls[0]["updates"]["is_active"] is True
    assert stub.update_calls[1]["updates"]["is_active"] is False
    assert activate.json()["is_active"] is True
    assert deactivate.json()["is_active"] is False


def test_validate_optimizer_model(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerModelsService()
    client = _build_client(stub, monkeypatch)

    response = client.post(
        "/api/optimizer/models/mdl_1/validate",
        params={"buyer_id": "1111111111", "timeout_seconds": 15},
    )

    assert response.status_code == 200
    assert len(stub.validate_calls) == 1
    call = stub.validate_calls[0]
    assert call["model_id"] == "mdl_1"
    assert call["buyer_id"] == "1111111111"
    assert call["timeout_seconds"] == 15
    payload = response.json()
    assert payload["valid"] is True
    assert payload["http_status"] == 200
