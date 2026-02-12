#!/usr/bin/env python3
"""Contract validation suite for CatScan platform.

Machine-checks contracts: C-ING-001, C-ING-002, C-EPT-001, C-PRE-002, C-PRE-003.

Usage:
    python scripts/contracts_check.py --days 7
    python scripts/contracts_check.py --days 7 --strict --json-out /tmp/contracts.json
    python scripts/contracts_check.py --buyer 6574658621 --db-dsn-env DATABASE_URL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

# Ensure project root is importable when run from scripts/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage.postgres_database import pg_query  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    contract_id: str
    name: str
    status: str  # "PASS", "FAIL", "WARN"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CatScan contract validation suite."
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Lookback window in days (default: 7)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN as FAIL (exit non-zero)",
    )
    parser.add_argument("--buyer", help="Scope to a single buyer_account_id")
    parser.add_argument(
        "--db-dsn-env",
        default="POSTGRES_SERVING_DSN",
        help="Env var holding the DB DSN (default: POSTGRES_SERVING_DSN)",
    )
    parser.add_argument("--json-out", help="Path to write JSON output")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Buyer discovery
# ---------------------------------------------------------------------------


async def discover_active_buyers(
    buyer_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return active buyers from buyer_seats."""
    if buyer_filter:
        return await pg_query(
            "SELECT buyer_id, bidder_id FROM buyer_seats "
            "WHERE active = true AND buyer_id = %s",
            (buyer_filter,),
        )
    return await pg_query(
        "SELECT buyer_id, bidder_id FROM buyer_seats "
        "WHERE active = true ORDER BY buyer_id"
    )


# ---------------------------------------------------------------------------
# Contract checks
# ---------------------------------------------------------------------------


async def check_ing_001(days: int) -> CheckResult:
    """C-ING-001: Every import run logged in ingestion_runs."""
    rows = await pg_query("SELECT COUNT(*) AS cnt FROM ingestion_runs")
    total = rows[0]["cnt"] if rows else 0

    stuck = await pg_query(
        "SELECT COUNT(*) AS cnt FROM ingestion_runs "
        "WHERE finished_at IS NULL AND started_at < NOW() - INTERVAL '1 hour'"
    )
    stuck_count = stuck[0]["cnt"] if stuck else 0

    details = {"total_runs": total, "stuck_runs": stuck_count}

    if total == 0:
        return CheckResult(
            "C-ING-001", "ingestion_runs populated", "FAIL",
            f"ingestion_runs has 0 rows", details,
        )
    if stuck_count > 0:
        return CheckResult(
            "C-ING-001", "ingestion_runs populated", "WARN",
            f"{stuck_count} stuck run(s) (started >1h ago, no finished_at)", details,
        )
    return CheckResult(
        "C-ING-001", "ingestion_runs populated", "PASS",
        f"{total} run(s), 0 stuck", details,
    )


async def check_ing_002(days: int, buyers: list[dict]) -> CheckResult:
    """C-ING-002: import_history covers all active buyers within 48h."""
    missing_buyers: list[str] = []
    for b in buyers:
        bid = b["buyer_id"]
        try:
            rows = await pg_query(
                "SELECT COUNT(*) AS cnt FROM import_history "
                "WHERE (buyer_id = %s OR filename LIKE '%%' || %s || '%%') "
                "AND imported_at > NOW() - INTERVAL '48 hours'",
                (bid, bid),
            )
        except Exception:
            # buyer_id column may not exist; fall back to filename only
            rows = await pg_query(
                "SELECT COUNT(*) AS cnt FROM import_history "
                "WHERE filename LIKE '%%' || %s || '%%' "
                "AND imported_at > NOW() - INTERVAL '48 hours'",
                (bid,),
            )
        if (rows[0]["cnt"] if rows else 0) == 0:
            missing_buyers.append(bid)

    details = {"missing_buyers": missing_buyers, "total_buyers": len(buyers)}

    if missing_buyers:
        return CheckResult(
            "C-ING-002", "import_history buyer coverage", "FAIL",
            f"{len(missing_buyers)}/{len(buyers)} buyers missing imports in 48h: "
            f"{missing_buyers}",
            details,
        )
    return CheckResult(
        "C-ING-002", "import_history buyer coverage", "PASS",
        f"All {len(buyers)} buyers have imports in 48h", details,
    )


async def check_ept_001() -> CheckResult:
    """C-EPT-001: rtb_endpoints_current populated for all endpoints."""
    total_rows = await pg_query("SELECT COUNT(*) AS cnt FROM rtb_endpoints")
    total_cnt = total_rows[0]["cnt"] if total_rows else 0

    if total_cnt == 0:
        return CheckResult(
            "C-EPT-001", "rtb_endpoints_current populated", "WARN",
            "No endpoints in rtb_endpoints (nothing to check)",
            {"total_endpoints": 0, "missing": 0, "stale": 0},
        )

    gaps = await pg_query(
        "SELECT e.bidder_id, e.endpoint_id, ec.observed_at "
        "FROM rtb_endpoints e "
        "LEFT JOIN rtb_endpoints_current ec "
        "  ON e.bidder_id = ec.bidder_id AND e.endpoint_id = ec.endpoint_id "
        "WHERE ec.id IS NULL OR ec.observed_at < NOW() - INTERVAL '24 hours'"
    )

    if gaps:
        missing = sum(1 for g in gaps if g.get("observed_at") is None)
        stale = len(gaps) - missing
        return CheckResult(
            "C-EPT-001", "rtb_endpoints_current populated", "FAIL",
            f"{len(gaps)}/{total_cnt} endpoints missing/stale "
            f"({missing} missing, {stale} stale)",
            {
                "total_endpoints": total_cnt,
                "missing": missing,
                "stale": stale,
                "gap_sample": [
                    {"bidder_id": g["bidder_id"], "endpoint_id": g["endpoint_id"]}
                    for g in gaps[:10]
                ],
            },
        )

    return CheckResult(
        "C-EPT-001", "rtb_endpoints_current populated", "PASS",
        f"All {total_cnt} endpoints have current observations",
        {"total_endpoints": total_cnt, "missing": 0, "stale": 0},
    )


async def check_pre_002(days: int, buyers: list[dict]) -> CheckResult:
    """C-PRE-002: All ACTIVE configs have rows in home_config_daily."""
    total_gap = 0
    buyer_gaps: dict[str, int] = {}

    for b in buyers:
        bid = b["buyer_id"]
        rows = await pg_query(
            "SELECT "
            "  COUNT(*) AS configured_active, "
            "  COUNT(hcd.billing_id) AS observed_precompute, "
            "  COUNT(*) - COUNT(hcd.billing_id) AS gap "
            "FROM pretargeting_configs pc "
            "JOIN buyer_seats bs "
            "  ON bs.bidder_id = pc.bidder_id AND bs.active = true "
            "LEFT JOIN ( "
            "  SELECT DISTINCT buyer_account_id, billing_id "
            "  FROM home_config_daily "
            "  WHERE metric_date::text >= (CURRENT_DATE - %s)::text "
            ") hcd ON hcd.buyer_account_id = pc.bidder_id "
            "  AND hcd.billing_id = pc.billing_id "
            "WHERE pc.state = 'ACTIVE' "
            "  AND pc.billing_id IS NOT NULL "
            "  AND pc.billing_id != '' "
            "  AND pc.bidder_id = %s",
            (days, bid),
        )
        if rows:
            gap = rows[0]["gap"]
            if gap > 0:
                buyer_gaps[bid] = gap
                total_gap += gap

    if total_gap > 0:
        return CheckResult(
            "C-PRE-002", "home_config_daily ACTIVE config coverage", "FAIL",
            f"{total_gap} ACTIVE config(s) missing from home_config_daily: "
            f"{buyer_gaps}",
            {"total_gap": total_gap, "buyer_gaps": buyer_gaps},
        )

    return CheckResult(
        "C-PRE-002", "home_config_daily ACTIVE config coverage", "PASS",
        f"All ACTIVE configs have rows in home_config_daily ({days}d window)",
        {"total_gap": 0, "buyers_checked": len(buyers)},
    )


async def check_pre_003(
    days: int, buyers: list[dict], strict: bool = False,
) -> CheckResult:
    """C-PRE-003: config_publisher_daily non-empty for buyers with data."""
    missing: list[str] = []
    justified: list[str] = []

    for b in buyers:
        bid = b["buyer_id"]

        # Does buyer have data in home_config_daily?
        hcd = await pg_query(
            "SELECT COUNT(*) AS cnt FROM home_config_daily "
            "WHERE buyer_account_id = %s "
            "AND metric_date::text >= (CURRENT_DATE - %s)::text",
            (bid, days),
        )
        if (hcd[0]["cnt"] if hcd else 0) == 0:
            continue

        # Check config_publisher_daily
        cpd = await pg_query(
            "SELECT COUNT(*) AS cnt FROM config_publisher_daily "
            "WHERE buyer_account_id = %s "
            "AND metric_date >= (CURRENT_DATE - %s)::text",
            (bid, days),
        )
        if (cpd[0]["cnt"] if cpd else 0) > 0:
            continue

        # Check if justified (no publisher_id in rtb_daily)
        pub = await pg_query(
            "SELECT COUNT(*) AS with_pub FROM rtb_daily "
            "WHERE buyer_account_id = %s "
            "AND metric_date::text >= (CURRENT_DATE - %s)::text "
            "AND publisher_id IS NOT NULL AND publisher_id != ''",
            (bid, days),
        )
        if (pub[0]["with_pub"] if pub else 0) == 0:
            justified.append(bid)
        else:
            missing.append(bid)

    details = {
        "buyers_checked": len(buyers),
        "missing": missing,
        "justified_exceptions": justified,
    }

    if missing:
        return CheckResult(
            "C-PRE-003", "config_publisher_daily coverage", "FAIL",
            f"{len(missing)} buyer(s) have home_config_daily but no "
            f"config_publisher_daily: {missing}",
            details,
        )
    if justified and strict:
        return CheckResult(
            "C-PRE-003", "config_publisher_daily coverage", "FAIL",
            f"{len(justified)} justified exception(s) fail under --strict: "
            f"{justified}",
            details,
        )
    if justified:
        return CheckResult(
            "C-PRE-003", "config_publisher_daily coverage", "WARN",
            f"All covered; {len(justified)} justified exception(s) "
            f"(no publisher_id in source): {justified}",
            details,
        )

    return CheckResult(
        "C-PRE-003", "config_publisher_daily coverage", "PASS",
        "All buyers with home_config_daily have config_publisher_daily data",
        details,
    )


# ---------------------------------------------------------------------------
# Web lane feature flag
# ---------------------------------------------------------------------------


def is_web_lane_enabled(buyer_id: str = "") -> bool:
    """Check if the web/domain lane is enabled globally and for a specific buyer."""
    if os.getenv("CATSCAN_WEB_LANE_ENABLED", "").lower() not in ("1", "true", "yes"):
        return False
    allowlist = os.getenv("CATSCAN_WEB_LANE_BUYERS", "")
    if not allowlist:
        return True  # global enabled, no per-buyer restriction
    return buyer_id in [b.strip() for b in allowlist.split(",")]


def _web_lane_buyer_sql_filter() -> str:
    """Return a SQL AND clause to scope to allowlisted buyers, or empty string."""
    allowlist = os.getenv("CATSCAN_WEB_LANE_BUYERS", "")
    if not allowlist:
        return ""
    buyers = [b.strip() for b in allowlist.split(",") if b.strip()]
    if not buyers:
        return ""
    placeholders = ", ".join(f"'{b}'" for b in buyers)
    return f" AND buyer_account_id IN ({placeholders})"


# ---------------------------------------------------------------------------
# Web lane contract checks
# ---------------------------------------------------------------------------


async def check_web_001(days: int) -> CheckResult:
    """C-WEB-001: inventory_type valid on all web_domain_daily rows."""
    if not is_web_lane_enabled():
        return CheckResult(
            "C-WEB-001", "inventory_type valid", "SKIP",
            "Web lane disabled (CATSCAN_WEB_LANE_ENABLED unset)",
        )

    buyer_filter = _web_lane_buyer_sql_filter()
    rows = await pg_query(
        "SELECT COUNT(*) AS cnt FROM web_domain_daily "
        "WHERE inventory_type NOT IN ('web', 'app', 'unknown') "
        f"AND metric_date >= (CURRENT_DATE - {days}){buyer_filter}"
    )
    bad = rows[0]["cnt"] if rows else 0

    if bad > 0:
        return CheckResult(
            "C-WEB-001", "inventory_type valid", "FAIL",
            f"{bad} row(s) with invalid inventory_type in last {days}d",
            {"invalid_rows": bad},
        )
    return CheckResult(
        "C-WEB-001", "inventory_type valid", "PASS",
        f"All web_domain_daily rows have valid inventory_type ({days}d)",
    )


async def check_web_002(days: int, buyers: list[dict]) -> CheckResult:
    """C-WEB-002: top-N invariant — distinct domains per group <= N+1."""
    if not is_web_lane_enabled():
        return CheckResult(
            "C-WEB-002", "domain cardinality", "SKIP",
            "Web lane disabled (CATSCAN_WEB_LANE_ENABLED unset)",
        )

    top_n = int(os.getenv("CATSCAN_DOMAIN_TOP_N", "200"))
    buyer_filter = _web_lane_buyer_sql_filter()

    rows = await pg_query(
        "SELECT metric_date, buyer_account_id, billing_id, "
        "COUNT(DISTINCT publisher_domain) AS domain_count "
        "FROM web_domain_daily "
        f"WHERE metric_date >= (CURRENT_DATE - {days}){buyer_filter} "
        "GROUP BY metric_date, buyer_account_id, billing_id "
        f"HAVING COUNT(DISTINCT publisher_domain) > {top_n + 1}"
    )

    if rows:
        return CheckResult(
            "C-WEB-002", "domain cardinality", "FAIL",
            f"{len(rows)} group(s) exceed top-N+1 ({top_n + 1}) domain limit",
            {"violating_groups": len(rows), "top_n": top_n},
        )
    return CheckResult(
        "C-WEB-002", "domain cardinality", "PASS",
        f"All groups within top-{top_n}+1 domain limit ({days}d)",
        {"top_n": top_n},
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def print_summary(results: list[CheckResult]) -> tuple[int, int, int]:
    """Print human-readable summary table. Returns (pass, warn, fail) counts."""
    print("\n" + "=" * 72)
    print("CONTRACT VALIDATION SUMMARY")
    print("=" * 72)
    print(f"{'Contract':<12} {'Status':<6} Message")
    print("-" * 72)

    for r in results:
        icon = {"PASS": "+", "FAIL": "X", "WARN": "!", "SKIP": "-"}.get(r.status, "?")
        print(f"{r.contract_id:<12} [{icon}] {r.status:<4}  {r.message}")

    print("-" * 72)
    passes = sum(1 for r in results if r.status == "PASS")
    warns = sum(1 for r in results if r.status == "WARN")
    fails = sum(1 for r in results if r.status == "FAIL")
    skips = sum(1 for r in results if r.status == "SKIP")
    print(f"Total: {passes} PASS, {warns} WARN, {fails} FAIL, {skips} SKIP")
    print("=" * 72)
    return passes, warns, fails


async def run_all_checks(
    days: int = 7,
    strict: bool = False,
    buyer_filter: Optional[str] = None,
) -> list[CheckResult]:
    """Execute all contract checks and return results."""
    buyers = await discover_active_buyers(buyer_filter)
    if not buyers:
        return [
            CheckResult(
                "DISCOVERY", "active buyer discovery", "FAIL",
                "No active buyers found in buyer_seats",
                {"buyer_filter": buyer_filter},
            )
        ]

    logger.info("Active buyers: %s", [b["buyer_id"] for b in buyers])

    return [
        await check_ing_001(days),
        await check_ing_002(days, buyers),
        await check_ept_001(),
        await check_pre_002(days, buyers),
        await check_pre_003(days, buyers, strict),
        await check_web_001(days),
        await check_web_002(days, buyers),
    ]


async def main() -> None:
    args = parse_args()

    # Bridge the DSN env var to what postgres_database expects.
    dsn = os.getenv(args.db_dsn_env)
    if dsn:
        os.environ.setdefault("POSTGRES_DSN", dsn)

    logger.info(
        "Contract check: days=%d, strict=%s, buyer=%s, dsn_env=%s",
        args.days, args.strict, args.buyer, args.db_dsn_env,
    )

    results = await run_all_checks(
        days=args.days, strict=args.strict, buyer_filter=args.buyer,
    )

    passes, warns, fails = print_summary(results)

    # JSON output
    if args.json_out:
        output = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "days": args.days,
            "strict": args.strict,
            "buyer_filter": args.buyer,
            "results": [asdict(r) for r in results],
            "summary": {"pass": passes, "warn": warns, "fail": fails},
        }
        with open(args.json_out, "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info("JSON output written to %s", args.json_out)

    # Exit code
    if fails > 0:
        sys.exit(1)
    if warns > 0 and args.strict:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
