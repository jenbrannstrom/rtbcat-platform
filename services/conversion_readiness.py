"""Conversion readiness scoring helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def compute_conversion_readiness_payload(
    *,
    health_payload: dict[str, Any],
    stats_payload: dict[str, Any],
    buyer_id: Optional[str],
    days: int,
    freshness_hours: int,
) -> dict[str, Any]:
    ingestion = health_payload.get("ingestion") or {}
    raw_lag_hours = ingestion.get("lag_hours")
    try:
        ingestion_lag_hours = float(raw_lag_hours) if raw_lag_hours is not None else None
    except (TypeError, ValueError):
        ingestion_lag_hours = None

    accepted_total = int(stats_payload.get("accepted_total") or 0)
    rejected_total = int(stats_payload.get("rejected_total") or 0)
    rows = stats_payload.get("rows") or []
    active_sources = sum(
        1
        for row in rows
        if isinstance(row, dict) and int(row.get("accepted_count") or 0) > 0
    )

    reasons: list[str] = []
    health_state = str(health_payload.get("state", "")).lower()
    if health_state == "unavailable":
        reasons.append("conversion health state is unavailable")
    if accepted_total <= 0:
        reasons.append(f"no accepted conversion events in last {days} days")
    ingestion_fresh = ingestion_lag_hours is not None and ingestion_lag_hours <= freshness_hours
    if ingestion_lag_hours is None:
        reasons.append("conversion ingestion lag is unknown")
    elif not ingestion_fresh:
        reasons.append(
            f"conversion ingestion lag {ingestion_lag_hours:.1f}h exceeds threshold {freshness_hours}h"
        )

    readiness_state = "ready"
    if reasons:
        if health_state == "unavailable":
            readiness_state = "unavailable"
        elif accepted_total <= 0:
            readiness_state = "not_ready"
        else:
            readiness_state = "degraded"

    return {
        "state": readiness_state,
        "buyer_id": buyer_id,
        "window_days": days,
        "freshness_threshold_hours": freshness_hours,
        "accepted_total": accepted_total,
        "rejected_total": rejected_total,
        "active_sources": active_sources,
        "ingestion_lag_hours": ingestion_lag_hours,
        "ingestion_fresh": ingestion_fresh,
        "reasons": reasons,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
