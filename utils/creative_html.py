"""Helpers for normalizing HTML creative payloads."""

from __future__ import annotations

from typing import Any


_HTML_SNIPPET_KEYS = (
    "snippet",
    "htmlSnippet",
    "html",
    "markup",
    "body",
    "content",
    "code",
)

_HTML_IMAGE_KEYS = (
    "thumbnailUrl",
    "thumbnail_url",
    "previewUrl",
    "preview_url",
    "imageUrl",
    "image_url",
    "creativeUrl",
    "creative_url",
    "url",
)


def get_html_payload(raw_data: dict[str, Any] | None) -> Any:
    """Return the HTML payload from known raw-data shapes."""
    if not isinstance(raw_data, dict):
        return None
    return raw_data.get("html") or raw_data.get("htmlSnippet") or raw_data.get("html_snippet")


def extract_html_snippet(raw_data: dict[str, Any] | None) -> str:
    """Extract HTML markup from canonical and Google-like payload variants."""
    html_payload = get_html_payload(raw_data)
    if isinstance(html_payload, str):
        return html_payload.strip()
    if isinstance(html_payload, dict):
        for key in _HTML_SNIPPET_KEYS:
            value = html_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(raw_data, dict):
        for key in ("htmlSnippet", "html_snippet"):
            value = raw_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def extract_html_dimensions(raw_data: dict[str, Any] | None) -> tuple[Any, Any]:
    """Return width and height from the HTML payload when present."""
    html_payload = get_html_payload(raw_data)
    if isinstance(html_payload, dict):
        return html_payload.get("width"), html_payload.get("height")
    return None, None


def extract_html_image_hints(raw_data: dict[str, Any] | None) -> list[str]:
    """Extract direct image/thumbnail hints from HTML payload metadata."""
    html_payload = get_html_payload(raw_data)
    candidates: list[str] = []
    if isinstance(html_payload, dict):
        for key in _HTML_IMAGE_KEYS:
            value = html_payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                candidates.append(value)
        image = html_payload.get("image")
        if isinstance(image, dict):
            value = image.get("url")
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                candidates.append(value)
    if isinstance(raw_data, dict):
        for key in _HTML_IMAGE_KEYS:
            value = raw_data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                candidates.append(value)

    seen: set[str] = set()
    unique: list[str] = []
    for value in candidates:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def set_html_thumbnail_hint(raw_data: dict[str, Any], thumbnail_url: str) -> dict[str, Any]:
    """Return raw_data with an HTML thumbnail URL hint attached."""
    html_payload = raw_data.get("html")
    if not isinstance(html_payload, dict):
        html_payload = {}
        raw_data["html"] = html_payload
    html_payload.setdefault("thumbnailUrl", thumbnail_url)
    return raw_data
