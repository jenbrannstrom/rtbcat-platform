from __future__ import annotations

from types import SimpleNamespace

from services.creative_destination_resolver import resolve_creative_destination_url


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
