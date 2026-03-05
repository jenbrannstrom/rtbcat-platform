"""Tests for campaign auto-cluster naming sanitation and resolution."""

import pytest

import api.campaigns_router as campaigns_router


def test_sanitize_destination_url_decodes_click_macro_url() -> None:
    raw = (
        "%%Click Url Unesc%%Https%3A%2F%2Fplay.google.com%2Fstore%2Fapps%2Fdetails"
        "%3Fid%3Dcom.super.example"
    )

    cleaned = campaigns_router._sanitize_destination_url(raw)

    assert cleaned.startswith("https://play.google.com/store/apps/details?id=com.super.example")


def test_name_garbage_rejects_numeric_only_values() -> None:
    assert campaigns_router._is_name_garbage("7000000000") is True
    assert campaigns_router._is_name_garbage("123456") is True
    assert campaigns_router._is_name_garbage("Star Trader") is False


def test_extract_cluster_key_and_name_from_encoded_play_url() -> None:
    raw = (
        "%%Click Url Unesc%%Https%3A%2F%2Fplay.google.com%2Fstore%2Fapps%2Fdetails"
        "%3Fid%3Dcom.super.example"
    )

    key, name = campaigns_router._extract_cluster_key_and_name(raw)

    assert key == "play:com.super.example"
    assert campaigns_router._is_usable_name(name)


@pytest.mark.asyncio
async def test_resolve_cluster_display_name_prefers_store_name(monkeypatch) -> None:
    async def _fake_get_app_name(app_id: str, store: str) -> str:
        assert app_id == "com.super.example"
        assert store == "play_store"
        return "Super Example"

    monkeypatch.setattr(campaigns_router, "get_app_name", _fake_get_app_name)

    resolved = await campaigns_router._resolve_cluster_display_name(
        cluster_key="app:com.super.example",
        app_name=None,
        app_id="com.super.example",
        app_store="play_store",
        final_url="https://play.google.com/store/apps/details?id=com.super.example",
        advertiser_name=None,
    )

    assert resolved == "Super Example"

