"""Service layer for configuration and credentials management."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import google.auth
from fastapi import HTTPException

from collectors import BuyerSeatsClient
from storage.models import ServiceAccount

logger = logging.getLogger(__name__)


class ConfigService:
    """Orchestrates configuration and credentials workflows."""

    @staticmethod
    def is_gcp_mode() -> bool:
        """Check if running in GCP mode with ADC (OAuth2 Proxy enabled)."""
        return os.environ.get("OAUTH2_PROXY_ENABLED", "").lower() in ("1", "true", "yes")

    def get_gcp_status(self) -> dict[str, Any]:
        """Return GCP/ADC status details."""
        if not self.is_gcp_mode():
            return {
                "gcp_mode": False,
                "adc_available": False,
                "service_account_email": None,
                "project_id": None,
                "message": "Not running in GCP mode. Upload service account credentials manually.",
            }

        try:
            credentials, project = google.auth.default()
            service_account_email = getattr(credentials, "service_account_email", None)
            return {
                "gcp_mode": True,
                "adc_available": True,
                "service_account_email": service_account_email,
                "project_id": project,
                "message": "GCP mode active. Using VM's attached service account via ADC.",
            }
        except Exception as exc:
            logger.warning(f"ADC not available: {exc}")
            return {
                "gcp_mode": True,
                "adc_available": False,
                "service_account_email": None,
                "project_id": None,
                "message": f"GCP mode active but ADC not available: {str(exc)}",
            }

    async def discover_via_adc(self, bidder_id: str, store: Any) -> dict[str, Any]:
        """Discover buyer seats using ADC."""
        if not self.is_gcp_mode():
            raise HTTPException(
                status_code=400,
                detail="Not running in GCP mode. Use /config/service-accounts to upload credentials.",
            )

        try:
            client = BuyerSeatsClient(credentials_path=None, account_id=bidder_id)
            seats = await client.discover_buyer_seats()

            if not seats:
                return {
                    "success": True,
                    "bidder_ids": [],
                    "buyer_seats_count": 0,
                    "message": (
                        "No buyer seats found. Ensure the VM's service account "
                        f"has been added to bidder {bidder_id} in the RTB API Console."
                    ),
                }

            bidder_ids = set()
            for seat in seats:
                seat.service_account_id = None
                await store.save_buyer_seat(seat)
                bidder_ids.add(seat.bidder_id)

            return {
                "success": True,
                "bidder_ids": list(bidder_ids),
                "buyer_seats_count": len(seats),
                "message": (
                    f"Discovered {len(seats)} buyer seat(s) under "
                    f"{len(bidder_ids)} bidder account(s) using ADC"
                ),
            }

        except Exception as exc:
            logger.error(f"GCP ADC discovery failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Discovery failed: {str(exc)}. "
                    "Ensure the VM's service account has RTB API access."
                ),
            ) from exc

    async def list_service_accounts(self, store: Any, active_only: bool) -> list[ServiceAccount]:
        """List all configured service accounts."""
        return await store.get_service_accounts(active_only=active_only)

    async def add_service_account(
        self,
        store: Any,
        service_account_json: str,
        display_name: Optional[str],
    ) -> dict[str, Any]:
        """Validate, persist credentials, and auto-discover buyer seats."""
        try:
            creds_data = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(exc)}") from exc

        required_fields = ["type", "client_email", "private_key", "project_id"]
        missing = [f for f in required_fields if f not in creds_data]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Missing required fields: "
                    f"{', '.join(missing)}. This doesn't appear to be a valid service account key."
                ),
            )

        if creds_data.get("type") != "service_account":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid credential type: '{creds_data.get('type')}'. "
                    "Expected 'service_account'."
                ),
            )

        client_email = creds_data.get("client_email")
        project_id = creds_data.get("project_id")

        existing = await store.get_service_account_by_email(client_email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Service account {client_email} is already configured.",
            )

        account_id = str(uuid.uuid4())
        creds_dir = Path.home() / ".catscan" / "credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(creds_dir, 0o700)

        creds_path = creds_dir / f"{account_id}.json"
        with open(creds_path, "w") as f:
            json.dump(creds_data, f, indent=2)
        os.chmod(creds_path, 0o600)

        try:
            service_account = ServiceAccount(
                id=account_id,
                client_email=client_email,
                project_id=project_id,
                display_name=display_name or project_id or client_email.split("@")[0],
                credentials_path=str(creds_path),
                is_active=True,
            )
            await store.save_service_account(service_account)

            logger.info(f"Service account added: {client_email} (id={account_id})")

            discovered_bidder_ids = []
            try:
                client = BuyerSeatsClient(
                    credentials_path=str(creds_path),
                    account_id="discovery",
                )
                seats = await client.discover_buyer_seats()

                if seats:
                    for seat in seats:
                        seat.service_account_id = account_id
                        await store.save_buyer_seat(seat)
                        discovered_bidder_ids.append(seat.bidder_id)
                    logger.info(
                        f"Discovered {len(seats)} buyer seats for {client_email}: "
                        f"bidders={set(discovered_bidder_ids)}"
                    )
                else:
                    logger.warning(f"No buyer seats discovered for {client_email}")
            except Exception as exc:
                logger.warning(
                    f"Failed to auto-discover buyer seats for {client_email}: {exc}"
                )

            message = "Service account added successfully"
            if discovered_bidder_ids:
                unique_bidders = set(discovered_bidder_ids)
                message += (
                    f". Discovered {len(unique_bidders)} bidder account(s): "
                    f"{', '.join(unique_bidders)}"
                )

            return {
                "success": True,
                "id": account_id,
                "client_email": client_email,
                "project_id": project_id,
                "message": message,
            }

        except Exception as exc:
            if creds_path.exists():
                creds_path.unlink()
            logger.error(f"Failed to save service account: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save service account: {str(exc)}",
            ) from exc

    async def get_service_account(self, store: Any, account_id: str) -> ServiceAccount | None:
        """Get a specific service account by ID."""
        return await store.get_service_account(account_id)

    async def discover_bidders_for_account(
        self, store: Any, account_id: str, account: ServiceAccount
    ) -> dict[str, Any]:
        """Discover bidder accounts for a service account."""
        try:
            client = BuyerSeatsClient(
                credentials_path=account.credentials_path,
                account_id="discovery",
            )
            seats = await client.discover_buyer_seats()

            if not seats:
                return {
                    "success": True,
                    "bidder_ids": [],
                    "buyer_seats_count": 0,
                    "message": (
                        "No bidder accounts found. Verify the service account has RTB API permissions."
                    ),
                }

            bidder_ids = set()
            for seat in seats:
                seat.service_account_id = account_id
                await store.save_buyer_seat(seat)
                bidder_ids.add(seat.bidder_id)

            return {
                "success": True,
                "bidder_ids": list(bidder_ids),
                "buyer_seats_count": len(seats),
                "message": (
                    f"Discovered {len(seats)} buyer seat(s) under "
                    f"{len(bidder_ids)} bidder account(s)"
                ),
            }

        except Exception as exc:
            logger.error(f"Bidder discovery failed for {account.client_email}: {exc}")
            raise HTTPException(status_code=500, detail=f"Discovery failed: {str(exc)}") from exc

    async def delete_service_account(self, store: Any, account: ServiceAccount) -> dict[str, Any]:
        """Delete a service account and credentials file."""
        creds_path = Path(account.credentials_path)
        if creds_path.exists():
            creds_path.unlink()

        deleted = await store.delete_service_account(account.id)
        if deleted:
            logger.info(f"Service account deleted: {account.client_email} (id={account.id})")
            return {"success": True, "message": "Service account deleted"}

        raise HTTPException(
            status_code=500,
            detail="Failed to delete service account from database",
        )

    async def get_gemini_key_status(self, store: Any) -> dict[str, Any]:
        """Get Gemini API key configuration status."""
        stored_key = await store.get_setting("gemini_api_key")
        if stored_key:
            return {
                "configured": True,
                "masked_key": self._mask_api_key(stored_key),
                "message": "Gemini API key configured from database",
            }

        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            return {
                "configured": True,
                "masked_key": self._mask_api_key(env_key),
                "message": "Gemini API key configured from environment variable",
            }

        return {
            "configured": False,
            "masked_key": None,
            "message": "Gemini API key not configured. Language detection is disabled.",
        }

    async def update_gemini_key(self, store: Any, api_key: str) -> dict[str, Any]:
        """Update Gemini API key."""
        key = api_key.strip()
        if len(key) < 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid API key format. Key is too short.",
            )

        await store.set_setting("gemini_api_key", key, updated_by="api")
        logger.info("Gemini API key updated")
        return {"success": True, "message": "Gemini API key saved successfully"}

    async def delete_gemini_key(self, store: Any) -> dict[str, Any]:
        """Delete Gemini API key from database."""
        await store.set_setting("gemini_api_key", "", updated_by="api")
        logger.info("Gemini API key removed")
        return {"success": True, "message": "Gemini API key removed"}

    @staticmethod
    def _mask_api_key(key: str) -> str:
        """Mask API key for display."""
        if len(key) <= 10:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"
