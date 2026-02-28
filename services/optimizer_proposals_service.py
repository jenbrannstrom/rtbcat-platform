"""QPS proposal generation and workflow operations for BYOM optimizer."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from storage.postgres_database import pg_execute, pg_query, pg_query_one


_ALLOWED_STATUSES = {"draft", "approved", "applied", "rejected"}


def _to_iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _to_dict(value: Any, default: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return default or {}


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item is not None]
        except json.JSONDecodeError:
            pass
    return []


class OptimizerProposalsService:
    """Builds and manages QPS allocation proposals."""

    async def generate_from_scores(
        self,
        *,
        model_id: str,
        buyer_id: str,
        days: int = 7,
        min_confidence: float = 0.3,
        max_delta_pct: float = 0.3,
        limit: int = 200,
    ) -> dict[str, Any]:
        safe_days = max(1, min(days, 90))
        safe_confidence = max(0.0, min(min_confidence, 1.0))
        safe_delta = max(0.05, min(max_delta_pct, 1.0))
        safe_limit = max(1, min(limit, 2000))

        score_rows = await pg_query(
            """
            SELECT
                score_id,
                model_id,
                buyer_id,
                billing_id,
                score_date,
                value_score,
                confidence,
                reason_codes,
                raw_response
            FROM segment_scores
            WHERE model_id = %s
                AND buyer_id = %s
                AND score_date >= CURRENT_DATE - %s::int
                AND COALESCE(confidence, 0) >= %s
            ORDER BY score_date DESC, value_score DESC
            LIMIT %s
            """,
            (model_id, buyer_id, safe_days, safe_confidence, safe_limit),
        )

        created = 0
        proposals: list[dict[str, Any]] = []
        for row in score_rows:
            proposal = self._build_proposal_row(
                model_id=model_id,
                buyer_id=buyer_id,
                score_row=row,
                max_delta_pct=safe_delta,
            )
            proposals.append(proposal)
            rowcount = await self._insert_proposal(proposal)
            if int(rowcount or 0) > 0:
                created += 1

        top = sorted(proposals, key=lambda item: abs(item["delta_qps"]), reverse=True)[:10]
        return {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "days": safe_days,
            "min_confidence": safe_confidence,
            "max_delta_pct": safe_delta,
            "scores_considered": len(score_rows),
            "proposals_created": created,
            "top_proposals": [
                {
                    "proposal_id": row["proposal_id"],
                    "billing_id": row["billing_id"],
                    "current_qps": row["current_qps"],
                    "proposed_qps": row["proposed_qps"],
                    "delta_qps": row["delta_qps"],
                    "rationale": row["rationale"],
                    "status": row["status"],
                }
                for row in top
            ],
        }

    async def list_proposals(
        self,
        *,
        buyer_id: str,
        model_id: Optional[str] = None,
        billing_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses = ["buyer_id = %s"]
        params: list[Any] = [buyer_id]
        if model_id:
            clauses.append("model_id = %s")
            params.append(model_id)
        if billing_id:
            clauses.append("billing_id = %s")
            params.append(billing_id)
        if status:
            safe_status = status.strip().lower()
            if safe_status not in _ALLOWED_STATUSES:
                raise ValueError("status must be one of: draft, approved, applied, rejected")
            clauses.append("status = %s")
            params.append(safe_status)
        where_sql = " AND ".join(clauses)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = await pg_query(
            f"""
            SELECT
                proposal_id,
                model_id,
                buyer_id,
                billing_id,
                current_qps,
                proposed_qps,
                delta_qps,
                rationale,
                projected_impact,
                status,
                created_at,
                updated_at,
                applied_at
            FROM qps_allocation_proposals
            WHERE {where_sql}
            ORDER BY created_at DESC, proposal_id
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )
        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM qps_allocation_proposals
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)
        payload_rows = [self._row_to_payload(row) for row in rows]
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

    async def update_status(
        self,
        *,
        proposal_id: str,
        buyer_id: str,
        status: str,
    ) -> Optional[dict[str, Any]]:
        safe_status = status.strip().lower()
        if safe_status not in _ALLOWED_STATUSES:
            raise ValueError("status must be one of: draft, approved, applied, rejected")
        if safe_status == "draft":
            raise ValueError("status transition to draft is not supported via workflow endpoint")

        row = await pg_query_one(
            """
            UPDATE qps_allocation_proposals
            SET
                status = %s,
                updated_at = NOW(),
                applied_at = CASE WHEN %s = 'applied' THEN NOW() ELSE applied_at END
            WHERE proposal_id = %s AND buyer_id = %s
            RETURNING
                proposal_id,
                model_id,
                buyer_id,
                billing_id,
                current_qps,
                proposed_qps,
                delta_qps,
                rationale,
                projected_impact,
                status,
                created_at,
                updated_at,
                applied_at
            """,
            (safe_status, safe_status, proposal_id, buyer_id),
        )
        if not row:
            return None
        return self._row_to_payload(row)

    def _build_proposal_row(
        self,
        *,
        model_id: str,
        buyer_id: str,
        score_row: dict[str, Any],
        max_delta_pct: float,
    ) -> dict[str, Any]:
        raw_response = _to_dict(score_row.get("raw_response"))
        reason_codes = _to_list(score_row.get("reason_codes"))
        value_score = _to_float(score_row.get("value_score"))
        confidence = _to_float(score_row.get("confidence"))

        impressions = _to_float(raw_response.get("impressions"))
        baseline_qps = max(10.0, impressions / 86400.0) if impressions > 0 else 10.0
        target_factor = 0.5 + max(0.0, min(value_score, 1.0))
        raw_target_qps = baseline_qps * target_factor
        max_delta = baseline_qps * max_delta_pct
        delta_qps = max(-max_delta, min(raw_target_qps - baseline_qps, max_delta))
        proposed_qps = max(1.0, baseline_qps + delta_qps)

        rationale_tokens = reason_codes[:3] or ["score_driven_adjustment"]
        rationale = (
            f"Based on score {value_score:.3f}, confidence {confidence:.3f}, "
            f"signals: {', '.join(rationale_tokens)}."
        )
        projected_impact = {
            "score_id": str(score_row.get("score_id") or ""),
            "value_score": value_score,
            "confidence": confidence,
            "max_delta_pct": max_delta_pct,
            "delta_pct": (delta_qps / baseline_qps) if baseline_qps > 0 else 0.0,
            "expected_event_lift_pct": round((delta_qps / baseline_qps) * 100.0 * 0.5, 3)
            if baseline_qps > 0
            else 0.0,
        }

        return {
            "proposal_id": f"prp_{uuid.uuid4().hex}",
            "model_id": model_id,
            "buyer_id": buyer_id,
            "billing_id": str(score_row.get("billing_id") or ""),
            "current_qps": round(baseline_qps, 6),
            "proposed_qps": round(proposed_qps, 6),
            "delta_qps": round(delta_qps, 6),
            "rationale": rationale,
            "projected_impact": projected_impact,
            "status": "draft",
        }

    async def _insert_proposal(self, row: dict[str, Any]) -> int:
        return await pg_execute(
            """
            INSERT INTO qps_allocation_proposals (
                proposal_id,
                model_id,
                buyer_id,
                billing_id,
                current_qps,
                proposed_qps,
                delta_qps,
                rationale,
                projected_impact,
                status,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW()
            )
            ON CONFLICT (proposal_id) DO NOTHING
            """,
            (
                row["proposal_id"],
                row["model_id"],
                row["buyer_id"],
                row["billing_id"],
                row["current_qps"],
                row["proposed_qps"],
                row["delta_qps"],
                row["rationale"],
                json.dumps(row["projected_impact"]),
                row["status"],
            ),
        )

    def _row_to_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "proposal_id": str(row.get("proposal_id") or ""),
            "model_id": str(row.get("model_id") or ""),
            "buyer_id": str(row.get("buyer_id") or ""),
            "billing_id": str(row.get("billing_id") or ""),
            "current_qps": _to_float(row.get("current_qps")),
            "proposed_qps": _to_float(row.get("proposed_qps")),
            "delta_qps": _to_float(row.get("delta_qps")),
            "rationale": str(row.get("rationale") or ""),
            "projected_impact": _to_dict(row.get("projected_impact")),
            "status": str(row.get("status") or "draft"),
            "created_at": _to_iso_ts(row.get("created_at")),
            "updated_at": _to_iso_ts(row.get("updated_at")),
            "applied_at": _to_iso_ts(row.get("applied_at")),
        }

