"""Model registry service for BYOM optimizer integrations."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from storage.postgres_database import pg_query, pg_query_one


_ALLOWED_MODEL_TYPES = {"api", "rules", "csv"}


def _to_iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _to_json_obj(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return default
    return default


def _normalize_model_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if token not in _ALLOWED_MODEL_TYPES:
        raise ValueError("model_type must be one of: api, rules, csv")
    return token


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


class OptimizerModelsService:
    """CRUD for optimization model registry records."""

    async def create_model(
        self,
        *,
        buyer_id: str,
        name: str,
        model_type: str,
        description: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        auth_header_encrypted: Optional[str] = None,
        input_schema: Optional[dict[str, Any]] = None,
        output_schema: Optional[dict[str, Any]] = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        safe_name = str(name or "").strip()
        if not safe_name:
            raise ValueError("name is required")
        safe_model_type = _normalize_model_type(model_type)
        if safe_model_type == "api" and not str(endpoint_url or "").strip():
            raise ValueError("endpoint_url is required for api model_type")

        model_id = f"mdl_{uuid.uuid4().hex}"
        row = await pg_query_one(
            """
            INSERT INTO optimization_models (
                model_id,
                buyer_id,
                name,
                description,
                model_type,
                endpoint_url,
                auth_header_encrypted,
                input_schema,
                output_schema,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, NOW(), NOW()
            )
            RETURNING
                model_id,
                buyer_id,
                name,
                description,
                model_type,
                endpoint_url,
                auth_header_encrypted,
                input_schema,
                output_schema,
                is_active,
                created_at,
                updated_at
            """,
            (
                model_id,
                buyer_id,
                safe_name,
                description,
                safe_model_type,
                endpoint_url,
                auth_header_encrypted,
                json.dumps(input_schema or {}),
                json.dumps(output_schema or {}),
                bool(is_active),
            ),
        )
        if not row:
            raise RuntimeError("Failed to create optimization model")
        return _model_row_to_payload(row)

    async def list_models(
        self,
        *,
        buyer_id: Optional[str] = None,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses = ["1=1"]
        params: list[Any] = []
        if buyer_id:
            clauses.append("buyer_id = %s")
            params.append(buyer_id)
        if not include_inactive:
            clauses.append("is_active = TRUE")
        where_sql = " AND ".join(clauses)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = await pg_query(
            f"""
            SELECT
                model_id,
                buyer_id,
                name,
                description,
                model_type,
                endpoint_url,
                auth_header_encrypted,
                input_schema,
                output_schema,
                is_active,
                created_at,
                updated_at
            FROM optimization_models
            WHERE {where_sql}
            ORDER BY updated_at DESC, model_id
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )
        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM optimization_models
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)
        payload_rows = [_model_row_to_payload(row) for row in rows]
        return {
            "rows": payload_rows,
            "meta": {
                "total": total,
                "returned": len(payload_rows),
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": safe_offset + len(payload_rows) < total,
            },
        }

    async def get_model(
        self,
        *,
        model_id: str,
        buyer_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        clauses = ["model_id = %s"]
        params: list[Any] = [model_id]
        if buyer_id:
            clauses.append("buyer_id = %s")
            params.append(buyer_id)
        where_sql = " AND ".join(clauses)
        row = await pg_query_one(
            f"""
            SELECT
                model_id,
                buyer_id,
                name,
                description,
                model_type,
                endpoint_url,
                auth_header_encrypted,
                input_schema,
                output_schema,
                is_active,
                created_at,
                updated_at
            FROM optimization_models
            WHERE {where_sql}
            LIMIT 1
            """,
            tuple(params),
        )
        if not row:
            return None
        return _model_row_to_payload(row)

    async def update_model(
        self,
        *,
        model_id: str,
        buyer_id: Optional[str] = None,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        if not updates:
            raise ValueError("No updates provided")

        existing = await self.get_model(model_id=model_id, buyer_id=buyer_id)
        if not existing:
            return None

        next_model_type = _normalize_model_type(
            str(updates.get("model_type") or existing["model_type"])
        )
        next_endpoint_url = (
            str(updates.get("endpoint_url")).strip()
            if "endpoint_url" in updates and updates.get("endpoint_url") is not None
            else str(existing.get("endpoint_url") or "").strip()
        )
        if next_model_type == "api" and not next_endpoint_url:
            raise ValueError("endpoint_url is required for api model_type")

        set_clauses: list[str] = []
        params: list[Any] = []

        if "name" in updates:
            safe_name = str(updates.get("name") or "").strip()
            if not safe_name:
                raise ValueError("name cannot be empty")
            set_clauses.append("name = %s")
            params.append(safe_name)
        if "description" in updates:
            set_clauses.append("description = %s")
            params.append(updates.get("description"))
        if "model_type" in updates:
            set_clauses.append("model_type = %s")
            params.append(next_model_type)
        if "endpoint_url" in updates:
            set_clauses.append("endpoint_url = %s")
            params.append(updates.get("endpoint_url"))
        if "auth_header_encrypted" in updates:
            set_clauses.append("auth_header_encrypted = %s")
            params.append(updates.get("auth_header_encrypted"))
        if "input_schema" in updates:
            set_clauses.append("input_schema = %s::jsonb")
            params.append(json.dumps(updates.get("input_schema") or {}))
        if "output_schema" in updates:
            set_clauses.append("output_schema = %s::jsonb")
            params.append(json.dumps(updates.get("output_schema") or {}))
        if "is_active" in updates:
            set_clauses.append("is_active = %s")
            params.append(_to_bool(updates.get("is_active")))

        if not set_clauses:
            raise ValueError("No supported updates provided")

        where_sql = "model_id = %s"
        params.append(model_id)
        if buyer_id:
            where_sql += " AND buyer_id = %s"
            params.append(buyer_id)

        row = await pg_query_one(
            f"""
            UPDATE optimization_models
            SET {", ".join(set_clauses)}, updated_at = NOW()
            WHERE {where_sql}
            RETURNING
                model_id,
                buyer_id,
                name,
                description,
                model_type,
                endpoint_url,
                auth_header_encrypted,
                input_schema,
                output_schema,
                is_active,
                created_at,
                updated_at
            """,
            tuple(params),
        )
        if not row:
            return None
        return _model_row_to_payload(row)

    async def validate_model_endpoint(
        self,
        *,
        model_id: str,
        buyer_id: Optional[str] = None,
        sample_payload: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 10,
    ) -> dict[str, Any]:
        model = await self.get_model(model_id=model_id, buyer_id=buyer_id)
        if not model:
            raise ValueError("Model not found")

        if str(model.get("model_type") or "") != "api":
            return {
                "model_id": model_id,
                "buyer_id": model.get("buyer_id"),
                "valid": True,
                "skipped": True,
                "message": "Validation skipped for non-api model_type",
            }

        endpoint_url = str(model.get("endpoint_url") or "").strip()
        if not endpoint_url:
            raise ValueError("API model missing endpoint_url")

        payload = sample_payload or {
            "model_id": model_id,
            "buyer_id": model.get("buyer_id"),
            "ping": True,
            "features": [],
        }
        headers = {"Content-Type": "application/json"}
        if model.get("has_auth_header"):
            # auth_header_encrypted is write-only in API responses; pull it directly.
            raw_model = await pg_query_one(
                """
                SELECT auth_header_encrypted
                FROM optimization_models
                WHERE model_id = %s
                LIMIT 1
                """,
                (model_id,),
            )
            if raw_model and raw_model.get("auth_header_encrypted"):
                headers["Authorization"] = str(raw_model.get("auth_header_encrypted"))

        result = await self._post_json(
            endpoint_url=endpoint_url,
            payload=payload,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        body = result.get("json")
        valid = False
        if isinstance(body, dict):
            if isinstance(body.get("scores"), list):
                valid = True
            elif body.get("ok") is True:
                valid = True

        return {
            "model_id": model_id,
            "buyer_id": model.get("buyer_id"),
            "valid": valid,
            "skipped": False,
            "http_status": result.get("status"),
            "message": "Model endpoint validated" if valid else "Model endpoint responded but contract check failed",
            "response_preview": (
                json.dumps(body)[:300]
                if isinstance(body, (dict, list))
                else str(result.get("raw") or "")[:300]
            ),
        }

    async def _post_json(
        self,
        *,
        endpoint_url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        def _request() -> dict[str, Any]:
            req = urllib_request.Request(
                endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
                    status = int(getattr(resp, "status", 200))
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib_error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
                return {"status": int(exc.code), "raw": raw, "json": _try_json(raw)}
            except Exception as exc:
                raise ValueError(f"Endpoint validation request failed: {exc}") from exc

            return {"status": status, "raw": raw, "json": _try_json(raw)}

        return await asyncio.to_thread(_request)


def _try_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _model_row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": str(row.get("model_id") or ""),
        "buyer_id": str(row.get("buyer_id") or ""),
        "name": str(row.get("name") or ""),
        "description": row.get("description"),
        "model_type": str(row.get("model_type") or ""),
        "endpoint_url": row.get("endpoint_url"),
        "has_auth_header": bool(row.get("auth_header_encrypted")),
        "input_schema": _to_json_obj(row.get("input_schema"), {}),
        "output_schema": _to_json_obj(row.get("output_schema"), {}),
        "is_active": _to_bool(row.get("is_active")),
        "created_at": _to_iso_ts(row.get("created_at")),
        "updated_at": _to_iso_ts(row.get("updated_at")),
    }
