"""Unit tests for v1 canary smoke readiness validation."""

from __future__ import annotations

import pytest

from scripts.v1_canary_smoke import SmokeFailure, validate_data_health_payload


def _base_payload() -> dict:
    return {
        "optimizer_readiness": {
            "report_completeness": {"availability_state": "healthy"},
            "rtb_quality_freshness": {"availability_state": "healthy"},
            "bidstream_dimension_coverage": {
                "availability_state": "healthy",
                "total_rows": 10,
                "platform_missing_pct": 5.0,
                "environment_missing_pct": 4.0,
                "transaction_type_missing_pct": 3.0,
            },
            "seat_day_completeness": {
                "availability_state": "healthy",
                "summary": {"total_seat_days": 2},
            },
        }
    }


def test_validate_data_health_payload_passes_default_rules():
    payload = _base_payload()
    validate_data_health_payload(
        payload,
        require_healthy_readiness=False,
        max_dimension_missing_pct=99.9,
    )


def test_validate_data_health_payload_rejects_unavailable_quality():
    payload = _base_payload()
    payload["optimizer_readiness"]["rtb_quality_freshness"]["availability_state"] = "unavailable"

    with pytest.raises(SmokeFailure, match="rtb_quality_freshness state is unavailable"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=False,
            max_dimension_missing_pct=99.9,
        )


def test_validate_data_health_payload_rejects_excessive_dimension_missing_pct():
    payload = _base_payload()
    payload["optimizer_readiness"]["bidstream_dimension_coverage"]["platform_missing_pct"] = 61.0

    with pytest.raises(SmokeFailure, match="platform_missing_pct=61.00% exceeds max 60.00%"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=False,
            max_dimension_missing_pct=60.0,
        )


def test_validate_data_health_payload_rejects_non_healthy_when_strict():
    payload = _base_payload()
    payload["optimizer_readiness"]["seat_day_completeness"]["availability_state"] = "degraded"

    with pytest.raises(SmokeFailure, match="seat_day_completeness state is 'degraded', expected healthy"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=True,
            max_dimension_missing_pct=99.9,
        )
