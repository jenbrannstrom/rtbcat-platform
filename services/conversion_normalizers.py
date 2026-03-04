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


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


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


def _diagnostic_field_keys(
    field_map: dict[str, str | list[str] | tuple[str, ...]] | None,
) -> set[str]:
    if field_map:
        keys: set[str] = set()
        for canonical, candidates in field_map.items():
            if isinstance(candidates, str):
                candidate_list = [candidates]
            elif isinstance(candidates, (list, tuple)):
                candidate_list = [str(item) for item in candidates if item]
            else:
                candidate_list = []
            if candidate_list:
                keys.add(str(canonical).strip())
        if keys:
            return keys
    return {"buyer_id", "billing_id", "creative_id", "click_id"}


def _coalesce_from_payload(payload: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_appsflyer_payload_with_diagnostics(
    payload: dict[str, Any],
    field_map: dict[str, str | list[str] | tuple[str, ...]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize AppsFlyer payload fields and return mapping diagnostics.

    Diagnostics include:
      - mapping_scope_fields_total: number of canonical fields in the active map
      - resolved_fields_count: number of canonical fields resolved in output
      - unresolved_fields: canonical fields still missing
      - field_hits: canonical field -> source field used (or "__already_present__")
      - unknown_mapping_count: len(unresolved_fields)
    """
    normalized = dict(payload)
    mapping = _normalize_field_map(field_map)
    diagnostic_keys = _diagnostic_field_keys(field_map)
    field_hits: dict[str, str] = {}
    unresolved_fields_all: list[str] = []

    for canonical_key, source_candidates in mapping.items():
        existing_value = normalized.get(canonical_key)
        if not _is_missing(existing_value):
            field_hits[canonical_key] = "__already_present__"
            continue

        selected_source: str | None = None
        selected_value: Any = None
        for source_field in source_candidates:
            candidate_value = payload.get(source_field)
            if _is_missing(candidate_value):
                continue
            selected_source = source_field
            selected_value = candidate_value
            break

        if selected_source is not None:
            normalized[canonical_key] = selected_value
            field_hits[canonical_key] = selected_source
            continue

        if _is_missing(normalized.get(canonical_key)):
            unresolved_fields_all.append(canonical_key)

    unresolved_fields = [key for key in unresolved_fields_all if key in diagnostic_keys]
    resolved_fields_count = max(len(diagnostic_keys) - len(unresolved_fields), 0)

    diagnostics = {
        "mapping_scope_fields_total": len(diagnostic_keys),
        "resolved_fields_count": resolved_fields_count,
        "unresolved_fields": unresolved_fields,
        "field_hits": field_hits,
        "unknown_mapping_count": len(unresolved_fields),
    }
    return normalized, diagnostics


def normalize_appsflyer_payload(
    payload: dict[str, Any],
    field_map: dict[str, str | list[str] | tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Normalize AppsFlyer payload fields into Cat-Scan canonical keys.

    field_map is buyer/integration-specific and maps canonical keys -> source keys.
    Example:
      {"buyer_id": "af_sub3", "creative_id": ["af_sub2", "af_ad_id"]}
    """
    normalized, _ = normalize_appsflyer_payload_with_diagnostics(payload, field_map=field_map)
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
