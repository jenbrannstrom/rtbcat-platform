"""Tests for conversion taxonomy normalization helpers."""

from services.conversion_taxonomy import (
    normalize_source_type,
    normalize_event_type,
    normalize_attribution_type,
    normalize_fraud_status,
    normalize_currency,
)


def test_normalize_source_type_known_values():
    assert normalize_source_type("AppsFlyer") == "appsflyer"
    assert normalize_source_type("manual_csv") == "manual_csv"


def test_normalize_source_type_unknown_falls_back_to_generic():
    assert normalize_source_type("custom_vendor") == "generic"
    assert normalize_source_type(None) == "generic"


def test_normalize_event_type_cross_source_registration_maps_consistently():
    assert normalize_event_type("af_complete_registration", source_type="appsflyer") == "registration"
    assert normalize_event_type("registration", source_type="adjust") == "registration"
    assert normalize_event_type("complete_registration", source_type="branch") == "registration"


def test_normalize_event_type_aliases_and_unknown():
    assert normalize_event_type("FTD", source_type="generic") == "first_deposit"
    assert normalize_event_type("begin-checkout", source_type="generic") == "checkout"
    assert normalize_event_type("brand_new_event", source_type="generic") == "custom"


def test_normalize_event_type_prefers_explicit_event_type():
    assert (
        normalize_event_type(
            "some-random-event",
            source_type="appsflyer",
            event_type="purchase",
        )
        == "purchase"
    )


def test_normalize_attribution_type():
    assert normalize_attribution_type("lastClick") == "last_click"
    assert normalize_attribution_type("view-through") == "view_through"
    assert normalize_attribution_type("organic") == "organic"
    assert normalize_attribution_type("strange") == "unknown"


def test_normalize_fraud_status():
    assert normalize_fraud_status("clean") == "clean"
    assert normalize_fraud_status("suspect") == "suspected"
    assert normalize_fraud_status("fraud") == "confirmed_fraud"
    assert normalize_fraud_status("") == "unknown"


def test_normalize_currency():
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("EUR") == "EUR"
    assert normalize_currency("us-dollar") is None
    assert normalize_currency(None) is None
