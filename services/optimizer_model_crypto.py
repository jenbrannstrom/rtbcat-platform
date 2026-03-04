"""Encryption helpers for optimizer model endpoint auth headers."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


_MODEL_AUTH_KEY_ENV = "CATSCAN_OPTIMIZER_MODEL_SECRET_KEY"
_ENC_PREFIX = "enc::v1:"


def _normalize_fernet_key(raw_key: str) -> bytes:
    token = raw_key.strip()
    if not token:
        raise ValueError("missing key")

    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8"))
        if len(decoded) == 32:
            return token.encode("utf-8")
    except Exception:
        logger.debug(
            "Optimizer model secret key is not a valid Fernet token; deriving deterministic key hash",
            exc_info=True,
        )

    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet() -> Optional[Fernet]:
    raw_key = os.getenv(_MODEL_AUTH_KEY_ENV, "").strip()
    if not raw_key:
        return None
    try:
        return Fernet(_normalize_fernet_key(raw_key))
    except Exception:
        logger.warning(
            "Failed to initialize optimizer model Fernet crypto; auth header decryption disabled",
            extra={"env_key": _MODEL_AUTH_KEY_ENV},
            exc_info=True,
        )
        return None


def clear_optimizer_model_crypto_cache() -> None:
    """Clear cached crypto state (useful for tests)."""
    _get_fernet.cache_clear()


def encrypt_optimizer_model_auth_header(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.startswith(_ENC_PREFIX):
        return raw

    fernet = _get_fernet()
    if fernet is None:
        # Backward-compatible fallback when no key is configured.
        return raw
    token = fernet.encrypt(raw.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def decrypt_optimizer_model_auth_header(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if not raw.startswith(_ENC_PREFIX):
        # Legacy plaintext storage.
        return raw

    fernet = _get_fernet()
    if fernet is None:
        return None

    token = raw[len(_ENC_PREFIX) :]
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
