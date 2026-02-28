"""Canonical conversion taxonomy and source normalization helpers."""

from __future__ import annotations

import re
from typing import Optional


CANONICAL_EVENT_TYPES = {
    "install",
    "open",
    "registration",
    "tutorial_complete",
    "level_achieved",
    "first_purchase",
    "first_deposit",
    "purchase",
    "subscription",
    "add_to_cart",
    "checkout",
    "custom",
}

CANONICAL_SOURCE_TYPES = {
    "appsflyer",
    "adjust",
    "branch",
    "pixel",
    "redtrack",
    "voluum",
    "bidder",
    "manual_csv",
    "generic",
}

_GENERIC_EVENT_ALIASES = {
    "install": "install",
    "first_open": "open",
    "open": "open",
    "app_open": "open",
    "registration": "registration",
    "register": "registration",
    "sign_up": "registration",
    "signup": "registration",
    "tutorial_complete": "tutorial_complete",
    "onboarding_complete": "tutorial_complete",
    "level_achieved": "level_achieved",
    "first_purchase": "first_purchase",
    "first_order": "first_purchase",
    "first_deposit": "first_deposit",
    "ftd": "first_deposit",
    "deposit": "first_deposit",
    "purchase": "purchase",
    "order_complete": "purchase",
    "subscription": "subscription",
    "subscribe": "subscription",
    "add_to_cart": "add_to_cart",
    "addtocart": "add_to_cart",
    "checkout": "checkout",
    "begin_checkout": "checkout",
}

_SOURCE_EVENT_ALIASES = {
    "appsflyer": {
        "af_purchase": "purchase",
        "af_first_purchase": "first_purchase",
        "af_complete_registration": "registration",
        "af_tutorial_completion": "tutorial_complete",
        "af_level_achieved": "level_achieved",
        "af_subscribe": "subscription",
        "af_add_to_cart": "add_to_cart",
        "af_initiated_checkout": "checkout",
        "af_first_deposit": "first_deposit",
        "af_deposit": "first_deposit",
        "af_app_opened": "open",
    },
    "adjust": {
        "session": "open",
        "open": "open",
        "registration": "registration",
        "signup": "registration",
        "tutorial_complete": "tutorial_complete",
        "first_purchase": "first_purchase",
        "purchase": "purchase",
        "first_deposit": "first_deposit",
        "deposit": "first_deposit",
        "subscription": "subscription",
        "add_to_cart": "add_to_cart",
        "checkout": "checkout",
    },
    "branch": {
        "complete_registration": "registration",
        "open": "open",
        "purchase": "purchase",
        "add_to_cart": "add_to_cart",
        "initiate_purchase": "checkout",
        "subscribe": "subscription",
        "first_purchase": "first_purchase",
        "first_deposit": "first_deposit",
    },
}

_ATTRIBUTION_VALUES = {"last_click", "view_through", "organic", "unknown"}
_FRAUD_VALUES = {"clean", "suspected", "confirmed_fraud", "unknown"}


def _token(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")


def normalize_source_type(source_type: Optional[str]) -> str:
    token = _token(source_type or "")
    if token in CANONICAL_SOURCE_TYPES:
        return token
    return "generic"


def normalize_event_type(
    event_name: Optional[str],
    *,
    source_type: Optional[str] = None,
    event_type: Optional[str] = None,
) -> str:
    """Return canonical event type from source-specific or free-form names."""
    source = normalize_source_type(source_type)
    if event_type:
        event_type_token = _token(event_type)
        if event_type_token in CANONICAL_EVENT_TYPES:
            return event_type_token
        if event_type_token in _GENERIC_EVENT_ALIASES:
            return _GENERIC_EVENT_ALIASES[event_type_token]

    event_name_token = _token(event_name or "")
    if not event_name_token:
        return "custom"

    source_map = _SOURCE_EVENT_ALIASES.get(source, {})
    if event_name_token in source_map:
        return source_map[event_name_token]
    if event_name_token in _GENERIC_EVENT_ALIASES:
        return _GENERIC_EVENT_ALIASES[event_name_token]
    return "custom"


def normalize_attribution_type(value: Optional[str]) -> str:
    token = _token(value or "")
    if token in _ATTRIBUTION_VALUES:
        return token
    if token in ("view", "viewthrough"):
        return "view_through"
    if token in ("click", "lastclick"):
        return "last_click"
    return "unknown"


def normalize_fraud_status(value: Optional[str]) -> str:
    token = _token(value or "")
    if token in _FRAUD_VALUES:
        return token
    if token in ("fraud", "confirmed"):
        return "confirmed_fraud"
    if token in ("suspect", "suspicious"):
        return "suspected"
    return "unknown"


def normalize_currency(value: Optional[str]) -> Optional[str]:
    token = (value or "").strip().upper()
    if not token:
        return None
    if len(token) == 3 and token.isalpha():
        return token
    return None
