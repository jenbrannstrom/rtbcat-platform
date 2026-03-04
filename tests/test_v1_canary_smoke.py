"""Unit tests for v1 canary smoke readiness validation."""

from __future__ import annotations

import urllib.error
import pytest

from scripts.v1_canary_smoke import (
    SmokeFailure,
    SmokeEnvironmentBlocked,
    SmokeClient,
    build_conversion_readiness_params,
    build_qps_load_latency_requests,
    build_qps_page_slo_params,
    build_webhook_hmac_signature,
    build_webhook_security_headers,
    build_pixel_request_params,
    build_webhook_postback_payload,
    build_workflow_request_params,
    is_auth_blocked_http_response,
    is_network_blocked_urlerror,
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
        bidstream_dimension_waiver=None,
    )


def test_validate_data_health_payload_allows_unavailable_quality():
    payload = _base_payload()
    payload["optimizer_readiness"]["rtb_quality_freshness"]["availability_state"] = "unavailable"

    validate_data_health_payload(
        payload,
        require_healthy_readiness=False,
        max_dimension_missing_pct=99.9,
        bidstream_dimension_waiver=None,
    )


def test_validate_data_health_payload_blocks_unavailable_bidstream():
    payload = _base_payload()
    payload["optimizer_readiness"]["bidstream_dimension_coverage"]["availability_state"] = "unavailable"
    payload["optimizer_readiness"]["bidstream_dimension_coverage"]["total_rows"] = 0

    with pytest.raises(SmokeEnvironmentBlocked, match="bidstream dimension coverage is unavailable"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=False,
            max_dimension_missing_pct=99.9,
            bidstream_dimension_waiver=None,
        )


def test_validate_data_health_payload_rejects_excessive_dimension_missing_pct():
    payload = _base_payload()
    payload["optimizer_readiness"]["bidstream_dimension_coverage"]["platform_missing_pct"] = 61.0

    with pytest.raises(SmokeFailure, match="platform_missing_pct=61.00% exceeds max 60.00%"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=False,
            max_dimension_missing_pct=60.0,
            bidstream_dimension_waiver=None,
        )


def test_validate_data_health_payload_rejects_non_healthy_when_strict():
    payload = _base_payload()
    payload["optimizer_readiness"]["seat_day_completeness"]["availability_state"] = "degraded"

    with pytest.raises(SmokeFailure, match="seat_day_completeness state is 'degraded', expected healthy"):
        validate_data_health_payload(
            payload,
            require_healthy_readiness=True,
            max_dimension_missing_pct=99.9,
            bidstream_dimension_waiver=None,
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


def test_build_qps_load_latency_requests_includes_buyer_and_days():
    requests = build_qps_load_latency_requests(
        buyer_id="buyer-1",
        days=21,
    )
    assert len(requests) == 4
    by_path = {path: params for path, params in requests}
    assert by_path["/settings/endpoints"]["buyer_id"] == "buyer-1"
    assert by_path["/settings/endpoints"]["live"] == "true"
    assert by_path["/settings/pretargeting"]["buyer_id"] == "buyer-1"
    assert by_path["/analytics/home/configs"]["days"] == 21
    assert by_path["/analytics/home/endpoint-efficiency"]["days"] == 21


def test_build_qps_page_slo_params_includes_expected_fields():
    params = build_qps_page_slo_params(
        buyer_id="buyer-1",
        since_hours=24,
        latest_limit=7,
        api_rollup_limit=15,
    )
    assert params["page"] == "qps_home"
    assert params["buyer_id"] == "buyer-1"
    assert params["since_hours"] == 24
    assert params["latest_limit"] == 7
    assert params["api_rollup_limit"] == 15


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


def test_build_webhook_hmac_signature_is_deterministic_with_timestamp():
    payload = {
        "buyer_id": "buyer-1",
        "source_type": "generic",
        "event_name": "purchase",
        "event_ts": "2026-03-01T00:00:00+00:00",
        "event_id": "evt-123",
    }
    sig_a = build_webhook_hmac_signature(secret="test-secret", payload=payload, timestamp=1709251200)
    sig_b = build_webhook_hmac_signature(secret="test-secret", payload=payload, timestamp=1709251200)
    assert sig_a == sig_b
    assert len(sig_a) == 64


def test_build_webhook_hmac_signature_changes_with_timestamp():
    payload = {
        "buyer_id": "buyer-1",
        "source_type": "generic",
        "event_name": "purchase",
        "event_ts": "2026-03-01T00:00:00+00:00",
        "event_id": "evt-123",
    }
    sig_a = build_webhook_hmac_signature(secret="test-secret", payload=payload, timestamp=1709251200)
    sig_b = build_webhook_hmac_signature(secret="test-secret", payload=payload, timestamp=1709251201)
    assert sig_a != sig_b


def test_build_webhook_security_headers_with_secret_only():
    payload = {
        "source_type": "generic",
        "event_name": "purchase",
        "event_ts": "2026-03-01T00:00:00+00:00",
        "event_id": "evt-123",
    }
    headers = build_webhook_security_headers(
        webhook_secret="secret-1",
        webhook_hmac_secret=None,
        payload=payload,
    )
    assert headers == {"X-Webhook-Secret": "secret-1"}


def test_build_webhook_security_headers_with_hmac_signature():
    payload = {
        "source_type": "generic",
        "event_name": "purchase",
        "event_ts": "2026-03-01T00:00:00+00:00",
        "event_id": "evt-123",
    }
    headers = build_webhook_security_headers(
        webhook_secret=None,
        webhook_hmac_secret="hmac-secret",
        payload=payload,
        timestamp=1709251200,
    )
    expected = build_webhook_hmac_signature(
        secret="hmac-secret",
        payload=payload,
        timestamp=1709251200,
    )
    assert headers["X-Webhook-Timestamp"] == "1709251200"
    assert headers["X-Signature"] == f"sha256={expected}"


def test_build_webhook_security_headers_can_force_invalid_signature():
    payload = {
        "source_type": "generic",
        "event_name": "purchase",
        "event_ts": "2026-03-01T00:00:00+00:00",
        "event_id": "evt-123",
    }
    headers = build_webhook_security_headers(
        webhook_secret="secret-1",
        webhook_hmac_secret="hmac-secret",
        payload=payload,
        timestamp=1709251200,
        force_invalid_signature=True,
    )
    assert headers["X-Webhook-Secret"] == "secret-1"
    assert headers["X-Webhook-Timestamp"] == "1709251200"
    assert headers["X-Signature"] == "sha256=invalid-signature"


def test_is_network_blocked_urlerror_detects_operation_not_permitted():
    exc = urllib.error.URLError(OSError(1, "Operation not permitted"))
    assert is_network_blocked_urlerror(exc) is True


def test_is_network_blocked_urlerror_detects_temporary_dns_resolution_failure():
    exc = urllib.error.URLError(OSError(-3, "Temporary failure in name resolution"))
    assert is_network_blocked_urlerror(exc) is True


def test_is_network_blocked_urlerror_ignores_connection_refused():
    exc = urllib.error.URLError(OSError(111, "Connection refused"))
    assert is_network_blocked_urlerror(exc) is False


def test_is_auth_blocked_http_response_detects_expired_session():
    assert is_auth_blocked_http_response(
        401,
        '{"detail":"Session expired or invalid. Please log in again."}',
    ) is True


def test_is_auth_blocked_http_response_ignores_non_auth_status():
    assert is_auth_blocked_http_response(500, '{"detail":"internal error"}') is False


def test_smoke_client_raises_environment_blocked_for_permission_denied_urlerror(
    monkeypatch: pytest.MonkeyPatch,
):
    def _raise_url_error(*_args, **_kwargs):
        raise urllib.error.URLError(OSError(1, "Operation not permitted"))

    monkeypatch.setattr("scripts.v1_canary_smoke.urllib.request.urlopen", _raise_url_error)
    client = SmokeClient(base_url="http://127.0.0.1:8000", token=None, cookie=None, timeout=1.0)

    with pytest.raises(SmokeEnvironmentBlocked, match="outbound network blocked"):
        client.request("GET", "/health")


def test_smoke_client_raises_environment_blocked_for_expired_session_http_response(
    monkeypatch: pytest.MonkeyPatch,
):
    def _mock_request_status_bytes(self, *_args, **_kwargs):
        return 401, {}, b'{"detail":"Session expired or invalid. Please log in again."}'

    monkeypatch.setattr(SmokeClient, "request_status_bytes", _mock_request_status_bytes)
    client = SmokeClient(base_url="http://127.0.0.1:8000", token=None, cookie=None, timeout=1.0)

    with pytest.raises(SmokeEnvironmentBlocked, match="auth blocked"):
        client.request("GET", "/system/data-health")
