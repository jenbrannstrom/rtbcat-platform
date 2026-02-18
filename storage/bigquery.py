"""BigQuery access helpers for analytics precompute jobs."""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Iterable, Sequence

from google.cloud import bigquery


def get_bigquery_client() -> bigquery.Client:
    """Build a BigQuery client using default credentials."""
    project_id = os.getenv("BIGQUERY_PROJECT_ID")
    if project_id:
        return bigquery.Client(project=project_id)
    return bigquery.Client()


def build_table_ref(
    client: bigquery.Client,
    *,
    table_env: str,
    default_table: str,
) -> str:
    dataset = os.getenv("BIGQUERY_DATASET")
    if not dataset:
        raise RuntimeError("BIGQUERY_DATASET must be set to query BigQuery.")
    table_name = os.getenv(table_env, default_table)
    return f"{client.project}.{dataset}.{table_name}"


def coerce_dates(dates: Sequence[str]) -> list[date]:
    return [date.fromisoformat(value) for value in dates]


def _is_retryable_error(exc: Exception) -> bool:
    """Best-effort retry classifier without hard-coding google-api-core deps."""
    name = exc.__class__.__name__
    return name in {
        "TooManyRequests",
        "ServiceUnavailable",
        "InternalServerError",
        "GatewayTimeout",
        "DeadlineExceeded",
        "RetryError",
    } or isinstance(exc, TimeoutError)


def run_query(
    client: bigquery.Client,
    *,
    sql: str,
    params: Iterable[bigquery.QueryParameter],
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> list[bigquery.table.Row]:
    """Run a BigQuery query with bounded wait and deterministic retry behavior."""
    query_timeout = timeout_seconds
    if query_timeout is None:
        query_timeout = float(os.getenv("BIGQUERY_QUERY_TIMEOUT_SECONDS", "180"))

    retries = max_retries
    if retries is None:
        retries = int(os.getenv("BIGQUERY_QUERY_MAX_RETRIES", "1"))
    retries = max(0, retries)

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        job_config = bigquery.QueryJobConfig(query_parameters=list(params))
        job = client.query(sql, job_config=job_config)

        try:
            return list(job.result(timeout=query_timeout))
        except Exception as exc:
            last_exc = exc
            try:
                job.cancel()
            except Exception:
                pass

            if attempt >= retries or not _is_retryable_error(exc):
                raise

            # Simple bounded backoff: 1s, 2s, 4s...
            time.sleep(min(2 ** attempt, 5))

    if last_exc is not None:
        raise last_exc
    return []
