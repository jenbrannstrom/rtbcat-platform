"""Tests for provider-specific conversion payload normalizers."""

from services.conversion_normalizers import (
    normalize_adjust_payload,
    normalize_appsflyer_payload,
    normalize_appsflyer_payload_with_diagnostics,
    normalize_branch_payload,
    normalize_generic_payload,
)


def test_normalize_appsflyer_payload_maps_core_fields():
    payload = {
        "eventName": "af_purchase",
        "eventTime": "2026-02-28T00:00:00Z",
        "af_sub1": "1111111111",
        "af_sub2": "cfg-1",
        "af_click_id": "clk-1",
        "country_code": "US",
    }
    normalized = normalize_appsflyer_payload(payload)
    assert normalized["event_name"] == "af_purchase"
    assert normalized["event_ts"] == "2026-02-28T00:00:00Z"
    assert normalized["buyer_id"] == "1111111111"
    assert normalized["billing_id"] == "cfg-1"
    assert normalized["click_id"] == "clk-1"
    assert normalized["country"] == "US"


def test_normalize_appsflyer_payload_allows_custom_mapping_profile():
    payload = {
        "eventName": "af_purchase",
        "eventTime": "2026-02-28T00:00:00Z",
        "af_sub1": "creative-1",
        "af_sub2": "1111111111",
        "clickid": "clk-2",
    }
    normalized = normalize_appsflyer_payload(
        payload,
        field_map={
            "buyer_id": ["af_sub2"],
            "creative_id": ["af_sub1"],
        },
    )
    assert normalized["buyer_id"] == "1111111111"
    assert normalized["creative_id"] == "creative-1"
    assert normalized["click_id"] == "clk-2"


def test_normalize_appsflyer_payload_keeps_existing_canonical_values():
    payload = {
        "buyer_id": "1111111111",
        "creative_id": "cr-7",
        "af_sub1": "should-not-overwrite",
        "af_sub2": "also-ignore",
    }
    normalized = normalize_appsflyer_payload(
        payload,
        field_map={
            "buyer_id": ["af_sub2"],
            "creative_id": ["af_sub1"],
        },
    )
    assert normalized["buyer_id"] == "1111111111"
    assert normalized["creative_id"] == "cr-7"


def test_normalize_appsflyer_payload_with_diagnostics_tracks_unresolved_fields():
    payload = {
        "eventName": "af_purchase",
        "eventTime": "2026-02-28T00:00:00Z",
        "af_sub2": "1111111111",
    }
    normalized, diagnostics = normalize_appsflyer_payload_with_diagnostics(
        payload,
        field_map={
            "buyer_id": ["af_sub2"],
            "creative_id": ["af_sub1"],
            "click_id": ["clickid"],
        },
    )

    assert normalized["buyer_id"] == "1111111111"
    assert diagnostics["mapping_scope_fields_total"] == 3
    assert diagnostics["resolved_fields_count"] == 1
    assert diagnostics["unknown_mapping_count"] == 2
    assert set(diagnostics["unresolved_fields"]) == {"creative_id", "click_id"}
    assert diagnostics["field_hits"]["buyer_id"] == "af_sub2"


def test_normalize_adjust_payload_maps_core_fields():
    payload = {
        "event_token": "first_deposit",
        "created_at": "2026-02-28T00:00:00Z",
        "click_time": "2026-02-27T23:00:00Z",
        "campaign_name": "camp-1",
        "revenue": "40.0",
        "currency": "usd",
        "os_name": "android",
    }
    normalized = normalize_adjust_payload(payload)
    assert normalized["event_name"] == "first_deposit"
    assert normalized["event_ts"] == "2026-02-28T00:00:00Z"
    assert normalized["click_ts"] == "2026-02-27T23:00:00Z"
    assert normalized["campaign_id"] == "camp-1"
    assert normalized["event_value"] == "40.0"
    assert normalized["currency"] == "usd"
    assert normalized["platform"] == "android"


def test_normalize_branch_payload_maps_core_fields():
    payload = {
        "name": "purchase",
        "timestamp": "2026-02-28T00:00:00Z",
        "~campaign": "camp-1",
        "~id": "clk-2",
        "revenue": 12.5,
        "currency": "EUR",
        "os": "ios",
    }
    normalized = normalize_branch_payload(payload)
    assert normalized["event_name"] == "purchase"
    assert normalized["event_ts"] == "2026-02-28T00:00:00Z"
    assert normalized["campaign_id"] == "camp-1"
    assert normalized["click_id"] == "clk-2"
    assert normalized["event_value"] == 12.5
    assert normalized["currency"] == "EUR"
    assert normalized["platform"] == "ios"


def test_normalize_generic_payload_passthrough():
    payload = {"event_name": "install", "buyer_id": "1111111111"}
    normalized = normalize_generic_payload(payload)
    assert normalized == payload
