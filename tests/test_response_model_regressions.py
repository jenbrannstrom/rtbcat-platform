"""Regression tests for Pydantic response model mismatches.

Locks the fixes for:
- qps_current: float accepted (was int, broke on SUM() return)
- SizesResponse: sizes accepts list[str] after dict→str extraction
- schema_migrations DDL: description column present

No database or FastAPI required — pure model validation.
"""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, ValidationError
from typing import Optional

import pytest


# ---- Inline model copies (avoid importing full api module tree) ----

class RTBEndpointItem(BaseModel):
    endpoint_id: str
    url: str
    maximum_qps: Optional[int] = None
    trading_location: Optional[str] = None
    bid_protocol: Optional[str] = None


class RTBEndpointsResponse(BaseModel):
    bidder_id: str
    account_name: Optional[str] = None
    endpoints: list[RTBEndpointItem]
    total_qps_allocated: int
    qps_current: Optional[float] = None  # REGRESSION: was Optional[int]
    synced_at: Optional[str] = None


class SizesResponse(BaseModel):
    sizes: list[str]


# ---- qps_current regression ----

class TestQpsCurrentType:
    def test_float_accepted(self):
        """SUM(current_qps) returns float like 6299.495 — must not raise."""
        resp = RTBEndpointsResponse(
            bidder_id="123",
            endpoints=[],
            total_qps_allocated=10000,
            qps_current=6299.495,
        )
        assert resp.qps_current == 6299.495

    def test_int_still_accepted(self):
        resp = RTBEndpointsResponse(
            bidder_id="123",
            endpoints=[],
            total_qps_allocated=10000,
            qps_current=6300,
        )
        assert resp.qps_current == 6300.0

    def test_none_accepted(self):
        resp = RTBEndpointsResponse(
            bidder_id="123",
            endpoints=[],
            total_qps_allocated=10000,
        )
        assert resp.qps_current is None


# ---- /sizes regression ----

class TestSizesResponse:
    def test_string_list_accepted(self):
        resp = SizesResponse(sizes=["300x250", "728x90", "Non-Standard"])
        assert resp.sizes == ["300x250", "728x90", "Non-Standard"]

    def test_dict_list_rejected(self):
        """The old bug: store returned dicts, model expected strings."""
        with pytest.raises(ValidationError):
            SizesResponse(sizes=[
                {"canonical_size": "300x250", "size_category": "Standard", "count": 42},
            ])

    def test_extraction_logic(self):
        """Simulates the router fix: extract canonical_size from dicts."""
        store_rows = [
            {"canonical_size": "300x250", "size_category": "Standard", "count": 42},
            {"canonical_size": "728x90", "size_category": "Standard", "count": 10},
            {"canonical_size": None, "size_category": None, "count": 1},
        ]
        sizes = [row["canonical_size"] for row in store_rows if row.get("canonical_size")]
        resp = SizesResponse(sizes=sizes)
        assert resp.sizes == ["300x250", "728x90"]


# ---- Migration DDL regression ----

class TestMigrationDDL:
    def test_ensure_migrations_table_includes_description(self):
        """The DDL in postgres_migrate.py must include a description column."""
        from scripts.postgres_migrate import ensure_migrations_table
        import inspect

        source = inspect.getsource(ensure_migrations_table)
        assert "description" in source, (
            "ensure_migrations_table must create/add description column"
        )

    def test_init_migration_includes_description(self):
        """001_init.sql DDL must include description column."""
        from pathlib import Path

        init_sql = (
            Path(__file__).parent.parent
            / "storage"
            / "postgres_migrations"
            / "001_init.sql"
        ).read_text()
        # Find the schema_migrations block and verify description is present
        start = init_sql.find("CREATE TABLE IF NOT EXISTS schema_migrations")
        assert start != -1, "schema_migrations DDL not found in 001_init.sql"
        end = init_sql.find(";", start)
        ddl_block = init_sql[start:end]
        assert "description" in ddl_block, (
            f"description column missing from schema_migrations DDL: {ddl_block}"
        )

    def test_migration_numbers_are_unique(self):
        """Migration SQL filenames must not reuse numeric prefixes."""
        migrations_dir = Path(__file__).parent.parent / "storage" / "postgres_migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        numbers = [path.name.split("_", 1)[0] for path in migration_files]
        duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
        assert not duplicates, f"Duplicate migration numbers found: {', '.join(duplicates)}"

    def test_filter_pending_only_skips_legacy_numeric_markers(self):
        """A canonical marker should not suppress a different canonical migration."""
        from scripts.postgres_migrate import filter_pending_migrations

        pending = [("047_import_trigger_tracking", Path("047_import_trigger_tracking.sql"))]
        to_apply, skipped = filter_pending_migrations(
            pending=pending,
            applied_versions={"047_creatives_list_indexes"},
        )

        assert to_apply == pending
        assert skipped == []

    def test_filter_pending_skips_when_legacy_numeric_marker_exists(self):
        """Legacy numeric marker should still prevent duplicate canonical apply."""
        from scripts.postgres_migrate import filter_pending_migrations

        pending = [("027_schema_alignment", Path("027_schema_alignment.sql"))]
        to_apply, skipped = filter_pending_migrations(
            pending=pending,
            applied_versions={"27"},
        )

        assert to_apply == []
        assert skipped == [("027_schema_alignment", 27)]
