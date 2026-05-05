from __future__ import annotations

from datetime import date


class _OperationalError(Exception):
    pass


class _FakeCursor:
    def __init__(self, should_fail: bool) -> None:
        self._should_fail = should_fail
        self.executemany_calls = 0

    def executemany(self, sql, values):  # noqa: ANN001
        del sql, values
        self.executemany_calls += 1
        if self._should_fail:
            raise _OperationalError("the connection is lost")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class _FakeConn:
    def __init__(self, should_fail: bool) -> None:
        self._should_fail = should_fail
        self.closed = False
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj = _FakeCursor(should_fail)

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_aggregate_date_retries_transient_postgres_disconnect(monkeypatch):
    from scripts import bq_aggregate_to_pg as agg

    monkeypatch.setattr(agg.bigquery, "Client", lambda project=None: object())

    rows = [{
        "metric_date": date(2026, 5, 5),
        "buyer_account_id": "buyer-1",
        "reached_queries": 10,
        "impressions": 5,
        "bids": 4,
        "successful_responses": 3,
        "bid_requests": 2,
        "auctions_won": 1,
    }]
    monkeypatch.setattr(
        agg,
        "run_bq_aggregation",
        lambda **kwargs: rows,
    )

    first_conn = _FakeConn(True)
    second_conn = _FakeConn(False)
    created = [first_conn, second_conn]

    def fake_connect(dsn):  # noqa: ANN001
        del dsn
        return created.pop(0)

    monkeypatch.setattr(agg.psycopg, "connect", fake_connect)
    monkeypatch.setattr(agg.time, "sleep", lambda *_args, **_kwargs: None)

    result = agg.aggregate_date(
        date(2026, 5, 5),
        tables=["home_seat_daily"],
        config={"project_id": "proj", "dataset": "ds", "postgres_dsn": "postgresql://x"},
    )

    assert result == {"home_seat_daily": 1}
    assert created == []
    assert first_conn.closed is True
    assert second_conn.closed is True
