"""Query Performance Framework for Cat-Scan RTB Platform.

This module provides tools for profiling and testing database query performance.
It helps identify slow queries, measure optimization effectiveness, and ensure
queries meet performance targets as data grows.

Usage:
    # Profile a specific query
    python tests/query_performance.py profile "SELECT * FROM rtb_daily"

    # Run all benchmark tests
    python tests/query_performance.py benchmark

    # Generate performance report
    python tests/query_performance.py report

Run with pytest: pytest tests/query_performance.py -v
"""

import sqlite3
import time
import statistics
import json
import sys
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any


# Performance targets (in milliseconds)
QUERY_TARGETS = {
    "fast": 50,      # Simple lookups
    "medium": 200,   # Aggregations
    "slow": 1000,    # Complex joins
    "report": 5000,  # Full reports
}


@dataclass
class QueryResult:
    """Result of a single query execution."""
    query: str
    execution_time_ms: float
    row_count: int
    success: bool
    error: Optional[str] = None


@dataclass
class QueryProfile:
    """Profile of multiple executions of a query."""
    query: str
    name: str
    executions: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    std_dev_ms: float
    row_count: int
    target_category: str
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "query": self.query[:100] + "..." if len(self.query) > 100 else self.query,
            "executions": self.executions,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "row_count": self.row_count,
            "target_category": self.target_category,
            "target_ms": QUERY_TARGETS.get(self.target_category, 1000),
            "passed": self.passed,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark queries to test."""
    name: str
    queries: List[Dict[str, Any]] = field(default_factory=list)

    def add_query(self, name: str, query: str, category: str = "medium",
                  params: tuple = None):
        """Add a query to the benchmark suite."""
        self.queries.append({
            "name": name,
            "query": query,
            "category": category,
            "params": params or (),
        })


class QueryProfiler:
    """Profiles database queries for performance analysis."""

    def __init__(self, db_path: str = None):
        """Initialize the profiler with a database path."""
        if db_path is None:
            db_path = str(Path.home() / ".catscan" / "catscan.db")
        self.db_path = db_path
        self._conn = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_query(self, query: str, params: tuple = None) -> QueryResult:
        """Execute a single query and measure time."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            start_time = time.perf_counter()
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            end_time = time.perf_counter()

            execution_time_ms = (end_time - start_time) * 1000

            return QueryResult(
                query=query,
                execution_time_ms=execution_time_ms,
                row_count=len(results),
                success=True,
            )
        except Exception as e:
            return QueryResult(
                query=query,
                execution_time_ms=0,
                row_count=0,
                success=False,
                error=str(e),
            )

    def profile_query(self, query: str, name: str = "unnamed",
                      executions: int = 5, category: str = "medium",
                      params: tuple = None) -> QueryProfile:
        """Profile a query with multiple executions."""
        times = []
        row_count = 0

        for _ in range(executions):
            result = self.execute_query(query, params)
            if result.success:
                times.append(result.execution_time_ms)
                row_count = result.row_count
            else:
                raise RuntimeError(f"Query failed: {result.error}")

        target_ms = QUERY_TARGETS.get(category, 1000)
        mean_time = statistics.mean(times)

        return QueryProfile(
            query=query,
            name=name,
            executions=executions,
            min_ms=min(times),
            max_ms=max(times),
            mean_ms=mean_time,
            median_ms=statistics.median(times),
            std_dev_ms=statistics.stdev(times) if len(times) > 1 else 0,
            row_count=row_count,
            target_category=category,
            passed=mean_time <= target_ms,
        )

    def run_benchmark(self, suite: BenchmarkSuite, executions: int = 5) -> List[QueryProfile]:
        """Run all queries in a benchmark suite."""
        profiles = []
        for q in suite.queries:
            profile = self.profile_query(
                query=q["query"],
                name=q["name"],
                executions=executions,
                category=q["category"],
                params=q.get("params"),
            )
            profiles.append(profile)
        return profiles

    def get_explain_plan(self, query: str) -> List[Dict]:
        """Get the EXPLAIN QUERY PLAN for a query."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {query}")
        return [dict(row) for row in cursor.fetchall()]


def get_standard_benchmark_suite() -> BenchmarkSuite:
    """Get the standard benchmark suite for Cat-Scan queries."""
    suite = BenchmarkSuite(name="Cat-Scan Standard Benchmarks")

    # Fast queries - should complete in <50ms
    suite.add_query(
        name="creative_lookup_by_id",
        query="SELECT * FROM creatives WHERE id = '12345'",
        category="fast",
    )

    suite.add_query(
        name="creative_count",
        query="SELECT COUNT(*) FROM creatives",
        category="fast",
    )

    # Medium queries - should complete in <200ms
    suite.add_query(
        name="creatives_by_format",
        query="SELECT format, COUNT(*) as count FROM creatives GROUP BY format",
        category="medium",
    )

    suite.add_query(
        name="rtb_daily_recent",
        query="""
            SELECT creative_id, SUM(impressions) as total_impressions,
                   SUM(spend_micros) as total_spend
            FROM rtb_daily
            WHERE metric_date >= date('now', '-7 days')
            GROUP BY creative_id
            LIMIT 100
        """,
        category="medium",
    )

    suite.add_query(
        name="performance_by_country",
        query="""
            SELECT country, COUNT(*) as rows, SUM(impressions) as impressions
            FROM rtb_daily
            WHERE metric_date >= date('now', '-7 days')
            GROUP BY country
            ORDER BY impressions DESC
            LIMIT 20
        """,
        category="medium",
    )

    suite.add_query(
        name="performance_by_size",
        query="""
            SELECT creative_size,
                   COUNT(*) as rows,
                   SUM(reached_queries) as reached,
                   SUM(impressions) as impressions,
                   SUM(spend_micros) as spend
            FROM rtb_daily
            WHERE metric_date >= date('now', '-7 days')
            GROUP BY creative_size
            ORDER BY reached DESC
        """,
        category="medium",
    )

    # Slow queries - should complete in <1000ms
    suite.add_query(
        name="creative_performance_join",
        query="""
            SELECT c.id, c.format, c.creative_status,
                   SUM(p.impressions) as total_impressions,
                   SUM(p.spend_micros) as total_spend
            FROM creatives c
            LEFT JOIN rtb_daily p ON c.id = p.creative_id
            WHERE p.metric_date >= date('now', '-7 days')
            GROUP BY c.id
            ORDER BY total_spend DESC
            LIMIT 50
        """,
        category="slow",
    )

    suite.add_query(
        name="waste_signal_analysis",
        query="""
            SELECT ws.creative_id, ws.signal_type, ws.confidence,
                   c.format, c.creative_status
            FROM waste_signals ws
            JOIN creatives c ON ws.creative_id = c.id
            WHERE ws.resolved_at IS NULL
            ORDER BY ws.detected_at DESC
            LIMIT 100
        """,
        category="slow",
    )

    # Report queries - should complete in <5000ms
    suite.add_query(
        name="full_waste_report",
        query="""
            SELECT
                p.creative_size,
                COUNT(DISTINCT p.creative_id) as creative_count,
                SUM(p.reached_queries) as total_reached,
                SUM(p.impressions) as total_impressions,
                SUM(p.spend_micros) as total_spend,
                CASE
                    WHEN SUM(p.reached_queries) > 0
                    THEN ROUND((SUM(p.reached_queries) - SUM(p.impressions)) * 100.0 / SUM(p.reached_queries), 2)
                    ELSE 0
                END as waste_pct
            FROM rtb_daily p
            WHERE p.metric_date >= date('now', '-7 days')
            GROUP BY p.creative_size
            ORDER BY total_reached DESC
        """,
        category="report",
    )

    return suite


def print_profile_report(profiles: List[QueryProfile], verbose: bool = False):
    """Print a formatted report of query profiles."""
    print("\n" + "=" * 80)
    print("QUERY PERFORMANCE REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().isoformat()}")
    print()

    passed = sum(1 for p in profiles if p.passed)
    total = len(profiles)

    print(f"Summary: {passed}/{total} queries passed performance targets")
    print()

    # Group by category
    by_category = {}
    for p in profiles:
        by_category.setdefault(p.target_category, []).append(p)

    for category in ["fast", "medium", "slow", "report"]:
        if category not in by_category:
            continue

        print(f"\n{category.upper()} Queries (target: {QUERY_TARGETS[category]}ms)")
        print("-" * 60)

        for p in by_category[category]:
            status = "PASS" if p.passed else "FAIL"
            print(f"  [{status}] {p.name}")
            print(f"         Mean: {p.mean_ms:.2f}ms | "
                  f"Min: {p.min_ms:.2f}ms | "
                  f"Max: {p.max_ms:.2f}ms | "
                  f"Rows: {p.row_count}")

            if verbose:
                print(f"         Query: {p.query[:60]}...")

        print()

    # Summary statistics
    all_times = [p.mean_ms for p in profiles]
    print("-" * 60)
    print("Overall Statistics:")
    print(f"  Total queries: {len(profiles)}")
    print(f"  Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"  Average time: {statistics.mean(all_times):.2f}ms")
    print(f"  Median time: {statistics.median(all_times):.2f}ms")
    if profiles:
        slowest = max(profiles, key=lambda p: p.mean_ms)
        print(f"  Slowest: {slowest.name} ({slowest.mean_ms:.2f}ms)")
    print("=" * 80)


def cmd_profile(args):
    """Profile a single query."""
    profiler = QueryProfiler()

    try:
        profile = profiler.profile_query(
            query=args.query,
            name="manual_query",
            executions=args.executions,
            category=args.category,
        )

        print("\n" + "=" * 60)
        print("QUERY PROFILE")
        print("=" * 60)
        print(f"Query: {profile.query}")
        print(f"Executions: {profile.executions}")
        print(f"Category: {profile.target_category} (target: {QUERY_TARGETS[profile.target_category]}ms)")
        print()
        print(f"Results:")
        print(f"  Min:    {profile.min_ms:.2f}ms")
        print(f"  Max:    {profile.max_ms:.2f}ms")
        print(f"  Mean:   {profile.mean_ms:.2f}ms")
        print(f"  Median: {profile.median_ms:.2f}ms")
        print(f"  StdDev: {profile.std_dev_ms:.2f}ms")
        print(f"  Rows:   {profile.row_count}")
        print()

        status = "PASSED" if profile.passed else "FAILED"
        print(f"Status: {status}")
        print("=" * 60)

        # Get explain plan
        print("\nEXPLAIN QUERY PLAN:")
        plan = profiler.get_explain_plan(args.query)
        for row in plan:
            print(f"  {row}")

    finally:
        profiler.close()


def cmd_benchmark(args):
    """Run the benchmark suite."""
    profiler = QueryProfiler()

    try:
        suite = get_standard_benchmark_suite()
        profiles = profiler.run_benchmark(suite, executions=args.executions)
        print_profile_report(profiles, verbose=args.verbose)

        # Exit with error code if any tests failed
        if not all(p.passed for p in profiles):
            sys.exit(1)
    finally:
        profiler.close()


def cmd_report(args):
    """Generate a JSON report."""
    profiler = QueryProfiler()

    try:
        suite = get_standard_benchmark_suite()
        profiles = profiler.run_benchmark(suite, executions=args.executions)

        report = {
            "generated_at": datetime.now().isoformat(),
            "db_path": profiler.db_path,
            "summary": {
                "total": len(profiles),
                "passed": sum(1 for p in profiles if p.passed),
                "failed": sum(1 for p in profiles if not p.passed),
            },
            "profiles": [p.to_dict() for p in profiles],
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report written to: {args.output}")
        else:
            print(json.dumps(report, indent=2))

    finally:
        profiler.close()


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Query Performance Framework for Cat-Scan"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # profile command
    profile_parser = subparsers.add_parser("profile", help="Profile a single query")
    profile_parser.add_argument("query", help="SQL query to profile")
    profile_parser.add_argument("--executions", "-n", type=int, default=5,
                               help="Number of executions (default: 5)")
    profile_parser.add_argument("--category", "-c", default="medium",
                               choices=["fast", "medium", "slow", "report"],
                               help="Target category (default: medium)")
    profile_parser.set_defaults(func=cmd_profile)

    # benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run benchmark suite")
    bench_parser.add_argument("--executions", "-n", type=int, default=5,
                             help="Number of executions per query (default: 5)")
    bench_parser.add_argument("--verbose", "-v", action="store_true",
                             help="Show verbose output")
    bench_parser.set_defaults(func=cmd_benchmark)

    # report command
    report_parser = subparsers.add_parser("report", help="Generate JSON report")
    report_parser.add_argument("--output", "-o", help="Output file path")
    report_parser.add_argument("--executions", "-n", type=int, default=5,
                              help="Number of executions per query (default: 5)")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


# Pytest test functions - only import when running tests
# These are loaded conditionally to allow CLI use without pytest
try:
    import pytest

    @pytest.fixture
    def profiler():
        """Create a profiler instance for testing."""
        p = QueryProfiler()
        yield p
        p.close()


    class TestQueryProfiler:
        """Tests for the QueryProfiler class."""

        def test_execute_simple_query(self, profiler):
            """Test executing a simple query."""
            result = profiler.execute_query("SELECT 1 as value")
            assert result.success
            assert result.row_count == 1
            assert result.execution_time_ms >= 0

        def test_execute_invalid_query(self, profiler):
            """Test handling of invalid queries."""
            result = profiler.execute_query("SELECT * FROM nonexistent_table")
            assert not result.success
            assert result.error is not None

        def test_profile_query(self, profiler):
            """Test profiling a query."""
            profile = profiler.profile_query(
                query="SELECT 1 as value",
                name="test_query",
                executions=3,
                category="fast",
            )
            assert profile.executions == 3
            assert profile.min_ms <= profile.mean_ms <= profile.max_ms
            assert profile.row_count == 1

        def test_profile_to_dict(self, profiler):
            """Test converting profile to dictionary."""
            profile = profiler.profile_query(
                query="SELECT 1 as value",
                name="test_query",
                executions=3,
                category="fast",
            )
            d = profile.to_dict()
            assert "name" in d
            assert "mean_ms" in d
            assert "passed" in d


    class TestBenchmarkSuite:
        """Tests for the BenchmarkSuite class."""

        def test_create_suite(self):
            """Test creating a benchmark suite."""
            suite = BenchmarkSuite(name="Test Suite")
            assert suite.name == "Test Suite"
            assert len(suite.queries) == 0

        def test_add_query(self):
            """Test adding queries to a suite."""
            suite = BenchmarkSuite(name="Test Suite")
            suite.add_query("test", "SELECT 1", "fast")
            assert len(suite.queries) == 1
            assert suite.queries[0]["name"] == "test"

        def test_standard_suite_exists(self):
            """Test that standard benchmark suite has queries."""
            suite = get_standard_benchmark_suite()
            assert len(suite.queries) > 0

except ImportError:
    # pytest not installed - skip test definitions
    pass


if __name__ == "__main__":
    main()
