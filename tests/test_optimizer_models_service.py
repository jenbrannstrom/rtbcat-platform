"""Tests for BYOM optimizer model registry service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.optimizer_models_service import OptimizerModelsService


@pytest.mark.asyncio
async def test_create_model_requires_endpoint_for_api():
    service = OptimizerModelsService()
    with pytest.raises(ValueError, match="endpoint_url is required"):
        await service.create_model(
            buyer_id="1111111111",
            name="Model A",
            model_type="api",
            endpoint_url=None,
        )


@pytest.mark.asyncio
async def test_create_model_shapes_response(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "INSERT INTO optimization_models" in sql
        assert params[1] == "1111111111"
        assert params[2] == "Model A"
        return {
            "model_id": "mdl_abc",
            "buyer_id": "1111111111",
            "name": "Model A",
            "description": "desc",
            "model_type": "api",
            "endpoint_url": "https://example.com/score",
            "auth_header_encrypted": "enc",
            "input_schema": {"features": ["spend_usd"]},
            "output_schema": {"score": "float"},
            "is_active": True,
            "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
        }

    monkeypatch.setattr("services.optimizer_models_service.pg_query_one", _stub_query_one)
    service = OptimizerModelsService()
    payload = await service.create_model(
        buyer_id="1111111111",
        name="Model A",
        description="desc",
        model_type="api",
        endpoint_url="https://example.com/score",
        auth_header_encrypted="enc",
        input_schema={"features": ["spend_usd"]},
        output_schema={"score": "float"},
    )

    assert payload["model_id"] == "mdl_abc"
    assert payload["buyer_id"] == "1111111111"
    assert payload["has_auth_header"] is True
    assert payload["input_schema"]["features"] == ["spend_usd"]
    assert payload["is_active"] is True


@pytest.mark.asyncio
async def test_list_models_returns_rows_and_meta(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM optimization_models" in sql
        return [
            {
                "model_id": "mdl_1",
                "buyer_id": "1111111111",
                "name": "Model A",
                "description": None,
                "model_type": "rules",
                "endpoint_url": None,
                "auth_header_encrypted": None,
                "input_schema": {},
                "output_schema": {},
                "is_active": True,
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {"total_rows": 1}

    monkeypatch.setattr("services.optimizer_models_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_models_service.pg_query_one", _stub_query_one)
    service = OptimizerModelsService()
    payload = await service.list_models(
        buyer_id="1111111111",
        include_inactive=False,
        limit=20,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    assert payload["rows"][0]["model_id"] == "mdl_1"
    assert payload["rows"][0]["model_type"] == "rules"


@pytest.mark.asyncio
async def test_update_model_enforces_endpoint_for_api(monkeypatch: pytest.MonkeyPatch):
    async def _stub_get_model(self, *, model_id: str, buyer_id=None):
        return {
            "model_id": model_id,
            "buyer_id": "1111111111",
            "name": "Existing",
            "description": None,
            "model_type": "rules",
            "endpoint_url": None,
            "has_auth_header": False,
            "input_schema": {},
            "output_schema": {},
            "is_active": True,
            "created_at": "2026-02-28T00:00:00+00:00",
            "updated_at": "2026-02-28T00:00:00+00:00",
        }

    monkeypatch.setattr(OptimizerModelsService, "get_model", _stub_get_model)
    service = OptimizerModelsService()

    with pytest.raises(ValueError, match="endpoint_url is required"):
        await service.update_model(
            model_id="mdl_1",
            buyer_id="1111111111",
            updates={"model_type": "api", "endpoint_url": ""},
        )


@pytest.mark.asyncio
async def test_update_model_returns_updated_row(monkeypatch: pytest.MonkeyPatch):
    async def _stub_get_model(self, *, model_id: str, buyer_id=None):
        return {
            "model_id": model_id,
            "buyer_id": "1111111111",
            "name": "Existing",
            "description": "old",
            "model_type": "api",
            "endpoint_url": "https://example.com/score",
            "has_auth_header": False,
            "input_schema": {},
            "output_schema": {},
            "is_active": True,
            "created_at": "2026-02-28T00:00:00+00:00",
            "updated_at": "2026-02-28T00:00:00+00:00",
        }

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "UPDATE optimization_models" in sql
        return {
            "model_id": "mdl_1",
            "buyer_id": "1111111111",
            "name": "Updated",
            "description": "new",
            "model_type": "api",
            "endpoint_url": "https://example.com/new-score",
            "auth_header_encrypted": None,
            "input_schema": {"foo": "bar"},
            "output_schema": {"score": "float"},
            "is_active": False,
            "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(OptimizerModelsService, "get_model", _stub_get_model)
    monkeypatch.setattr("services.optimizer_models_service.pg_query_one", _stub_query_one)
    service = OptimizerModelsService()
    payload = await service.update_model(
        model_id="mdl_1",
        buyer_id="1111111111",
        updates={
            "name": "Updated",
            "description": "new",
            "endpoint_url": "https://example.com/new-score",
            "input_schema": {"foo": "bar"},
            "output_schema": {"score": "float"},
            "is_active": False,
        },
    )

    assert payload is not None
    assert payload["name"] == "Updated"
    assert payload["endpoint_url"] == "https://example.com/new-score"
    assert payload["is_active"] is False

