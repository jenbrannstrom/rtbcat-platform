"""BigQuery raw-schema health checks for raw parquet exports."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from importers import parquet_pipeline

logger = logging.getLogger(__name__)

RAW_EXPORT_TABLES = (
    "rtb_daily",
    "rtb_bidstream",
    "rtb_bid_filtering",
)


def get_bigquery_raw_schema_health() -> dict[str, Any]:
    """Return BigQuery raw-table schema compatibility for runtime exports."""
    bucket = parquet_pipeline._gcs_bucket()
    dataset = parquet_pipeline._bq_dataset()
    project = parquet_pipeline._bq_project() or None
    raw_export_enabled = parquet_pipeline._raw_export_enabled()

    checked_at = datetime.now(timezone.utc).isoformat()
    if not raw_export_enabled or not bucket or not dataset:
        return {
            "checked_at": checked_at,
            "enabled": False,
            "project": project,
            "dataset": dataset or None,
            "bucket": bucket or None,
            "healthy": True,
            "status": "disabled",
            "summary": {
                "tables_checked": 0,
                "healthy_tables": 0,
                "degraded_tables": 0,
                "unavailable_tables": 0,
                "missing_columns": 0,
            },
            "tables": [],
        }

    if not getattr(parquet_pipeline, "_HAS_BQ", False):
        return {
            "checked_at": checked_at,
            "enabled": True,
            "project": project,
            "dataset": dataset,
            "bucket": bucket,
            "healthy": False,
            "status": "unavailable",
            "summary": {
                "tables_checked": 0,
                "healthy_tables": 0,
                "degraded_tables": 0,
                "unavailable_tables": len(RAW_EXPORT_TABLES),
                "missing_columns": 0,
            },
            "tables": [],
        }

    try:
        client = parquet_pipeline.bigquery.Client(project=project or None)
    except Exception as exc:
        return {
            "checked_at": checked_at,
            "enabled": True,
            "project": project,
            "dataset": dataset,
            "bucket": bucket,
            "healthy": False,
            "status": "unavailable",
            "summary": {
                "tables_checked": 0,
                "healthy_tables": 0,
                "degraded_tables": 0,
                "unavailable_tables": len(RAW_EXPORT_TABLES),
                "missing_columns": 0,
            },
            "tables": [
                {
                    "table_name": table_name,
                    "table_id": f"{project or 'unknown'}.{dataset}.{table_name}",
                    "exists": False,
                    "status": "unavailable",
                    "expected_columns": [],
                    "actual_columns": [],
                    "missing_columns": [],
                    "error": str(exc),
                }
                for table_name in RAW_EXPORT_TABLES
            ],
        }

    resolved_project = client.project
    table_states: list[dict[str, Any]] = []
    healthy_tables = 0
    degraded_tables = 0
    unavailable_tables = 0
    missing_columns_total = 0

    for table_name in RAW_EXPORT_TABLES:
        table_id = f"{resolved_project}.{dataset}.{table_name}"
        expected_columns = [
            field.name for field in parquet_pipeline._bq_schema_for_table(table_name)
        ]
        try:
            table = client.get_table(table_id)
            actual_columns = [field.name for field in table.schema]
            missing_columns = [
                column for column in expected_columns if column not in actual_columns
            ]
            status = "healthy" if not missing_columns else "degraded"
            healthy_tables += int(status == "healthy")
            degraded_tables += int(status == "degraded")
            missing_columns_total += len(missing_columns)
            table_states.append(
                {
                    "table_name": table_name,
                    "table_id": table_id,
                    "exists": True,
                    "status": status,
                    "expected_columns": expected_columns,
                    "actual_columns": actual_columns,
                    "missing_columns": missing_columns,
                    "error": None,
                }
            )
        except Exception as exc:
            unavailable_tables += 1
            logger.warning("BigQuery raw schema check failed for %s", table_id, exc_info=True)
            table_states.append(
                {
                    "table_name": table_name,
                    "table_id": table_id,
                    "exists": False,
                    "status": "unavailable",
                    "expected_columns": expected_columns,
                    "actual_columns": [],
                    "missing_columns": expected_columns,
                    "error": str(exc),
                }
            )

    status = "healthy"
    if unavailable_tables:
        status = "unavailable"
    elif degraded_tables:
        status = "degraded"

    return {
        "checked_at": checked_at,
        "enabled": True,
        "project": resolved_project,
        "dataset": dataset,
        "bucket": bucket,
        "healthy": status == "healthy",
        "status": status,
        "summary": {
            "tables_checked": len(table_states),
            "healthy_tables": healthy_tables,
            "degraded_tables": degraded_tables,
            "unavailable_tables": unavailable_tables,
            "missing_columns": missing_columns_total,
        },
        "tables": table_states,
    }
