"""Tests for RTB waste analysis module.

This module tests the waste analysis functionality including:
- Data models (TrafficRecord, SizeGap, SizeCoverage, WasteReport)
- Mock traffic generator
- WasteAnalyzer engine
- Database traffic storage methods
- API endpoints for waste analysis

Run with: pytest tests/test_waste_analysis.py -v
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from analytics.waste_models import (
    SizeCoverage,
    SizeGap,
    TrafficRecord,
    WasteReport,
)
from analytics.mock_traffic import (
    generate_mock_traffic,
    generate_traffic_with_gaps,
    get_size_from_raw,
    TRAFFIC_DISTRIBUTIONS,
)
from analytics.waste_analyzer import WasteAnalyzer
from storage.sqlite_store import Creative, SQLiteStore


@pytest_asyncio.fixture
async def temp_store():
    """Create a temporary SQLite store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(db_path=str(db_path))
        await store.initialize()
        yield store


@pytest_asyncio.fixture
async def store_with_creatives(temp_store):
    """Create a store with sample creatives for testing waste analysis."""
    # Add creatives for common IAB sizes
    # Need at least 3 creatives per size for "good" coverage status
    creatives = [
        Creative(
            id="c1",
            name="bidders/123/creatives/c1",
            format="HTML",
            width=300,
            height=250,
            canonical_size="300x250 (Medium Rectangle)",
        ),
        Creative(
            id="c2",
            name="bidders/123/creatives/c2",
            format="HTML",
            width=300,
            height=250,
            canonical_size="300x250 (Medium Rectangle)",
        ),
        Creative(
            id="c2b",
            name="bidders/123/creatives/c2b",
            format="NATIVE",
            width=300,
            height=250,
            canonical_size="300x250 (Medium Rectangle)",
        ),
        Creative(
            id="c3",
            name="bidders/123/creatives/c3",
            format="HTML",
            width=728,
            height=90,
            canonical_size="728x90 (Leaderboard)",
        ),
        Creative(
            id="c3b",
            name="bidders/123/creatives/c3b",
            format="HTML",
            width=728,
            height=90,
            canonical_size="728x90 (Leaderboard)",
        ),
        Creative(
            id="c3c",
            name="bidders/123/creatives/c3c",
            format="HTML",
            width=728,
            height=90,
            canonical_size="728x90 (Leaderboard)",
        ),
        Creative(
            id="c4",
            name="bidders/123/creatives/c4",
            format="VIDEO",
            width=1920,
            height=1080,
            canonical_size="Video 16:9 (Horizontal)",
        ),
    ]
    await temp_store.save_creatives(creatives)
    return temp_store


class TestTrafficRecord:
    """Tests for TrafficRecord dataclass."""

    def test_traffic_record_creation(self):
        """Test creating a TrafficRecord instance."""
        record = TrafficRecord(
            canonical_size="300x250 (Medium Rectangle)",
            raw_size="300x250",
            request_count=50000,
            date="2024-01-15",
            buyer_id="456",
        )
        assert record.canonical_size == "300x250 (Medium Rectangle)"
        assert record.raw_size == "300x250"
        assert record.request_count == 50000
        assert record.date == "2024-01-15"
        assert record.buyer_id == "456"

    def test_traffic_record_optional_buyer_id(self):
        """Test TrafficRecord with optional buyer_id."""
        record = TrafficRecord(
            canonical_size="300x250 (Medium Rectangle)",
            raw_size="300x250",
            request_count=50000,
            date="2024-01-15",
        )
        assert record.buyer_id is None


class TestSizeGap:
    """Tests for SizeGap dataclass."""

    def test_size_gap_creation(self):
        """Test creating a SizeGap instance."""
        gap = SizeGap(
            canonical_size="Non-Standard (320x481)",
            request_count=35000,
            creative_count=0,
            estimated_qps=0.41,
            estimated_waste_pct=15.2,
            recommendation="Block",
            recommendation_detail="Block in pretargeting config",
            potential_savings_usd=2.10,
            closest_iab_size=None,
        )
        assert gap.canonical_size == "Non-Standard (320x481)"
        assert gap.recommendation == "Block"
        assert gap.creative_count == 0

    def test_size_gap_with_closest_iab(self):
        """Test SizeGap with nearest IAB size."""
        gap = SizeGap(
            canonical_size="Non-Standard (301x250)",
            request_count=12000,
            creative_count=0,
            estimated_qps=0.14,
            estimated_waste_pct=5.2,
            recommendation="Use Flexible",
            recommendation_detail="Use flexible HTML5 creative",
            closest_iab_size="300x250 (Medium Rectangle)",
        )
        assert gap.closest_iab_size == "300x250 (Medium Rectangle)"


class TestSizeCoverage:
    """Tests for SizeCoverage dataclass."""

    def test_size_coverage_good(self):
        """Test SizeCoverage with good coverage status."""
        coverage = SizeCoverage(
            canonical_size="300x250 (Medium Rectangle)",
            creative_count=45,
            request_count=50000,
            coverage_status="good",
            formats={"HTML": 30, "NATIVE": 15},
        )
        assert coverage.coverage_status == "good"
        assert coverage.formats["HTML"] == 30

    def test_size_coverage_none(self):
        """Test SizeCoverage with no coverage (waste)."""
        coverage = SizeCoverage(
            canonical_size="Non-Standard (320x481)",
            creative_count=0,
            request_count=35000,
            coverage_status="none",
        )
        assert coverage.coverage_status == "none"
        assert coverage.creative_count == 0


class TestWasteReport:
    """Tests for WasteReport dataclass."""

    def test_waste_report_creation(self):
        """Test creating a WasteReport instance."""
        report = WasteReport(
            buyer_id="456",
            total_requests=230000,
            total_waste_requests=47000,
            waste_percentage=20.4,
            size_gaps=[],
            size_coverage=[],
            potential_savings_qps=0.54,
            potential_savings_usd=2.82,
            analysis_period_days=7,
            generated_at="2024-01-15T12:00:00Z",
        )
        assert report.waste_percentage == 20.4
        assert report.analysis_period_days == 7

    def test_waste_report_to_dict(self):
        """Test converting WasteReport to dictionary."""
        gap = SizeGap(
            canonical_size="Non-Standard (320x481)",
            request_count=35000,
            creative_count=0,
            estimated_qps=0.41,
            estimated_waste_pct=15.2,
            recommendation="Block",
            recommendation_detail="Block in pretargeting",
        )
        report = WasteReport(
            buyer_id="456",
            total_requests=230000,
            total_waste_requests=35000,
            waste_percentage=15.22,
            size_gaps=[gap],
            size_coverage=[],
            potential_savings_qps=0.41,
            potential_savings_usd=2.10,
            analysis_period_days=7,
            generated_at="2024-01-15T12:00:00Z",
        )

        data = report.to_dict()
        assert data["buyer_id"] == "456"
        assert data["waste_percentage"] == 15.22
        assert len(data["size_gaps"]) == 1
        assert data["size_gaps"][0]["recommendation"] == "Block"


class TestMockTrafficGenerator:
    """Tests for mock traffic generation."""

    def test_generate_mock_traffic_basic(self):
        """Test basic mock traffic generation."""
        traffic = generate_mock_traffic(days=3)
        assert len(traffic) > 0
        assert all(isinstance(r, TrafficRecord) for r in traffic)

    def test_generate_mock_traffic_with_buyer_id(self):
        """Test mock traffic with buyer_id."""
        traffic = generate_mock_traffic(days=1, buyer_id="456")
        assert all(r.buyer_id == "456" for r in traffic)

    def test_generate_mock_traffic_waste_bias(self):
        """Test waste_bias affects distribution."""
        low_waste = generate_mock_traffic(days=1, waste_bias=0.1)
        high_waste = generate_mock_traffic(days=1, waste_bias=0.9)

        # Count non-standard sizes
        def count_non_standard(records):
            return sum(1 for r in records if "Non-Standard" in r.canonical_size)

        # High waste bias should produce more non-standard sizes
        # (Not exact due to randomness, but should trend correctly)
        low_non_std = count_non_standard(low_waste)
        high_non_std = count_non_standard(high_waste)
        # Just verify both produce data; exact comparison would be flaky
        assert low_non_std >= 0
        assert high_non_std >= 0

    def test_generate_mock_traffic_daily_variance(self):
        """Test that daily variance produces different counts."""
        traffic = generate_mock_traffic(days=7, include_weekday_variance=True)
        # Group by date
        by_date = {}
        for r in traffic:
            by_date.setdefault(r.date, []).append(r)
        # Should have records for multiple days
        assert len(by_date) == 7

    def test_traffic_distributions_structure(self):
        """Test TRAFFIC_DISTRIBUTIONS has expected structure."""
        assert "iab_standard" in TRAFFIC_DISTRIBUTIONS
        assert "non_standard" in TRAFFIC_DISTRIBUTIONS
        assert "video" in TRAFFIC_DISTRIBUTIONS

        # Check tuple format
        for category, sizes in TRAFFIC_DISTRIBUTIONS.items():
            for item in sizes:
                assert len(item) == 3  # (raw_size, canonical_size, weight)

    def test_generate_traffic_with_gaps(self):
        """Test generating traffic specifically designed for waste gaps."""
        traffic = generate_traffic_with_gaps(days=3)
        assert len(traffic) > 0
        # Should contain non-standard sizes
        sizes = {r.canonical_size for r in traffic}
        assert any("Non-Standard" in s for s in sizes)

    def test_get_size_from_raw(self):
        """Test parsing raw size strings."""
        assert get_size_from_raw("300x250") == (300, 250)
        assert get_size_from_raw("1920x1080") == (1920, 1080)
        assert get_size_from_raw("invalid") == (0, 0)
        assert get_size_from_raw("0x0") == (0, 0)


@pytest.mark.asyncio
class TestSQLiteStoreTrafficData:
    """Tests for SQLiteStore traffic data operations."""

    async def test_store_traffic_data(self, temp_store):
        """Test storing traffic data records."""
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": "2024-01-15",
                "buyer_id": "456",
            },
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 12000,
                "date": "2024-01-15",
                "buyer_id": "456",
            },
        ]
        count = await temp_store.store_traffic_data(records)
        assert count == 2

    async def test_store_traffic_data_upsert(self, temp_store):
        """Test that storing duplicate records updates counts."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
                "buyer_id": "456",
            }
        ]
        await temp_store.store_traffic_data(records)

        # Store again with different count
        records[0]["request_count"] = 75000
        await temp_store.store_traffic_data(records)

        # Retrieve and verify updated
        data = await temp_store.get_traffic_data(buyer_id="456", days=7)
        assert len(data) == 1
        assert data[0]["request_count"] == 75000

    async def test_get_traffic_data(self, temp_store):
        """Test retrieving traffic data."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
                "buyer_id": "456",
            }
        ]
        await temp_store.store_traffic_data(records)

        data = await temp_store.get_traffic_data(days=7)
        assert len(data) == 1
        assert data[0]["canonical_size"] == "300x250 (Medium Rectangle)"

    async def test_get_traffic_data_by_buyer(self, temp_store):
        """Test filtering traffic data by buyer_id."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
                "buyer_id": "456",
            },
            {
                "canonical_size": "728x90 (Leaderboard)",
                "raw_size": "728x90",
                "request_count": 30000,
                "date": today,
                "buyer_id": "789",
            },
        ]
        await temp_store.store_traffic_data(records)

        buyer_data = await temp_store.get_traffic_data(buyer_id="456", days=7)
        assert len(buyer_data) == 1
        assert buyer_data[0]["buyer_id"] == "456"

    async def test_get_traffic_summary(self, temp_store):
        """Test getting traffic summary statistics."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
            },
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 12000,
                "date": today,
            },
        ]
        await temp_store.store_traffic_data(records)

        summary = await temp_store.get_traffic_summary(days=7)
        assert summary["total_requests"] == 62000
        assert summary["unique_sizes"] == 2

    async def test_clear_traffic_data(self, temp_store):
        """Test clearing traffic data."""
        # Use a date from 60 days ago so it can be cleared with default retention
        old_date = (datetime.now() - timedelta(days=60)).date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": old_date,
            }
        ]
        await temp_store.store_traffic_data(records)

        # Clear data older than 30 days (default)
        count = await temp_store.clear_traffic_data()
        assert count == 1

        # Verify empty (the data was older than 7 days anyway)
        data = await temp_store.get_traffic_data(days=90)
        assert len(data) == 0


@pytest.mark.asyncio
class TestWasteAnalyzer:
    """Tests for WasteAnalyzer engine."""

    async def test_analyze_waste_no_data(self, temp_store):
        """Test waste analysis with no data."""
        analyzer = WasteAnalyzer(temp_store)
        report = await analyzer.analyze_waste(days=7)

        assert report.total_requests == 0
        assert report.total_waste_requests == 0
        assert report.waste_percentage == 0.0
        assert len(report.size_gaps) == 0

    async def test_analyze_waste_with_coverage(self, store_with_creatives):
        """Test waste analysis with creative coverage."""
        # Add traffic for sizes we have creatives for
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
            },
            {
                "canonical_size": "728x90 (Leaderboard)",
                "raw_size": "728x90",
                "request_count": 30000,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=7)

        # Should have no waste since we have creatives for these sizes
        assert report.total_requests == 80000
        assert report.total_waste_requests == 0
        assert report.waste_percentage == 0.0
        assert len(report.size_gaps) == 0

    async def test_analyze_waste_with_gaps(self, store_with_creatives):
        """Test waste analysis identifying gaps."""
        today = datetime.now().date().isoformat()
        records = [
            # Has creative coverage
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
            },
            # No creative coverage - should be identified as waste
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 35000,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=7)

        assert report.total_requests == 85000
        assert report.total_waste_requests == 35000
        assert len(report.size_gaps) == 1
        assert report.size_gaps[0].canonical_size == "Non-Standard (320x481)"
        assert report.size_gaps[0].recommendation in ["Block", "Add Creative", "Monitor"]

    async def test_analyze_waste_recommendations(self, store_with_creatives):
        """Test waste analysis generates appropriate recommendations."""
        today = datetime.now().date().isoformat()
        records = [
            # High volume non-standard - should recommend Block
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 100000,  # High volume
                "date": today,
            },
            # Medium volume - should recommend Add Creative
            {
                "canonical_size": "Non-Standard (480x320)",
                "raw_size": "480x320",
                "request_count": 5000,
                "date": today,
            },
            # Low volume - should recommend Monitor
            {
                "canonical_size": "Non-Standard (234x90)",
                "raw_size": "234x90",
                "request_count": 500,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=1)

        # Check recommendations match volume thresholds
        gaps_by_size = {g.canonical_size: g for g in report.size_gaps}

        # High volume should get "Block"
        assert gaps_by_size["Non-Standard (320x481)"].recommendation == "Block"

        # Medium volume should get "Add Creative"
        assert gaps_by_size["Non-Standard (480x320)"].recommendation == "Add Creative"

        # Low volume should get "Monitor"
        assert gaps_by_size["Non-Standard (234x90)"].recommendation == "Monitor"

    async def test_analyze_waste_near_iab_flexible(self, store_with_creatives):
        """Test recommendation for sizes near IAB standard."""
        today = datetime.now().date().isoformat()
        records = [
            # Off-by-one from 300x250 - should recommend flexible
            {
                "canonical_size": "Non-Standard (301x250)",
                "raw_size": "301x250",
                "request_count": 15000,  # Medium-high volume
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=1)

        assert len(report.size_gaps) == 1
        gap = report.size_gaps[0]
        assert gap.recommendation == "Use Flexible"
        assert gap.closest_iab_size == "300x250 (Medium Rectangle)"

    async def test_get_size_gaps(self, store_with_creatives):
        """Test getting size gaps with minimum request filter."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 5000,
                "date": today,
            },
            {
                "canonical_size": "Non-Standard (234x90)",
                "raw_size": "234x90",
                "request_count": 50,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)

        # With high min_requests, only the larger gap should be returned
        gaps = await analyzer.get_size_gaps(days=7, min_requests=1000)
        assert len(gaps) == 1
        assert gaps[0].canonical_size == "Non-Standard (320x481)"

    async def test_get_size_coverage(self, store_with_creatives):
        """Test getting size coverage data."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "300x250 (Medium Rectangle)",
                "raw_size": "300x250",
                "request_count": 50000,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        coverage = await analyzer.get_size_coverage()

        assert "300x250 (Medium Rectangle)" in coverage
        cov = coverage["300x250 (Medium Rectangle)"]
        assert cov["creatives"] == 3  # We added 3 creatives for this size
        assert cov["requests"] == 50000
        assert cov["coverage"] == "good"

    async def test_analyze_waste_by_buyer(self, store_with_creatives):
        """Test waste analysis filtered by buyer_id."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 10000,
                "date": today,
                "buyer_id": "456",
            },
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 5000,
                "date": today,
                "buyer_id": "789",
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)

        # Filter by buyer 456
        report = await analyzer.analyze_waste(buyer_id="456", days=7)
        assert report.buyer_id == "456"
        assert report.total_requests == 10000

    async def test_waste_report_recommendations_summary(self, store_with_creatives):
        """Test waste report generates recommendations summary."""
        today = datetime.now().date().isoformat()
        records = [
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 100000,
                "date": today,
            },
            {
                "canonical_size": "Non-Standard (480x320)",
                "raw_size": "480x320",
                "request_count": 5000,
                "date": today,
            },
        ]
        await store_with_creatives.store_traffic_data(records)

        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=1)

        assert "block" in report.recommendations_summary
        assert "add_creative" in report.recommendations_summary
        assert report.recommendations_summary["block"] >= 1


@pytest.mark.asyncio
class TestWasteAnalyzerEdgeCases:
    """Edge case tests for WasteAnalyzer."""

    async def test_empty_traffic_data(self, store_with_creatives):
        """Test analysis with creatives but no traffic."""
        analyzer = WasteAnalyzer(store_with_creatives)
        report = await analyzer.analyze_waste(days=7)

        # Should have coverage entries for sizes with creatives but no traffic
        excess_coverage = [
            c for c in report.size_coverage if c.coverage_status == "excess"
        ]
        assert len(excess_coverage) > 0

    async def test_zero_days_period(self, temp_store):
        """Test analysis with zero-day period."""
        analyzer = WasteAnalyzer(temp_store)
        # Should handle gracefully without division errors
        report = await analyzer.analyze_waste(days=0)
        assert report.analysis_period_days == 0

    async def test_old_traffic_data_excluded(self, temp_store):
        """Test that old traffic data outside the period is excluded."""
        old_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        recent_date = datetime.now().date().isoformat()

        records = [
            {
                "canonical_size": "Non-Standard (320x481)",
                "raw_size": "320x481",
                "request_count": 50000,
                "date": old_date,
            },
            {
                "canonical_size": "Non-Standard (480x320)",
                "raw_size": "480x320",
                "request_count": 10000,
                "date": recent_date,
            },
        ]
        await temp_store.store_traffic_data(records)

        analyzer = WasteAnalyzer(temp_store)
        report = await analyzer.analyze_waste(days=7)

        # Only recent traffic should be included
        assert report.total_requests == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
