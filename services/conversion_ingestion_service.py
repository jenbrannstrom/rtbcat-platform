"""Conversion ingestion and normalization service."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from storage.postgres_database import (
    pg_execute,
    pg_insert_returning_id,
    pg_query,
    pg_query_one,
)
from services.conversion_taxonomy import (
    normalize_attribution_type,
    normalize_currency,
    normalize_event_type,
    normalize_fraud_status,
    normalize_source_type,
)


_NUMERIC_CLEAN_RE = re.compile(r"[^0-9.\-]+")


def _token(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coalesce_str(payload: dict[str, Any], keys: list[str]) -> Optional[str]:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return str(payload[key]).strip()
    return None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _NUMERIC_CLEAN_RE.sub("", str(value))
    if s in ("", "-", ".", "-.", ".-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_ts(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    s = str(value).strip()
    if not s:
        return None

    # unix epoch as string
    if s.isdigit() and len(s) >= 10:
        return datetime.fromtimestamp(float(s), tz=timezone.utc)

    iso = s.replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(iso)
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    except ValueError:
        pass

    # Basic fallback formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(s, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _extract_event_value_and_currency(payload: dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    direct_value = _coalesce_str(
        payload,
        [
            "event_value",
            "eventValue",
            "revenue",
            "af_revenue",
            "value",
            "amount",
            "event_revenue",
            "s2s_revenue",
            "payout",
        ],
    )
    direct_currency = _coalesce_str(
        payload,
        ["currency", "currency_code", "af_currency", "event_currency", "revenue_currency"],
    )

    # AppsFlyer commonly sends eventValue as a JSON string.
    nested = payload.get("eventValue")
    nested_value = None
    nested_currency = None
    if isinstance(nested, str):
        stripped = nested.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                nested_payload = json.loads(stripped)
                nested_value = _coalesce_str(
                    nested_payload,
                    ["af_revenue", "revenue", "value", "amount"],
                )
                nested_currency = _coalesce_str(
                    nested_payload,
                    ["af_currency", "currency", "currency_code"],
                )
            except json.JSONDecodeError:
                pass
    elif isinstance(nested, dict):
        nested_value = _coalesce_str(nested, ["af_revenue", "revenue", "value", "amount"])
        nested_currency = _coalesce_str(nested, ["af_currency", "currency", "currency_code"])

    value = _parse_float(nested_value if nested_value is not None else direct_value)
    currency = normalize_currency(nested_currency if nested_currency is not None else direct_currency)
    return value, currency


class ConversionIngestionService:
    """Normalizes provider payloads and writes idempotent conversion events."""

    async def ingest_provider_payload(
        self,
        *,
        source_type: str,
        payload: dict[str, Any],
        buyer_id_override: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        import_batch_id: Optional[str] = None,
    ) -> dict[str, Any]:
        source = normalize_source_type(source_type)
        batch_id = import_batch_id or str(uuid.uuid4())
        event = self._normalize_event(
            source_type=source,
            payload=payload,
            buyer_id_override=buyer_id_override,
            idempotency_key=idempotency_key,
            import_batch_id=batch_id,
        )
        inserted = await self._insert_event(event)
        return {
            "accepted": True,
            "duplicate": not inserted,
            "source_type": source,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "buyer_id": event["buyer_id"],
            "event_ts": event["event_ts"].isoformat(),
            "import_batch_id": batch_id,
        }

    async def ingest_csv(
        self,
        *,
        csv_text: str,
        source_type: str = "manual_csv",
        buyer_id_override: Optional[str] = None,
        import_batch_id: Optional[str] = None,
    ) -> dict[str, Any]:
        source = normalize_source_type(source_type or "manual_csv")
        batch_id = import_batch_id or str(uuid.uuid4())
        rows_read = 0
        rows_inserted = 0
        rows_duplicate = 0
        rows_skipped = 0
        errors: list[str] = []

        reader = csv.DictReader(io.StringIO(csv_text))
        for idx, row in enumerate(reader, start=2):
            rows_read += 1
            try:
                payload = {k: v for k, v in row.items()}
                event = self._normalize_event(
                    source_type=source,
                    payload=payload,
                    buyer_id_override=buyer_id_override,
                    idempotency_key=None,
                    import_batch_id=batch_id,
                )
                inserted = await self._insert_event(event)
                if inserted:
                    rows_inserted += 1
                else:
                    rows_duplicate += 1
            except Exception as exc:
                rows_skipped += 1
                if len(errors) < 20:
                    errors.append(f"row {idx}: {exc}")

        return {
            "accepted": True,
            "source_type": source,
            "import_batch_id": batch_id,
            "rows_read": rows_read,
            "rows_inserted": rows_inserted,
            "rows_duplicate": rows_duplicate,
            "rows_skipped": rows_skipped,
            "errors": errors,
        }

    def _normalize_event(
        self,
        *,
        source_type: str,
        payload: dict[str, Any],
        buyer_id_override: Optional[str],
        idempotency_key: Optional[str],
        import_batch_id: str,
    ) -> dict[str, Any]:
        event_name = _coalesce_str(
            payload,
            ["event_name", "eventName", "event", "event_token", "name"],
        )
        raw_event_type = _coalesce_str(payload, ["event_type", "type", "conversion_type"])
        event_type = normalize_event_type(
            event_name,
            source_type=source_type,
            event_type=raw_event_type,
        )

        buyer_id = (
            _token(buyer_id_override)
            or _token(_coalesce_str(payload, ["buyer_id", "buyer_account_id", "seat_id", "bidder_id"]))
            or "unknown"
        )
        billing_id = _token(_coalesce_str(payload, ["billing_id", "config_id", "pretargeting_id"]))
        creative_id = _token(_coalesce_str(payload, ["creative_id", "ad_id", "creative"]))
        app_id = _token(_coalesce_str(payload, ["app_id", "bundle_id", "package_name", "app"]))
        publisher_id = _token(_coalesce_str(payload, ["publisher_id", "publisher", "site_id"]))
        campaign_id = _token(_coalesce_str(payload, ["campaign_id", "campaign", "campaign_name"]))
        country = _token(_coalesce_str(payload, ["country", "country_code", "geo"]))
        platform = _token(_coalesce_str(payload, ["platform", "os", "device_os"]))
        click_id = _token(
            _coalesce_str(
                payload,
                ["click_id", "gclid", "af_click_id", "adjust_click_id", "tracker_token"],
            )
        )
        impression_id = _token(
            _coalesce_str(
                payload,
                ["impression_id", "af_impression_id", "ad_impression_id"],
            )
        )

        attribution_type = normalize_attribution_type(
            _coalesce_str(payload, ["attribution_type", "attributed_touch_type", "match_type"])
        )
        fraud_status = normalize_fraud_status(
            _coalesce_str(payload, ["fraud_status", "fraud", "is_fraud", "validation_result"])
        )
        is_retargeting = _parse_bool(
            _coalesce_str(payload, ["is_retargeting", "retargeting", "reengagement"])
        )

        event_ts = (
            _parse_ts(
                _coalesce_str(
                    payload,
                    [
                        "event_ts",
                        "event_time",
                        "eventTime",
                        "conversion_time",
                        "created_at",
                        "timestamp",
                        "install_time",
                    ],
                )
            )
            or datetime.now(timezone.utc)
        )
        click_ts = _parse_ts(
            _coalesce_str(
                payload,
                ["click_ts", "click_time", "clickTime", "touch_time"],
            )
        )
        latency_seconds = None
        if click_ts and event_ts and event_ts >= click_ts:
            latency_seconds = int((event_ts - click_ts).total_seconds())

        event_value, currency = _extract_event_value_and_currency(payload)

        event_id = self._derive_event_id(
            source_type=source_type,
            payload=payload,
            event_name=event_name,
            event_ts=event_ts,
            click_id=click_id,
            impression_id=impression_id,
            buyer_id=buyer_id,
            billing_id=billing_id,
            creative_id=creative_id,
            publisher_id=publisher_id,
            event_value=event_value,
            idempotency_key=idempotency_key,
        )

        return {
            "event_id": event_id,
            "source_type": source_type,
            "buyer_id": buyer_id,
            "billing_id": billing_id or None,
            "creative_id": creative_id or None,
            "event_type": event_type,
            "event_name": event_name or None,
            "event_value": event_value,
            "currency": currency,
            "country": country or None,
            "platform": platform or None,
            "app_id": app_id or None,
            "publisher_id": publisher_id or None,
            "campaign_id": campaign_id or None,
            "click_id": click_id or None,
            "impression_id": impression_id or None,
            "attribution_type": attribution_type,
            "is_retargeting": is_retargeting,
            "click_ts": click_ts,
            "event_ts": event_ts,
            "latency_seconds": latency_seconds,
            "fraud_status": fraud_status,
            "raw_payload": json.dumps(payload),
            "import_batch_id": import_batch_id,
        }

    def _derive_event_id(
        self,
        *,
        source_type: str,
        payload: dict[str, Any],
        event_name: Optional[str],
        event_ts: datetime,
        click_id: str,
        impression_id: str,
        buyer_id: str,
        billing_id: str,
        creative_id: str,
        publisher_id: str,
        event_value: Optional[float],
        idempotency_key: Optional[str],
    ) -> str:
        explicit = _coalesce_str(
            payload,
            [
                "event_id",
                "id",
                "postback_id",
                "conversion_id",
                "transaction_id",
                "install_id",
            ],
        )
        if explicit:
            return explicit

        if idempotency_key:
            return str(idempotency_key).strip()

        appsflyer_id = _coalesce_str(payload, ["appsflyer_id"])
        if source_type == "appsflyer" and appsflyer_id:
            return f"{appsflyer_id}:{event_name or 'event'}:{event_ts.isoformat()}"

        adjust_adid = _coalesce_str(payload, ["adid", "gps_adid", "idfa"])
        if source_type == "adjust" and adjust_adid:
            return f"{adjust_adid}:{event_name or 'event'}:{event_ts.isoformat()}"

        branch_id = _coalesce_str(payload, ["branch_id", "branch_identity"])
        if source_type == "branch" and branch_id:
            return f"{branch_id}:{event_name or 'event'}:{event_ts.isoformat()}"

        hash_input = "|".join(
            [
                source_type,
                _token(event_name),
                event_ts.isoformat(),
                click_id,
                impression_id,
                buyer_id,
                billing_id,
                creative_id,
                publisher_id,
                str(event_value) if event_value is not None else "",
            ]
        )
        return hashlib.sha1(hash_input.encode("utf-8")).hexdigest()

    async def _insert_event(self, event: dict[str, Any]) -> bool:
        sql = """
            INSERT INTO conversion_events (
                event_id,
                source_type,
                buyer_id,
                billing_id,
                creative_id,
                event_type,
                event_name,
                event_value,
                currency,
                country,
                platform,
                app_id,
                publisher_id,
                campaign_id,
                click_id,
                impression_id,
                attribution_type,
                is_retargeting,
                click_ts,
                event_ts,
                latency_seconds,
                fraud_status,
                raw_payload,
                import_batch_id,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s, NOW(), NOW()
            )
            ON CONFLICT (source_type, event_id) DO NOTHING
        """
        rowcount = await pg_execute(
            sql,
            (
                event["event_id"],
                event["source_type"],
                event["buyer_id"],
                event["billing_id"],
                event["creative_id"],
                event["event_type"],
                event["event_name"],
                event["event_value"],
                event["currency"],
                event["country"],
                event["platform"],
                event["app_id"],
                event["publisher_id"],
                event["campaign_id"],
                event["click_id"],
                event["impression_id"],
                event["attribution_type"],
                event["is_retargeting"],
                event["click_ts"],
                event["event_ts"],
                event["latency_seconds"],
                event["fraud_status"],
                event["raw_payload"],
                event["import_batch_id"],
            ),
        )
        return int(rowcount or 0) > 0

    async def record_failure(
        self,
        *,
        source_type: str,
        payload: dict[str, Any],
        error_code: str,
        error_message: str,
        buyer_id: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> int:
        source = normalize_source_type(source_type)
        sql = """
            INSERT INTO conversion_ingestion_failures (
                source_type,
                buyer_id,
                endpoint_path,
                error_code,
                error_message,
                payload,
                request_headers,
                idempotency_key,
                status,
                replay_attempts,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, 'pending', 0, NOW(), NOW()
            )
            RETURNING id
        """
        return await pg_insert_returning_id(
            sql,
            (
                source,
                buyer_id,
                endpoint_path,
                error_code,
                error_message[:500],
                json.dumps(payload),
                json.dumps(headers or {}),
                idempotency_key,
            ),
        )

    async def list_failures(
        self,
        *,
        source_type: Optional[str] = None,
        buyer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses = ["1=1"]
        params: list[Any] = []
        if source_type:
            clauses.append("source_type = %s")
            params.append(normalize_source_type(source_type))
        if buyer_id:
            clauses.append("buyer_id = %s")
            params.append(buyer_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        where_sql = " AND ".join(clauses)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = await pg_query(
            f"""
            SELECT
                id,
                source_type,
                buyer_id,
                endpoint_path,
                error_code,
                error_message,
                payload,
                request_headers,
                idempotency_key,
                status,
                replay_attempts,
                last_replayed_at,
                created_at,
                updated_at
            FROM conversion_ingestion_failures
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )
        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM conversion_ingestion_failures
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)

        return {
            "rows": [
                {
                    "id": int(row.get("id") or 0),
                    "source_type": str(row.get("source_type") or ""),
                    "buyer_id": row.get("buyer_id"),
                    "endpoint_path": row.get("endpoint_path"),
                    "error_code": str(row.get("error_code") or ""),
                    "error_message": str(row.get("error_message") or ""),
                    "payload": row.get("payload") or {},
                    "request_headers": row.get("request_headers") or {},
                    "idempotency_key": row.get("idempotency_key"),
                    "status": str(row.get("status") or "pending"),
                    "replay_attempts": int(row.get("replay_attempts") or 0),
                    "last_replayed_at": _to_iso_ts(row.get("last_replayed_at")),
                    "created_at": _to_iso_ts(row.get("created_at")),
                    "updated_at": _to_iso_ts(row.get("updated_at")),
                }
                for row in rows
            ],
            "meta": {
                "total": total,
                "returned": len(rows),
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": safe_offset + len(rows) < total,
            },
        }

    async def replay_failure(self, failure_id: int) -> dict[str, Any]:
        row = await pg_query_one(
            """
            SELECT
                id,
                source_type,
                buyer_id,
                payload,
                idempotency_key,
                replay_attempts
            FROM conversion_ingestion_failures
            WHERE id = %s
            """,
            (failure_id,),
        )
        if not row:
            raise ValueError("Failure item not found")

        payload = row.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            payload = {}

        try:
            result = await self.ingest_provider_payload(
                source_type=str(row.get("source_type") or "generic"),
                payload=payload,
                buyer_id_override=str(row.get("buyer_id") or "") or None,
                idempotency_key=str(row.get("idempotency_key") or "") or None,
            )
            await pg_execute(
                """
                UPDATE conversion_ingestion_failures
                SET
                    status = 'replayed',
                    replay_attempts = COALESCE(replay_attempts, 0) + 1,
                    last_replayed_at = NOW(),
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (failure_id,),
            )
            return {
                "failure_id": failure_id,
                "status": "replayed",
                "result": result,
            }
        except Exception as exc:
            await pg_execute(
                """
                UPDATE conversion_ingestion_failures
                SET
                    status = 'pending',
                    replay_attempts = COALESCE(replay_attempts, 0) + 1,
                    last_replayed_at = NOW(),
                    error_message = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (str(exc)[:500], failure_id),
            )
            raise

    async def discard_failure(self, failure_id: int) -> bool:
        rowcount = await pg_execute(
            """
            UPDATE conversion_ingestion_failures
            SET status = 'discarded', updated_at = NOW()
            WHERE id = %s
            """,
            (failure_id,),
        )
        return int(rowcount or 0) > 0

    async def get_ingestion_stats(
        self,
        *,
        days: int = 7,
        source_type: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        safe_days = max(1, min(days, 365))
        source_filter_accepted = ""
        source_filter_rejected = ""
        buyer_filter_accepted = ""
        buyer_filter_rejected = ""
        params: list[Any] = [safe_days]

        if source_type:
            source = normalize_source_type(source_type)
            source_filter_accepted = " AND source_type = %s"
            source_filter_rejected = " AND source_type = %s"
            params.append(source)
        if buyer_id:
            buyer_filter_accepted = " AND buyer_id = %s"
            buyer_filter_rejected = " AND buyer_id = %s"
            params.append(buyer_id)

        sql = f"""
            WITH accepted AS (
                SELECT
                    event_ts::date AS metric_date,
                    source_type,
                    COUNT(*)::bigint AS accepted_count
                FROM conversion_events
                WHERE event_ts::date >= CURRENT_DATE - %s::int
                    {source_filter_accepted}
                    {buyer_filter_accepted}
                GROUP BY event_ts::date, source_type
            ),
            rejected AS (
                SELECT
                    created_at::date AS metric_date,
                    source_type,
                    COUNT(*)::bigint AS rejected_count
                FROM conversion_ingestion_failures
                WHERE created_at::date >= CURRENT_DATE - %s::int
                    {source_filter_rejected}
                    {buyer_filter_rejected}
                GROUP BY created_at::date, source_type
            )
            SELECT
                COALESCE(a.metric_date, r.metric_date) AS metric_date,
                COALESCE(a.source_type, r.source_type) AS source_type,
                COALESCE(a.accepted_count, 0)::bigint AS accepted_count,
                COALESCE(r.rejected_count, 0)::bigint AS rejected_count
            FROM accepted a
            FULL OUTER JOIN rejected r
                ON a.metric_date = r.metric_date
                AND a.source_type = r.source_type
            ORDER BY metric_date DESC, source_type
        """

        # params for accepted and rejected use same filter tuple
        filter_params = params[1:]
        rows = await pg_query(sql, tuple([safe_days, *filter_params, safe_days, *filter_params]))

        accepted_total = 0
        rejected_total = 0
        normalized_rows = []
        for row in rows:
            accepted = int(row.get("accepted_count") or 0)
            rejected = int(row.get("rejected_count") or 0)
            accepted_total += accepted
            rejected_total += rejected
            normalized_rows.append(
                {
                    "metric_date": _to_iso_ts(row.get("metric_date")),
                    "source_type": str(row.get("source_type") or ""),
                    "accepted_count": accepted,
                    "rejected_count": rejected,
                }
            )

        return {
            "days": safe_days,
            "source_type": normalize_source_type(source_type) if source_type else None,
            "buyer_id": buyer_id,
            "accepted_total": accepted_total,
            "rejected_total": rejected_total,
            "rows": normalized_rows,
        }

    async def get_failure_taxonomy(
        self,
        *,
        days: int = 7,
        source_type: Optional[str] = None,
        buyer_id: Optional[str] = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        safe_days = max(1, min(days, 365))
        safe_limit = max(1, min(limit, 100))
        clauses = ["created_at::date >= CURRENT_DATE - %s::int"]
        params: list[Any] = [safe_days]
        if source_type:
            clauses.append("source_type = %s")
            params.append(normalize_source_type(source_type))
        if buyer_id:
            clauses.append("buyer_id = %s")
            params.append(buyer_id)
        where_sql = " AND ".join(clauses)

        rows = await pg_query(
            f"""
            SELECT
                error_code,
                COUNT(*)::bigint AS failure_count,
                MAX(created_at) AS last_seen_at,
                MAX(error_message) AS sample_error_message
            FROM conversion_ingestion_failures
            WHERE {where_sql}
            GROUP BY error_code
            ORDER BY failure_count DESC, error_code
            LIMIT %s
            """,
            tuple([*params, safe_limit]),
        )
        total_row = await pg_query_one(
            f"""
            SELECT COUNT(*)::bigint AS total_failures
            FROM conversion_ingestion_failures
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total_failures = int((total_row or {}).get("total_failures") or 0)

        taxonomy_rows = []
        accounted = 0
        for row in rows:
            count = int(row.get("failure_count") or 0)
            accounted += count
            taxonomy_rows.append(
                {
                    "error_code": str(row.get("error_code") or "unknown"),
                    "failure_count": count,
                    "last_seen_at": _to_iso_ts(row.get("last_seen_at")),
                    "sample_error_message": str(row.get("sample_error_message") or ""),
                }
            )

        other_count = max(total_failures - accounted, 0)
        return {
            "days": safe_days,
            "source_type": normalize_source_type(source_type) if source_type else None,
            "buyer_id": buyer_id,
            "total_failures": total_failures,
            "other_count": other_count,
            "rows": taxonomy_rows,
        }


def _to_iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)
