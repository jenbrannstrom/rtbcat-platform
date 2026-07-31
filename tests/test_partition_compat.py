"""rtb_daily partition-cutover compatibility (scripts/partition_migration/).

The importer must pick the dedup conflict target that matches whichever
rtb_daily shape is live: UNIQUE (row_hash) on the legacy table,
UNIQUE (metric_date, row_hash) on the partitioned one.
"""

from __future__ import annotations

from pathlib import Path

from importers.unified_importer import rtb_daily_conflict_target


class _FakeCursor:
    """Mimics a psycopg cursor for the pg_partitioned_table probe."""

    def __init__(self, is_partitioned: bool, dict_rows: bool):
        self._is_partitioned = is_partitioned
        self._dict_rows = dict_rows
        self.executed: list[str] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append(sql)

    def fetchone(self):
        if self._dict_rows:
            return {"is_partitioned": self._is_partitioned}
        return (self._is_partitioned,)


def test_legacy_table_uses_row_hash():
    cursor = _FakeCursor(is_partitioned=False, dict_rows=True)
    assert rtb_daily_conflict_target(cursor) == "(row_hash)"
    assert "pg_partitioned_table" in cursor.executed[0]


def test_partitioned_table_includes_partition_key():
    cursor = _FakeCursor(is_partitioned=True, dict_rows=True)
    assert rtb_daily_conflict_target(cursor) == "(metric_date, row_hash)"


def test_tuple_row_factory_supported():
    assert rtb_daily_conflict_target(
        _FakeCursor(is_partitioned=True, dict_rows=False)
    ) == "(metric_date, row_hash)"
    assert rtb_daily_conflict_target(
        _FakeCursor(is_partitioned=False, dict_rows=False)
    ) == "(row_hash)"


def test_fresh_partition_schema_preserves_application_ownership():
    schema = (
        Path(__file__).parents[1]
        / "scripts"
        / "partition_migration"
        / "001_partitioned_schema.sql"
    ).read_text()

    assert r"\if :{?owner_role}" in schema
    assert 'ALTER TABLE :parent OWNER TO :"owner_role";' in schema
    assert "'ALTER TABLE %s OWNER TO %I'" in schema
    assert "SELECT :'parent' = 'rtb_daily' AS fresh_target" in schema
    assert 'ALTER SEQUENCE rtb_daily_id_seq OWNER TO :"owner_role";' in schema
    assert "ALTER SEQUENCE rtb_daily_id_seq OWNED BY :parent.id;" in schema
    assert (
        "buyer_id                text GENERATED ALWAYS AS "
        "(buyer_account_id) STORED"
    ) in schema
