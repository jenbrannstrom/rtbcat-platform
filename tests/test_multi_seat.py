"""Tests for multi-seat buyer account support.

This module tests the buyer seats functionality including:
- Database schema migrations
- BuyerSeatsClient operations
- PostgresStore buyer seat methods
- API endpoints for seat management

Run with: pytest tests/test_multi_seat.py -v
"""

import os
import uuid
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from storage import BuyerSeat, Creative, PostgresStore


@pytest_asyncio.fixture
async def temp_store():
    """Create a Postgres store for testing (skips if DSN not set)."""
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        pytest.skip("POSTGRES_DSN or DATABASE_URL not set; skipping PostgresStore tests.")
    store = PostgresStore()
    await store.initialize()
    yield store


def _test_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


class TestBuyerSeatDataclass:
    """Tests for the BuyerSeat dataclass."""

    def test_buyer_seat_creation(self):
        """Test creating a BuyerSeat instance."""
        seat = BuyerSeat(
            buyer_id="456",
            bidder_id="123",
            display_name="Test Buyer",
            active=True,
            creative_count=10,
        )
        assert seat.buyer_id == "456"
        assert seat.bidder_id == "123"
        assert seat.display_name == "Test Buyer"
        assert seat.active is True
        assert seat.creative_count == 10

    def test_buyer_seat_defaults(self):
        """Test BuyerSeat default values."""
        seat = BuyerSeat(buyer_id="456", bidder_id="123")
        assert seat.display_name is None
        assert seat.active is True
        assert seat.creative_count == 0
        assert seat.last_synced is None
        assert seat.created_at is None


class TestCreativeWithBuyerId:
    """Tests for Creative dataclass with buyer_id field."""

    def test_creative_with_buyer_id(self):
        """Test creating a Creative with buyer_id."""
        creative = Creative(
            id="abc123",
            name="bidders/123/creatives/abc123",
            format="HTML",
            account_id="123",
            buyer_id="456",
        )
        assert creative.buyer_id == "456"

    def test_creative_without_buyer_id(self):
        """Test Creative defaults to None buyer_id."""
        creative = Creative(
            id="abc123",
            name="bidders/123/creatives/abc123",
            format="HTML",
        )
        assert creative.buyer_id is None


@pytest.mark.asyncio
class TestPostgresStoreBuyerSeats:
    """Tests for PostgresStore buyer seat operations."""

    async def test_save_buyer_seat(self, temp_store):
        """Test saving a buyer seat."""
        seat = BuyerSeat(
            buyer_id=_test_id("buyer"),
            bidder_id=_test_id("bidder"),
            display_name="Test Buyer",
            active=True,
        )
        await temp_store.save_buyer_seat(seat)

        # Retrieve and verify
        retrieved = await temp_store.get_buyer_seat(seat.buyer_id)
        assert retrieved is not None
        assert retrieved.buyer_id == seat.buyer_id
        assert retrieved.bidder_id == seat.bidder_id
        assert retrieved.display_name == "Test Buyer"

    async def test_save_buyer_seat_update(self, temp_store):
        """Test updating an existing buyer seat."""
        seat = BuyerSeat(
            buyer_id=_test_id("buyer"),
            bidder_id=_test_id("bidder"),
            display_name="Original Name",
        )
        await temp_store.save_buyer_seat(seat)

        # Update
        seat.display_name = "Updated Name"
        await temp_store.save_buyer_seat(seat)

        retrieved = await temp_store.get_buyer_seat(seat.buyer_id)
        assert retrieved.display_name == "Updated Name"

    async def test_get_buyer_seats_all(self, temp_store):
        """Test getting all buyer seats."""
        bidder_id = _test_id("bidder")
        seats = [
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, display_name="Buyer 1"),
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, display_name="Buyer 2"),
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=_test_id("bidder"), display_name="Buyer 3"),
        ]
        for seat in seats:
            await temp_store.save_buyer_seat(seat)

        all_seats = await temp_store.get_buyer_seats()
        assert len(all_seats) == 3

    async def test_get_buyer_seats_by_bidder(self, temp_store):
        """Test filtering buyer seats by bidder_id."""
        bidder_id = _test_id("bidder")
        seats = [
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, display_name="Buyer 1"),
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, display_name="Buyer 2"),
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=_test_id("bidder"), display_name="Buyer 3"),
        ]
        for seat in seats:
            await temp_store.save_buyer_seat(seat)

        bidder_seats = await temp_store.get_buyer_seats(bidder_id=bidder_id)
        assert len(bidder_seats) == 2

    async def test_get_buyer_seats_active_only(self, temp_store):
        """Test filtering active buyer seats."""
        bidder_id = _test_id("bidder")
        seats = [
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, active=True),
            BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=bidder_id, active=False),
        ]
        for seat in seats:
            await temp_store.save_buyer_seat(seat)

        active_seats = await temp_store.get_buyer_seats(active_only=True)
        assert len(active_seats) == 1
        assert active_seats[0].buyer_id == seats[0].buyer_id

    async def test_get_buyer_seat_not_found(self, temp_store):
        """Test getting a non-existent buyer seat."""
        seat = await temp_store.get_buyer_seat("nonexistent")
        assert seat is None

    async def test_update_seat_creative_count(self, temp_store):
        """Test updating creative count for a seat."""
        # Create seat
        seat = BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=_test_id("bidder"))
        await temp_store.save_buyer_seat(seat)

        # Add creatives with this buyer_id
        creatives = [
            Creative(
                id=_test_id(f"c{i}"),
                name=f"bidders/{seat.bidder_id}/creatives/{i}",
                format="HTML",
                buyer_id=seat.buyer_id,
            )
            for i in range(5)
        ]
        await temp_store.save_creatives(creatives)

        # Update count
        count = await temp_store.update_seat_creative_count(seat.buyer_id)
        assert count == 5

        # Verify
        updated_seat = await temp_store.get_buyer_seat(seat.buyer_id)
        assert updated_seat.creative_count == 5

    async def test_update_seat_sync_time(self, temp_store):
        """Test updating sync time for a seat."""
        seat = BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=_test_id("bidder"))
        await temp_store.save_buyer_seat(seat)

        # Initially no sync time
        initial = await temp_store.get_buyer_seat(seat.buyer_id)
        assert initial.last_synced is None

        # Update sync time
        await temp_store.update_seat_sync_time(seat.buyer_id)

        # Verify
        updated = await temp_store.get_buyer_seat(seat.buyer_id)
        assert updated.last_synced is not None


@pytest.mark.asyncio
class TestPostgresStoreCreativesWithBuyerId:
    """Tests for creative operations with buyer_id support."""

    async def test_save_creative_with_buyer_id(self, temp_store):
        """Test saving a creative with buyer_id."""
        buyer_id = _test_id("buyer")
        creative = Creative(
            id=_test_id("creative"),
            name=f"bidders/{_test_id('bidder')}/creatives/abc123",
            format="HTML",
            account_id="123",
            buyer_id=buyer_id,
        )
        await temp_store.save_creatives([creative])

        retrieved = await temp_store.get_creative(creative.id)
        assert retrieved.buyer_id == buyer_id

    async def test_list_creatives_by_buyer_id(self, temp_store):
        """Test filtering creatives by buyer_id."""
        buyer_a = _test_id("buyer")
        buyer_b = _test_id("buyer")
        creatives = [
            Creative(
                id=_test_id("c1"),
                name=f"bidders/{_test_id('bidder')}/creatives/c1",
                format="HTML",
                buyer_id=buyer_a,
            ),
            Creative(
                id=_test_id("c2"),
                name=f"bidders/{_test_id('bidder')}/creatives/c2",
                format="HTML",
                buyer_id=buyer_a,
            ),
            Creative(
                id=_test_id("c3"),
                name=f"bidders/{_test_id('bidder')}/creatives/c3",
                format="HTML",
                buyer_id=buyer_b,
            ),
        ]
        await temp_store.save_creatives(creatives)

        buyer_creatives = await temp_store.list_creatives(buyer_id=buyer_a)
        assert len(buyer_creatives) == 2

        other_creatives = await temp_store.list_creatives(buyer_id=buyer_b)
        assert len(other_creatives) == 1


class TestBuyerSeatsClient:
    """Tests for BuyerSeatsClient (mocked API calls)."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock Google API service."""
        service = MagicMock()
        return service

    def test_parse_buyer_response(self):
        """Test parsing buyer API response."""
        from collectors.seats import BuyerSeatsClient

        client = BuyerSeatsClient.__new__(BuyerSeatsClient)
        client.account_id = "123"

        data = {
            "name": "buyers/456",
            "displayName": "Test Buyer Account",
            "state": "ACTIVE",
        }

        seat = client._parse_buyer_response(data)
        assert seat.buyer_id == "456"
        assert seat.bidder_id == "123"
        assert seat.display_name == "Test Buyer Account"
        assert seat.active is True

    def test_parse_buyer_response_inactive(self):
        """Test parsing inactive buyer."""
        from collectors.seats import BuyerSeatsClient

        client = BuyerSeatsClient.__new__(BuyerSeatsClient)
        client.account_id = "123"

        data = {
            "name": "buyers/456",
            "displayName": "Inactive Buyer",
            "state": "SUSPENDED",
        }

        seat = client._parse_buyer_response(data)
        assert seat.active is False

    def test_parse_buyer_response_no_display_name(self):
        """Test parsing buyer without display name."""
        from collectors.seats import BuyerSeatsClient

        client = BuyerSeatsClient.__new__(BuyerSeatsClient)
        client.account_id = "123"

        data = {
            "name": "buyers/456",
            "state": "ACTIVE",
        }

        seat = client._parse_buyer_response(data)
        assert seat.display_name == "Buyer 456"


class TestCreativeParserBuyerId:
    """Tests for creative parser with buyer_id support."""

    def test_parse_creative_with_buyer_id(self):
        """Test parsing creative with buyer_id parameter."""
        from collectors.creatives.parsers import parse_creative_response

        data = {
            "name": "bidders/123/creatives/abc",
            "html": {"snippet": "<div></div>", "width": 300, "height": 250},
        }

        result = parse_creative_response(data, "123", buyer_id="456")
        assert result["buyerId"] == "456"
        assert result["accountId"] == "123"

    def test_parse_creative_without_buyer_id(self):
        """Test parsing creative without buyer_id."""
        from collectors.creatives.parsers import parse_creative_response

        data = {
            "name": "bidders/123/creatives/abc",
            "html": {"snippet": "<div></div>", "width": 300, "height": 250},
        }

        result = parse_creative_response(data, "123")
        assert result["buyerId"] is None


class TestStorageAdapter:
    """Tests for storage adapter with buyer_id."""

    def test_creative_dict_to_storage_with_buyer_id(self):
        """Test adapter converts buyerId correctly."""
        from storage.adapters import creative_dict_to_storage

        data = {
            "creativeId": "abc123",
            "creativeName": "bidders/123/creatives/abc123",
            "accountId": "123",
            "buyerId": "456",
            "format": "HTML",
            "html": {"width": 300, "height": 250},
        }

        creative = creative_dict_to_storage(data)
        assert creative.buyer_id == "456"

    def test_creative_dict_to_storage_without_buyer_id(self):
        """Test adapter handles missing buyerId."""
        from storage.adapters import creative_dict_to_storage

        data = {
            "creativeId": "abc123",
            "creativeName": "bidders/123/creatives/abc123",
            "accountId": "123",
            "format": "HTML",
        }

        creative = creative_dict_to_storage(data)
        assert creative.buyer_id is None


@pytest.mark.asyncio
class TestDatabaseMigration:
    """Tests for database schema migrations."""

    async def test_migration_creates_buyer_seats_table(self, temp_store):
        """Test that initialization creates buyer_seats table."""
        # The temp_store fixture already calls initialize()
        # Verify we can perform buyer seat operations
        seat = BuyerSeat(buyer_id=_test_id("buyer"), bidder_id=_test_id("bidder"))
        await temp_store.save_buyer_seat(seat)
        retrieved = await temp_store.get_buyer_seat(seat.buyer_id)
        assert retrieved is not None

    async def test_migration_adds_buyer_id_column(self, temp_store):
        """Test that initialization adds buyer_id column to creatives."""
        creative = Creative(
            id=_test_id("creative"),
            name=f"bidders/{_test_id('bidder')}/creatives/test",
            format="HTML",
            buyer_id=_test_id("buyer"),
        )
        await temp_store.save_creatives([creative])
        retrieved = await temp_store.get_creative(creative.id)
        assert retrieved.buyer_id == creative.buyer_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
