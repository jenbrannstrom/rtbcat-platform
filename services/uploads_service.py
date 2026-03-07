"""Business logic for upload tracking and import history."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from storage.postgres_repositories.uploads_repo import UploadsRepository


@dataclass
class DailyUploadSummary:
    """Summary of uploads for a single day."""
    upload_date: str
    total_uploads: int
    successful_uploads: int
    failed_uploads: int
    total_rows_written: int
    total_file_size_mb: float
    avg_rows_per_upload: float
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    has_anomaly: bool = False
    anomaly_reason: Optional[str] = None


@dataclass
class ImportHistoryEntry:
    """Single import history entry."""
    batch_id: str
    filename: Optional[str]
    imported_at: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    rows_duplicate: int
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    total_spend_usd: float
    file_size_mb: float
    status: str
    error_message: Optional[str]
    buyer_id: Optional[str]
    buyer_display_name: Optional[str]
    bidder_id: Optional[str]
    billing_ids_found: Optional[list[str]]
    columns_found: Optional[list[str]]
    columns_missing: Optional[list[str]]
    date_gaps: Optional[list[str]]
    date_gap_warning: Optional[str]
    import_trigger: Optional[str] = None


@dataclass
class DailyFileUpload:
    """Single file upload for a day."""
    rows: int
    status: str
    error_message: Optional[str] = None


@dataclass
class DailyUploadRow:
    """One row in the daily uploads grid."""
    date: str
    date_iso: str
    uploads: list[DailyFileUpload] = field(default_factory=list)
    total_rows: int = 0
    has_error: bool = False


@dataclass
class AccountUploadStats:
    """Upload statistics for a single account."""
    bidder_id: str
    total_uploads: int
    total_rows: int
    latest_upload: Optional[str] = None
    billing_ids: list[str] = field(default_factory=list)


@dataclass
class ImportMatrixCell:
    """Coverage status for one account and one CSV type."""
    csv_type: str
    status: str
    source: Optional[str]
    last_imported_at: Optional[str]
    error_summary: Optional[str] = None


@dataclass
class AccountImportMatrix:
    """Import matrix row group for a buyer account."""
    buyer_id: str
    bidder_id: str
    display_name: Optional[str]
    csv_types: list[ImportMatrixCell] = field(default_factory=list)


class UploadsService:
    """Service layer for upload tracking and import history."""

    EXPECTED_CSV_TYPES = [
        "quality",
        "bidsinauction",
        "pipeline-geo",
        "pipeline-publisher",
        "bid-filtering",
    ]

    VALID_IMPORT_SOURCES = {"manual", "gmail-auto", "gmail-manual"}

    def __init__(self, repo: UploadsRepository | None = None) -> None:
        self._repo = repo or UploadsRepository()

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        return await self._repo.table_exists(table_name)

    async def get_tracking_summary(self, days: int) -> dict[str, Any]:
        """Get daily upload tracking summary with aggregated stats."""
        if not await self._repo.table_exists("daily_upload_summary"):
            return {
                "daily_summaries": [],
                "total_days": 0,
                "total_uploads": 0,
                "total_rows": 0,
                "days_with_anomalies": 0,
            }

        rows = await self._repo.get_daily_upload_summaries(days)

        daily_summaries = []
        total_uploads = 0
        total_rows = 0
        days_with_anomalies = 0

        for row in rows:
            file_size_mb = (row.get("total_file_size_bytes") or 0) / (1024 * 1024)
            has_anomaly = bool(row.get("has_anomaly", False))

            summary = DailyUploadSummary(
                upload_date=row["upload_date"],
                total_uploads=row.get("total_uploads") or 0,
                successful_uploads=row.get("successful_uploads") or 0,
                failed_uploads=row.get("failed_uploads") or 0,
                total_rows_written=row.get("total_rows_written") or 0,
                total_file_size_mb=round(file_size_mb, 2),
                avg_rows_per_upload=round(row.get("avg_rows_per_upload") or 0, 1),
                min_rows=row.get("min_rows"),
                max_rows=row.get("max_rows"),
                has_anomaly=has_anomaly,
                anomaly_reason=row.get("anomaly_reason"),
            )
            daily_summaries.append(summary)

            total_uploads += row.get("total_uploads") or 0
            total_rows += row.get("total_rows_written") or 0
            if has_anomaly:
                days_with_anomalies += 1

        return {
            "daily_summaries": daily_summaries,
            "total_days": len(daily_summaries),
            "total_uploads": total_uploads,
            "total_rows": total_rows,
            "days_with_anomalies": days_with_anomalies,
        }

    async def get_import_history(
        self,
        limit: int,
        offset: int,
        buyer_id: Optional[str] = None,
        bidder_id: Optional[str] = None,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> list[ImportHistoryEntry]:
        """Get import history entries with optional filtering."""
        if not await self._repo.table_exists("import_history"):
            return []

        rows = await self._repo.get_import_history(
            limit=limit,
            offset=offset,
            buyer_id=buyer_id,
            bidder_id=bidder_id,
            allowed_bidder_ids=allowed_bidder_ids,
        )

        results = []
        for row in rows:
            file_size_bytes = row.get("file_size_bytes") or 0
            file_size_mb = file_size_bytes / (1024 * 1024)

            billing_ids = self._parse_single_billing_ids(row.get("billing_ids_found"))

            columns_found = self._split_columns(row.get("columns_found"))
            columns_missing = self._split_columns(row.get("columns_missing"))
            date_gaps = self._parse_date_gaps(row.get("date_gaps"))

            results.append(ImportHistoryEntry(
                batch_id=row["batch_id"],
                filename=row.get("filename"),
                imported_at=row.get("imported_at") or "",
                rows_read=row.get("rows_read") or 0,
                rows_imported=row.get("rows_imported") or 0,
                rows_skipped=row.get("rows_skipped") or 0,
                rows_duplicate=row.get("rows_duplicate") or 0,
                date_range_start=row.get("date_range_start"),
                date_range_end=row.get("date_range_end"),
                total_spend_usd=row.get("total_spend_usd") or 0,
                file_size_mb=round(file_size_mb, 2),
                status=row.get("status") or "unknown",
                error_message=row.get("error_message"),
                buyer_id=row.get("buyer_id"),
                buyer_display_name=row.get("buyer_display_name"),
                bidder_id=row.get("bidder_id"),
                billing_ids_found=billing_ids,
                columns_found=columns_found,
                columns_missing=columns_missing,
                date_gaps=date_gaps,
                date_gap_warning=row.get("date_gap_warning"),
                import_trigger=row.get("import_trigger"),
            ))

        return results

    async def get_daily_grid(
        self,
        days: int,
        expected_per_day: int,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get daily uploads in grid format."""
        if not await self._repo.table_exists("import_history"):
            return {"days": [], "expected_uploads_per_day": expected_per_day}

        if allowed_bidder_ids is not None and not allowed_bidder_ids:
            return {"days": [], "expected_uploads_per_day": expected_per_day}

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        imports = await self._repo.get_daily_imports(start_date, allowed_bidder_ids)

        # Group imports by date
        imports_by_date: dict[str, list] = {}
        for row in imports:
            date_str = str(row["import_date"])
            if date_str not in imports_by_date:
                imports_by_date[date_str] = []
            imports_by_date[date_str].append({
                "rows": row.get("rows_imported") or 0,
                "status": row.get("status") or "unknown",
                "error_message": row.get("error_message"),
            })

        # Build response for each day in range
        result_days = []
        current = datetime.now().date()

        for i in range(days):
            check_date = current - timedelta(days=i)
            date_iso = check_date.strftime("%Y-%m-%d")
            date_display = check_date.strftime("%a %d %b")

            day_uploads = imports_by_date.get(date_iso, [])

            uploads = []
            total_rows = 0
            has_error = False

            for upload in day_uploads:
                status = "success" if upload["status"] == "complete" else "error"
                if status == "error":
                    has_error = True
                uploads.append(DailyFileUpload(
                    rows=upload["rows"],
                    status=status,
                    error_message=upload["error_message"],
                ))
                total_rows += upload["rows"]

            # Pad with missing placeholders
            while len(uploads) < expected_per_day:
                uploads.append(DailyFileUpload(rows=0, status="missing"))

            result_days.append(DailyUploadRow(
                date=date_display,
                date_iso=date_iso,
                uploads=uploads,
                total_rows=total_rows,
                has_error=has_error,
            ))

        return {
            "days": result_days,
            "expected_uploads_per_day": expected_per_day,
        }

    async def get_accounts_summary(
        self,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get upload statistics grouped by account."""
        if not await self._repo.table_exists("import_history"):
            return {"accounts": [], "total_accounts": 0, "unassigned_uploads": 0}

        if allowed_bidder_ids is not None and not allowed_bidder_ids:
            return {"accounts": [], "total_accounts": 0, "unassigned_uploads": 0}

        rows = await self._repo.get_account_upload_stats(allowed_bidder_ids)

        if allowed_bidder_ids is None:
            unassigned = await self._repo.get_unassigned_uploads_count()
        else:
            unassigned = 0

        accounts = []
        for row in rows:
            billing_ids = self._parse_billing_ids(row.get("all_billing_ids"))

            accounts.append(AccountUploadStats(
                bidder_id=row["bidder_id"],
                total_uploads=row.get("upload_count") or 0,
                total_rows=row.get("total_rows") or 0,
                latest_upload=row.get("latest_upload"),
                billing_ids=sorted(billing_ids),
            ))

        return {
            "accounts": accounts,
            "total_accounts": len(accounts),
            "unassigned_uploads": unassigned,
        }

    async def get_import_tracking_matrix(
        self,
        days: int,
        allowed_bidder_ids: Optional[list[str]] = None,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return account x CSV-type matrix with pass/fail/not-imported status."""
        if not await self._repo.table_exists("ingestion_runs"):
            return {
                "accounts": [],
                "expected_csv_types": list(self.EXPECTED_CSV_TYPES),
                "total_accounts": 0,
                "pass_count": 0,
                "fail_count": 0,
                "not_imported_count": 0,
            }

        accounts = await self._repo.get_active_import_accounts(
            allowed_bidder_ids=allowed_bidder_ids,
            buyer_id=buyer_id,
        )
        if not accounts:
            return {
                "accounts": [],
                "expected_csv_types": list(self.EXPECTED_CSV_TYPES),
                "total_accounts": 0,
                "pass_count": 0,
                "fail_count": 0,
                "not_imported_count": 0,
            }

        buyer_ids = [str(row["buyer_id"]) for row in accounts if row.get("buyer_id")]
        if not buyer_ids:
            return {
                "accounts": [],
                "expected_csv_types": list(self.EXPECTED_CSV_TYPES),
                "total_accounts": 0,
                "pass_count": 0,
                "fail_count": 0,
                "not_imported_count": 0,
            }

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        latest_runs = await self._repo.get_latest_import_matrix_runs(
            start_date=start_date,
            buyer_ids=buyer_ids,
        )

        latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in latest_runs:
            account_id = str(row.get("account_id") or "")
            csv_type = str(row.get("csv_type") or "")
            if not account_id or not csv_type:
                continue
            latest_by_key[(account_id, csv_type)] = row

        pass_count = 0
        fail_count = 0
        not_imported_count = 0
        matrix_accounts: list[AccountImportMatrix] = []

        for row in accounts:
            buyer_account = str(row.get("buyer_id") or "")
            if not buyer_account:
                continue

            cells: list[ImportMatrixCell] = []
            for csv_type in self.EXPECTED_CSV_TYPES:
                latest = latest_by_key.get((buyer_account, csv_type))
                if not latest:
                    not_imported_count += 1
                    cells.append(
                        ImportMatrixCell(
                            csv_type=csv_type,
                            status="not_imported",
                            source=None,
                            last_imported_at=None,
                            error_summary=None,
                        )
                    )
                    continue

                raw_status = str(latest.get("status") or "").lower()
                status = "pass" if raw_status == "success" else "fail"
                if status == "pass":
                    pass_count += 1
                else:
                    fail_count += 1

                source = str(latest.get("import_trigger") or "manual")
                if source not in self.VALID_IMPORT_SOURCES:
                    source = "manual"

                last_imported = latest.get("finished_at") or latest.get("started_at")
                cells.append(
                    ImportMatrixCell(
                        csv_type=csv_type,
                        status=status,
                        source=source,
                        last_imported_at=str(last_imported) if last_imported else None,
                        error_summary=latest.get("error_summary"),
                    )
                )

            matrix_accounts.append(
                AccountImportMatrix(
                    buyer_id=buyer_account,
                    bidder_id=str(row.get("bidder_id") or ""),
                    display_name=row.get("display_name"),
                    csv_types=cells,
                )
            )

        return {
            "accounts": matrix_accounts,
            "expected_csv_types": list(self.EXPECTED_CSV_TYPES),
            "total_accounts": len(matrix_accounts),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "not_imported_count": not_imported_count,
        }

    async def get_data_freshness_grid(
        self,
        days: int,
        allowed_bidder_ids: Optional[list[str]] = None,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build a date x csv_type freshness grid from actual target tables.

        Returns dates (descending, excluding today), csv_types, a cells dict
        mapping date -> csv_type -> "imported"|"missing", and a coverage summary.
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = await self._repo.get_data_freshness_by_table(
            start_date=start_date,
            buyer_id=buyer_id,
        )

        # Index query results: (date_str, csv_type) -> row_count
        data_index: dict[tuple[str, str], int] = {}
        for row in rows:
            date_str = str(row["metric_date"])
            csv_type = str(row["csv_type"])
            data_index[(date_str, csv_type)] = int(row["row_count"])

        # Build date list: yesterday .. today-days (descending)
        today = datetime.now().date()
        dates: list[str] = []
        for i in range(1, days + 1):
            dates.append((today - timedelta(days=i)).strftime("%Y-%m-%d"))

        csv_types = list(self.EXPECTED_CSV_TYPES)

        # Build cells
        cells: dict[str, dict[str, str]] = {}
        imported_count = 0
        missing_count = 0

        for date_str in dates:
            cells[date_str] = {}
            for csv_type in csv_types:
                count = data_index.get((date_str, csv_type), 0)
                if count > 0:
                    cells[date_str][csv_type] = "imported"
                    imported_count += 1
                else:
                    cells[date_str][csv_type] = "missing"
                    missing_count += 1

        total_cells = imported_count + missing_count
        coverage_pct = round((imported_count / total_cells * 100), 1) if total_cells > 0 else 0.0

        return {
            "dates": dates,
            "csv_types": csv_types,
            "cells": cells,
            "summary": {
                "total_cells": total_cells,
                "imported_count": imported_count,
                "missing_count": missing_count,
                "coverage_pct": coverage_pct,
            },
            "lookback_days": days,
        }

    @staticmethod
    def _split_columns(value: Optional[str]) -> Optional[list[str]]:
        """Split comma-separated column string into list."""
        if not value:
            return None
        columns = [col.strip() for col in value.split(",") if col.strip()]
        return columns or None

    @staticmethod
    def _parse_date_gaps(value: Any) -> Optional[list[str]]:
        """Parse date_gaps field from JSON/text into a list of YYYY-MM-DD strings."""
        if not value:
            return None
        if isinstance(value, list):
            return [str(v) for v in value if v]
        if isinstance(value, str):
            # Preferred storage is JSON array text.
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed if v]
            except json.JSONDecodeError:
                # Legacy fallback: comma-separated dates.
                gaps = [part.strip() for part in value.split(",") if part.strip()]
                return gaps or None
        return None

    @staticmethod
    def _parse_single_billing_ids(value: Any) -> Optional[list[str]]:
        """Parse billing_ids_found field - handles both JSON string and JSONB list."""
        if not value:
            return None
        # If already a list (JSONB), return directly
        if isinstance(value, list):
            return value
        # If dict (shouldn't happen, but handle gracefully)
        if isinstance(value, dict):
            return list(value.keys()) if value else None
        # If string, try to parse as JSON
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _parse_billing_ids(value: Any) -> list[str]:
        """Parse aggregated billing IDs from comma-separated JSON strings or JSONB."""
        if not value:
            return []
        # If already a list (JSONB), return directly
        if isinstance(value, list):
            return [str(v) for v in value]
        # If not a string, can't parse
        if not isinstance(value, str):
            return []
        # Parse comma-separated JSON strings (from STRING_AGG)
        billing_ids: set[str] = set()
        for json_str in value.split(","):
            if json_str:
                try:
                    ids = json.loads(json_str)
                    if isinstance(ids, list):
                        billing_ids.update(str(v) for v in ids)
                except json.JSONDecodeError:
                    pass
        return list(billing_ids)
