"""Resolve canonical click destination URLs from creative payloads."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)


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
_MACRO_TOKEN_PATTERN = re.compile(r"%%[A-Z0-9_]+%%")
_URL_PARAM_MACRO_PATTERN = re.compile(r"\{[a-zA-Z0-9_]+\}")


def _is_click_url_macro(token: str) -> bool:
    normalized = token.upper()
    return normalized.startswith("%%CLICK_URL") and normalized.endswith("%%")


def _extract_detection_urls(value: Optional[str]) -> list[str]:
    if not value:
        return []
    raw = str(value).strip()
    if not raw:
        return []

    variants = [raw]
    current = raw
    # Some creatives double-encode URL payloads; decode a small bounded number of times.
    for _ in range(2):
        decoded = unquote(current)
        if decoded == current:
            break
        variants.append(decoded)
        current = decoded

    urls: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        cleaned = url.rstrip(",;)}]>")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)

    for candidate in variants:
        if candidate.startswith(("http://", "https://")):
            _add(candidate)
        for match in re.findall(r"https?://[^\s\"'<>]+", candidate):
            _add(match)

    return urls


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


def extract_creative_destination_candidates(creative: Any) -> list[dict[str, str]]:
    raw_data = getattr(creative, "raw_data", {}) or {}
    declared_urls_raw = raw_data.get("declaredClickThroughUrls", [])
    declared_urls = declared_urls_raw if isinstance(declared_urls_raw, list) else []
    html_payload = raw_data.get("html")
    html_snippet = str(html_payload.get("snippet") or "") if isinstance(html_payload, dict) else ""
    html_click_destinations = extract_click_destinations_from_html(html_snippet)

    native_payload = raw_data.get("native")
    native_click_url = (
        str(native_payload.get("clickLinkUrl") or "").strip()
        if isinstance(native_payload, dict)
        else ""
    )

    rows: list[dict[str, str]] = []

    def add(source: str, value: Optional[str]) -> None:
        if value is None:
            rows.append({"source": source, "url": ""})
            return
        rows.append({"source": source, "url": str(value).strip()})

    add("final_url", getattr(creative, "final_url", None))
    add("display_url", getattr(creative, "display_url", None))
    for url in declared_urls:
        add("declared_click_through_url", url)
    if native_click_url:
        add("native_click_link_url", native_click_url)
    for url in html_click_destinations:
        add("html_snippet", url)
    return rows


def extract_macro_tokens(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return sorted(set(_MACRO_TOKEN_PATTERN.findall(str(value))))


def build_creative_click_macro_summary(creative: Any) -> dict[str, Any]:
    creative_format = (getattr(creative, "format", "") or "").upper()

    # Native creatives are exempt: Google handles click tracking automatically
    # at serving time — no %%CLICK_URL%% macro needed in the payload.
    is_native_exempt = creative_format == "NATIVE"

    candidates = extract_creative_destination_candidates(creative)
    macro_tokens: set[str] = set()
    click_macro_tokens: set[str] = set()
    source_hints: set[str] = set()
    sample_url: Optional[str] = None
    appsflyer_url_count = 0
    appsflyer_clickid_url_count = 0
    sample_appsflyer_url: Optional[str] = None

    for row in candidates:
        url = row.get("url", "")
        source = row.get("source", "")
        if _is_appsflyer_url(url):
            appsflyer_url_count += 1
            if sample_appsflyer_url is None:
                sample_appsflyer_url = url
            if _url_has_clickid(url):
                appsflyer_clickid_url_count += 1
        tokens = extract_macro_tokens(url)
        if not tokens:
            continue
        if sample_url is None:
            sample_url = url
        source_hints.add(source)
        macro_tokens.update(tokens)
        for token in tokens:
            if _is_click_url_macro(token):
                click_macro_tokens.add(token)

    # Also scan raw HTML snippet, VAST XML, and native clickLinkUrl directly
    # — the URL extraction pipeline strips macro prefixes, so click macros
    # embedded in HTML hrefs (e.g. href="%%CLICK_URL_UNESC%%https://...") are
    # lost by the time we inspect candidate URLs above.
    raw_data = getattr(creative, "raw_data", {}) or {}
    raw_text_sources: list[tuple[str, str]] = []
    html_payload = raw_data.get("html")
    if isinstance(html_payload, dict):
        snippet = html_payload.get("snippet") or ""
        if snippet:
            raw_text_sources.append(("html_snippet", str(snippet)))
    native_payload = raw_data.get("native")
    if isinstance(native_payload, dict):
        click_link = native_payload.get("clickLinkUrl") or ""
        if click_link:
            raw_text_sources.append(("native_click_link_url", str(click_link)))
    video_payload = raw_data.get("video")
    if isinstance(video_payload, dict):
        for key in ("videoVastXml", "vastXml"):
            vast_xml = video_payload.get(key) or ""
            if vast_xml:
                raw_text_sources.append(("video_vast_xml", str(vast_xml)))
                break
    for source, text in raw_text_sources:
        tokens = extract_macro_tokens(text)
        for token in tokens:
            macro_tokens.add(token)
            if _is_click_url_macro(token):
                click_macro_tokens.add(token)
                source_hints.add(source)

    has_click_macro = bool(click_macro_tokens) or is_native_exempt

    return {
        "has_any_macro": bool(macro_tokens),
        "has_click_macro": has_click_macro,
        "is_native_exempt": is_native_exempt,
        "macro_tokens": sorted(macro_tokens),
        "click_macro_tokens": sorted(click_macro_tokens),
        "url_sources": sorted(source_hints),
        "url_count": len(candidates),
        "sample_url": sample_url,
        "has_appsflyer_url": appsflyer_url_count > 0,
        "has_appsflyer_clickid": appsflyer_clickid_url_count > 0,
        "appsflyer_url_count": appsflyer_url_count,
        "appsflyer_clickid_url_count": appsflyer_clickid_url_count,
        "sample_appsflyer_url": sample_appsflyer_url,
    }


def _is_appsflyer_url(value: Optional[str]) -> bool:
    for url in _extract_detection_urls(value):
        try:
            parsed = urlparse(url)
        except Exception:
            logger.debug(
                "Failed to parse candidate URL while checking AppsFlyer destination",
                extra={"url_preview": str(url)[:160]},
                exc_info=True,
            )
            continue
        host = (parsed.netloc or "").lower()
        if host.endswith("app.appsflyer.com") or host.endswith("onelink.me"):
            return True
    return False


def _url_has_clickid(value: Optional[str]) -> bool:
    if not value:
        return False
    url = str(value).strip()
    if not url:
        return False
    lowered = url.lower()
    if "clickid=" in lowered or "af_click_id=" in lowered:
        return True
    if "clickid%3d" in lowered or "af_click_id%3d" in lowered:
        return True
    # Buyers often use placeholder tokens that are replaced at click time.
    if "{dsp_params}" in lowered or "{clickid}" in lowered:
        return True

    for detection_url in _extract_detection_urls(url):
        parsed = urlparse(detection_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        clickid_value = params.get("clickid", [None])[0]
        if isinstance(clickid_value, str) and clickid_value.strip():
            return True
        af_clickid_value = params.get("af_click_id", [None])[0]
        if isinstance(af_clickid_value, str) and af_clickid_value.strip():
            return True
        if _URL_PARAM_MACRO_PATTERN.search(detection_url):
            clickid_value = params.get("clickid", [None])[0]
            if isinstance(clickid_value, str) and clickid_value.strip():
                return True
    return False


def classify_click_destination(url: Optional[str]) -> tuple[bool, Optional[str]]:
    if not url:
        return False, "empty"
    value = str(url).strip()
    if not value:
        return False, "empty"
    if _MACRO_TOKEN_PATTERN.search(value):
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
        logger.debug(
            "Failed to parse click destination URL; marking as invalid_url",
            extra={"url_preview": value[:160]},
            exc_info=True,
        )
        return False, "invalid_url"


def is_probably_click_destination(url: Optional[str]) -> bool:
    is_valid, _ = classify_click_destination(url)
    return is_valid


def build_creative_destination_diagnostics(creative: Any) -> dict[str, Any]:
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

    for row in extract_creative_destination_candidates(creative):
        add_candidate(row.get("url"), row.get("source", "unknown"))

    macro_summary = build_creative_click_macro_summary(creative)

    return {
        "resolved_destination_url": eligible[0] if eligible else None,
        "candidate_count": len(candidate_rows),
        "eligible_count": len(eligible),
        "candidates": candidate_rows,
        "has_any_macro": macro_summary["has_any_macro"],
        "has_click_macro": macro_summary["has_click_macro"],
        "macro_tokens": macro_summary["macro_tokens"],
        "click_macro_tokens": macro_summary["click_macro_tokens"],
    }


def resolve_creative_destination_url(creative: Any) -> Optional[str]:
    diagnostics = build_creative_destination_diagnostics(creative)
    return diagnostics.get("resolved_destination_url")
