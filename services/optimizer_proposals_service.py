"""QPS proposal generation and workflow operations for BYOM optimizer."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from services.changes_service import ChangesService
from services.pretargeting_service import PretargetingService
from storage.postgres_database import pg_execute, pg_query, pg_query_one

if TYPE_CHECKING:
    from services.actions_service import ActionsService


_ALLOWED_STATUSES = {"draft", "approved", "applied", "rejected"}
_ALLOWED_APPLY_MODES = {"queue", "live"}


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

    def __init__(
        self,
        *,
        changes_service: ChangesService | None = None,
        pretargeting_service: PretargetingService | None = None,
        actions_service: "ActionsService | None" = None,
    ) -> None:
        self._changes = changes_service or ChangesService()
        self._pretargeting = pretargeting_service or PretargetingService()
        self._actions = actions_service

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
        apply_mode: str = "queue",
        applied_by: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        safe_status = status.strip().lower()
        if safe_status not in _ALLOWED_STATUSES:
            raise ValueError("status must be one of: draft, approved, applied, rejected")
        if safe_status == "draft":
            raise ValueError("status transition to draft is not supported via workflow endpoint")
        safe_apply_mode = str(apply_mode or "queue").strip().lower()
        if safe_apply_mode not in _ALLOWED_APPLY_MODES:
            raise ValueError("apply_mode must be one of: queue, live")

        if safe_status == "applied":
            return await self._apply_proposal(
                proposal_id=proposal_id,
                buyer_id=buyer_id,
                apply_mode=safe_apply_mode,
                applied_by=applied_by,
            )

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

    async def _apply_proposal(
        self,
        *,
        proposal_id: str,
        buyer_id: str,
        apply_mode: str,
        applied_by: Optional[str],
    ) -> Optional[dict[str, Any]]:
        proposal = await pg_query_one(
            """
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
            WHERE proposal_id = %s AND buyer_id = %s
            LIMIT 1
            """,
            (proposal_id, buyer_id),
        )
        if not proposal:
            return None

        billing_id = str(proposal.get("billing_id") or "").strip()
        if not billing_id:
            raise ValueError("Cannot apply proposal without billing_id")

        pretargeting_config = await self._pretargeting.get_config(billing_id)
        if not pretargeting_config:
            raise ValueError(f"Pretargeting config not found for billing_id={billing_id}")

        proposed_qps = _to_float(proposal.get("proposed_qps"))
        qps_value = max(0, int(round(proposed_qps)))
        pending_change_id = await self._changes.create_pending_change(
            config_id=str(pretargeting_config.get("config_id") or ""),
            billing_id=billing_id,
            change_type="set_maximum_qps",
            field_name="maximum_qps",
            value=str(qps_value),
            reason=f"optimizer_proposal:{proposal_id}",
            estimated_qps_impact=_to_float(proposal.get("delta_qps")),
            created_by=applied_by or "optimizer",
        )

        live_result: Optional[dict[str, Any]] = None
        if apply_mode == "live":
            if self._actions is None:
                from services.actions_service import ActionsService
                self._actions = ActionsService()
            live_result = await self._actions.apply_pending_change(
                billing_id=billing_id,
                change_id=int(pending_change_id),
                dry_run=False,
            )

        projected = _to_dict(proposal.get("projected_impact"))
        projected["apply"] = {
            "mode": apply_mode,
            "pending_change_id": int(pending_change_id),
            "queued_maximum_qps": qps_value,
            "applied_by": applied_by,
            "live_result": live_result,
        }

        row = await pg_query_one(
            """
            UPDATE qps_allocation_proposals
            SET
                status = 'applied',
                projected_impact = %s::jsonb,
                updated_at = NOW(),
                applied_at = NOW()
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
            (json.dumps(projected), proposal_id, buyer_id),
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
        projected_impact = _to_dict(row.get("projected_impact"))
        apply_details = projected_impact.get("apply")
        return {
            "proposal_id": str(row.get("proposal_id") or ""),
            "model_id": str(row.get("model_id") or ""),
            "buyer_id": str(row.get("buyer_id") or ""),
            "billing_id": str(row.get("billing_id") or ""),
            "current_qps": _to_float(row.get("current_qps")),
            "proposed_qps": _to_float(row.get("proposed_qps")),
            "delta_qps": _to_float(row.get("delta_qps")),
            "rationale": str(row.get("rationale") or ""),
            "projected_impact": projected_impact,
            "apply_details": apply_details if isinstance(apply_details, dict) else None,
            "status": str(row.get("status") or "draft"),
            "created_at": _to_iso_ts(row.get("created_at")),
            "updated_at": _to_iso_ts(row.get("updated_at")),
            "applied_at": _to_iso_ts(row.get("applied_at")),
        }
