#!/usr/bin/env python3
"""Read-only verification of retained Google services from the Hetzner API."""

from __future__ import annotations

import json
import os
import sys

import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery, secretmanager, storage


def require_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError(f"Missing required configuration: {' or '.join(names)}")


def main() -> int:
    project = require_env("GCP_PROJECT_ID", "GOOGLE_CLOUD_PROJECT")
    bq_project = require_env("BIGQUERY_PROJECT_ID", "CATSCAN_BQ_PROJECT")
    dataset = require_env("BIGQUERY_DATASET", "CATSCAN_BQ_DATASET")
    bucket = require_env("CATSCAN_GCS_BUCKET", "RAW_PARQUET_BUCKET")
    prefix = os.getenv("SECRETS_NAME_PREFIX", "catscan").strip() or "catscan"

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    credentials.refresh(Request())

    secret_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
    secret_response = secret_client.access_secret_version(
        request={
            "name": f"projects/{project}/secrets/{prefix}-api-key/versions/latest"
        }
    )
    if not secret_response.payload.data:
        raise RuntimeError("Secret Manager returned an empty required secret.")

    bq_client = bigquery.Client(project=bq_project, credentials=credentials)
    next(iter(bq_client.list_tables(f"{bq_project}.{dataset}", max_results=1)), None)

    storage_client = storage.Client(project=project, credentials=credentials)
    next(iter(storage_client.list_blobs(bucket, max_results=1)), None)

    print(
        json.dumps(
            {
                "adc": "ok",
                "secret_manager_read": "ok",
                "bigquery_metadata_read": "ok",
                "gcs_list": "ok",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Google access verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
