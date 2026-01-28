"""Parquet export pipeline for CSV imports."""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

_HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None
_HAS_GCS = importlib.util.find_spec("google.cloud.storage") is not None
_HAS_BQ = importlib.util.find_spec("google.cloud.bigquery") is not None

if _HAS_PYARROW:
    import pyarrow as pa
    import pyarrow.parquet as pq

if _HAS_GCS:
    from google.cloud import storage

if _HAS_BQ:
    from google.cloud import bigquery


PARQUET_BATCH_SIZE = int(os.getenv("CATSCAN_PARQUET_BATCH_SIZE", "5000"))
GCS_BUCKET = os.getenv("CATSCAN_GCS_BUCKET", "")
GCS_PREFIX = os.getenv("CATSCAN_GCS_PREFIX", "catscan/parquet").strip("/")
BQ_DATASET = os.getenv("CATSCAN_BQ_DATASET", "")
BQ_PROJECT = os.getenv("CATSCAN_BQ_PROJECT", "")
BQ_LOAD_MODE = os.getenv("CATSCAN_BQ_LOAD_MODE", "load").lower().strip()


def _parquet_schema_for_table(table_name: str) -> "pa.Schema":
    if table_name == "rtb_daily":
        return pa.schema(
            [
                ("metric_date", pa.date32()),
                ("hour", pa.int64()),
                ("billing_id", pa.string()),
                ("creative_id", pa.string()),
                ("creative_size", pa.string()),
                ("creative_format", pa.string()),
                ("country", pa.string()),
                ("platform", pa.string()),
                ("environment", pa.string()),
                ("publisher_id", pa.string()),
                ("publisher_name", pa.string()),
                ("publisher_domain", pa.string()),
                ("app_id", pa.string()),
                ("app_name", pa.string()),
                ("buyer_account_id", pa.string()),
                ("reached_queries", pa.int64()),
                ("impressions", pa.int64()),
                ("clicks", pa.int64()),
                ("spend_micros", pa.int64()),
                ("bids", pa.int64()),
                ("bids_in_auction", pa.int64()),
                ("auctions_won", pa.int64()),
                ("video_starts", pa.int64()),
                ("video_completions", pa.int64()),
                ("viewable_impressions", pa.int64()),
                ("measurable_impressions", pa.int64()),
                ("bidder_id", pa.string()),
                ("report_type", pa.string()),
                ("row_hash", pa.string()),
                ("import_batch_id", pa.string()),
            ]
        )
    if table_name == "rtb_bidstream":
        return pa.schema(
            [
                ("metric_date", pa.date32()),
                ("hour", pa.int64()),
                ("country", pa.string()),
                ("buyer_account_id", pa.string()),
                ("publisher_id", pa.string()),
                ("publisher_name", pa.string()),
                ("platform", pa.string()),
                ("environment", pa.string()),
                ("transaction_type", pa.string()),
                ("inventory_matches", pa.int64()),
                ("bid_requests", pa.int64()),
                ("successful_responses", pa.int64()),
                ("reached_queries", pa.int64()),
                ("bids", pa.int64()),
                ("bids_in_auction", pa.int64()),
                ("auctions_won", pa.int64()),
                ("impressions", pa.int64()),
                ("clicks", pa.int64()),
                ("bidder_id", pa.string()),
                ("report_type", pa.string()),
                ("row_hash", pa.string()),
                ("import_batch_id", pa.string()),
            ]
        )
    if table_name == "rtb_bid_filtering":
        return pa.schema(
            [
                ("metric_date", pa.date32()),
                ("country", pa.string()),
                ("buyer_account_id", pa.string()),
                ("filtering_reason", pa.string()),
                ("creative_id", pa.string()),
                ("bids", pa.int64()),
                ("bids_in_auction", pa.int64()),
                ("opportunity_cost_micros", pa.int64()),
                ("bidder_id", pa.string()),
                ("row_hash", pa.string()),
                ("import_batch_id", pa.string()),
            ]
        )
    raise ValueError(f"Unknown table for parquet schema: {table_name}")


def _bq_schema_for_table(table_name: str) -> list["bigquery.SchemaField"]:
    if table_name == "rtb_daily":
        return [
            bigquery.SchemaField("metric_date", "DATE"),
            bigquery.SchemaField("hour", "INT64"),
            bigquery.SchemaField("billing_id", "STRING"),
            bigquery.SchemaField("creative_id", "STRING"),
            bigquery.SchemaField("creative_size", "STRING"),
            bigquery.SchemaField("creative_format", "STRING"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("platform", "STRING"),
            bigquery.SchemaField("environment", "STRING"),
            bigquery.SchemaField("publisher_id", "STRING"),
            bigquery.SchemaField("publisher_name", "STRING"),
            bigquery.SchemaField("publisher_domain", "STRING"),
            bigquery.SchemaField("app_id", "STRING"),
            bigquery.SchemaField("app_name", "STRING"),
            bigquery.SchemaField("buyer_account_id", "STRING"),
            bigquery.SchemaField("reached_queries", "INT64"),
            bigquery.SchemaField("impressions", "INT64"),
            bigquery.SchemaField("clicks", "INT64"),
            bigquery.SchemaField("spend_micros", "INT64"),
            bigquery.SchemaField("bids", "INT64"),
            bigquery.SchemaField("bids_in_auction", "INT64"),
            bigquery.SchemaField("auctions_won", "INT64"),
            bigquery.SchemaField("video_starts", "INT64"),
            bigquery.SchemaField("video_completions", "INT64"),
            bigquery.SchemaField("viewable_impressions", "INT64"),
            bigquery.SchemaField("measurable_impressions", "INT64"),
            bigquery.SchemaField("bidder_id", "STRING"),
            bigquery.SchemaField("report_type", "STRING"),
            bigquery.SchemaField("row_hash", "STRING"),
            bigquery.SchemaField("import_batch_id", "STRING"),
        ]
    if table_name == "rtb_bidstream":
        return [
            bigquery.SchemaField("metric_date", "DATE"),
            bigquery.SchemaField("hour", "INT64"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("buyer_account_id", "STRING"),
            bigquery.SchemaField("publisher_id", "STRING"),
            bigquery.SchemaField("publisher_name", "STRING"),
            bigquery.SchemaField("platform", "STRING"),
            bigquery.SchemaField("environment", "STRING"),
            bigquery.SchemaField("transaction_type", "STRING"),
            bigquery.SchemaField("inventory_matches", "INT64"),
            bigquery.SchemaField("bid_requests", "INT64"),
            bigquery.SchemaField("successful_responses", "INT64"),
            bigquery.SchemaField("reached_queries", "INT64"),
            bigquery.SchemaField("bids", "INT64"),
            bigquery.SchemaField("bids_in_auction", "INT64"),
            bigquery.SchemaField("auctions_won", "INT64"),
            bigquery.SchemaField("impressions", "INT64"),
            bigquery.SchemaField("clicks", "INT64"),
            bigquery.SchemaField("bidder_id", "STRING"),
            bigquery.SchemaField("report_type", "STRING"),
            bigquery.SchemaField("row_hash", "STRING"),
            bigquery.SchemaField("import_batch_id", "STRING"),
        ]
    if table_name == "rtb_bid_filtering":
        return [
            bigquery.SchemaField("metric_date", "DATE"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("buyer_account_id", "STRING"),
            bigquery.SchemaField("filtering_reason", "STRING"),
            bigquery.SchemaField("creative_id", "STRING"),
            bigquery.SchemaField("bids", "INT64"),
            bigquery.SchemaField("bids_in_auction", "INT64"),
            bigquery.SchemaField("opportunity_cost_micros", "INT64"),
            bigquery.SchemaField("bidder_id", "STRING"),
            bigquery.SchemaField("row_hash", "STRING"),
            bigquery.SchemaField("import_batch_id", "STRING"),
        ]
    raise ValueError(f"Unknown table for BigQuery schema: {table_name}")


def _clean_numeric_string(value: Any) -> str:
    """Strip currency symbols and formatting from numeric strings."""
    s = str(value).strip()
    # Remove currency symbols and thousands separators
    for char in ("$", "€", "£", ","):
        s = s.replace(char, "")
    return s


def _normalize_value(value: Any, field_type: "pa.DataType") -> Any:
    if value is None or value == "":
        return None
    if pa.types.is_date32(field_type):
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
    if pa.types.is_integer(field_type):
        if isinstance(value, int):
            return value
        # Handle currency-formatted strings like "$0.49" -> 0
        cleaned = _clean_numeric_string(value)
        try:
            return int(cleaned)
        except ValueError:
            # If it's a float string, convert to int (truncate)
            return int(float(cleaned))
    if pa.types.is_floating(field_type):
        if isinstance(value, (int, float)):
            return float(value)
        return float(_clean_numeric_string(value))
    if pa.types.is_string(field_type):
        return str(value)
    return value


@dataclass
class ParquetExportManager:
    table_name: str
    batch_id: str
    result_errors: list[str]
    enabled: bool = True
    local_root: Path = field(
        default_factory=lambda: Path(
            os.getenv("CATSCAN_PARQUET_DIR", "~/.catscan/parquet")
        ).expanduser()
    )
    _buffers: Dict[str, list[Dict[str, Any]]] = field(default_factory=dict, init=False)
    _writers: Dict[str, "pq.ParquetWriter"] = field(default_factory=dict, init=False)
    _paths: Dict[str, Path] = field(default_factory=dict, init=False)
    _schema: Optional["pa.Schema"] = field(default=None, init=False)

    @classmethod
    def from_env(cls, table_name: str, batch_id: str, result_errors: list[str]) -> "ParquetExportManager":
        enabled = bool(GCS_BUCKET)
        if not _HAS_PYARROW:
            enabled = False
            logger.warning("pyarrow not installed; Parquet export disabled.")
        if not GCS_BUCKET:
            logger.info("CATSCAN_GCS_BUCKET not set; skipping Parquet export.")
        return cls(table_name=table_name, batch_id=batch_id, result_errors=result_errors, enabled=enabled)

    def add_row(self, day: str, row: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        if not day:
            return
        buffer = self._buffers.setdefault(day, [])
        buffer.append(row)
        if len(buffer) >= PARQUET_BATCH_SIZE:
            self._flush_day(day)

    def _flush_day(self, day: str) -> None:
        if not self.enabled:
            return
        buffer = self._buffers.get(day, [])
        if not buffer:
            return
        schema = self._get_schema()
        normalized = [
            {
                name: _normalize_value(entry.get(name), field.type)
                for name, field in zip(schema.names, schema)
            }
            for entry in buffer
        ]
        table = pa.Table.from_pylist(normalized, schema=schema)
        writer = self._get_writer(day, schema)
        writer.write_table(table)
        buffer.clear()

    def _get_schema(self) -> "pa.Schema":
        if self._schema is None:
            self._schema = _parquet_schema_for_table(self.table_name)
        return self._schema

    def _get_writer(self, day: str, schema: "pa.Schema") -> "pq.ParquetWriter":
        writer = self._writers.get(day)
        if writer:
            return writer
        path = self._parquet_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = pq.ParquetWriter(str(path), schema=schema)
        self._writers[day] = writer
        self._paths[day] = path
        return writer

    def _parquet_path(self, day: str) -> Path:
        return self.local_root / self.table_name / f"day={day}" / f"{self.batch_id}.parquet"

    def finalize(self) -> list[str]:
        if not self.enabled:
            return []
        for day in list(self._buffers.keys()):
            self._flush_day(day)
        for writer in self._writers.values():
            writer.close()
        uploaded = self._upload_files()
        if uploaded and _HAS_BQ and BQ_DATASET:
            self._register_bigquery(uploaded)
        elif uploaded and not _HAS_BQ and BQ_DATASET:
            self._append_error("BigQuery dependencies missing; skipping BigQuery registration.")
        return uploaded

    def _upload_files(self) -> list[str]:
        if not _HAS_GCS:
            self._append_error("google-cloud-storage not installed; skipping GCS upload.")
            return []
        if not GCS_BUCKET:
            return []
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        uploaded = []
        for day, path in self._paths.items():
            gcs_key = f"{GCS_PREFIX}/{self.table_name}/day={day}/{path.name}"
            try:
                blob = bucket.blob(gcs_key)
                blob.upload_from_filename(str(path))
                gcs_uri = f"gs://{GCS_BUCKET}/{gcs_key}"
                uploaded.append(gcs_uri)
                logger.info("Uploaded Parquet to %s", gcs_uri)
            except Exception as exc:
                self._append_error(f"GCS upload failed for {path}: {exc}")
        return uploaded

    def _register_bigquery(self, gcs_uris: Iterable[str]) -> None:
        if not BQ_DATASET:
            return
        client = bigquery.Client(project=BQ_PROJECT or None)
        table_id = f"{client.project}.{BQ_DATASET}.{self.table_name}"
        schema = _bq_schema_for_table(self.table_name)
        if BQ_LOAD_MODE == "external":
            self._register_external_table(client, table_id, schema)
            return
        for gcs_uri in gcs_uris:
            try:
                config = bigquery.LoadJobConfig(
                    schema=schema,
                    source_format=bigquery.SourceFormat.PARQUET,
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                )
                config.time_partitioning = bigquery.TimePartitioning(field="metric_date")
                job = client.load_table_from_uri(gcs_uri, table_id, job_config=config)
                job.result()
                logger.info("Loaded Parquet into BigQuery table %s", table_id)
            except Exception as exc:
                self._append_error(f"BigQuery load failed for {gcs_uri}: {exc}")

    def _register_external_table(
        self,
        client: "bigquery.Client",
        table_id: str,
        schema: list["bigquery.SchemaField"],
    ) -> None:
        try:
            table = bigquery.Table(table_id)
            external_config = bigquery.ExternalConfig("PARQUET")
            external_config.schema = schema
            external_config.source_uris = [
                f"gs://{GCS_BUCKET}/{GCS_PREFIX}/{self.table_name}/day=*/*.parquet"
            ]
            table.external_data_configuration = external_config
            client.create_table(table, exists_ok=True)
            logger.info("Registered external BigQuery table %s", table_id)
        except Exception as exc:
            self._append_error(f"BigQuery external table registration failed: {exc}")

    def _append_error(self, message: str) -> None:
        logger.warning(message)
        if len(self.result_errors) < 20:
            self.result_errors.append(message)
