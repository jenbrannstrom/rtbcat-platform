"""Provider-agnostic secrets manager.

Supports four backends:
- env (default)
- gcp (Google Secret Manager)
- aws (AWS Secrets Manager)
- alibaba (Alibaba Cloud KMS Secrets Manager API)
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class SecretBackend(Protocol):
    def get_secret(self, secret_id: str) -> Optional[str]:
        """Return secret value or None when unavailable."""


class EnvSecretBackend:
    """Environment variable backend."""

    def get_secret(self, secret_id: str) -> Optional[str]:
        return os.getenv(secret_id)


class GcpSecretBackend:
    """Google Secret Manager backend."""

    def __init__(self) -> None:
        try:
            from google.cloud import secretmanager  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-secret-manager not installed"
            ) from exc

        project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise RuntimeError("GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set")

        self._project = project
        self._client = secretmanager.SecretManagerServiceClient()

    def get_secret(self, secret_id: str) -> Optional[str]:
        name = f"projects/{self._project}/secrets/{secret_id}/versions/latest"
        try:
            resp = self._client.access_secret_version(request={"name": name})
            return resp.payload.data.decode("utf-8")
        except Exception as exc:
            logger.warning("GCP secret lookup failed for %s: %s", secret_id, exc)
            return None


class AwsSecretBackend:
    """AWS Secrets Manager backend."""

    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise RuntimeError("boto3 not installed") from exc

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise RuntimeError("AWS_REGION or AWS_DEFAULT_REGION must be set")

        self._client = boto3.client("secretsmanager", region_name=region)

    def get_secret(self, secret_id: str) -> Optional[str]:
        try:
            resp = self._client.get_secret_value(SecretId=secret_id)
            if "SecretString" in resp and resp["SecretString"] is not None:
                return str(resp["SecretString"])
            binary = resp.get("SecretBinary")
            if binary:
                if isinstance(binary, str):
                    return base64.b64decode(binary).decode("utf-8")
                return base64.b64decode(binary).decode("utf-8")
            return None
        except Exception as exc:
            logger.warning("AWS secret lookup failed for %s: %s", secret_id, exc)
            return None


class AlibabaSecretBackend:
    """Alibaba Cloud KMS Secrets Manager backend."""

    def __init__(self) -> None:
        try:
            from alibabacloud_kms20160120.client import Client as KmsClient  # type: ignore
            from alibabacloud_kms20160120 import models as kms_models  # type: ignore
            from alibabacloud_tea_openapi import models as open_api_models  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Alibaba SDK not installed (need alibabacloud-kms20160120, "
                "alibabacloud-tea-openapi)"
            ) from exc

        region = os.getenv("ALIBABA_REGION_ID")
        access_key_id = os.getenv("ALIBABA_ACCESS_KEY_ID")
        access_key_secret = os.getenv("ALIBABA_ACCESS_KEY_SECRET")

        if not region:
            raise RuntimeError("ALIBABA_REGION_ID must be set")
        if not access_key_id or not access_key_secret:
            raise RuntimeError(
                "ALIBABA_ACCESS_KEY_ID and ALIBABA_ACCESS_KEY_SECRET must be set"
            )

        cfg = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region_id=region,
        )
        cfg.endpoint = os.getenv("ALIBABA_KMS_ENDPOINT", f"kms.{region}.aliyuncs.com")

        self._client = KmsClient(cfg)
        self._models = kms_models

    def get_secret(self, secret_id: str) -> Optional[str]:
        try:
            req = self._models.GetSecretValueRequest(secret_name=secret_id)
            resp = self._client.get_secret_value(req)
            body = getattr(resp, "body", None)
            if body is None:
                return None
            value = getattr(body, "secret_data", None)
            return str(value) if value is not None else None
        except Exception as exc:
            logger.warning("Alibaba secret lookup failed for %s: %s", secret_id, exc)
            return None


@dataclass
class SecretsConfig:
    backend: str
    name_prefix: str
    prefer_env: bool

    @staticmethod
    def from_env() -> "SecretsConfig":
        return SecretsConfig(
            backend=os.getenv("SECRETS_BACKEND", "env").strip().lower(),
            name_prefix=os.getenv("SECRETS_NAME_PREFIX", "catscan").strip(),
            prefer_env=os.getenv("SECRETS_PREFER_ENV", "true").strip().lower() in ("1", "true", "yes"),
        )


class SecretsManager:
    """Unified secrets access with backend abstraction and simple in-process cache."""

    def __init__(self, cfg: Optional[SecretsConfig] = None) -> None:
        self.cfg = cfg or SecretsConfig.from_env()
        self._backend = self._build_backend(self.cfg.backend)
        self._cache: dict[str, Optional[str]] = {}

    def _build_backend(self, backend_name: str) -> SecretBackend:
        if backend_name == "env":
            return EnvSecretBackend()
        if backend_name == "gcp":
            return GcpSecretBackend()
        if backend_name == "aws":
            return AwsSecretBackend()
        if backend_name in ("alibaba", "aliyun"):
            return AlibabaSecretBackend()
        raise RuntimeError(
            "Unsupported SECRETS_BACKEND. Use one of: env, gcp, aws, alibaba"
        )

    def _secret_id_for(self, key: str) -> str:
        override = os.getenv(f"SECRET_ID_{key}")
        if override:
            return override.strip()
        normalized = key.lower().replace("_", "-")
        return f"{self.cfg.name_prefix}-{normalized}"

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get logical secret by key.

        Resolution order:
        1) env var key (if SECRETS_PREFER_ENV=true)
        2) configured backend lookup
        3) env var key (if SECRETS_PREFER_ENV=false)
        4) default
        """
        if key in self._cache:
            return self._cache[key]

        env_value = os.getenv(key)
        value: Optional[str] = None

        if self.cfg.prefer_env and env_value:
            value = env_value
        else:
            secret_id = self._secret_id_for(key)
            value = self._backend.get_secret(secret_id)
            if value is None and not self.cfg.prefer_env and env_value:
                value = env_value

        if value is None:
            value = default

        self._cache[key] = value
        return value

    def get_int(self, key: str, default: int) -> int:
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except Exception:
            return default


@lru_cache(maxsize=1)
def get_secrets_manager() -> SecretsManager:
    """Singleton-style accessor for request handlers."""
    return SecretsManager()
