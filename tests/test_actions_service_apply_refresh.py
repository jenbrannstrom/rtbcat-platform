"""Apply path: use the bidder's own service account and refresh the local row.

Regression for the 2026-10-13 "Push to Google didn't take" report: the QPS
patch reached Google, but the page kept showing the stored pre-push value
because nothing refreshed the local config row and the follow-up sync hit a
different bidder.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import actions_service as actions_module
from services.actions_service import ActionsService


class _PretargetingStub:
    def __init__(self, config: dict):
        self.config = config
        self.saved_rows: list[dict] = []
        self.history_calls: list[dict] = []

    async def get_config(self, billing_id: str):
        return self.config if billing_id == self.config["billing_id"] else None

    async def save_config(self, row: dict):
        self.saved_rows.append(row)

    async def add_history(self, **kwargs):
        self.history_calls.append(kwargs)
        return 1


class _ChangesStub:
    def __init__(self, changes: list[dict]):
        self.changes = {c["id"]: c for c in changes}
        self.applied: list[int] = []

    async def get_pending_change(self, change_id: int):
        return self.changes.get(change_id)

    async def list_pending_changes(self, billing_id: str, status: str, limit: int):
        # The real service returns newest-first; apply_all reverses to oldest-first.
        rows = [c for c in self.changes.values() if c["billing_id"] == billing_id and c["status"] == status]
        return list(reversed(rows))

    async def mark_pending_change_applied(self, change_id: int, applied_by=None):
        self.applied.append(change_id)
        return 1


class _SnapshotsStub:
    async def create_snapshot(self, **kwargs):
        return 1


class _SeatsStub:
    def __init__(self, owner, first):
        self.owner = owner
        self.first = first
        self.bidder_lookups: list[str] = []

    async def get_service_account_for_bidder(self, bidder_id: str):
        self.bidder_lookups.append(bidder_id)
        return self.owner

    async def get_service_accounts(self, active_only: bool = True):
        return [self.first]


class _GoogleClientStub:
    """Behaves like Google: the GET after a patch returns the new value."""

    def __init__(self, live_config: dict, *, get_raises: Exception | None = None):
        self.live_config = live_config
        self.get_raises = get_raises
        self.patch_calls: list[dict] = []

    async def patch_pretargeting_config(self, config_id: str, update_body: dict, update_mask=None):
        self.patch_calls.append({"config_id": config_id, "body": update_body, "mask": update_mask})
        self.live_config = {**self.live_config, **{k: str(v) for k, v in update_body.items()}}
        return self.live_config

    async def get_pretargeting_config_by_id(self, config_id: str):
        if self.get_raises:
            raise self.get_raises
        return dict(self.live_config)


def _service_account(tmp_path, name: str):
    creds = tmp_path / f"{name}.json"
    creds.write_text("{}")
    return SimpleNamespace(id=f"sa-{name}", display_name=name, credentials_path=str(creds))


def _qps_change(change_id: int, billing_id: str, value: str = "15000") -> dict:
    return {
        "id": change_id,
        "billing_id": billing_id,
        "change_type": "set_maximum_qps",
        "field_name": "maximum_qps",
        "value": value,
        "status": "pending",
        "reason": None,
    }


@pytest.mark.asyncio
async def test_client_uses_service_account_that_owns_the_bidder(monkeypatch, tmp_path):
    owner = _service_account(tmp_path, "owner")
    first = _service_account(tmp_path, "aaa-first-alphabetically")
    seats = _SeatsStub(owner=owner, first=first)
    config = {"billing_id": "198363911721", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    built: list[dict] = []

    def _fake_client(credentials_path: str, account_id: str):
        built.append({"credentials_path": credentials_path, "account_id": account_id})
        return object()

    monkeypatch.setattr(actions_module, "PretargetingClient", _fake_client)
    service = ActionsService(
        changes_service=_ChangesStub([]),
        pretargeting_service=_PretargetingStub(config),
        snapshots_service=_SnapshotsStub(),
        seats_service=seats,
    )

    _client, config_id, bidder_id = await service._get_pretargeting_client("198363911721")

    assert (config_id, bidder_id) == ("cfg-1", "bidder-B")
    assert seats.bidder_lookups == ["bidder-B"]
    assert built == [{"credentials_path": owner.credentials_path, "account_id": "bidder-B"}]


@pytest.mark.asyncio
async def test_client_falls_back_to_first_account_when_bidder_unlinked(monkeypatch, tmp_path, caplog):
    first = _service_account(tmp_path, "only-account")
    seats = _SeatsStub(owner=None, first=first)
    config = {"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-X"}
    built: list[dict] = []
    monkeypatch.setattr(
        actions_module, "PretargetingClient",
        lambda credentials_path, account_id: built.append(credentials_path) or object(),
    )
    service = ActionsService(
        changes_service=_ChangesStub([]),
        pretargeting_service=_PretargetingStub(config),
        snapshots_service=_SnapshotsStub(),
        seats_service=seats,
    )

    with caplog.at_level(logging.WARNING):
        await service._get_pretargeting_client("b-1")

    assert built == [first.credentials_path]
    assert "No service account linked to bidder bidder-X" in caplog.text


@pytest.mark.asyncio
async def test_apply_qps_change_stores_googles_updated_config(monkeypatch):
    config = {"billing_id": "198363911721", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    pretargeting = _PretargetingStub(config)
    changes = _ChangesStub([_qps_change(49, "198363911721")])
    client = _GoogleClientStub({
        "configId": "cfg-1",
        "billingId": "198363911721",
        "displayName": "US+CAN_CTV",
        "state": "ACTIVE",
        "maximumQps": "10000",
        "includedFormats": ["VIDEO"],
        "includedCreativeDimensions": [{"width": 1920, "height": 1080}],
        "geoTargeting": {"includedIds": ["2840", "2124"]},
    })
    service = ActionsService(
        changes_service=changes,
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(),
        seats_service=object(),
    )

    async def _stub_get_client(_billing_id: str):
        return client, "cfg-1", "bidder-B"

    monkeypatch.setattr(service, "_get_pretargeting_client", _stub_get_client)

    result = await service.apply_pending_change("198363911721", 49, dry_run=False)

    assert result["status"] == "applied"
    assert result["local_refresh_succeeded"] is True
    assert client.patch_calls == [{"config_id": "cfg-1", "body": {"maximumQps": 15000}, "mask": "maximumQps"}]
    assert changes.applied == [49]
    assert len(pretargeting.saved_rows) == 1
    row = pretargeting.saved_rows[0]
    assert row["bidder_id"] == "bidder-B"
    assert row["config_id"] == "cfg-1"
    assert row["billing_id"] == "198363911721"
    assert json.loads(row["raw_config"])["maximumQps"] == "15000"
    assert json.loads(row["included_sizes"]) == ["1920x1080"]
    assert json.loads(row["included_geos"]) == ["2840", "2124"]


@pytest.mark.asyncio
async def test_refresh_failure_does_not_undo_an_applied_change(monkeypatch, caplog):
    config = {"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    pretargeting = _PretargetingStub(config)
    changes = _ChangesStub([_qps_change(1, "b-1")])
    client = _GoogleClientStub({"configId": "cfg-1", "maximumQps": "1"}, get_raises=RuntimeError("google down"))
    service = ActionsService(
        changes_service=changes,
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(),
        seats_service=object(),
    )

    async def _stub_get_client(_billing_id: str):
        return client, "cfg-1", "bidder-B"

    monkeypatch.setattr(service, "_get_pretargeting_client", _stub_get_client)

    with caplog.at_level(logging.ERROR):
        result = await service.apply_pending_change("b-1", 1, dry_run=False)

    assert result["status"] == "applied"
    assert result["local_refresh_succeeded"] is False
    assert changes.applied == [1]
    assert pretargeting.saved_rows == []
    assert "failed to refresh the local row" in caplog.text


@pytest.mark.asyncio
async def test_apply_all_refreshes_the_local_row_once_per_batch(monkeypatch):
    config = {"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    pretargeting = _PretargetingStub(config)
    changes = _ChangesStub([_qps_change(1, "b-1", "12000"), _qps_change(2, "b-1", "15000")])
    client = _GoogleClientStub({"configId": "cfg-1", "billingId": "b-1", "maximumQps": "10000"})
    service = ActionsService(
        changes_service=changes,
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(),
        seats_service=object(),
    )

    async def _stub_get_client(_billing_id: str):
        return client, "cfg-1", "bidder-B"

    monkeypatch.setattr(service, "_get_pretargeting_client", _stub_get_client)

    result = await service.apply_all_pending_changes("b-1", dry_run=False)

    assert (result["changes_applied"], result["changes_failed"]) == (2, 0)
    assert result["local_refresh_succeeded"] is True
    assert changes.applied == [1, 2]
    assert len(client.patch_calls) == 2
    assert len(pretargeting.saved_rows) == 1
    assert json.loads(pretargeting.saved_rows[0]["raw_config"])["maximumQps"] == "15000"


@pytest.mark.asyncio
async def test_apply_all_logs_the_swallowed_failure(monkeypatch, caplog):
    config = {"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    pretargeting = _PretargetingStub(config)
    changes = _ChangesStub([_qps_change(7, "b-1")])
    service = ActionsService(
        changes_service=changes,
        pretargeting_service=pretargeting,
        snapshots_service=_SnapshotsStub(),
        seats_service=object(),
    )

    async def _boom(**kwargs):
        raise RuntimeError("403 PERMISSION_DENIED")

    monkeypatch.setattr(service, "apply_pending_change", _boom)

    with caplog.at_level(logging.ERROR):
        result = await service.apply_all_pending_changes("b-1", dry_run=False)

    assert result["changes_failed"] == 1
    assert result["changes_applied"] == 0
    assert "Failed to apply pending change 7 (set_maximum_qps=15000) for billing b-1" in caplog.text
    assert "403 PERMISSION_DENIED" in caplog.text


@pytest.mark.asyncio
async def test_apply_refuses_ambiguous_credentials_for_unlinked_bidder(monkeypatch, tmp_path):
    first = _service_account(tmp_path, "first")
    other = _service_account(tmp_path, "other")
    seats = _SeatsStub(owner=None, first=first)
    seats.get_service_accounts = AsyncMock(return_value=[first, other])
    config = {"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"}
    service = ActionsService(pretargeting_service=_PretargetingStub(config), seats_service=seats)

    with pytest.raises(ValueError, match="link one before applying"):
        await service._get_pretargeting_client("b-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("live", [
    None,
    {"configId": "cfg-1", "billingId": None},
    {"configId": "cfg-1", "billingId": "wrong-billing"},
    {"configId": "wrong-config", "billingId": "b-1"},
])
async def test_refresh_preserves_local_row_when_google_cannot_identify_target(live):
    pretargeting = _PretargetingStub({"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"})
    service = ActionsService(pretargeting_service=pretargeting, seats_service=object())
    client = SimpleNamespace(get_pretargeting_config_by_id=AsyncMock(return_value=live))

    refreshed = await service._refresh_local_config(client, "cfg-1", "bidder-B", "b-1")

    assert refreshed is False
    assert pretargeting.saved_rows == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["google", "database"])
async def test_batch_reports_refresh_failure_without_reclassifying_google_writes(monkeypatch, failure):
    pretargeting = _PretargetingStub({"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"})
    changes = _ChangesStub([_qps_change(1, "b-1")])
    client = _GoogleClientStub(
        {"configId": "cfg-1", "billingId": "b-1", "maximumQps": "10000"},
        get_raises=RuntimeError("Google unavailable") if failure == "google" else None,
    )
    if failure == "database":
        pretargeting.save_config = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    service = ActionsService(changes_service=changes, pretargeting_service=pretargeting,
                             snapshots_service=_SnapshotsStub(), seats_service=object())
    monkeypatch.setattr(service, "_get_pretargeting_client", AsyncMock(return_value=(client, "cfg-1", "bidder-B")))

    result = await service.apply_all_pending_changes("b-1", dry_run=False)

    assert result["changes_applied"] == 1
    assert result["changes_failed"] == 0
    assert result["local_refresh_succeeded"] is False
    assert changes.applied == [1]
    assert client.live_config["maximumQps"] == "15000"


@pytest.mark.asyncio
async def test_partial_batch_refreshes_only_the_confirmed_google_state(monkeypatch):
    pretargeting = _PretargetingStub({"billing_id": "b-1", "config_id": "cfg-1", "bidder_id": "bidder-B"})
    changes = _ChangesStub([_qps_change(1, "b-1", "12000"), _qps_change(2, "b-1", "15000")])
    client = _GoogleClientStub({"configId": "cfg-1", "billingId": "b-1", "maximumQps": "10000"})
    patch = client.patch_pretargeting_config

    async def reject_second(*args, **kwargs):
        if kwargs["update_body"]["maximumQps"] == 15000:
            raise RuntimeError("Google rejected second change")
        return await patch(*args, **kwargs)

    client.patch_pretargeting_config = reject_second
    service = ActionsService(changes_service=changes, pretargeting_service=pretargeting,
                             snapshots_service=_SnapshotsStub(), seats_service=object())
    monkeypatch.setattr(service, "_get_pretargeting_client", AsyncMock(return_value=(client, "cfg-1", "bidder-B")))

    result = await service.apply_all_pending_changes("b-1", dry_run=False)

    assert (result["changes_applied"], result["changes_failed"]) == (1, 1)
    assert result["local_refresh_succeeded"] is True
    assert changes.applied == [1]
    assert len(pretargeting.saved_rows) == 1
    assert json.loads(pretargeting.saved_rows[0]["raw_config"])["maximumQps"] == "12000"
