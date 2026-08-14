"""Precompute-only creative reads for the Agent API."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import HTTPException

from api.schemas.agent_provenance import build_provenance
from services.creative_destination_resolver import resolve_creative_destination_url
from storage.postgres_database import pg_query_with_timeout

MAX_CREATIVE_RANGE_DAYS = 90


def _int(value: object) -> int:
    return 0 if value is None else int(value)


def _date_str(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _requested_dates(start_date: date, end_date: date) -> list[str]:
    return [
        date.fromordinal(ordinal).isoformat()
        for ordinal in range(start_date.toordinal(), end_date.toordinal() + 1)
    ]


def _normalize_domain(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if "://" in candidate:
        candidate = (urlparse(candidate).hostname or "").lower()
    else:
        candidate = candidate.split("/", 1)[0].split(":", 1)[0]
    candidate = candidate.strip(".")
    if not candidate:
        raise HTTPException(status_code=400, detail="domain must contain a host name.")
    return candidate


def _encode_cursor(spend_micros: int, creative_id: str) -> str:
    raw = json.dumps([spend_micros, creative_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[int, str] | None:
    if cursor is None:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if (
            not isinstance(decoded, list)
            or len(decoded) != 2
            or isinstance(decoded[0], bool)
            or not isinstance(decoded[0], int)
            or decoded[0] < 0
            or not isinstance(decoded[1], str)
            or not decoded[1]
        ):
            raise ValueError
        return decoded[0], decoded[1]
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid creative cursor.") from None


@dataclass
class AgentCreativesRepository:
    """Statement-bounded SQL access for buyer-scoped creative evidence."""

    statement_timeout_ms: int = 5000

    async def list_creatives(
        self,
        *,
        buyer_id: str,
        start_date: date,
        end_date: date,
        domain: str | None,
        creative_format: str | None,
        approval_filter: str,
        activity: str,
        search: str | None,
        cursor: tuple[int, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        conditions = ["c.buyer_id = %s"]
        params: list[Any] = [buyer_id, start_date, end_date, buyer_id]

        if domain:
            host_expression = (
                "LOWER(REGEXP_REPLACE(SPLIT_PART(REGEXP_REPLACE(COALESCE({column}, ''), "
                "'^https?://', '', 'i'), '/', 1), ':[0-9]+$', ''))"
            )
            final_host = host_expression.format(column="c.final_url")
            display_host = host_expression.format(column="c.display_url")
            conditions.append(
                f"({final_host} = %s OR {final_host} LIKE %s OR "
                f"{display_host} = %s OR {display_host} LIKE %s)"
            )
            subdomain = f"%.{domain}"
            params.extend([domain, subdomain, domain, subdomain])
        if creative_format:
            conditions.append("c.format = %s")
            params.append(creative_format)
        if approval_filter == "approved":
            conditions.append("c.approval_status = 'APPROVED'")
        elif approval_filter == "not_approved":
            conditions.append("(c.approval_status IS NULL OR c.approval_status != 'APPROVED')")
        if activity == "active":
            conditions.append(
                "(COALESCE(p.spend_micros, 0) > 0 OR COALESCE(p.impressions, 0) > 0)"
            )
        elif activity == "inactive":
            conditions.append(
                "COALESCE(p.spend_micros, 0) = 0 AND COALESCE(p.impressions, 0) = 0"
            )
        search_term = (search or "").strip()
        if search_term:
            pattern = f"%{search_term}%"
            conditions.append(
                "(c.id ILIKE %s OR COALESCE(c.name, '') ILIKE %s OR "
                "COALESCE(c.advertiser_name, '') ILIKE %s OR "
                "COALESCE(c.utm_campaign, '') ILIKE %s)"
            )
            params.extend([pattern, pattern, pattern, pattern])

        sql = f"""
            WITH perf AS (
                SELECT creative_id,
                       COALESCE(SUM(spend_micros), 0)::bigint AS spend_micros,
                       COALESCE(SUM(impressions), 0)::bigint AS impressions,
                       ARRAY_AGG(DISTINCT metric_date ORDER BY metric_date) AS source_dates
                FROM config_creative_daily
                WHERE buyer_account_id = %s
                  AND metric_date BETWEEN %s AND %s
                GROUP BY creative_id
            ), ranked AS (
                SELECT c.id AS creative_id,
                       c.buyer_id,
                       c.name,
                       c.format,
                       c.approval_status,
                       c.final_url,
                       c.display_url,
                       c.raw_data,
                       COALESCE(p.spend_micros, 0)::bigint AS spend_micros,
                       COALESCE(p.impressions, 0)::bigint AS impressions,
                       p.source_dates,
                       ROW_NUMBER() OVER (
                           ORDER BY COALESCE(p.spend_micros, 0) DESC, c.id ASC
                       )::int AS spend_rank
                FROM creatives c
                LEFT JOIN perf p ON p.creative_id = c.id
                WHERE {' AND '.join(conditions)}
            )
            SELECT *
            FROM ranked
        """
        if cursor:
            sql += (
                " WHERE spend_micros < %s"
                " OR (spend_micros = %s AND creative_id > %s)"
            )
            params.extend([cursor[0], cursor[0], cursor[1]])
        sql += " ORDER BY spend_micros DESC, creative_id ASC LIMIT %s"
        params.append(limit)
        return await pg_query_with_timeout(
            sql,
            tuple(params),
            statement_timeout_ms=self.statement_timeout_ms,
        )


class AgentCreativesService:
    """Build compact creative evidence without raw-table fallbacks."""

    def __init__(self, repo: AgentCreativesRepository | None = None) -> None:
        self._repo = repo or AgentCreativesRepository()

    async def list_creatives(
        self,
        *,
        buyer_id: str,
        start_date: date,
        end_date: date,
        domain: str | None = None,
        creative_format: str | None = None,
        approval_filter: str = "all",
        activity: str = "all",
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if end_date < start_date:
            raise HTTPException(
                status_code=400, detail="end_date must be on or after start_date."
            )
        requested_days = (end_date - start_date).days + 1
        if requested_days > MAX_CREATIVE_RANGE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Date range is limited to {MAX_CREATIVE_RANGE_DAYS} "
                    "days per request."
                ),
            )

        decoded_cursor = _decode_cursor(cursor)
        normalized_domain = _normalize_domain(domain)
        rows = await self._repo.list_creatives(
            buyer_id=buyer_id,
            start_date=start_date,
            end_date=end_date,
            domain=normalized_domain,
            creative_format=creative_format.upper() if creative_format else None,
            approval_filter=approval_filter,
            activity=activity,
            search=search,
            cursor=decoded_cursor,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        requested_dates = _requested_dates(start_date, end_date)
        creatives = [
            self._list_row(row, buyer_id=buyer_id, requested_dates=requested_dates)
            for row in page_rows
        ]
        next_cursor = None
        if has_more and page_rows:
            last_row = page_rows[-1]
            next_cursor = _encode_cursor(
                _int(last_row.get("spend_micros")),
                str(last_row["creative_id"]),
            )

        return {
            "api_version": "agent.v1",
            "buyer_id": buyer_id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": requested_days,
            },
            "source_table": "config_creative_daily",
            "creatives": creatives,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def _list_row(
        self,
        row: dict[str, Any],
        *,
        buyer_id: str,
        requested_dates: list[str],
    ) -> dict[str, Any]:
        source_dates = {
            _date_str(value) for value in (row.get("source_dates") or [])
        }
        missing_dates = [value for value in requested_dates if value not in source_dates]
        latest_complete_date: str | None = None
        for value in requested_dates:
            if value not in source_dates:
                break
            latest_complete_date = value
        spend_micros = _int(row.get("spend_micros"))
        impressions = _int(row.get("impressions"))
        creative = SimpleNamespace(**row)
        creative_id = str(row["creative_id"])
        return {
            "creative_id": creative_id,
            "buyer_id": str(row["buyer_id"]),
            "name": str(row.get("name") or creative_id),
            "format": str(row.get("format") or "UNKNOWN"),
            "approval_status": row.get("approval_status"),
            "destination_url": row.get("final_url") or row.get("display_url"),
            "resolved_destination_url": resolve_creative_destination_url(creative),
            "preview_reference": (
                f"/api/agent/v1/creatives/{quote(creative_id, safe='')}/assets"
            ),
            "activity_status": (
                "active" if spend_micros > 0 or impressions > 0 else "inactive"
            ),
            "metrics": {
                "spend_micros": spend_micros,
                "impressions": impressions,
                "spend_rank": _int(row.get("spend_rank")),
                "provenance": build_provenance(
                    metric_source="config_creative_daily",
                    is_canonical=False,
                    buyer_scope=buyer_id,
                    latest_complete_date=latest_complete_date,
                    latest_source_date=max(source_dates) if source_dates else None,
                    missing_source_dates=missing_dates,
                ),
            },
        }
