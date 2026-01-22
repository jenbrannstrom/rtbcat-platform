"""BigQuery access helpers for analytics precompute jobs."""

from __future__ import annotations

import os
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


def run_query(
    client: bigquery.Client,
    *,
    sql: str,
    params: Iterable[bigquery.QueryParameter],
) -> list[bigquery.table.Row]:
    job_config = bigquery.QueryJobConfig(query_parameters=list(params))
    return list(client.query(sql, job_config=job_config).result())
