"""Security utilities for masking sensitive values in logs and responses."""

from __future__ import annotations

import re
from typing import Any

# Keys whose values should always be redacted when logging dicts
_SENSITIVE_KEYS = re.compile(
    r"(token|secret|password|api_key|apikey|access_key|credential|bearer|authorization|"
    r"client_secret|refresh_token|id_token|private_key|session_id)",
    re.IGNORECASE,
)


def mask_secret(value: str, *, visible: int = 4) -> str:
    """Mask a secret string, showing only the first/last `visible` chars.

    >>> mask_secret("sk-1234567890abcdef")
    'sk-1***cdef'
    >>> mask_secret("short")
    '*****'
    >>> mask_secret("")
    '***'
    """
    if not value:
        return "***"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}***{value[-visible:]}"


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *data* with sensitive values masked.

    Only string values whose keys match ``_SENSITIVE_KEYS`` are replaced.
    """
    out: dict[str, Any] = {}
    for key, val in data.items():
        if _SENSITIVE_KEYS.search(key) and isinstance(val, str):
            out[key] = mask_secret(val)
        elif isinstance(val, dict):
            out[key] = redact_dict(val)
        else:
            out[key] = val
    return out


def redact_response_body(body: str, *, max_length: int = 200) -> str:
    """Truncate and scrub a raw HTTP response body for safe logging.

    Strips anything that looks like a token or key value, then truncates.
    """
    if not body:
        return "<empty>"
    # Replace quoted strings that look like tokens/secrets
    scrubbed = re.sub(
        r'("(?:access_token|refresh_token|id_token|token|secret|api_key|password|client_secret|authorization|bearer)"'
        r'\s*:\s*")'
        r'[^"]+(")',
        r"\1<REDACTED>\2",
        body,
        flags=re.IGNORECASE,
    )
    if len(scrubbed) > max_length:
        return scrubbed[:max_length] + "...<truncated>"
    return scrubbed
