#!/usr/bin/env python3
"""Hydrate retained app credential files from GSM without logging values."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import google.auth
from google.cloud import secretmanager


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def require_json(name: str, payload: bytes) -> dict:
    try:
        parsed = json.loads(payload)
    except Exception as exc:
        raise RuntimeError(f"{name} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{name} must contain a JSON object")
    return parsed


def main() -> int:
    project = (
        os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip()
    prefix = os.getenv("SECRETS_NAME_PREFIX", "catscan").strip() or "catscan"
    if not project:
        raise RuntimeError("GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT is required")

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    client = secretmanager.SecretManagerServiceClient(credentials=credentials)
    credential_dir = Path.home() / ".catscan" / "credentials"

    specs = (
        ("gmail-oauth-client", "gmail-oauth-client.json"),
        ("gmail-token", "gmail-token.json"),
        ("ab-service-account", "catscan-service-account.json"),
    )
    hydrated: dict[str, bytes] = {}
    for suffix, filename in specs:
        response = client.access_secret_version(
            request={
                "name": f"projects/{project}/secrets/{prefix}-{suffix}/versions/latest"
            }
        )
        payload = bytes(response.payload.data)
        if not payload:
            raise RuntimeError(f"Required credential secret is empty: {suffix}")
        require_json(suffix, payload)
        hydrated[filename] = payload

    oauth_client = require_json(
        "gmail-oauth-client", hydrated["gmail-oauth-client.json"]
    )
    if not (isinstance(oauth_client.get("web"), dict) or isinstance(oauth_client.get("installed"), dict)):
        raise RuntimeError("Gmail OAuth client JSON lacks web/installed configuration")
    gmail_token = require_json("gmail-token", hydrated["gmail-token.json"])
    if not gmail_token.get("refresh_token"):
        raise RuntimeError("Gmail token JSON lacks a refresh token")
    ab_account = require_json(
        "ab-service-account", hydrated["catscan-service-account.json"]
    )
    if ab_account.get("type") != "service_account":
        raise RuntimeError("Authorized Buyers credential is not a service-account JSON")

    for filename, payload in hydrated.items():
        atomic_write(credential_dir / filename, payload)

    adc_link = credential_dir / "google-credentials.json"
    try:
        adc_link.unlink()
    except FileNotFoundError:
        pass
    adc_link.symlink_to("catscan-service-account.json")

    print("Hydrated three retained Google credential files from Secret Manager.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
