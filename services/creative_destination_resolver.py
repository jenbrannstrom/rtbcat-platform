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


def classify_click_destination(url: Optional[str]) -> tuple[bool, Optional[str]]:
    if not url:
        return False, "empty"
    value = str(url).strip()
    if not value:
        return False, "empty"
    if _CLICK_MACRO_PATTERN.search(value):
        return False, "contains_click_macro"
    if not value.startswith(("http://", "https://")):
        return False, "unsupported_scheme"
    try:
        parsed = urlparse(value)
        if not parsed.netloc:
            return False, "missing_host"
        if parsed.path.lower().endswith(_ASSET_EXTENSIONS):
            return False, "asset_url"
        return True, None
    except Exception:
        return False, "invalid_url"


def is_probably_click_destination(url: Optional[str]) -> bool:
    is_valid, _ = classify_click_destination(url)
    return is_valid


def build_creative_destination_diagnostics(creative: Any) -> dict[str, Any]:
    raw_data = getattr(creative, "raw_data", {}) or {}
    declared_urls_raw = raw_data.get("declaredClickThroughUrls", [])
    declared_urls = declared_urls_raw if isinstance(declared_urls_raw, list) else []
    html_payload = raw_data.get("html")
    html_snippet = str(html_payload.get("snippet") or "") if isinstance(html_payload, dict) else ""
    html_click_destinations = extract_click_destinations_from_html(html_snippet)

    candidate_rows: list[dict[str, Any]] = []
    eligible: list[str] = []
    seen_eligible: set[str] = set()

    def add_candidate(url: Optional[str], source: str) -> None:
        value = "" if url is None else str(url).strip()
        is_valid, reason = classify_click_destination(value)
        if is_valid:
            if value in seen_eligible:
                candidate_rows.append(
                    {
                        "source": source,
                        "url": value,
                        "eligible": False,
                        "reason": "duplicate",
                    }
                )
                return
            seen_eligible.add(value)
            eligible.append(value)
            candidate_rows.append(
                {
                    "source": source,
                    "url": value,
                    "eligible": True,
                    "reason": None,
                }
            )
            return
        candidate_rows.append(
            {
                "source": source,
                "url": value,
                "eligible": False,
                "reason": reason,
            }
        )

    add_candidate(getattr(creative, "final_url", None), "final_url")
    add_candidate(getattr(creative, "display_url", None), "display_url")
    for url in declared_urls:
        add_candidate(url, "declared_click_through_url")
    for url in html_click_destinations:
        add_candidate(url, "html_snippet")

    return {
        "resolved_destination_url": eligible[0] if eligible else None,
        "candidate_count": len(candidate_rows),
        "eligible_count": len(eligible),
        "candidates": candidate_rows,
    }


def resolve_creative_destination_url(creative: Any) -> Optional[str]:
    diagnostics = build_creative_destination_diagnostics(creative)
    return diagnostics.get("resolved_destination_url")
