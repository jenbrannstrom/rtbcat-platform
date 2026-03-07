"""Tests for pretargeting actions service rollback workflows."""

from __future__ import annotations

import logging

import pytest

from services.actions_service import ActionsService


class _PretargetingStub:
    def __init__(self, current_config: dict):
        self.current_config = current_config
        self.history_calls: list[dict] = []

    async def get_config(self, billing_id: str):
        if billing_id != self.current_config.get("billing_id"):
            return None
        return self.current_config

    async def add_history(self, **kwargs):
        self.history_calls.append(kwargs)
        return 42


class _SnapshotsStub:
    def __init__(self, snapshot: dict):
        self.snapshot = snapshot

    async def get_snapshot(self, snapshot_id: int):
        if snapshot_id != self.snapshot.get("id"):
            return None
        return self.snapshot


class _ClientStub:
    def __init__(self):
        self.patch_calls: list[dict] = []
        self.suspend_calls: list[str] = []
        self.activate_calls: list[str] = []

    async def patch_pretargeting_config(self, **kwargs):
        self.patch_calls.append(kwargs)

    async def suspend_pretargeting_config(self, config_id: str):
        self.suspend_calls.append(config_id)

    async def activate_pretargeting_config(self, config_id: str):
        self.activate_calls.append(config_id)


@pytest.mark.asyncio
async def test_rollback_to_snapshot_dry_run_returns_changes_only():
    snapshot = {
        "id": 7,
        "billing_id": "cfg-1",
        "included_sizes": ["300x250", "320x50"],
        "included_geos": ["US"],
        "included_formats": ["VIDEO"],
        "excluded_geos": [],
        "state": "ACTIVE",
        "publisher_targeting_mode": None,
        "publisher_targeting_values": [],
    }
    current = {
        "billing_id": "cfg-1",
        "config_id": "google-cfg-1",
        "bidder_id": "buyer-1",
        "included_sizes": ["300x250"],
        "included_geos": ["US"],
        "included_formats": ["VIDEO"],
        "state": "ACTIVE",
    }
    pretargeting = _PretargetingStub(current)
    service = ActionsService(
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(snapshot),
        seats_service=object(),
    )

    payload = await service.rollback_to_snapshot(
        billing_id="cfg-1",
        snapshot_id=7,
        dry_run=True,
    )

    assert payload["status"] == "dry_run"
    assert payload["dry_run"] is True
    assert payload["snapshot_id"] == 7
    assert payload["changes_made"] == ["add_size: 320x50"]
    assert pretargeting.history_calls == []


@pytest.mark.asyncio
async def test_rollback_to_snapshot_persists_optimizer_audit_context(monkeypatch: pytest.MonkeyPatch):
    snapshot = {
        "id": 9,
        "billing_id": "cfg-9",
        "included_sizes": ["300x250", "320x50"],
        "included_geos": ["US"],
        "included_formats": ["VIDEO"],
        "excluded_geos": [],
        "state": "ACTIVE",
        "publisher_targeting_mode": None,
        "publisher_targeting_values": [],
    }
    current = {
        "billing_id": "cfg-9",
        "config_id": "google-cfg-9",
        "bidder_id": "buyer-9",
        "included_sizes": ["300x250"],
        "included_geos": ["US"],
        "included_formats": ["VIDEO"],
        "state": "ACTIVE",
    }
    pretargeting = _PretargetingStub(current)
    client = _ClientStub()
    service = ActionsService(
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(snapshot),
        seats_service=object(),
    )

    async def _stub_get_client(_billing_id: str):
        return client, "google-cfg-9", "buyer-9"

    monkeypatch.setattr(service, "_get_pretargeting_client", _stub_get_client)
    payload = await service.rollback_to_snapshot(
        billing_id="cfg-9",
        snapshot_id=9,
        dry_run=False,
        reason="Post-apply performance dropped",
        proposal_id="prp_123",
        initiated_by="u1",
    )

    assert payload["status"] == "applied"
    assert payload["history_id"] == 42
    assert len(client.patch_calls) == 1
    assert len(pretargeting.history_calls) == 1

    history = pretargeting.history_calls[0]
    assert history["change_type"] == "rollback"
    assert history["new_value"] == "snapshot_9"
    assert history["changed_by"] == "u1"
    assert history["change_source"] == "optimizer"
    context = history["raw_config_snapshot"]
    assert context["snapshot_id"] == 9
    assert context["proposal_id"] == "prp_123"
    assert context["reason"] == "Post-apply performance dropped"
    assert context["initiated_by"] == "u1"
    assert "add_size: 320x50" in context["changes_made"]


def test_parse_json_list_logs_warning_and_defaults_on_invalid_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        parsed = ActionsService._parse_json_list("{not-json}")
    assert parsed == []
    assert "Failed to parse JSON list payload in ActionsService" in caplog.text
