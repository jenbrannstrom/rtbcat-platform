"""Execute the changed SQL on an isolated PostgreSQL database, never production.

Set RTBCAT_SQL_TEST_DSN to a database named rtbcat_query_tests. Every test
creates its own schema inside a transaction and rolls the whole transaction back.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from analytics import qps_optimizer
from importers.unified_importer import ensure_table_exists, rtb_daily_conflict_target
from services import config_precompute
from storage.serving_database import _normalize_sql_placeholders


@pytest.fixture
def db():
    dsn = os.getenv("RTBCAT_SQL_TEST_DSN")
    if not dsn:
        pytest.skip("RTBCAT_SQL_TEST_DSN is required for PostgreSQL regression tests")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if conn.info.dbname != "rtbcat_query_tests":
            pytest.fail("Refusing writes outside the dedicated rtbcat_query_tests database")
        try:
            schema = sql.Identifier("query_test_" + uuid.uuid4().hex)
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(schema))
            conn.execute("SET LOCAL statement_timeout = '10s'")
            conn.execute("""
                CREATE TABLE rtb_daily (
                    id bigserial, metric_date date NOT NULL, hour integer DEFAULT 0,
                    creative_id text, billing_id text, buyer_account_id text,
                    bidder_id text, creative_size text, creative_format text,
                    country text, publisher_id text, publisher_name text, app_id text,
                    reached_queries bigint, impressions bigint, clicks bigint,
                    spend_micros bigint, row_hash text,
                    PRIMARY KEY (metric_date, id), UNIQUE (metric_date, row_hash)
                ) PARTITION BY RANGE (metric_date);
                CREATE TABLE rtb_daily_jan PARTITION OF rtb_daily
                    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
                CREATE TABLE rtb_daily_feb PARTITION OF rtb_daily
                    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
                CREATE TABLE rtb_daily_mar PARTITION OF rtb_daily
                    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
                CREATE TABLE rtb_daily_other PARTITION OF rtb_daily DEFAULT;
                CREATE TABLE rtb_geo_daily (
                    metric_date date, buyer_account_id text, country text,
                    reached_queries bigint, impressions bigint
                );
                CREATE TABLE rtb_publisher_daily (
                    metric_date date, buyer_account_id text, publisher_id text,
                    publisher_name text, reached_queries bigint, impressions bigint
                );
            """)
            yield conn
        finally:
            conn.rollback()


class RecordingConnection:
    def __init__(self, conn, *, legacy=False):
        self.conn = conn
        self.legacy = legacy
        self.statements = []

    def execute(self, query, params=()):
        if self.legacy:
            query = query.replace(
                "metric_date = ANY(%s::date[])", "metric_date::text = ANY(%s)"
            )
        self.statements.append((query, params))
        return self.conn.execute(query, params)

    def cursor(self):
        return self.conn.cursor()


def snapshot(conn):
    result = {}
    for table in (
        "config_publisher_daily", "config_creative_daily",
        "fact_delivery_daily", "fact_dimension_gaps_daily",
    ):
        rows = conn.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
        result[table] = sorted(
            (repr({k: v for k, v in row.items() if k not in ("created_at", "updated_at")})
             for row in rows)
        )
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("buyer", [None, "buyer-a"])
async def test_precompute_preserves_results_scope_and_prunes_months(db, monkeypatch, buyer):
    db.execute("""
        INSERT INTO rtb_daily (
            metric_date, buyer_account_id, billing_id, creative_id, creative_size,
            creative_format, country, publisher_id, publisher_name,
            reached_queries, impressions, clicks, spend_micros
        ) VALUES
            ('2026-01-31','buyer-a','bill-a','creative-a','300x250','BANNER','ZA','pub-a','A',100,10,1,1000),
            ('2026-01-31','buyer-a','bill-a','creative-a','300x250','BANNER','ZA','pub-a','A',200,20,2,2000),
            ('2026-02-01','buyer-a','bill-a','creative-a','300x250','BANNER','ZA','pub-a','A',900,90,9,9000),
            ('2026-03-01','buyer-a','bill-a','creative-a','300x250','BANNER','ZA','pub-a','A',300,30,3,3000),
            ('2026-01-31','buyer-b','bill-b','creative-b','320x50','BANNER','US','pub-b','B',400,40,4,4000),
            ('2026-03-01','buyer-b','bill-b','creative-b','320x50','BANNER','US','pub-b','B',500,50,5,5000);
        INSERT INTO rtb_geo_daily VALUES ('2026-01-31','buyer-c','DE',700,70);
        INSERT INTO rtb_publisher_daily VALUES ('2026-01-31','buyer-c','pub-c','C',800,80);
    """)
    monkeypatch.setattr(config_precompute, "get_bigquery_client", lambda: object())
    monkeypatch.setattr(config_precompute, "build_table_ref", lambda *a, **kw: "test.rtb_daily")
    monkeypatch.setattr(config_precompute, "run_query", lambda *a, **kw: [])
    recorder = RecordingConnection(db, legacy=True)

    async def transaction(fn):
        return fn(recorder)

    monkeypatch.setattr(config_precompute, "pg_transaction_async", transaction)
    await config_precompute.refresh_config_breakdowns(dates=["2026-01-31", "2026-02-01", "2026-03-01"])
    baseline = snapshot(db)
    recorder.legacy = False
    recorder.statements.clear()
    await config_precompute.refresh_config_breakdowns(
        dates=["2026-03-01", "2026-01-31", "2026-01-31"], buyer_account_id=buyer
    )
    assert snapshot(db) == baseline
    facts = db.execute("""
        SELECT reached_queries, impressions, clicks, spend_micros
        FROM fact_delivery_daily
        WHERE metric_date='2026-01-31' AND buyer_account_id='buyer-a' AND country='ZA'
    """).fetchone()
    assert facts == dict(reached_queries=300, impressions=30, clicks=3, spend_micros=3000)

    raw_refreshes = [(q, p) for q, p in recorder.statements
                     if "INSERT INTO" in q and "FROM rtb_daily" in q]
    assert len(raw_refreshes) == 5
    for query, params in raw_refreshes:
        plan = db.execute("EXPLAIN (FORMAT JSON) " + query, params).fetchone()["QUERY PLAN"]
        relations = set()

        def walk(node):
            name = node.get("Relation Name", "")
            if name.startswith("rtb_daily_"):
                relations.add(name)
            for child in node.get("Plans", []):
                walk(child)

        walk(plan[0]["Plan"])
        assert relations == {"rtb_daily_jan", "rtb_daily_mar"}


@pytest.mark.asyncio
@pytest.mark.parametrize("bidder", [None, "bidder-a"])
async def test_qps_size_gaps_aggregate_filter_sort_and_scope(db, monkeypatch, bidder):
    db.execute("""
        INSERT INTO rtb_daily (metric_date,bidder_id,creative_size,creative_format,
                              reached_queries,impressions,spend_micros)
        VALUES
            (CURRENT_DATE,'bidder-a','300x250','BANNER',500,50,1000000),
            (CURRENT_DATE,'bidder-a','300x250','BANNER',500,50,2000000),
            (CURRENT_DATE,'bidder-a','320x50',NULL,400,100,1000000),
            (CURRENT_DATE,'bidder-a','728x90','BANNER',200,100,1000000),
            (CURRENT_DATE,'bidder-a','all-null','BANNER',NULL,NULL,NULL),
            (CURRENT_DATE,'bidder-a',NULL,'BANNER',5000,0,0),
            (CURRENT_DATE-8,'bidder-a','expired','BANNER',5000,0,0),
            (CURRENT_DATE,'bidder-b','970x250','BANNER',2000,100,4000000);
    """)

    async def query(statement, params):
        return db.execute(_normalize_sql_placeholders(statement), params).fetchall()

    monkeypatch.setattr(qps_optimizer, "db_query", query)
    rows = await qps_optimizer.QPSOptimizer().get_size_coverage_gaps(7, bidder)
    expected_sizes = ["300x250", "320x50"]
    if bidder is None:
        expected_sizes.insert(0, "970x250")
    assert [row["size"] for row in rows] == expected_sizes
    main = next(row for row in rows if row["size"] == "300x250")
    assert main == dict(size="300x250", format="BANNER", reached_queries=1000,
                       impressions=100, spend_usd=3.0, win_rate_pct=10.0, gap_queries=900)
    assert rows[-1]["format"] == "BANNER"


def test_importer_keeps_required_indexes_and_dedup_without_retired_index(db):
    with db.cursor() as cursor:
        ensure_table_exists(cursor, "rtb_daily")
        target = rtb_daily_conflict_target(cursor)
        assert target == "(metric_date, row_hash)"
        for _ in range(2):
            cursor.execute(f"""
                INSERT INTO rtb_daily (metric_date,row_hash,creative_id)
                VALUES ('2026-01-31','same-hash','creative-a')
                ON CONFLICT {target} DO NOTHING
            """)
        ensure_table_exists(cursor, "rtb_daily")
    names = {row["indexname"] for row in db.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() AND tablename='rtb_daily'"
    )}
    assert "idx_rtb_daily_metric_creative" not in names
    assert {"idx_rtb_daily_creative", "idx_rtb_daily_bidder", "idx_rtb_daily_metric_billing"} <= names
    assert db.execute("SELECT count(*) AS n FROM rtb_daily").fetchone()["n"] == 1


def test_guarded_index_removal_preserves_rows_and_alternatives(db):
    db.execute("""
        CREATE TABLE public.rtb_daily (
            metric_date date, creative_id text, spend_micros bigint,
            impressions bigint, clicks bigint
        ) PARTITION BY RANGE (metric_date);
        CREATE TABLE public.rtb_daily_jan PARTITION OF public.rtb_daily
            FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
        CREATE INDEX idx_rtb_daily_metric_creative ON public.rtb_daily(metric_date,creative_id);
        CREATE INDEX idx_rtb_daily_creative ON public.rtb_daily(creative_id);
        CREATE INDEX rtbd_p_creative_date_perf ON public.rtb_daily(creative_id,metric_date)
            INCLUDE (spend_micros,impressions,clicks);
        INSERT INTO public.rtb_daily VALUES ('2026-01-31','creative-a',1000,10,1);
    """)
    script = (Path(__file__).parents[1] / "scripts/hetzner/drop_unused_rtb_daily_creative_index.sql").read_text()
    # The fixture owns the transaction; keep this destructive rehearsal rollback-only.
    script = re.sub(r"^(?:\\set[^\n]*|BEGIN;|COMMIT;)\n", "", script, flags=re.M)
    db.execute(script)
    assert db.execute("SELECT to_regclass('public.idx_rtb_daily_metric_creative') AS idx").fetchone()["idx"] is None
    assert db.execute("SELECT count(*) AS n FROM public.rtb_daily").fetchone()["n"] == 1
    assert db.execute("SELECT to_regclass('public.rtbd_p_creative_date_perf') AS idx").fetchone()["idx"] is not None
