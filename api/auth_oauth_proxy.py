"""OAuth2 Proxy authentication for Cat-Scan.

This module provides user authentication via OAuth2 Proxy (Google Auth):
- Users authenticate via Google through OAuth2 Proxy
- X-Email header from OAuth2 Proxy identifies the user
- Users are auto-created on first login (first user gets admin role)
- Session middleware handles all authentication

Password-based login has been removed - Google Auth only.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

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
    permissions: list[str]  # List of service account IDs
    default_language: Optional[str] = None


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
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


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
        return UserInfo(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_admin=user.role == "admin",
            permissions=permissions,
            default_language=getattr(user, "default_language", None),
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
    User is authenticated via OAuth2 Proxy.
    """
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        return {
            "authenticated": True,
            "auth_method": "oauth2_proxy",
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "is_admin": user.role == "admin",
                "default_language": getattr(user, "default_language", None),
            },
        }

    return {
        "authenticated": False,
        "user": None,
    }


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
