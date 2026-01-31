"""Business logic for applying pretargeting changes and rollbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from collectors import PretargetingClient
from services.changes_service import ChangesService
from services.pretargeting_service import PretargetingService
from services.snapshots_service import SnapshotsService

if TYPE_CHECKING:
    from services.seats_service import SeatsService


class ActionsService:
    """Service layer for apply/suspend/activate/rollback workflows."""

    def __init__(
        self,
        changes_service: ChangesService | None = None,
        pretargeting_service: PretargetingService | None = None,
        snapshots_service: SnapshotsService | None = None,
        seats_service: "SeatsService | None" = None,
    ) -> None:
        self._changes = changes_service or ChangesService()
        self._pretargeting = pretargeting_service or PretargetingService()
        self._snapshots = snapshots_service or SnapshotsService()
        # Lazily import to avoid circular imports
        if seats_service is None:
            from services.seats_service import SeatsService
            seats_service = SeatsService()
        self._seats = seats_service

    @staticmethod
    def _parse_json_list(value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return []
        return list(value)

    async def _get_pretargeting_client(self, billing_id: str):
        config = await self._pretargeting.get_config(billing_id)
        if not config:
            raise ValueError(f"Config not found for billing_id: {billing_id}")

        bidder_id = config["bidder_id"]
        config_id = config["config_id"]

        accounts = await self._seats.get_service_accounts(active_only=True)
        if not accounts:
            raise ValueError("No service account configured")

        service_account = accounts[0]
        if not service_account.credentials_path:
            raise ValueError("Credentials path not configured")

        creds_path = Path(service_account.credentials_path).expanduser()
        if not creds_path.exists():
            raise ValueError("Credentials file not found")

        client = PretargetingClient(
            credentials_path=str(creds_path),
            account_id=bidder_id,
        )
        return client, config_id, bidder_id

    async def apply_pending_change(
        self,
        billing_id: str,
        change_id: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        change = await self._changes.get_pending_change(change_id)
        if not change or change["billing_id"] != billing_id:
            raise ValueError("Pending change not found")
        if change["status"] != "pending":
            raise ValueError(f"Change is not pending: {change['status']}")

        if dry_run:
            return {
                "status": "dry_run",
                "change_id": change_id,
                "dry_run": True,
                "message": f"Would apply {change['change_type']}: {change['value']} to {change['field_name']}",
            }

        client, config_id, bidder_id = await self._get_pretargeting_client(billing_id)
        await self._apply_change_to_client(change, client, config_id, billing_id)

        await self._changes.mark_pending_change_applied(change_id, applied_by="system")
        await self._pretargeting.add_history(
            config_id=str(config_id),
            bidder_id=str(bidder_id),
            change_type="api_write",
            field_changed=change["field_name"],
            old_value=None,
            new_value=f"{change['change_type']}:{change['value']}",
            changed_by="system",
            change_source="api",
        )

        return {
            "status": "applied",
            "change_id": change_id,
            "dry_run": False,
            "message": f"Successfully applied {change['change_type']}: {change['value']}",
        }

    async def apply_all_pending_changes(
        self,
        billing_id: str,
        dry_run: bool,
    ) -> dict[str, Any]:
        changes = await self._changes.list_pending_changes(
            billing_id=billing_id, status="pending", limit=500
        )
        if not changes:
            return {
                "status": "no_changes",
                "dry_run": dry_run,
                "changes_applied": 0,
                "changes_failed": 0,
                "message": "No pending changes to apply",
            }

        if dry_run:
            change_list = [f"{c['change_type']}: {c['value']}" for c in changes]
            return {
                "status": "dry_run",
                "dry_run": True,
                "changes_applied": 0,
                "changes_failed": 0,
                "message": f"Would apply {len(changes)} changes: {', '.join(change_list)}",
            }

        await self._snapshots.create_snapshot(
            billing_id=billing_id,
            snapshot_name="Auto-snapshot before changes",
            snapshot_type="before_change",
            notes="Created before applying pending changes",
        )

        applied = 0
        failed = 0

        for change in changes:
            try:
                await self.apply_pending_change(
                    billing_id=billing_id,
                    change_id=change["id"],
                    dry_run=False,
                )
                applied += 1
            except Exception:
                failed += 1

        return {
            "status": "completed",
            "dry_run": False,
            "changes_applied": applied,
            "changes_failed": failed,
            "message": f"Applied {applied} changes, {failed} failed",
        }

    async def suspend_config(self, billing_id: str) -> dict[str, Any]:
        await self._snapshots.create_snapshot(
            billing_id=billing_id,
            snapshot_name="Auto-snapshot before suspend",
            snapshot_type="before_change",
            notes="Automatically created before suspend operation",
        )

        client, config_id, bidder_id = await self._get_pretargeting_client(billing_id)
        await client.suspend_pretargeting_config(config_id)
        await self._pretargeting.update_state(billing_id, "SUSPENDED")
        await self._pretargeting.add_history(
            config_id=str(config_id),
            bidder_id=str(bidder_id),
            change_type="state_change",
            field_changed="state",
            old_value="ACTIVE",
            new_value="SUSPENDED",
            changed_by="system",
            change_source="api",
        )
        return {
            "status": "success",
            "billing_id": billing_id,
            "new_state": "SUSPENDED",
            "message": "Config suspended. Auto-snapshot created for rollback.",
        }

    async def activate_config(self, billing_id: str) -> dict[str, Any]:
        client, config_id, bidder_id = await self._get_pretargeting_client(billing_id)
        await client.activate_pretargeting_config(config_id)
        await self._pretargeting.update_state(billing_id, "ACTIVE")
        await self._pretargeting.add_history(
            config_id=str(config_id),
            bidder_id=str(bidder_id),
            change_type="state_change",
            field_changed="state",
            old_value="SUSPENDED",
            new_value="ACTIVE",
            changed_by="system",
            change_source="api",
        )
        return {
            "status": "success",
            "billing_id": billing_id,
            "new_state": "ACTIVE",
            "message": "Config activated. QPS consumption resumed.",
        }

    async def rollback_to_snapshot(
        self,
        billing_id: str,
        snapshot_id: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        snapshot = await self._snapshots.get_snapshot(snapshot_id)
        if not snapshot or snapshot["billing_id"] != billing_id:
            raise ValueError("Snapshot not found")

        current = await self._pretargeting.get_config(billing_id)
        if not current:
            raise ValueError("Config not found")

        current_sizes = set(self._parse_json_list(current.get("included_sizes")))
        snapshot_sizes = set(self._parse_json_list(snapshot.get("included_sizes")))
        current_geos = set(self._parse_json_list(current.get("included_geos")))
        snapshot_geos = set(self._parse_json_list(snapshot.get("included_geos")))
        current_formats = set(self._parse_json_list(current.get("included_formats")))
        snapshot_formats = set(self._parse_json_list(snapshot.get("included_formats")))

        changes: list[str] = []
        for size in snapshot_sizes - current_sizes:
            changes.append(f"add_size: {size}")
        for size in current_sizes - snapshot_sizes:
            changes.append(f"remove_size: {size}")
        for geo in snapshot_geos - current_geos:
            changes.append(f"add_geo: {geo}")
        for geo in current_geos - snapshot_geos:
            changes.append(f"remove_geo: {geo}")
        for fmt in snapshot_formats - current_formats:
            changes.append(f"add_format: {fmt}")
        for fmt in current_formats - snapshot_formats:
            changes.append(f"remove_format: {fmt}")
        if snapshot.get("state") and current.get("state") != snapshot.get("state"):
            changes.append(f"state: {current.get('state')} -> {snapshot.get('state')}")

        if not changes:
            return {
                "status": "no_changes",
                "dry_run": dry_run,
                "snapshot_id": snapshot_id,
                "changes_made": [],
                "message": "Config matches snapshot - no changes needed",
            }

        if dry_run:
            return {
                "status": "dry_run",
                "dry_run": True,
                "snapshot_id": snapshot_id,
                "changes_made": changes,
                "message": f"Would apply {len(changes)} changes to restore snapshot",
            }

        client, config_id, bidder_id = await self._get_pretargeting_client(billing_id)

        snapshot_dims = []
        for size_str in snapshot_sizes:
            parts = size_str.split("x")
            if len(parts) == 2:
                snapshot_dims.append({"width": int(parts[0]), "height": int(parts[1])})

        snapshot_publisher_mode = snapshot.get("publisher_targeting_mode")
        snapshot_publisher_values = self._parse_json_list(snapshot.get("publisher_targeting_values"))

        update_body = {
            "includedCreativeDimensions": snapshot_dims,
            "geoTargeting": {
                "includedIds": list(snapshot_geos),
                "excludedIds": self._parse_json_list(snapshot.get("excluded_geos")),
            },
            "includedFormats": list(snapshot_formats),
        }
        update_mask = ["includedCreativeDimensions", "geoTargeting", "includedFormats"]

        if snapshot_publisher_mode is not None:
            update_body["publisherTargeting"] = {
                "targetingMode": snapshot_publisher_mode,
                "values": snapshot_publisher_values,
            }
            update_mask.append("publisherTargeting")

        await client.patch_pretargeting_config(
            config_id=config_id,
            update_body=update_body,
            update_mask=",".join(update_mask),
        )

        if snapshot.get("state") == "SUSPENDED" and current.get("state") == "ACTIVE":
            await client.suspend_pretargeting_config(config_id)
        elif snapshot.get("state") == "ACTIVE" and current.get("state") == "SUSPENDED":
            await client.activate_pretargeting_config(config_id)

        await self._pretargeting.add_history(
            config_id=str(config_id),
            bidder_id=str(bidder_id),
            change_type="rollback",
            field_changed="all",
            old_value=None,
            new_value=f"snapshot_{snapshot_id}",
            changed_by="system",
            change_source="api",
        )

        return {
            "status": "applied",
            "dry_run": False,
            "snapshot_id": snapshot_id,
            "changes_made": changes,
            "message": f"Rolled back to snapshot. Applied {len(changes)} changes.",
        }

    async def _apply_change_to_client(
        self, change: dict[str, Any], client: PretargetingClient, config_id: str, billing_id: str
    ) -> None:
        change_type = change["change_type"]
        value = change["value"]

        if change_type == "add_size":
            parts = value.split("x")
            size = {"width": int(parts[0]), "height": int(parts[1])}
            await client.add_sizes_to_config(config_id, [size])
        elif change_type == "remove_size":
            parts = value.split("x")
            size = {"width": int(parts[0]), "height": int(parts[1])}
            await client.remove_sizes_from_config(config_id, [size])
        elif change_type == "add_geo":
            await client.add_geos_to_config(config_id, [value])
        elif change_type == "remove_geo":
            await client.remove_geos_from_config(config_id, [value])
        elif change_type == "add_excluded_geo":
            await client.add_geos_to_config(config_id, [value], exclude=True)
        elif change_type == "remove_excluded_geo":
            await client.remove_geos_from_config(config_id, [value], from_excluded=True)
        elif change_type in {"add_publisher", "remove_publisher", "set_publisher_mode"}:
            config_row = await self._pretargeting.get_config(billing_id)
            raw_config = json.loads(config_row["raw_config"]) if config_row and config_row.get("raw_config") else {}
            publisher_targeting = raw_config.get("publisherTargeting") or {}
            current_mode = publisher_targeting.get("targetingMode") or "EXCLUSIVE"
            current_values = list(publisher_targeting.get("values") or [])

            if change_type == "set_publisher_mode":
                updated_mode = value
                updated_values = []
            else:
                updated_mode = current_mode
                updated_values = current_values.copy()
                if change_type == "add_publisher" and value not in updated_values:
                    updated_values.append(value)
                elif change_type == "remove_publisher" and value in updated_values:
                    updated_values.remove(value)

            update_body = {
                "publisherTargeting": {
                    "targetingMode": updated_mode,
                    "values": updated_values,
                }
            }
            await client.patch_pretargeting_config(
                config_id=config_id,
                update_body=update_body,
                update_mask="publisherTargeting",
            )
        else:
            raise ValueError(f"Unsupported change type: {change_type}")
