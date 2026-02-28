"""Service layer for admin endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Optional, Callable, Awaitable, Any

from fastapi import HTTPException

from services.auth_service import AuthService, User
from storage.postgres_repositories.admin_repo import AdminRepository


ALLOWED_DEFAULT_LANGUAGES = {
    "en",
    "pl",
    "zh",
    "ru",
    "uk",
    "es",
    "da",
    "fr",
    "nl",
    "he",
    "ar",
}


class AdminService:
    """Orchestrates admin workflows."""

    def __init__(
        self,
        auth_service: AuthService | None = None,
        repo: AdminRepository | None = None,
        password_hasher: Callable[[str], str] | None = None,
        password_hash_writer: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._auth = auth_service or AuthService()
        self._repo = repo or AdminRepository()
        self._password_hasher = password_hasher
        self._password_hash_writer = password_hash_writer

    @staticmethod
    def _validate_default_language(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise HTTPException(status_code=400, detail="Default language cannot be empty")
        if normalized not in ALLOWED_DEFAULT_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported default language: {normalized}",
            )
        return normalized

    @staticmethod
    def _validate_create_auth_method(value: Optional[str]) -> str:
        if value is None:
            return "oauth-precreate"  # backward-compatible default for older clients
        normalized = value.strip().lower()
        if normalized not in ("local-password", "oauth-precreate"):
            raise HTTPException(
                status_code=400,
                detail="auth_method must be 'local-password' or 'oauth-precreate'",
            )
        return normalized

    @staticmethod
    def _validate_local_password(password: Optional[str]) -> str:
        if password is None:
            raise HTTPException(
                status_code=400,
                detail="Password is required when auth_method is 'local-password'",
            )
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        return password

    async def _store_local_password(self, user_id: str, password: str) -> None:
        if self._password_hasher is None:
            from api.auth_password import hash_password

            self._password_hasher = hash_password

        if self._password_hash_writer is None:
            self._password_hash_writer = self._auth.set_user_password_hash

        password_hash = self._password_hasher(password)
        await self._password_hash_writer(user_id, password_hash)

    async def list_users(self, active_only: bool, role: Optional[str]) -> list[User]:
        return await self._auth.get_users(active_only=active_only, role=role)

    async def create_user(
        self,
        admin: User,
        email: str,
        display_name: Optional[str],
        role: str,
        default_language: Optional[str],
        auth_method: Optional[str],
        password: Optional[str],
        client_ip: Optional[str],
    ) -> dict[str, str]:
        existing = await self._auth.get_user_by_email(email.lower().strip())
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")

        if role not in ("sudo", "admin", "read"):
            raise HTTPException(status_code=400, detail="Role must be 'sudo', 'admin', or 'read'")

        normalized_auth_method = self._validate_create_auth_method(auth_method)
        if normalized_auth_method == "local-password":
            normalized_password = self._validate_local_password(password)
        else:
            normalized_password = None
            if password:
                raise HTTPException(
                    status_code=400,
                    detail="Password is only allowed when auth_method is 'local-password'",
                )

        normalized_language = self._validate_default_language(default_language or "en")
        user_id = str(uuid.uuid4())
        user = await self._auth.create_user(
            user_id=user_id,
            email=email.lower().strip(),
            display_name=display_name,
            role=role,
            default_language=normalized_language or "en",
        )

        if normalized_auth_method == "local-password":
            await self._store_local_password(user_id, normalized_password)

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="create_user",
            user_id=admin.id,
            resource_type="user",
            resource_id=user_id,
            details=json.dumps(
                {
                    "email": user.email,
                    "role": user.role,
                    "created_by": admin.email,
                    "auth_method": normalized_auth_method,
                }
            ),
            ip_address=client_ip,
        )

        if normalized_auth_method == "local-password":
            message = "User created with local password authentication."
        else:
            message = "User created. They can now log in via external authentication."

        return {
            "status": "success",
            "user_id": user_id,
            "email": user.email,
            "message": message,
        }

    async def get_user(self, user_id: str) -> User | None:
        return await self._auth.get_user_by_id(user_id)

    async def update_user(
        self,
        admin: User,
        user_id: str,
        display_name: Optional[str],
        role: Optional[str],
        is_active: Optional[bool],
        default_language: Optional[str],
        client_ip: Optional[str],
    ) -> User:
        user = await self._auth.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if is_active is False and user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

        if role in ("admin", "read") and user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot remove your own sudo role")

        normalized_language = self._validate_default_language(default_language)
        await self._auth.update_user(
            user_id=user_id,
            display_name=display_name,
            role=role,
            is_active=is_active,
            default_language=normalized_language,
        )

        changes = {}
        if display_name is not None:
            changes["display_name"] = display_name
        if role is not None:
            changes["role"] = role
        if is_active is not None:
            changes["is_active"] = is_active
        if default_language is not None:
            changes["default_language"] = normalized_language

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="update_user",
            user_id=admin.id,
            resource_type="user",
            resource_id=user_id,
            details=json.dumps(changes),
            ip_address=client_ip,
        )

        updated_user = await self._auth.get_user_by_id(user_id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        return updated_user

    async def deactivate_user(
        self,
        admin: User,
        user_id: str,
        client_ip: Optional[str],
    ) -> dict[str, str | int]:
        user = await self._auth.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

        await self._auth.update_user(user_id=user_id, is_active=False)
        sessions_deleted = await self._auth.delete_user_sessions(user_id)

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="deactivate_user",
            user_id=admin.id,
            resource_type="user",
            resource_id=user_id,
            details=json.dumps(
                {
                    "email": user.email,
                    "sessions_deleted": sessions_deleted,
                }
            ),
            ip_address=client_ip,
        )

        return {
            "status": "success",
            "message": "User deactivated",
            "sessions_deleted": sessions_deleted,
        }

    async def get_user_permissions(self, user_id: str):
        return await self._auth.get_user_permissions(user_id)

    async def get_user_buyer_seat_permissions(self, user_id: str):
        return await self._auth.get_user_buyer_seat_permissions(user_id)

    async def grant_buyer_seat_permission(
        self,
        admin: User,
        user_id: str,
        buyer_id: str,
        access_level: str,
        client_ip: Optional[str],
    ):
        if access_level not in ("read", "admin"):
            raise HTTPException(
                status_code=400,
                detail="Seat access level must be 'read' or 'admin'",
            )

        permission_id = str(uuid.uuid4())
        permission = await self._auth.grant_user_buyer_seat_permission(
            permission_id=permission_id,
            user_id=user_id,
            buyer_id=buyer_id,
            access_level=access_level,
            granted_by=admin.id,
        )

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="grant_buyer_seat_permission",
            user_id=admin.id,
            resource_type="buyer_seat_permission",
            resource_id=permission_id,
            details=json.dumps(
                {
                    "target_user": user_id,
                    "buyer_id": buyer_id,
                    "access_level": access_level,
                }
            ),
            ip_address=client_ip,
        )

        return permission

    async def revoke_buyer_seat_permission(
        self,
        admin: User,
        user_id: str,
        buyer_id: str,
        client_ip: Optional[str],
    ) -> bool:
        revoked = await self._auth.revoke_user_buyer_seat_permission(user_id, buyer_id)
        if not revoked:
            raise HTTPException(status_code=404, detail="Seat permission not found")

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="revoke_buyer_seat_permission",
            user_id=admin.id,
            resource_type="buyer_seat_permission",
            details=json.dumps(
                {
                    "target_user": user_id,
                    "buyer_id": buyer_id,
                }
            ),
            ip_address=client_ip,
        )

        return True

    async def grant_permission(
        self,
        admin: User,
        user_id: str,
        service_account_id: str,
        permission_level: str,
        client_ip: Optional[str],
    ):
        if permission_level not in ("read", "write", "admin"):
            raise HTTPException(
                status_code=400,
                detail="Permission level must be 'read', 'write', or 'admin'",
            )

        permission_id = str(uuid.uuid4())
        permission = await self._auth.grant_permission(
            permission_id=permission_id,
            user_id=user_id,
            service_account_id=service_account_id,
            permission_level=permission_level,
            granted_by=admin.id,
        )

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="grant_permission",
            user_id=admin.id,
            resource_type="permission",
            resource_id=permission_id,
            details=json.dumps(
                {
                    "target_user": user_id,
                    "service_account_id": service_account_id,
                    "permission_level": permission_level,
                }
            ),
            ip_address=client_ip,
        )

        return permission

    async def revoke_permission(
        self,
        admin: User,
        user_id: str,
        service_account_id: str,
        client_ip: Optional[str],
    ) -> bool:
        revoked = await self._auth.revoke_permission(user_id, service_account_id)
        if not revoked:
            raise HTTPException(status_code=404, detail="Permission not found")

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="revoke_permission",
            user_id=admin.id,
            resource_type="permission",
            details=json.dumps(
                {
                    "target_user": user_id,
                    "service_account_id": service_account_id,
                }
            ),
            ip_address=client_ip,
        )

        return True

    async def get_audit_logs(
        self,
        user_id: Optional[str],
        action: Optional[str],
        resource_type: Optional[str],
        days: int,
        limit: int,
        offset: int,
    ):
        return await self._auth.get_audit_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            since_days=days,
            limit=limit,
            offset=offset,
        )

    async def get_settings(self) -> dict:
        return await self._auth.get_all_settings()

    async def update_setting(
        self,
        admin: User,
        key: str,
        value: str,
        client_ip: Optional[str],
    ) -> dict[str, str]:
        if key == "audit_retention_days":
            try:
                days = int(value)
                if days not in (0, 30, 60, 90, 120):
                    raise ValueError("Invalid retention period")
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Audit retention must be 0 (unlimited), 30, 60, 90, or 120 days",
                ) from exc

        if key == "multi_user_enabled" and value not in ("0", "1"):
            raise HTTPException(
                status_code=400,
                detail="multi_user_enabled must be '0' or '1'",
            )

        await self._auth.set_setting(key, value, updated_by=admin.id)

        await self._auth.log_audit(
            audit_id=str(uuid.uuid4()),
            action="update_setting",
            user_id=admin.id,
            resource_type="setting",
            resource_id=key,
            details=json.dumps({"value": value}),
            ip_address=client_ip,
        )

        return {"status": "success", "key": key, "value": value}

    async def get_admin_stats(self) -> dict[str, Any]:
        users = await self._auth.get_users()
        active_users = [u for u in users if u.is_active]
        admin_users = [u for u in users if u.role == "sudo"]

        expected_report_kinds = [
            "catscan-quality",
            "catscan-bidsinauction",
            "catscan-pipeline-geo",
            "catscan-pipeline",
            "catscan-bid-filtering",
        ]

        report_health = {
            "expected_per_seat": len(expected_report_kinds),
            "seats": [],
        }

        seats = await self._repo.get_active_buyer_ids()

        for seat_id in seats:
            latest_date = await self._repo.get_latest_gmail_import_date(seat_id)
            if not latest_date:
                report_health["seats"].append(
                    {
                        "buyer_id": seat_id,
                        "latest_date": None,
                        "received": 0,
                        "missing": expected_report_kinds,
                        "failed": [],
                    }
                )
                continue

            report_rows = await self._repo.get_gmail_import_runs(seat_id, latest_date)
            received_kinds = set()
            failed_kinds = set()
            for row in report_rows:
                if row["success"]:
                    received_kinds.add(row["report_kind"])
                else:
                    failed_kinds.add(row["report_kind"])

            missing_kinds = [
                kind for kind in expected_report_kinds if kind not in received_kinds
            ]
            report_health["seats"].append(
                {
                    "buyer_id": seat_id,
                    "latest_date": latest_date,
                    "received": len(received_kinds),
                    "missing": missing_kinds,
                    "failed": sorted(failed_kinds),
                }
            )

        return {
            "total_users": len(users),
            "active_users": len(active_users),
            "admin_users": len(admin_users),
            "multi_user_enabled": await self._auth.is_multi_user_enabled(),
            "report_health": report_health,
        }

    async def get_diagnostics(self) -> dict[str, Any]:
        diagnostics = {}

        seats_rows = await self._repo.list_buyer_seats_with_creative_count()
        diagnostics["buyer_seats"] = [
            {
                "buyer_id": row["buyer_id"],
                "bidder_id": row["bidder_id"],
                "display_name": row["display_name"],
                "active": bool(row["active"]),
                "creative_count": row["creative_count"],
                "last_synced": row["last_synced"],
                "service_account_id": row["service_account_id"],
            }
            for row in seats_rows
        ]

        campaigns_rows = await self._repo.list_campaign_samples(limit=20)
        campaigns_data = []
        for row in campaigns_rows:
            creative_ids_raw = row["creative_ids"] or "[]"
            try:
                creative_ids = (
                    json.loads(creative_ids_raw)
                    if isinstance(creative_ids_raw, str)
                    else creative_ids_raw
                )
            except Exception:
                creative_ids = []
            campaigns_data.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "creative_ids_count": len(creative_ids) if creative_ids else 0,
                    "sample_ids": creative_ids[:5] if creative_ids else [],
                }
            )
        diagnostics["campaigns_status"] = {
            "campaigns": campaigns_data,
            "total_campaigns": len(campaigns_data),
        }

        thumbnail_rows = await self._repo.get_thumbnail_status_summary()
        thumbnail_data = {}
        for row in thumbnail_rows:
            fmt = row["format"] or "UNKNOWN"
            thumbnail_data[fmt] = {
                "total": row["total"],
                "with_thumbnail": row["with_thumbnail"],
                "missing_thumbnail": row["total"] - row["with_thumbnail"],
            }
        diagnostics["thumbnail_status"] = thumbnail_data

        import_rows = await self._repo.get_import_history_by_buyer()
        diagnostics["import_history"] = [
            {
                "buyer_id": row["buyer_id"],
                "import_count": row["import_count"],
                "last_import": str(row["last_import"]) if row["last_import"] else None,
                "total_records": row["total_records"],
            }
            for row in import_rows
        ]

        id_rows = await self._repo.get_creative_id_samples(limit=5)
        diagnostics["creative_id_samples"] = [
            {
                "id": row["id"],
                "type": row["type"],
                "account_id": row["account_id"],
            }
            for row in id_rows
        ]

        return diagnostics

    async def activate_inactive_seats(self) -> dict[str, Any]:
        inactive_count = await self._repo.count_inactive_seats()
        await self._repo.activate_inactive_seats()
        return {
            "status": "success",
            "message": f"Activated {inactive_count} buyer seat(s)",
            "seats_activated": inactive_count,
        }
