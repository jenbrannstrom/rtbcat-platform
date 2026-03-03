#!/usr/bin/env python3
"""Export AppsFlyer raw payloads from conversion_events into JSONL.

This script helps Phase-A attribution audits when the team has ingested
AppsFlyer postbacks already but does not have local export files.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg is required. Install with: pip install psycopg[binary]") from exc


def _resolve_dsn(explicit_dsn: str | None) -> str:
    dsn = explicit_dsn or os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or ""
    if not dsn:
        raise SystemExit("Missing DSN: provide --dsn or set POSTGRES_DSN/DATABASE_URL.")
    return dsn


def _payload_dict(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    if isinstance(raw_payload, str):
        raw = raw_payload.strip()
        if raw.startswith("{") and raw.endswith("}"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return dict(parsed)
            except json.JSONDecodeError:
                pass
        return {"_raw_payload": raw_payload}
    return {"_raw_payload": raw_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export AppsFlyer raw payloads for audit")
    parser.add_argument("--buyer-id", required=True, help="Buyer ID filter")
    parser.add_argument("--source-type", default="appsflyer", help="Source type (default: appsflyer)")
    parser.add_argument("--since-days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--limit", type=int, default=500000, help="Max rows to export (default: 500000)")
    parser.add_argument("--dsn", help="Postgres DSN override (otherwise POSTGRES_DSN/DATABASE_URL)")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    args = parser.parse_args()

    if args.since_days < 1 or args.since_days > 3650:
        raise SystemExit("--since-days must be 1..3650")
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    dsn = _resolve_dsn(args.dsn)
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sql = """
        SELECT id, event_id, event_ts, buyer_id, source_type, raw_payload
        FROM conversion_events
        WHERE source_type = %s
          AND buyer_id = %s
          AND event_ts >= CURRENT_TIMESTAMP - make_interval(days => %s::int)
          AND raw_payload IS NOT NULL
        ORDER BY event_ts DESC
        LIMIT %s
    """
    params = (str(args.source_type), str(args.buyer_id), int(args.since_days), int(args.limit))

    row_count = 0
    with psycopg.connect(dsn, row_factory=dict_row) as conn, out_path.open("w", encoding="utf-8") as handle:
        cursor = conn.execute(sql, params)
        for row in cursor:
            payload = _payload_dict(row.get("raw_payload"))
            payload["_catscan_meta"] = {
                "conversion_event_id": row.get("id"),
                "event_id": row.get("event_id"),
                "event_ts": row.get("event_ts").isoformat() if row.get("event_ts") else None,
                "buyer_id": row.get("buyer_id"),
                "source_type": row.get("source_type"),
            }
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
            row_count += 1

    print(f"buyer_id={args.buyer_id}")
    print(f"source_type={args.source_type}")
    print(f"since_days={args.since_days}")
    print(f"rows_exported={row_count}")
    print(f"output={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
