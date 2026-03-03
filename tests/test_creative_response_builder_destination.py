from __future__ import annotations

from types import SimpleNamespace

from services.creative_destination_resolver import (
    build_creative_click_macro_summary,
    build_creative_destination_diagnostics,
    resolve_creative_destination_url,
)


def test_resolve_destination_prefers_valid_final_url() -> None:
    creative = SimpleNamespace(
        final_url="https://example.com/landing",
        display_url="https://example.com/display",
        raw_data={},
    )

    assert resolve_creative_destination_url(creative) == "https://example.com/landing"


def test_resolve_destination_falls_back_to_declared_url_when_final_is_macro() -> None:
    creative = SimpleNamespace(
        final_url="%%CLICK_URL_UNESC%%",
        display_url=None,
        raw_data={
            "declaredClickThroughUrls": [
                "https://tracking.example.com/pixel.gif",
                "https://example.com/offer",
            ],
        },
    )

    assert resolve_creative_destination_url(creative) == "https://example.com/offer"


def test_resolve_destination_uses_html_click_target_not_image_asset() -> None:
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "html": {
                "snippet": """
                    <a href='%%CLICK_URL_UNESC%%https://example.com/deal?id=1'>
                      <img src='https://cdn.example.com/creative/banner.png' />
                    </a>
                """
            }
        },
    )

    assert resolve_creative_destination_url(creative) == "https://example.com/deal?id=1"


def test_resolve_destination_returns_none_when_only_assets_exist() -> None:
    creative = SimpleNamespace(
        final_url="https://cdn.example.com/creative/banner.jpg",
        display_url=None,
        raw_data={"declaredClickThroughUrls": ["https://cdn.example.com/creative/alt.webp"]},
    )

    assert resolve_creative_destination_url(creative) is None


def test_destination_diagnostics_classifies_rejected_candidates() -> None:
    creative = SimpleNamespace(
        final_url="%%CLICK_URL_UNESC%%",
        display_url="javascript:alert(1)",
        raw_data={
            "declaredClickThroughUrls": [
                "https://cdn.example.com/banner.png",
                "https://example.com/final",
            ],
            "html": {"snippet": "<a href='https://example.com/final'>Open</a>"},
        },
    )

    diagnostics = build_creative_destination_diagnostics(creative)
    assert diagnostics["resolved_destination_url"] == "https://example.com/final"
    assert diagnostics["candidate_count"] >= 4
    assert diagnostics["eligible_count"] == 1

    reasons = {
        (row["source"], row["reason"])
        for row in diagnostics["candidates"]
        if not row["eligible"]
    }
    assert ("final_url", "contains_click_macro") in reasons
    assert ("display_url", "unsupported_scheme") in reasons
    assert ("declared_click_through_url", "asset_url") in reasons
    assert ("html_snippet", "duplicate") in reasons


def test_click_macro_summary_detects_url_encoded_appsflyer_and_clickid() -> None:
    creative = SimpleNamespace(
        final_url=(
            "%%CLICK_URL_UNESC%%https%3A%2F%2Fapp.appsflyer.com%2Fcom.drop.frenzy.bubbly"
            "%3Fpid%3Duplivo2wj_int%26af_siteid%3D%7Badxcode%7D_%7Bbundle%7D"
            "%26clickid%3D%7Bdsp_params%7D"
        ),
        display_url=None,
        raw_data={},
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_appsflyer_url"] is True
    assert summary["has_appsflyer_clickid"] is True
    assert summary["appsflyer_url_count"] == 1
    assert summary["appsflyer_clickid_url_count"] == 1


def test_click_macro_summary_detects_appsflyer_without_clickid() -> None:
    creative = SimpleNamespace(
        final_url=(
            "%%CLICK_URL_UNESC%%https%3A%2F%2Fapp.appsflyer.com%2Fcom.drop.frenzy.bubbly"
            "%3Fpid%3Duplivo2wj_int%26af_siteid%3D%7Badxcode%7D_%7Bbundle%7D"
        ),
        display_url=None,
        raw_data={},
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_appsflyer_url"] is True
    assert summary["has_appsflyer_clickid"] is False
