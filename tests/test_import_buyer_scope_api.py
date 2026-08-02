"""API wiring tests for row-level CSV buyer authorization."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from api.routers import performance as performance_router
from importers.unified_importer import UnifiedImportResult
from services.auth_service import User


def test_import_csv_passes_admin_seats_to_unified_importer(monkeypatch) -> None:
    user = User(id="admin-1", email="admin@example.com")
    captured: dict = {}

    async def _admin_buyer_ids(request_user: User):
        assert request_user is user
        return ["2222222222"]

    class _UploadsRepository:
        async def start_ingestion_run(self, **_kwargs) -> None:
            return None

        async def finish_ingestion_run(self, **_kwargs) -> None:
            return None

    class _PerformanceService:
        async def record_import(self, **_kwargs) -> None:
            return None

    def _unified_import(path: str, **kwargs) -> UnifiedImportResult:
        captured.update(path=path, **kwargs)
        result = UnifiedImportResult(success=False)
        result.error_message = "test import stopped"
        return result

    monkeypatch.setattr(performance_router, "get_admin_buyer_ids", _admin_buyer_ids)
    monkeypatch.setattr(performance_router, "UploadsRepository", _UploadsRepository)
    monkeypatch.setattr(performance_router, "PerformanceService", _PerformanceService)
    monkeypatch.setattr(performance_router, "unified_import", _unified_import)

    response = asyncio.run(
        performance_router.import_performance_csv(
            background_tasks=BackgroundTasks(),
            file=UploadFile(
                filename="catscan-quality-2222222222-yesterday-UTC.csv",
                file=BytesIO(b"Day,Buyer Account ID\n2026-08-01,2222222222\n"),
            ),
            user=user,
        )
    )

    assert response.success is False
    assert captured["buyer_scope"].allowed_buyer_ids == frozenset({"2222222222"})
    assert captured["source_filename"] == (
        "catscan-quality-2222222222-yesterday-UTC.csv"
    )


def test_import_scope_is_unrestricted_only_for_global_admin(monkeypatch) -> None:
    user = User(id="sudo-1", email="sudo@example.com")

    async def _all_buyers(_request_user: User):
        return None

    monkeypatch.setattr(performance_router, "get_admin_buyer_ids", _all_buyers)

    scope = asyncio.run(performance_router._import_buyer_scope(user))

    assert scope.is_unrestricted is True


def test_import_csv_rejects_foreign_filename_before_creating_import_state(
    monkeypatch,
) -> None:
    user = User(id="admin-1", email="admin@example.com")

    async def _admin_buyer_ids(_request_user: User):
        return ["2222222222"]

    class _UnexpectedUploadsRepository:
        def __init__(self) -> None:
            raise AssertionError("unauthorized filename must fail before ingestion tracking")

    monkeypatch.setattr(performance_router, "get_admin_buyer_ids", _admin_buyer_ids)
    monkeypatch.setattr(
        performance_router,
        "UploadsRepository",
        _UnexpectedUploadsRepository,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            performance_router.import_performance_csv(
                background_tasks=BackgroundTasks(),
                file=UploadFile(
                    filename="catscan-quality-1111111111-yesterday-UTC.csv",
                    file=BytesIO(
                        b"Day,Buyer Account ID\n2026-08-01,1111111111\n"
                    ),
                ),
                user=user,
            )
        )

    assert exc_info.value.status_code == 403
    assert "outside the authorized import scope" in str(exc_info.value.detail)


def test_stream_completion_passes_admin_seats_to_unified_importer(
    tmp_path,
    monkeypatch,
) -> None:
    user = User(id="admin-1", email="admin@example.com")
    upload_path = tmp_path / "upload.part"
    upload_path.write_bytes(b"Day,Buyer Account ID\n2026-08-01,2222222222\n")
    captured: dict = {}

    async def _admin_buyer_ids(_request_user: User):
        return ["2222222222"]

    class _PerformanceService:
        async def record_import(self, **_kwargs) -> None:
            return None

    def _unified_import(path: str, **kwargs) -> UnifiedImportResult:
        captured.update(path=path, **kwargs)
        result = UnifiedImportResult(success=False)
        result.error_message = "test import stopped"
        return result

    file_size = upload_path.stat().st_size
    monkeypatch.setattr(performance_router, "get_admin_buyer_ids", _admin_buyer_ids)
    monkeypatch.setattr(performance_router, "PerformanceService", _PerformanceService)
    monkeypatch.setattr(performance_router, "unified_import", _unified_import)
    monkeypatch.setattr(performance_router, "_ensure_upload_dir", lambda: None)
    monkeypatch.setattr(performance_router, "_data_path", lambda _upload_id: upload_path)
    monkeypatch.setattr(
        performance_router,
        "_load_meta",
        lambda _upload_id: {
            "filename": "catscan-quality-2222222222-yesterday-UTC.csv",
            "total_chunks": 1,
            "chunks_received": 1,
            "bytes_received": file_size,
            "file_size_bytes": file_size,
        },
    )
    monkeypatch.setattr(
        performance_router.Path,
        "home",
        classmethod(lambda _cls: tmp_path),
    )

    response = asyncio.run(
        performance_router.complete_stream_import(
            request=performance_router.StreamCompleteRequest(upload_id="upload-1"),
            background_tasks=BackgroundTasks(),
            user=user,
        )
    )

    assert response.success is False
    assert captured["buyer_scope"].allowed_buyer_ids == frozenset({"2222222222"})
    assert captured["source_filename"] == (
        "catscan-quality-2222222222-yesterday-UTC.csv"
    )
