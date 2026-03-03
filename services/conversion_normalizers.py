"""Provider-specific conversion payload normalizers."""

from __future__ import annotations

from typing import Any


DEFAULT_APPSFLYER_FIELD_MAP: dict[str, list[str]] = {
    "event_name": ["event_name", "eventName"],
    "event_ts": ["event_ts", "eventTime"],
    "buyer_id": ["buyer_id", "af_sub1"],
    "billing_id": ["billing_id", "af_sub2"],
    "creative_id": ["creative_id", "af_sub3", "af_ad_id"],
    "click_id": ["click_id", "af_click_id", "clickid"],
    "impression_id": ["impression_id", "af_impression_id"],
    "campaign_id": ["campaign_id", "campaign", "af_c_id"],
    "platform": ["platform"],
    "country": ["country", "country_code"],
}


def _normalize_field_map(field_map: dict[str, str | list[str] | tuple[str, ...]] | None) -> dict[str, list[str]]:
    if not field_map:
        return dict(DEFAULT_APPSFLYER_FIELD_MAP)

    normalized: dict[str, list[str]] = {}
    for canonical, candidates in field_map.items():
        if isinstance(candidates, str):
            candidate_list = [candidates]
        elif isinstance(candidates, (list, tuple)):
            candidate_list = [str(item) for item in candidates if item]
        else:
            continue

        deduped: list[str] = []
        for candidate in candidate_list:
            name = candidate.strip()
            if not name or name in deduped:
                continue
            deduped.append(name)
        if deduped:
            normalized[str(canonical)] = deduped

    merged = dict(DEFAULT_APPSFLYER_FIELD_MAP)
    merged.update(normalized)
    return merged


def _coalesce_from_payload(payload: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_appsflyer_payload(
    payload: dict[str, Any],
    field_map: dict[str, str | list[str] | tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Normalize AppsFlyer payload fields into Cat-Scan canonical keys.

    field_map is buyer/integration-specific and maps canonical keys -> source keys.
    Example:
      {"buyer_id": "af_sub3", "creative_id": ["af_sub2", "af_ad_id"]}
    """
    normalized = dict(payload)
    mapping = _normalize_field_map(field_map)

    for canonical_key, source_candidates in mapping.items():
        if normalized.get(canonical_key) not in (None, ""):
            continue
        value = _coalesce_from_payload(payload, source_candidates)
        if value is not None and value != "":
            normalized[canonical_key] = value
    return normalized


def normalize_adjust_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "event_name" not in normalized and payload.get("event_token"):
        normalized["event_name"] = payload.get("event_token")
    if "event_ts" not in normalized and payload.get("created_at"):
        normalized["event_ts"] = payload.get("created_at")
    if "click_ts" not in normalized and payload.get("click_time"):
        normalized["click_ts"] = payload.get("click_time")
    if "campaign_id" not in normalized and payload.get("campaign_name"):
        normalized["campaign_id"] = payload.get("campaign_name")
    if "click_id" not in normalized and payload.get("tracker_token"):
        normalized["click_id"] = payload.get("tracker_token")
    if "event_value" not in normalized and payload.get("revenue") is not None:
        normalized["event_value"] = payload.get("revenue")
    if "currency" not in normalized and payload.get("currency"):
        normalized["currency"] = payload.get("currency")
    if "platform" not in normalized and payload.get("os_name"):
        normalized["platform"] = payload.get("os_name")
    if "app_id" not in normalized and payload.get("app_token"):
        normalized["app_id"] = payload.get("app_token")
    return normalized


def normalize_branch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "event_name" not in normalized and payload.get("name"):
        normalized["event_name"] = payload.get("name")
    if "event_ts" not in normalized and payload.get("timestamp"):
        normalized["event_ts"] = payload.get("timestamp")
    if "campaign_id" not in normalized and payload.get("~campaign"):
        normalized["campaign_id"] = payload.get("~campaign")
    if "click_id" not in normalized and payload.get("~id"):
        normalized["click_id"] = payload.get("~id")
    if "event_value" not in normalized and payload.get("revenue") is not None:
        normalized["event_value"] = payload.get("revenue")
    if "currency" not in normalized and payload.get("currency"):
        normalized["currency"] = payload.get("currency")
    if "app_id" not in normalized and payload.get("app_id"):
        normalized["app_id"] = payload.get("app_id")
    if "platform" not in normalized and payload.get("os"):
        normalized["platform"] = payload.get("os")
    return normalized


def normalize_generic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload)
