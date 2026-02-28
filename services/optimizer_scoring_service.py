"""Rules-based segment scoring for BYOM optimizer foundation."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from storage.postgres_database import pg_execute, pg_query, pg_query_one
from services.optimizer_models_service import OptimizerModelsService


def _to_iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _parse_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


class OptimizerScoringService:
    """Builds segment features and persists rule-based scores."""

    async def run_scoring(
        self,
        *,
        model_id: str,
        buyer_id: str,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        model_service = OptimizerModelsService()
        model = await model_service.get_model(model_id=model_id, buyer_id=buyer_id)
        if not model:
            raise ValueError("Model not found")

        model_type = str(model.get("model_type") or "").strip().lower()
        if model_type == "rules":
            payload = await self.run_rules_scoring(
                model_id=model_id,
                buyer_id=buyer_id,
                days=days,
                start_date=start_date,
                end_date=end_date,
                event_type=event_type,
                limit=limit,
            )
            payload["model_type"] = "rules"
            return payload

        if model_type == "api":
            auth_header = model.get("auth_header_encrypted")
            if not auth_header and model.get("has_auth_header"):
                auth_header = await model_service.get_model_auth_header(
                    model_id=model_id,
                    buyer_id=buyer_id,
                )
            payload = await self.run_api_scoring(
                model_id=model_id,
                buyer_id=buyer_id,
                endpoint_url=str(model.get("endpoint_url") or ""),
                auth_header_encrypted=auth_header,
                days=days,
                start_date=start_date,
                end_date=end_date,
                event_type=event_type,
                limit=limit,
            )
            payload["model_type"] = "api"
            return payload

        raise ValueError(f"Unsupported model_type for scoring: {model_type or 'unknown'}")

    async def run_rules_scoring(
        self,
        *,
        model_id: str,
        buyer_id: str,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        model_service = OptimizerModelsService()
        model = await model_service.get_model(model_id=model_id, buyer_id=buyer_id)
        if not model:
            raise ValueError("Model not found")
        if str(model.get("model_type") or "") != "rules":
            raise ValueError("run_rules_scoring requires model_type=rules")

        start, end = self._resolve_date_range(days=days, start_date=start_date, end_date=end_date)
        safe_limit = max(1, min(limit, 5000))
        features = await self._fetch_segment_features(
            buyer_id=buyer_id,
            start_date=start,
            end_date=end,
            event_type=event_type,
            limit=safe_limit,
        )

        inserted = 0
        score_rows: list[dict[str, Any]] = []
        for feature_row in features:
            score_row = self._score_feature_row(
                model_id=model_id,
                buyer_id=buyer_id,
                feature_row=feature_row,
            )
            score_rows.append(score_row)
            rowcount = await self._insert_score(score_row)
            if int(rowcount or 0) > 0:
                inserted += 1

        top_rows = sorted(score_rows, key=lambda row: row["value_score"], reverse=True)[:10]
        return {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "event_type": event_type,
            "segments_scanned": len(features),
            "scores_written": inserted,
            "top_scores": [
                {
                    "score_id": row["score_id"],
                    "billing_id": row["billing_id"],
                    "country": row["country"],
                    "publisher_id": row["publisher_id"],
                    "app_id": row["app_id"],
                    "score_date": row["score_date"].isoformat(),
                    "value_score": row["value_score"],
                    "confidence": row["confidence"],
                    "reason_codes": row["reason_codes"],
                }
                for row in top_rows
            ],
        }

    async def run_api_scoring(
        self,
        *,
        model_id: str,
        buyer_id: str,
        endpoint_url: str,
        auth_header_encrypted: Optional[str],
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        endpoint = str(endpoint_url or "").strip()
        if not endpoint:
            raise ValueError("API model missing endpoint_url")

        start, end = self._resolve_date_range(days=days, start_date=start_date, end_date=end_date)
        safe_limit = max(1, min(limit, 5000))
        features = await self._fetch_segment_features(
            buyer_id=buyer_id,
            start_date=start,
            end_date=end,
            event_type=event_type,
            limit=safe_limit,
        )
        feature_payload = [self._feature_row_to_model_payload(row) for row in features]

        scores_by_feature_id = await self._invoke_external_model(
            endpoint_url=endpoint,
            auth_header_encrypted=auth_header_encrypted,
            model_id=model_id,
            buyer_id=buyer_id,
            event_type=event_type,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            features=feature_payload,
        )

        inserted = 0
        score_rows: list[dict[str, Any]] = []
        for feature_row in features:
            feature_id = self._feature_id(feature_row)
            output = scores_by_feature_id.get(feature_id, {})
            score_row = self._external_output_to_score_row(
                model_id=model_id,
                buyer_id=buyer_id,
                feature_row=feature_row,
                output=output,
            )
            score_rows.append(score_row)
            rowcount = await self._insert_score(score_row)
            if int(rowcount or 0) > 0:
                inserted += 1

        top_rows = sorted(score_rows, key=lambda row: row["value_score"], reverse=True)[:10]
        return {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "event_type": event_type,
            "segments_scanned": len(features),
            "scores_written": inserted,
            "top_scores": [
                {
                    "score_id": row["score_id"],
                    "billing_id": row["billing_id"],
                    "country": row["country"],
                    "publisher_id": row["publisher_id"],
                    "app_id": row["app_id"],
                    "score_date": row["score_date"].isoformat(),
                    "value_score": row["value_score"],
                    "confidence": row["confidence"],
                    "reason_codes": row["reason_codes"],
                }
                for row in top_rows
            ],
        }

    async def list_scores(
        self,
        *,
        model_id: Optional[str],
        buyer_id: str,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        billing_id: Optional[str] = None,
        country: Optional[str] = None,
        publisher_id: Optional[str] = None,
        app_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        start, end = self._resolve_date_range(days=days, start_date=start_date, end_date=end_date)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        clauses = ["buyer_id = %s", "score_date BETWEEN %s AND %s"]
        params: list[Any] = [buyer_id, start, end]
        if model_id:
            clauses.append("model_id = %s")
            params.append(model_id)
        if billing_id:
            clauses.append("billing_id = %s")
            params.append(billing_id)
        if country:
            clauses.append("country = %s")
            params.append(country)
        if publisher_id:
            clauses.append("publisher_id = %s")
            params.append(publisher_id)
        if app_id:
            clauses.append("app_id = %s")
            params.append(app_id)
        where_sql = " AND ".join(clauses)

        rows = await pg_query(
            f"""
            SELECT
                score_id,
                model_id,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                app_id,
                creative_size,
                platform,
                environment,
                hour,
                score_date,
                value_score,
                confidence,
                reason_codes,
                raw_response,
                created_at
            FROM segment_scores
            WHERE {where_sql}
            ORDER BY score_date DESC, value_score DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )
        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM segment_scores
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)
        payload_rows = [self._score_row_to_payload(row) for row in rows]
        return {
            "rows": payload_rows,
            "meta": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "total": total,
                "returned": len(payload_rows),
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": safe_offset + len(payload_rows) < total,
            },
        }

    def _resolve_date_range(
        self,
        *,
        days: int,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[date, date]:
        if start_date and end_date:
            start = _parse_date(start_date, "start_date")
            end = _parse_date(end_date, "end_date")
            if end < start:
                raise ValueError("end_date must be >= start_date")
            return start, end

        safe_days = max(1, min(days, 365))
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=safe_days - 1)
        return start, end

    async def _fetch_segment_features(
        self,
        *,
        buyer_id: str,
        start_date: date,
        end_date: date,
        event_type: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        event_filter = ""
        params: list[Any] = [buyer_id, start_date, end_date]
        if event_type:
            event_filter = "AND event_type = %s"
            params.append(event_type)
        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                agg_date::date AS score_date,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                app_id,
                SUM(event_count)::bigint AS event_count,
                SUM(event_value_total)::numeric AS event_value_total,
                SUM(impressions)::bigint AS impressions,
                SUM(clicks)::bigint AS clicks,
                SUM(spend_usd)::numeric AS spend_usd
            FROM conversion_aggregates_daily
            WHERE buyer_id = %s
                AND agg_date BETWEEN %s AND %s
                {event_filter}
            GROUP BY agg_date, buyer_id, billing_id, country, publisher_id, app_id
            ORDER BY agg_date DESC, SUM(spend_usd) DESC, SUM(event_count) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def _invoke_external_model(
        self,
        *,
        endpoint_url: str,
        auth_header_encrypted: Optional[str],
        model_id: str,
        buyer_id: str,
        event_type: Optional[str],
        start_date: str,
        end_date: str,
        features: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        if auth_header_encrypted:
            # Stored value is treated as an already-prepared Authorization header token.
            headers["Authorization"] = str(auth_header_encrypted)

        payload = {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "features": features,
        }
        body = await self._post_json(endpoint_url=endpoint_url, payload=payload, headers=headers)

        scores = body.get("scores") if isinstance(body, dict) else None
        if not isinstance(scores, list):
            raise ValueError("External model response must include 'scores' list")

        results: dict[str, dict[str, Any]] = {}
        for idx, item in enumerate(scores):
            if not isinstance(item, dict):
                continue
            feature_id = str(item.get("feature_id") or "").strip()
            if not feature_id and idx < len(features):
                feature_id = str(features[idx].get("feature_id") or "").strip()
            if not feature_id:
                continue
            results[feature_id] = item
        return results

    async def _post_json(
        self,
        *,
        endpoint_url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        def _request() -> dict[str, Any]:
            req = urllib_request.Request(
                endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib_request.urlopen(req, timeout=20) as resp:
                    status = int(getattr(resp, "status", 200))
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib_error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
                raise ValueError(f"External model returned HTTP {exc.code}: {raw[:300]}") from exc
            except Exception as exc:
                raise ValueError(f"External model request failed: {exc}") from exc

            if status >= 400:
                raise ValueError(f"External model returned HTTP {status}: {raw[:300]}")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"External model returned non-JSON response: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("External model response must be a JSON object")
            return parsed

        return await asyncio.to_thread(_request)

    def _feature_id(self, feature_row: dict[str, Any]) -> str:
        score_date_value = feature_row.get("score_date")
        if isinstance(score_date_value, datetime):
            score_date = score_date_value.date().isoformat()
        elif isinstance(score_date_value, date):
            score_date = score_date_value.isoformat()
        else:
            score_date = str(score_date_value or "")
        parts = [
            str(feature_row.get("billing_id") or ""),
            str(feature_row.get("country") or ""),
            str(feature_row.get("publisher_id") or ""),
            str(feature_row.get("app_id") or ""),
            score_date,
        ]
        return "|".join(parts)

    def _feature_row_to_model_payload(self, feature_row: dict[str, Any]) -> dict[str, Any]:
        event_count = int(feature_row.get("event_count") or 0)
        impressions = int(feature_row.get("impressions") or 0)
        clicks = int(feature_row.get("clicks") or 0)
        spend_usd = _to_float(feature_row.get("spend_usd"))
        event_value_total = _to_float(feature_row.get("event_value_total"))
        score_date_value = feature_row.get("score_date")
        if isinstance(score_date_value, datetime):
            score_date = score_date_value.date().isoformat()
        elif isinstance(score_date_value, date):
            score_date = score_date_value.isoformat()
        else:
            score_date = str(score_date_value or "")

        return {
            "feature_id": self._feature_id(feature_row),
            "score_date": score_date,
            "billing_id": str(feature_row.get("billing_id") or ""),
            "country": str(feature_row.get("country") or ""),
            "publisher_id": str(feature_row.get("publisher_id") or ""),
            "app_id": str(feature_row.get("app_id") or ""),
            "event_count": event_count,
            "impressions": impressions,
            "clicks": clicks,
            "spend_usd": spend_usd,
            "event_value_total": event_value_total,
            "event_rate": (event_count / impressions) if impressions > 0 else 0.0,
            "cost_per_event": (spend_usd / event_count) if event_count > 0 else None,
            "roas": (event_value_total / spend_usd) if spend_usd > 0 else None,
        }

    def _external_output_to_score_row(
        self,
        *,
        model_id: str,
        buyer_id: str,
        feature_row: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        value_score = _clamp(_to_float(output.get("value_score"), 0.5))
        confidence = _clamp(_to_float(output.get("confidence"), 0.5))
        reason_codes = output.get("reason_codes")
        if isinstance(reason_codes, list):
            normalized_reasons = [str(code) for code in reason_codes if code is not None]
        else:
            normalized_reasons = []
        if not normalized_reasons:
            normalized_reasons = ["external_model_score"]

        score_date_value = feature_row.get("score_date")
        if isinstance(score_date_value, datetime):
            score_date = score_date_value.date()
        elif isinstance(score_date_value, date):
            score_date = score_date_value
        else:
            score_date = datetime.now(timezone.utc).date()

        return {
            "score_id": f"scr_{uuid.uuid4().hex}",
            "model_id": model_id,
            "buyer_id": buyer_id,
            "billing_id": str(feature_row.get("billing_id") or ""),
            "country": str(feature_row.get("country") or ""),
            "publisher_id": str(feature_row.get("publisher_id") or ""),
            "app_id": str(feature_row.get("app_id") or ""),
            "creative_size": str(output.get("creative_size") or ""),
            "platform": str(output.get("platform") or ""),
            "environment": str(output.get("environment") or ""),
            "hour": output.get("hour"),
            "score_date": score_date,
            "value_score": round(value_score, 6),
            "confidence": round(confidence, 6),
            "reason_codes": sorted(set(normalized_reasons)),
            "raw_response": output if isinstance(output, dict) else {},
        }

    def _score_feature_row(
        self,
        *,
        model_id: str,
        buyer_id: str,
        feature_row: dict[str, Any],
    ) -> dict[str, Any]:
        event_count = int(feature_row.get("event_count") or 0)
        impressions = int(feature_row.get("impressions") or 0)
        clicks = int(feature_row.get("clicks") or 0)
        spend_usd = _to_float(feature_row.get("spend_usd"))
        event_value_total = _to_float(feature_row.get("event_value_total"))

        event_rate = (event_count / impressions) if impressions > 0 else 0.0
        cost_per_event = (spend_usd / event_count) if event_count > 0 else None
        roas = (event_value_total / spend_usd) if spend_usd > 0 else None

        score = 0.0
        reason_codes: list[str] = []

        volume_component = min(event_count / 50.0, 1.0)
        score += volume_component * 0.40
        if event_count >= 10:
            reason_codes.append("high_event_volume")
        elif event_count == 0:
            reason_codes.append("no_events")

        rate_component = min(event_rate * 40.0, 1.0)
        score += rate_component * 0.30
        if event_rate >= 0.02:
            reason_codes.append("strong_event_rate")

        if cost_per_event is not None:
            cpa_component = max(0.0, 1.0 - min(cost_per_event / 50.0, 1.0))
            score += cpa_component * 0.20
            if cost_per_event <= 10.0:
                reason_codes.append("low_cpa")
        else:
            reason_codes.append("no_cpa")

        if roas is not None:
            roas_component = min(roas / 2.0, 1.0)
            score += roas_component * 0.10
            if roas >= 1.0:
                reason_codes.append("positive_value")
        else:
            reason_codes.append("no_value_signal")

        confidence = (
            min(impressions / 5000.0, 1.0) * 0.50
            + min(event_count / 20.0, 1.0) * 0.50
        )
        if impressions < 200:
            confidence *= 0.6
            reason_codes.append("sparse_data")

        score_date_value = feature_row.get("score_date")
        if isinstance(score_date_value, datetime):
            score_date = score_date_value.date()
        elif isinstance(score_date_value, date):
            score_date = score_date_value
        else:
            score_date = datetime.now(timezone.utc).date()

        return {
            "score_id": f"scr_{uuid.uuid4().hex}",
            "model_id": model_id,
            "buyer_id": buyer_id,
            "billing_id": str(feature_row.get("billing_id") or ""),
            "country": str(feature_row.get("country") or ""),
            "publisher_id": str(feature_row.get("publisher_id") or ""),
            "app_id": str(feature_row.get("app_id") or ""),
            "creative_size": "",
            "platform": "",
            "environment": "",
            "hour": None,
            "score_date": score_date,
            "value_score": round(_clamp(score), 6),
            "confidence": round(_clamp(confidence), 6),
            "reason_codes": sorted(set(reason_codes)),
            "raw_response": {
                "event_count": event_count,
                "impressions": impressions,
                "clicks": clicks,
                "spend_usd": spend_usd,
                "event_value_total": event_value_total,
                "event_rate": event_rate,
                "cost_per_event": cost_per_event,
                "roas": roas,
            },
        }

    async def _insert_score(self, row: dict[str, Any]) -> int:
        return await pg_execute(
            """
            INSERT INTO segment_scores (
                score_id,
                model_id,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                app_id,
                creative_size,
                platform,
                environment,
                hour,
                score_date,
                value_score,
                confidence,
                reason_codes,
                raw_response,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW()
            )
            ON CONFLICT (score_id) DO NOTHING
            """,
            (
                row["score_id"],
                row["model_id"],
                row["buyer_id"],
                row["billing_id"],
                row["country"],
                row["publisher_id"],
                row["app_id"],
                row["creative_size"],
                row["platform"],
                row["environment"],
                row["hour"],
                row["score_date"],
                row["value_score"],
                row["confidence"],
                json.dumps(row["reason_codes"]),
                json.dumps(row["raw_response"]),
            ),
        )

    def _score_row_to_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        reason_codes = row.get("reason_codes") or []
        if isinstance(reason_codes, str):
            try:
                parsed = json.loads(reason_codes)
                if isinstance(parsed, list):
                    reason_codes = parsed
            except json.JSONDecodeError:
                reason_codes = []
        raw_response = row.get("raw_response") or {}
        if isinstance(raw_response, str):
            try:
                parsed = json.loads(raw_response)
                if isinstance(parsed, dict):
                    raw_response = parsed
            except json.JSONDecodeError:
                raw_response = {}

        return {
            "score_id": str(row.get("score_id") or ""),
            "model_id": str(row.get("model_id") or ""),
            "buyer_id": str(row.get("buyer_id") or ""),
            "billing_id": str(row.get("billing_id") or ""),
            "country": str(row.get("country") or ""),
            "publisher_id": str(row.get("publisher_id") or ""),
            "app_id": str(row.get("app_id") or ""),
            "creative_size": str(row.get("creative_size") or ""),
            "platform": str(row.get("platform") or ""),
            "environment": str(row.get("environment") or ""),
            "hour": row.get("hour"),
            "score_date": _to_iso_date(row.get("score_date")),
            "value_score": _to_float(row.get("value_score")),
            "confidence": _to_float(row.get("confidence")),
            "reason_codes": list(reason_codes) if isinstance(reason_codes, list) else [],
            "raw_response": raw_response if isinstance(raw_response, dict) else {},
            "created_at": _to_iso_ts(row.get("created_at")),
        }
