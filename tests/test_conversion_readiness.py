"""Unit tests for conversion readiness scoring."""

from __future__ import annotations

from services.conversion_readiness import compute_conversion_readiness_payload


def _health_payload(state: str = "healthy", lag_hours: float | None = 1.0) -> dict:
    return {
        "state": state,
        "ingestion": {
            "lag_hours": lag_hours,
        },
    }


def _stats_payload(accepted_total: int, rejected_total: int, rows: list[dict]) -> dict:
    return {
        "accepted_total": accepted_total,
        "rejected_total": rejected_total,
        "rows": rows,
    }


def test_compute_conversion_readiness_ready_state():
    payload = compute_conversion_readiness_payload(
        health_payload=_health_payload(state="healthy", lag_hours=1.0),
        stats_payload=_stats_payload(
            accepted_total=10,
            rejected_total=2,
            rows=[{"source_type": "appsflyer", "accepted_count": 10, "rejected_count": 2}],
        ),
        buyer_id="1111111111",
        days=14,
        freshness_hours=72,
    )

    assert payload["state"] == "ready"
    assert payload["ingestion_fresh"] is True
    assert payload["accepted_total"] == 10
    assert payload["active_sources"] == 1
    assert payload["reasons"] == []


def test_compute_conversion_readiness_not_ready_when_no_accepted_events():
    payload = compute_conversion_readiness_payload(
        health_payload=_health_payload(state="healthy", lag_hours=1.0),
        stats_payload=_stats_payload(
            accepted_total=0,
            rejected_total=0,
            rows=[{"source_type": "appsflyer", "accepted_count": 0, "rejected_count": 0}],
        ),
        buyer_id="1111111111",
        days=14,
        freshness_hours=72,
    )

    assert payload["state"] == "not_ready"
    assert any("no accepted conversion events" in reason for reason in payload["reasons"])


def test_compute_conversion_readiness_degraded_when_lag_exceeds_threshold():
    payload = compute_conversion_readiness_payload(
        health_payload=_health_payload(state="healthy", lag_hours=120.0),
        stats_payload=_stats_payload(
            accepted_total=5,
            rejected_total=1,
            rows=[{"source_type": "generic", "accepted_count": 5, "rejected_count": 1}],
        ),
        buyer_id="1111111111",
        days=14,
        freshness_hours=72,
    )

    assert payload["state"] == "degraded"
    assert payload["ingestion_fresh"] is False
    assert any("exceeds threshold" in reason for reason in payload["reasons"])


def test_compute_conversion_readiness_unavailable_takes_precedence():
    payload = compute_conversion_readiness_payload(
        health_payload=_health_payload(state="unavailable", lag_hours=None),
        stats_payload=_stats_payload(
            accepted_total=10,
            rejected_total=2,
            rows=[{"source_type": "appsflyer", "accepted_count": 10, "rejected_count": 2}],
        ),
        buyer_id="1111111111",
        days=14,
        freshness_hours=72,
    )

    assert payload["state"] == "unavailable"
    assert any("unavailable" in reason for reason in payload["reasons"])
