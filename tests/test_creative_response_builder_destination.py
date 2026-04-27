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


def test_resolve_destination_decodes_macro_prefixed_encoded_html_href() -> None:
    creative = SimpleNamespace(
        final_url="redbrid-7be14.web.app",
        display_url="redbrid-7be14.web.app",
        raw_data={
            "declaredClickThroughUrls": ["redbrid-7be14.web.app"],
            "html": {
                "snippet": (
                    "<a href='%%CLICK_URL_UNESC%%"
                    "https%3A%2F%2Fapp.appsflyer.com%2Fid6740606431"
                    "%3Fpid%3Duplivo2wj_int%26af_ad_id%3D197224"
                    "%26clickid%3D10104%257C276%257C704'>Open</a>"
                )
            },
        },
    )

    diagnostics = build_creative_destination_diagnostics(creative)

    assert diagnostics["resolved_destination_url"].startswith(
        "https://app.appsflyer.com/id6740606431"
    )
    assert "af_ad_id=197224" in diagnostics["resolved_destination_url"]
    assert any(
        row["source"] == "declared_click_through_url"
        and row["url"] == "redbrid-7be14.web.app"
        and row["reason"] == "unsupported_scheme"
        for row in diagnostics["candidates"]
    )
    assert any(
        row["source"] == "html_snippet" and row["eligible"]
        for row in diagnostics["candidates"]
    )


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


def test_click_macro_summary_detects_macro_in_html_snippet() -> None:
    """Macros embedded in HTML hrefs must count as click-path macros."""
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "html": {
                "snippet": (
                    "<a href='%%CLICK_URL_UNESC%%https://example.com/deal?id=1'>"
                    "<img src='https://cdn.example.com/banner.png' /></a>"
                )
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is True
    assert "%%CLICK_URL_UNESC%%" in summary["click_macro_tokens"]
    assert "html_snippet" in summary["url_sources"]
    assert summary["has_payload_only_click_macro"] is False


def test_click_macro_summary_detects_macro_in_html_js_clickthrough() -> None:
    """Click macros in JS click handlers (window.open, location.href) must be detected."""
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "html": {
                "snippet": (
                    '<div onclick="window.open(\'%%CLICK_URL%%\')">'
                    '<img src="https://cdn.example.com/ad.jpg" /></div>'
                )
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is True
    assert "%%CLICK_URL%%" in summary["click_macro_tokens"]
    assert "html_snippet" in summary["url_sources"]


def test_click_macro_summary_native_with_macro_in_js() -> None:
    """Native creatives with click macros embedded in markup must count as click-path macros."""
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "native": {
                "headline": "Great App",
                "clickLinkUrl": "https://play.google.com/store/apps/details?id=com.example",
                "snippet": (
                    '<script>const urls={click:"%%CLICK_URL_UNESC%%'
                    'https://play.google.com/store/apps/details?id=com.example"};</script>'
                ),
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is True
    assert "%%CLICK_URL_UNESC%%" in summary["click_macro_tokens"]
    assert "native_snippet" in summary["url_sources"]


def test_click_macro_summary_native_without_macro() -> None:
    """Native creatives without any click macro must show as missing."""
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "native": {
                "headline": "Great App",
                "clickLinkUrl": "https://play.google.com/store/apps/details?id=com.example",
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is False


def test_click_macro_summary_video_vast_xml() -> None:
    """Click macros in VAST XML must be detected for video creatives."""
    creative = SimpleNamespace(
        final_url=None,
        display_url=None,
        raw_data={
            "video": {
                "videoVastXml": (
                    '<VAST><Ad><InLine><Creatives><Creative>'
                    '<VideoClicks><ClickThrough>%%CLICK_URL_ESC%%https://example.com</ClickThrough>'
                    '</VideoClicks></Creative></Creatives></InLine></Ad></VAST>'
                )
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is True
    assert "%%CLICK_URL_ESC%%" in summary["click_macro_tokens"]
    assert "video_vast_xml" in summary["url_sources"]


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


def test_click_macro_summary_separates_payload_only_tokens_from_click_path() -> None:
    creative = SimpleNamespace(
        final_url="https://example.com/landing",
        display_url="https://example.com/display",
        raw_data={
            "notes": {
                "debug_html": "<div data-token='%%CLICK_URL_UNESC%%'></div>",
            }
        },
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is False
    assert summary["has_payload_click_macro"] is True
    assert summary["has_payload_only_click_macro"] is True
    assert summary["click_macro_tokens"] == []
    assert "%%CLICK_URL_UNESC%%" in summary["payload_click_macro_tokens"]


def test_click_macro_summary_does_not_treat_display_url_as_click_path() -> None:
    creative = SimpleNamespace(
        final_url="https://example.com/landing",
        display_url="%%CLICK_URL_UNESC%%https://example.com/display",
        raw_data={},
    )

    summary = build_creative_click_macro_summary(creative)

    assert summary["has_click_macro"] is False
    assert summary["has_payload_click_macro"] is False
