"""OAuth2 Proxy authentication for Cat-Scan.

This module provides user authentication via OAuth2 Proxy (Google Auth):
- Users authenticate via Google through OAuth2 Proxy
- X-Email header from OAuth2 Proxy identifies the user
- Users are auto-created on first login (first user gets sudo role)
- Session middleware handles all authentication

Password-based login has been removed - Google Auth only.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from api.auth_providers import get_auth_provider_status
from api.request_trust import get_client_ip
from services.auth_service import AuthService

# Session cookie name (used by OAuth2 Proxy flow)
SESSION_COOKIE_NAME = "rtbcat_session"

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==================== Request/Response Models ====================

class UserInfo(BaseModel):
    """Current user information."""
    id: str
    email: str
    display_name: Optional[str]
    role: str
    is_admin: bool
    permissions: list[str]  # List of service account IDs (legacy)
    default_language: Optional[str] = None
    # RBAC v2 fields
    global_role: Optional[str] = None  # "sudo" for global users, else None
    seat_permissions: Optional[dict[str, str]] = None  # {buyer_id: "read"|"admin"}


class AuthProvidersResponse(BaseModel):
    """Runtime auth provider availability for the login page."""

    password: bool
    google: bool
    authing: bool
    enabled_methods: list[str]
    default_method: str


# ==================== Helper Functions ====================

# Singleton AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from trusted request metadata."""
    return get_client_ip(request)


# ==================== Auth Endpoints ====================

@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session.

    Clears any session cookies. With OAuth2 Proxy, user will need to
    re-authenticate through Google on next request.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        auth_svc = get_auth_service()
        user = await auth_svc.validate_session(session_id)
        await auth_svc.delete_session(session_id)

        if user:
            await auth_svc.log_audit(
                audit_id=str(uuid.uuid4()),
                action="logout",
                user_id=user.id,
                resource_type="auth",
                ip_address=_get_client_ip(request),
            )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )

    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(request: Request):
    """Get current authenticated user information.

    Returns user details and their permissions (service account access).
    User is authenticated via OAuth2 Proxy (X-Email header).
    """
    # User should be set by session middleware from OAuth2 Proxy headers
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        auth_svc = get_auth_service()
        permissions = await auth_svc.get_user_service_account_ids(user.id)
        # RBAC v2: build seat permissions map for non-sudo users
        is_sudo = user.role == "sudo"
        global_role = "sudo" if is_sudo else None
        seat_perms = {} if is_sudo else await auth_svc.get_user_buyer_seat_access_map(user.id)
        return UserInfo(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_admin=is_sudo,
            permissions=permissions,
            default_language=getattr(user, "default_language", None),
            global_role=global_role,
            seat_permissions=seat_perms,
        )

    # No user means OAuth2 Proxy didn't authenticate them
    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Please sign in with Google."
    )


@router.get("/check")
async def check_auth_status(request: Request):
    """Check if user is authenticated.

    Returns authentication status and user info if authenticated.
    Returns 503 with error details if the auth system is degraded
    (e.g. database unreachable), so the frontend can show a retry
    screen instead of triggering an infinite OAuth redirect loop.
    """
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        is_sudo = user.role == "sudo"
        return {
            "authenticated": True,
            "auth_method": "oauth2_proxy",
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "is_admin": is_sudo,
                "default_language": getattr(user, "default_language", None),
                "global_role": "sudo" if is_sudo else None,
            },
        }

    # Distinguish "not authenticated" from "auth system broken"
    auth_error = getattr(request.state, "auth_error", None)
    if auth_error:
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "authenticated": False,
                "user": None,
                "error": auth_error,
                "detail": getattr(request.state, "auth_error_detail", "Service temporarily unavailable"),
            },
        )

    return {
        "authenticated": False,
        "user": None,
    }


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers():
    """Return enabled login providers so UI can present valid choices."""
    return AuthProvidersResponse(**get_auth_provider_status())


# ==================== Maintenance Functions ====================

async def cleanup_sessions():
    """Cleanup expired sessions and old login attempts.

    Should be called periodically (e.g., daily cron).
    """
    auth_svc = get_auth_service()
    sessions_deleted = await auth_svc.cleanup_expired_sessions()
    return {
        "sessions_deleted": sessions_deleted,
    }


async def cleanup_audit_logs():
    """Cleanup old audit logs based on retention setting.

    Should be called periodically (e.g., daily cron).
    """
    auth_svc = get_auth_service()

    retention_str = await auth_svc.get_setting("audit_retention_days")
    retention_days = int(retention_str) if retention_str else 60

    if retention_days <= 0:
        return {"deleted": 0, "message": "Retention set to unlimited"}

    deleted = await auth_svc.cleanup_old_audit_logs(retention_days)
    return {"deleted": deleted, "retention_days": retention_days}
