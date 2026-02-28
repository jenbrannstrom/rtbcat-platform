"""Provider-specific conversion payload normalizers."""

from __future__ import annotations

from typing import Any


def normalize_appsflyer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "event_name" not in normalized and "eventName" in payload:
        normalized["event_name"] = payload.get("eventName")
    if "event_ts" not in normalized and "eventTime" in payload:
        normalized["event_ts"] = payload.get("eventTime")
    if "buyer_id" not in normalized and payload.get("af_sub1"):
        normalized["buyer_id"] = payload.get("af_sub1")
    if "billing_id" not in normalized and payload.get("af_sub2"):
        normalized["billing_id"] = payload.get("af_sub2")
    if "click_id" not in normalized and payload.get("af_click_id"):
        normalized["click_id"] = payload.get("af_click_id")
    if "impression_id" not in normalized and payload.get("af_impression_id"):
        normalized["impression_id"] = payload.get("af_impression_id")
    if "campaign_id" not in normalized and payload.get("campaign_id"):
        normalized["campaign_id"] = payload.get("campaign_id")
    if "campaign_id" not in normalized and payload.get("campaign"):
        normalized["campaign_id"] = payload.get("campaign")
    if "platform" not in normalized and payload.get("platform"):
        normalized["platform"] = payload.get("platform")
    if "country" not in normalized and payload.get("country_code"):
        normalized["country"] = payload.get("country_code")
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
