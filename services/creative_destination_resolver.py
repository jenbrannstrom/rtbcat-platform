"""Resolve canonical click destination URLs from creative payloads."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse


_ASSET_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    ".mp4",
    ".webm",
    ".m4v",
    ".mov",
    ".js",
    ".css",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
)
_CLICK_MACRO_PATTERN = re.compile(r"%%[A-Z_]+%%")


def extract_click_destinations_from_html(html_snippet: str) -> list[str]:
    if not html_snippet:
        return []
    candidates: list[str] = []

    def _append_urls(value: str) -> None:
        urls = re.findall(r"https?://[^\s\"'<>]+", value)
        for url in urls:
            cleaned = url.rstrip(",;)}]>")
            if cleaned not in candidates:
                candidates.append(cleaned)

    for pattern in (
        r"\bhref\s*=\s*(['\"])(.*?)\1",
        r"\bhref\s*=\s*([^\s\"'<>]+)",
        r"%%[A-Z_]+%%\s*(https?://[^\s\"'<>]+)",
        r"(?:window\.open|location\.href\s*=|location\.assign\()\s*['\"]([^'\"]+)['\"]",
    ):
        for match in re.findall(pattern, html_snippet, re.IGNORECASE):
            value = match[1] if isinstance(match, tuple) else match
            _append_urls(value)
    return candidates


def is_probably_click_destination(url: Optional[str]) -> bool:
    if not url:
        return False
    value = str(url).strip()
    if not value:
        return False
    if _CLICK_MACRO_PATTERN.search(value):
        return False
    if not value.startswith(("http://", "https://")):
        return False
    try:
        parsed = urlparse(value)
        if not parsed.netloc:
            return False
        return not parsed.path.lower().endswith(_ASSET_EXTENSIONS)
    except Exception:
        return False


def resolve_creative_destination_url(creative: Any) -> Optional[str]:
    candidates: list[str] = []
    if is_probably_click_destination(getattr(creative, "final_url", None)):
        candidates.append(str(getattr(creative, "final_url")))
    if is_probably_click_destination(getattr(creative, "display_url", None)):
        candidates.append(str(getattr(creative, "display_url")))

    raw_data = getattr(creative, "raw_data", {}) or {}
    declared_urls = raw_data.get("declaredClickThroughUrls", [])
    if isinstance(declared_urls, list):
        for url in declared_urls:
            if is_probably_click_destination(url):
                candidates.append(str(url))

    html_snippet = ""
    html_payload = raw_data.get("html")
    if isinstance(html_payload, dict):
        html_snippet = str(html_payload.get("snippet") or "")
    for url in extract_click_destinations_from_html(html_snippet):
        if is_probably_click_destination(url):
            candidates.append(url)

    if not candidates:
        return None
    return candidates[0]

