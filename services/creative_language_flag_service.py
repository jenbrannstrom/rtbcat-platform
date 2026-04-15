"""Deterministic language and market-flag helpers for creative auditing."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Optional

from utils.country_codes import get_country_alpha3, normalize_country_code
from utils.language_country_map import check_language_country_match

_CURRENCY_PATTERNS = re.compile(
    r"(?:[$€£¥₹₩₱₫₺₽₸₮]|"
    r"\b(?:USD|EUR|GBP|JPY|INR|KRW|AED|SAR|MYR|SGD|THB|IDR|PHP|VND|BRL|AUD|CAD|CNY)\b)",
    re.IGNORECASE,
)

_CURRENCY_NORMALIZATION = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "₩": "KRW",
    "₱": "PHP",
    "₫": "VND",
    "₺": "TRY",
    "₽": "RUB",
    "₸": "KZT",
    "₮": "MNT",
}

_CURRENCY_TO_COUNTRIES = {
    "AED": ["AE"],
    "AUD": ["AU"],
    "BRL": ["BR"],
    "CAD": ["CA"],
    "CNY": ["CN"],
    "EUR": ["AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK"],
    "GBP": ["GB"],
    "IDR": ["ID"],
    "INR": ["IN"],
    "JPY": ["JP"],
    "KRW": ["KR"],
    "MYR": ["MY"],
    "PHP": ["PH"],
    "SAR": ["SA"],
    "SGD": ["SG"],
    "THB": ["TH"],
    "USD": ["US"],
    "VND": ["VN"],
}

_PRIMARY_ENGLISH_MARKETS = {"US", "GB", "CA", "AU", "NZ", "IE", "ZA", "SG"}
_ENGLISH_HINT_WORDS = {
    "only",
    "free",
    "shipping",
    "new",
    "app",
    "users",
    "orders",
    "order",
    "download",
    "install",
    "shop",
    "buy",
    "save",
    "learn",
    "more",
    "play",
    "now",
    "with",
    "for",
    "your",
    "the",
    "and",
}

_SPANISH_HINT_WORDS = {
    "instalar",
    "instala",
    "descargar",
    "descarga",
    "comprar",
    "ahora",
    "jugar",
    "abrir",
    "obtener",
    "obtenga",
    "suscribete",
    "suscribirse",
    "registrarse",
    "mas",
}

_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "hi": "Hindi",
}


def _strip_html_tags(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


def _extract_text_from_vast(vast_xml: str) -> str:
    text_parts: list[str] = []
    for pattern in (
        r"<AdTitle[^>]*>(?:<!\[CDATA\[)?([^\]<]+)",
        r"<Description[^>]*>(?:<!\[CDATA\[)?([^\]<]+)",
        r"<HTMLResource[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</HTMLResource>",
    ):
        for match in re.findall(pattern, vast_xml, re.IGNORECASE | re.DOTALL):
            value = _strip_html_tags(match)
            if value:
                text_parts.append(value)
    return " ".join(text_parts)


def _coerce_raw_data(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def extract_creative_market_text(creative: Any) -> str:
    raw_data = _coerce_raw_data(getattr(creative, "raw_data", None))
    parts: list[str] = []

    for value in (
        getattr(creative, "advertiser_name", None),
        raw_data.get("advertiserName"),
    ):
        if value:
            parts.append(str(value))

    html_payload = raw_data.get("html")
    if isinstance(html_payload, dict):
        snippet = str(html_payload.get("snippet") or "").strip()
        if snippet:
            parts.append(_strip_html_tags(snippet))

    native_payload = raw_data.get("native")
    if isinstance(native_payload, dict):
        for field_name in ("headline", "body", "callToAction", "advertiserName", "snippet"):
            value = native_payload.get(field_name)
            if value:
                parts.append(_strip_html_tags(str(value)))

    video_payload = raw_data.get("video")
    if isinstance(video_payload, dict):
        vast_xml = str(video_payload.get("vastXml") or video_payload.get("videoVastXml") or "").strip()
        if vast_xml:
            parts.append(_extract_text_from_vast(vast_xml))
    else:
        vast_xml = str(raw_data.get("videoVastXml") or "").strip()
        if vast_xml:
            parts.append(_extract_text_from_vast(vast_xml))

    return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()


def detect_currencies(text: str) -> list[str]:
    normalized: set[str] = set()
    for token in _CURRENCY_PATTERNS.findall(text or ""):
        value = _CURRENCY_NORMALIZATION.get(token, token.upper())
        if value:
            normalized.add(value)
    return sorted(normalized)


def infer_language_code(text: str) -> Optional[str]:
    return _detect_obvious_language_code(text)


def _normalize_token_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _detect_obvious_language_code(text: str) -> Optional[str]:
    words = re.findall(r"[A-Za-z]{2,}", text or "")
    if re.search(r"[\u0900-\u097F]", text or ""):
        return "hi"
    if len(words) < 4:
        short_words = re.findall(r"[A-Za-z]{2,}", _normalize_token_text(text or ""))
        lowered_short = [word.lower() for word in short_words]
        if any(word in _SPANISH_HINT_WORDS for word in lowered_short):
            return "es"
        if any(word in _ENGLISH_HINT_WORDS for word in lowered_short):
            return "en"
        return None

    lowered = [word.lower() for word in re.findall(r"[A-Za-z]{2,}", _normalize_token_text(text or ""))]
    english_hits = sum(1 for word in lowered if word in _ENGLISH_HINT_WORDS)
    spanish_hits = sum(1 for word in lowered if word in _SPANISH_HINT_WORDS)

    if english_hits >= 2 and english_hits > spanish_hits:
        return "en"
    if spanish_hits >= 1 and spanish_hits >= english_hits:
        return "es"
    if english_hits >= 1:
        return "en"
    return None


def _format_country_list(country_codes: list[str]) -> str:
    values = [get_country_alpha3(code) or code for code in _normalize_country_list(country_codes)[:3]]
    return ", ".join(values)


def _normalize_country_list(country_codes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for code in country_codes:
        canonical = normalize_country_code(code)
        if not canonical or canonical in seen:
            continue
        normalized.append(canonical)
        seen.add(canonical)
    return normalized


def _status_rank(status: Optional[str]) -> int:
    return {"green": 0, "orange": 1, "red": 2}.get(str(status or "").lower(), 0)


def _build_native_plaintext_language_signal(
    creative: Any,
    serving_countries: list[str],
    primary_language_code: Optional[str],
) -> Optional[dict[str, str]]:
    raw_data = _coerce_raw_data(getattr(creative, "raw_data", None))
    native_payload = raw_data.get("native")
    if not isinstance(native_payload, dict):
        return None

    body_text = " ".join(
        str(native_payload.get(field_name) or "").strip()
        for field_name in ("headline", "body", "snippet")
        if str(native_payload.get(field_name) or "").strip()
    ).strip()
    cta_text = str(native_payload.get("callToAction") or "").strip()
    if not body_text or not cta_text:
        return None

    body_language_code = primary_language_code or _detect_obvious_language_code(body_text)
    cta_language_code = _detect_obvious_language_code(cta_text)
    if not body_language_code or not cta_language_code or body_language_code == cta_language_code:
        return None

    body_language = _LANGUAGE_NAMES.get(body_language_code, body_language_code.upper())
    cta_language = _LANGUAGE_NAMES.get(cta_language_code, cta_language_code.upper())
    cta_match = check_language_country_match(cta_language_code, serving_countries)
    status = "orange" if cta_match["is_match"] else "red"
    country_suffix = _format_country_list(serving_countries) if serving_countries else "current markets"

    return {
        "status": status,
        "reason": f"{cta_language} CTA '{cta_text}' mixed into {body_language} creative serving in {country_suffix}",
        "primary_language_code": body_language_code,
        "primary_language": body_language,
        "secondary_language_code": cta_language_code,
        "secondary_language": cta_language,
        "cta_text": cta_text,
        "summary": f"Primary plaintext: {body_language} · CTA: {cta_language} ('{cta_text}')",
    }


def assess_language_market_flag(
    detected_language_code: Optional[str],
    serving_countries: list[str],
    heuristic_language_code: Optional[str] = None,
) -> dict[str, Any]:
    serving_countries = _normalize_country_list(serving_countries)
    effective_language_code = (detected_language_code or heuristic_language_code or "").lower() or None
    source = "stored" if detected_language_code else ("heuristic" if heuristic_language_code else "missing")

    if not serving_countries:
        return {
            "status": "orange",
            "reason": "No serving-country data available",
            "effective_language_code": effective_language_code,
            "source": source,
        }

    if not effective_language_code:
        return {
            "status": "orange",
            "reason": f"No language detection for {_format_country_list(serving_countries)} serving",
            "effective_language_code": None,
            "source": source,
        }

    comparison = check_language_country_match(effective_language_code, serving_countries)
    matching_countries = comparison["matching_countries"]
    mismatched_countries = comparison["mismatched_countries"]

    if effective_language_code == "en" and not any(
        country in _PRIMARY_ENGLISH_MARKETS for country in serving_countries
    ):
        return {
            "status": "orange",
            "reason": f"English creative serving in {_format_country_list(serving_countries)}",
            "effective_language_code": effective_language_code,
            "source": source,
        }

    if not matching_countries and mismatched_countries:
        return {
            "status": "red",
            "reason": f"{effective_language_code.upper()} mismatches {_format_country_list(mismatched_countries)}",
            "effective_language_code": effective_language_code,
            "source": source,
        }

    if matching_countries and mismatched_countries:
        return {
            "status": "orange",
            "reason": f"Mixed serving across {_format_country_list(mismatched_countries)}",
            "effective_language_code": effective_language_code,
            "source": source,
        }

    return {
        "status": "green",
        "reason": f"{effective_language_code.upper()} matches {_format_country_list(serving_countries)}",
        "effective_language_code": effective_language_code,
        "source": source,
    }


def assess_currency_market_flag(
    detected_currencies: list[str],
    serving_countries: list[str],
) -> dict[str, Any]:
    serving_countries = _normalize_country_list(serving_countries)
    if not detected_currencies:
        return {
            "status": "orange",
            "reason": "No obvious market currency detected",
        }

    if not serving_countries:
        return {
            "status": "orange",
            "reason": f"Detected currencies {', '.join(detected_currencies)} without serving-country data",
        }

    mismatched: list[str] = []
    matched: list[str] = []
    for currency in detected_currencies:
        expected_countries = _CURRENCY_TO_COUNTRIES.get(currency, [])
        if not expected_countries:
            continue
        if any(country in expected_countries for country in serving_countries):
            matched.append(currency)
        else:
            mismatched.append(currency)

    if mismatched:
        return {
            "status": "red",
            "reason": f"Currency {', '.join(mismatched)} conflicts with {_format_country_list(serving_countries)}",
        }

    if matched:
        return {
            "status": "green",
            "reason": f"Currency {', '.join(matched)} fits {_format_country_list(serving_countries)}",
        }

    return {
        "status": "orange",
        "reason": f"Detected currencies {', '.join(detected_currencies)} need review",
    }


def assess_geo_linguistic_flag(
    latest_geo_run: Optional[dict[str, Any]],
    currency_flag: dict[str, Any],
) -> dict[str, Any]:
    summarized_reason = _summarize_geo_linguistic_reason(latest_geo_run) if latest_geo_run else None
    if currency_flag["status"] == "red":
        if latest_geo_run:
            status = str(latest_geo_run.get("status") or "")
            result = latest_geo_run.get("result") or {}
            decision = str(result.get("decision") or "unknown")
            if status == "completed" and decision == "match":
                return {
                    "status": "red",
                    "reason": f"{currency_flag['reason']} (overrides AI match)",
                    "decision": "heuristic_currency_mismatch",
                }
            if status == "completed" and decision == "needs_review":
                return {
                    "status": "red",
                    "reason": f"{currency_flag['reason']} (stronger than AI review)",
                    "decision": "heuristic_currency_mismatch",
                }
        return {
            "status": "red",
            "reason": f"{currency_flag['reason']} (heuristic)",
            "decision": "heuristic_currency_mismatch",
        }

    if latest_geo_run:
        status = str(latest_geo_run.get("status") or "")
        result = latest_geo_run.get("result") or {}
        decision = str(result.get("decision") or "unknown")
        if status == "completed":
            if decision == "mismatch":
                return {
                    "status": "red",
                    "reason": summarized_reason or "AI report flagged mismatch",
                    "decision": decision,
                }
            if decision == "needs_review":
                return {
                    "status": "orange",
                    "reason": summarized_reason or "AI report needs review",
                    "decision": decision,
                }
            if decision == "match":
                return {
                    "status": "green",
                    "reason": summarized_reason or "AI report matched market",
                    "decision": decision,
                }
        if status == "failed":
            return {
                "status": "orange",
                "reason": latest_geo_run.get("error_message") or "AI report failed",
                "decision": decision,
            }
        return {"status": "orange", "reason": "AI report pending", "decision": decision}

    return {
        "status": "orange",
        "reason": "No AI geo-linguistic report yet",
        "decision": "not_run",
    }


def _summarize_geo_linguistic_reason(latest_geo_run: dict[str, Any]) -> Optional[str]:
    result = latest_geo_run.get("result") or {}
    findings = result.get("findings") or []
    if isinstance(findings, list):
        for preferred_category in ("language_mismatch", "incomplete_localization", "currency_mismatch"):
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                if finding.get("category") != preferred_category:
                    continue
                description = str(finding.get("description") or "").strip()
                evidence = str(finding.get("evidence") or "").strip()
                if description:
                    return description
                if evidence:
                    return evidence
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            description = str(finding.get("description") or "").strip()
            evidence = str(finding.get("evidence") or "").strip()
            if description:
                return description
            if evidence:
                return evidence

    primary_languages = [str(value) for value in (result.get("primary_languages") or []) if value]
    secondary_languages = [str(value) for value in (result.get("secondary_languages") or []) if value]
    if primary_languages and secondary_languages:
        return f"AI found mixed languages: {', '.join(primary_languages)} + {', '.join(secondary_languages)}"
    if primary_languages:
        return f"AI identified primary language: {', '.join(primary_languages)}"
    return None


def build_creative_language_flag_row(
    creative: Any,
    serving_countries: list[str],
    latest_geo_run: Optional[dict[str, Any]],
) -> dict[str, Any]:
    serving_countries = _normalize_country_list(serving_countries)
    text = extract_creative_market_text(creative)
    heuristic_language_code = infer_language_code(text) if not getattr(creative, "detected_language_code", None) else None
    detected_currencies = detect_currencies(text)
    language_flag = assess_language_market_flag(
        getattr(creative, "detected_language_code", None),
        serving_countries,
        heuristic_language_code=heuristic_language_code,
    )
    plaintext_language_signal = _build_native_plaintext_language_signal(
        creative=creative,
        serving_countries=serving_countries,
        primary_language_code=language_flag.get("effective_language_code"),
    )
    if plaintext_language_signal and (
        _status_rank(plaintext_language_signal["status"]) >= _status_rank(language_flag["status"])
    ):
        language_flag = {
            **language_flag,
            "status": plaintext_language_signal["status"],
            "reason": plaintext_language_signal["reason"],
            "source": "plaintext_fields",
        }
    currency_flag = assess_currency_market_flag(detected_currencies, serving_countries)
    geo_flag = assess_geo_linguistic_flag(latest_geo_run, currency_flag)

    return {
        "creative_id": creative.id,
        "creative_name": getattr(creative, "name", "") or "",
        "buyer_id": getattr(creative, "buyer_id", None),
        "format": getattr(creative, "format", None),
        "approval_status": getattr(creative, "approval_status", None),
        "detected_language": getattr(creative, "detected_language", None),
        "detected_language_code": getattr(creative, "detected_language_code", None),
        "heuristic_language_code": heuristic_language_code,
        "plaintext_language_summary": (
            plaintext_language_signal.get("summary") if plaintext_language_signal else None
        ),
        "primary_text_language": (
            plaintext_language_signal.get("primary_language") if plaintext_language_signal else None
        ),
        "primary_text_language_code": (
            plaintext_language_signal.get("primary_language_code") if plaintext_language_signal else None
        ),
        "secondary_text_language": (
            plaintext_language_signal.get("secondary_language") if plaintext_language_signal else None
        ),
        "secondary_text_language_code": (
            plaintext_language_signal.get("secondary_language_code") if plaintext_language_signal else None
        ),
        "secondary_text_sample": (
            plaintext_language_signal.get("cta_text") if plaintext_language_signal else None
        ),
        "serving_countries": serving_countries,
        "detected_currencies": detected_currencies,
        "language_flag_status": language_flag["status"],
        "language_flag_reason": language_flag["reason"],
        "language_flag_source": language_flag["source"],
        "effective_language_code": language_flag.get("effective_language_code"),
        "currency_flag_status": currency_flag["status"],
        "currency_flag_reason": currency_flag["reason"],
        "geo_linguistic_status": geo_flag["status"],
        "geo_linguistic_reason": geo_flag["reason"],
        "geo_linguistic_decision": geo_flag.get("decision"),
        "geo_linguistic_completed_at": latest_geo_run.get("completed_at") if latest_geo_run else None,
    }
