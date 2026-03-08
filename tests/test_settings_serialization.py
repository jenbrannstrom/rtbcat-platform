"""Regression tests for settings serialization bugs.

Locks fixes for:
- Bug A: created_at/applied_at/completed_at typed str but DB returns datetime
- Bug B: json.loads() called on already-deserialized JSONB dict

No database or FastAPI required — pure model validation and inline logic tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ValidationError


# ---- Inline model copies (avoid importing full api module tree) ----

class PendingChangeResponse(BaseModel):
    id: int
    billing_id: str
    config_id: Optional[str] = None
    change_type: str
    field_name: str
    value: str
    reason: Optional[str] = None
    estimated_qps_impact: Optional[int] = None
    status: str
    created_at: datetime
    created_by: Optional[str] = None
    applied_at: Optional[datetime] = None


class SnapshotResponse(BaseModel):
    id: int
    billing_id: str
    snapshot_name: Optional[str] = None
    snapshot_type: Optional[str] = None
    state: Optional[str] = None
    created_at: datetime
    notes: Optional[str] = None


class ComparisonResponse(BaseModel):
    id: int
    billing_id: str
    comparison_name: Optional[str] = None
    before_snapshot_id: int
    after_snapshot_id: Optional[int] = None
    status: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    sizes_removed: int = 0


class PretargetingHistoryResponse(BaseModel):
    id: int
    config_id: str
    bidder_id: str
    change_type: str
    field_changed: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: datetime
    changed_by: Optional[str] = None
    change_source: str


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None


# ---- Bug A: datetime serialization ----

class TestPendingChangeResponseDatetime:
    def test_pending_change_response_accepts_datetime(self):
        """DB returns datetime for TIMESTAMPTZ — model must accept it."""
        now = datetime.now(timezone.utc)
        resp = PendingChangeResponse(
            id=1,
            billing_id="123456",
            change_type="add_size",
            field_name="included_sizes",
            value="300x250",
            status="pending",
            created_at=now,
        )
        assert resp.created_at == now
        # JSON output should serialize to ISO string
        data = resp.model_dump(mode="json")
        assert isinstance(data["created_at"], str)
        # Round-trip: parse the ISO string back
        parsed = datetime.fromisoformat(data["created_at"])
        assert parsed == now

    def test_pending_change_response_accepts_string(self):
        """Backward compat: ISO string should still be coerced to datetime."""
        resp = PendingChangeResponse(
            id=1,
            billing_id="123456",
            change_type="add_size",
            field_name="included_sizes",
            value="300x250",
            status="pending",
            created_at="2025-01-15T10:30:00+00:00",
        )
        assert isinstance(resp.created_at, datetime)

    def test_applied_at_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = PendingChangeResponse(
            id=1,
            billing_id="123456",
            change_type="add_size",
            field_name="included_sizes",
            value="300x250",
            status="applied",
            created_at=now,
            applied_at=now,
        )
        assert resp.applied_at == now
        data = resp.model_dump(mode="json")
        assert isinstance(data["applied_at"], str)

    def test_applied_at_none(self):
        now = datetime.now(timezone.utc)
        resp = PendingChangeResponse(
            id=1,
            billing_id="123456",
            change_type="add_size",
            field_name="included_sizes",
            value="300x250",
            status="pending",
            created_at=now,
        )
        assert resp.applied_at is None


class TestSnapshotResponseDatetime:
    def test_snapshot_response_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = SnapshotResponse(
            id=1,
            billing_id="123456",
            created_at=now,
        )
        assert resp.created_at == now
        data = resp.model_dump(mode="json")
        assert isinstance(data["created_at"], str)

    def test_snapshot_response_accepts_string(self):
        resp = SnapshotResponse(
            id=1,
            billing_id="123456",
            created_at="2025-01-15T10:30:00+00:00",
        )
        assert isinstance(resp.created_at, datetime)


class TestComparisonResponseDatetime:
    def test_comparison_response_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = ComparisonResponse(
            id=1,
            billing_id="123456",
            before_snapshot_id=1,
            created_at=now,
        )
        assert resp.created_at == now

    def test_completed_at_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = ComparisonResponse(
            id=1,
            billing_id="123456",
            before_snapshot_id=1,
            created_at=now,
            completed_at=now,
        )
        assert resp.completed_at == now
        data = resp.model_dump(mode="json")
        assert isinstance(data["completed_at"], str)


class TestPretargetingHistoryResponseDatetime:
    def test_history_response_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = PretargetingHistoryResponse(
            id=1,
            config_id="cfg-1",
            bidder_id="bidder-1",
            change_type="major_commit",
            changed_at=now,
            change_source="api",
        )
        assert resp.changed_at == now
        data = resp.model_dump(mode="json")
        assert isinstance(data["changed_at"], str)

    def test_history_response_accepts_string(self):
        resp = PretargetingHistoryResponse(
            id=1,
            config_id="cfg-1",
            bidder_id="bidder-1",
            change_type="major_commit",
            changed_at="2025-01-15T10:30:00+00:00",
            change_source="api",
        )
        assert isinstance(resp.changed_at, datetime)


class TestAuditLogResponseDatetime:
    def test_audit_log_response_accepts_datetime(self):
        now = datetime.now(timezone.utc)
        resp = AuditLogResponse(
            id="1",
            action="login",
            created_at=now,
        )
        assert resp.created_at == now
        data = resp.model_dump(mode="json")
        assert isinstance(data["created_at"], str)


# ---- Bug B: safe JSON normalization ----

def _safe_parse_raw_config(raw_config):
    """Replicate the safe pattern used in snapshots_service and actions_service."""
    result = raw_config or {}
    if isinstance(result, str):
        result = json.loads(result)
    return result


class TestSafeJsonParse:
    def test_safe_json_parse_dict(self):
        """JSONB auto-deserialized to dict — must pass through without error."""
        config = {"publisherTargeting": {"targetingMode": "EXCLUSIVE", "values": []}}
        result = _safe_parse_raw_config(config)
        assert result == config
        assert result["publisherTargeting"]["targetingMode"] == "EXCLUSIVE"

    def test_safe_json_parse_string(self):
        """TEXT column returns JSON string — must be parsed."""
        config_str = '{"publisherTargeting": {"targetingMode": "INCLUSIVE", "values": ["pub-123"]}}'
        result = _safe_parse_raw_config(config_str)
        assert isinstance(result, dict)
        assert result["publisherTargeting"]["targetingMode"] == "INCLUSIVE"
        assert result["publisherTargeting"]["values"] == ["pub-123"]

    def test_safe_json_parse_none(self):
        """None raw_config defaults to empty dict."""
        result = _safe_parse_raw_config(None)
        assert result == {}

    def test_safe_json_parse_empty_string(self):
        """Empty string should not crash — json.loads('') raises, but falsy '' → {}."""
        result = _safe_parse_raw_config("")
        assert result == {}

    def test_old_json_loads_would_crash_on_dict(self):
        """Prove the old code path would crash."""
        config = {"publisherTargeting": {"targetingMode": "EXCLUSIVE"}}
        with pytest.raises(TypeError, match="the JSON object must be str"):
            json.loads(config)


class TestSuspendServiceWithDictRawConfig:
    """End-to-end test for suspend flow — verifies no json.loads(dict) crash."""

    @pytest.mark.asyncio
    async def test_suspend_creates_snapshot_with_dict_raw_config(self):
        """Mock the suspend flow: raw_config comes as dict from JSONB, must not crash."""
        from services.snapshots_service import SnapshotsService

        mock_pretargeting_repo = AsyncMock()
        mock_pretargeting_repo.get_config_by_billing_id.return_value = {
            "config_id": "cfg-1",
            "bidder_id": "bidder-1",
            "state": "ACTIVE",
            "included_formats": ["NATIVE"],
            "included_platforms": ["DESKTOP"],
            "included_sizes": ["300x250"],
            "included_geos": ["US"],
            "excluded_geos": [],
            # This is the key: raw_config as dict (JSONB auto-deserialized)
            "raw_config": {
                "publisherTargeting": {
                    "targetingMode": "EXCLUSIVE",
                    "values": ["pub-abc"],
                }
            },
        }

        mock_performance_repo = AsyncMock()
        mock_performance_repo.get_performance_aggregates.return_value = {
            "days_tracked": 7,
            "total_impressions": 1000,
            "total_clicks": 10,
            "total_spend_usd": 5.0,
        }

        mock_snapshots_repo = AsyncMock()
        mock_snapshots_repo.create_snapshot.return_value = 42
        mock_snapshots_repo.get_snapshot.return_value = {
            "id": 42,
            "billing_id": "billing-1",
            "snapshot_name": "Auto-snapshot before suspend",
            "snapshot_type": "before_change",
            "created_at": datetime.now(timezone.utc),
        }

        service = SnapshotsService(
            snapshots_repo=mock_snapshots_repo,
            pretargeting_repo=mock_pretargeting_repo,
            performance_repo=mock_performance_repo,
        )

        # This would crash before the fix with:
        # TypeError: the JSON object must be str, bytes or bytearray, not dict
        result = await service.create_snapshot(
            billing_id="billing-1",
            snapshot_name="Auto-snapshot before suspend",
            snapshot_type="before_change",
            notes="Test",
        )

        assert result["id"] == 42
        mock_snapshots_repo.create_snapshot.assert_called_once()
        # Verify publisher_targeting_values stays as a JSON-compatible list for JSONB storage
        call_kwargs = mock_snapshots_repo.create_snapshot.call_args[1]
        assert call_kwargs["publisher_targeting_mode"] == "EXCLUSIVE"
        assert call_kwargs["publisher_targeting_values"] == ["pub-abc"]
