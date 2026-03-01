"""Unit tests for v1 canary smoke readiness validation."""

from __future__ import annotations

import pytest

from scripts.v1_canary_smoke import (
    SmokeFailure,
    build_conversion_readiness_params,
    build_pixel_request_params,
    build_webhook_postback_payload,
    build_workflow_request_params,
    validate_data_health_payload,
)


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


def test_build_workflow_request_params_includes_profile_when_present():
    params = build_workflow_request_params(
        model_id="model-1",
        buyer_id="buyer-1",
        workflow_days=14,
        workflow_score_limit=1000,
        workflow_proposal_limit=200,
        workflow_min_confidence=0.3,
        workflow_max_delta_pct=0.3,
        workflow_profile="balanced",
    )
    assert params["profile"] == "balanced"
    assert params["days"] == 14
    assert params["score_limit"] == 1000


def test_build_workflow_request_params_omits_profile_when_missing():
    params = build_workflow_request_params(
        model_id="model-1",
        buyer_id=None,
        workflow_days=14,
        workflow_score_limit=1000,
        workflow_proposal_limit=200,
        workflow_min_confidence=0.3,
        workflow_max_delta_pct=0.3,
        workflow_profile=None,
    )
    assert "profile" not in params
    assert params["buyer_id"] is None


def test_build_pixel_request_params_includes_buyer_id_when_present():
    params = build_pixel_request_params(
        buyer_id="buyer-1",
        pixel_source_type="pixel",
        pixel_event_name="purchase",
        event_ts="2026-03-01T00:00:00+00:00",
        event_id="evt-1",
    )
    assert params["buyer_id"] == "buyer-1"
    assert params["source_type"] == "pixel"
    assert params["event_name"] == "purchase"


def test_build_pixel_request_params_allows_missing_buyer_id():
    params = build_pixel_request_params(
        buyer_id=None,
        pixel_source_type="pixel",
        pixel_event_name="purchase",
        event_ts="2026-03-01T00:00:00+00:00",
        event_id="evt-1",
    )
    assert params["buyer_id"] is None
    assert params["event_id"] == "evt-1"


def test_build_conversion_readiness_params_includes_fields():
    params = build_conversion_readiness_params(
        buyer_id="buyer-1",
        days=14,
        freshness_hours=72,
    )
    assert params["buyer_id"] == "buyer-1"
    assert params["days"] == 14
    assert params["freshness_hours"] == 72


def test_build_webhook_postback_payload_includes_expected_fields():
    payload = build_webhook_postback_payload(
        buyer_id="buyer-1",
        source_type="generic",
        event_name="purchase",
        event_ts="2026-03-01T00:00:00+00:00",
        event_id="evt-123",
    )
    assert payload["buyer_id"] == "buyer-1"
    assert payload["source_type"] == "generic"
    assert payload["event_name"] == "purchase"
    assert payload["event_id"] == "evt-123"
