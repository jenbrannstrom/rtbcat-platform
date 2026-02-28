"""Bootstrap endpoint for first-sudo provisioning.

When CATSCAN_BOOTSTRAP_TOKEN is set, the first admin must be created via
POST /auth/bootstrap with the correct token.  This prevents an attacker
from racing to become admin on a fresh deploy.

When CATSCAN_BOOTSTRAP_TOKEN is *not* set, the legacy behaviour (first
OAuth/password user auto-promoted to sudo) remains active for dev-friendly
local workflows.
"""

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Bootstrap"])

SESSION_COOKIE_NAME = "rtbcat_session"

_auth_service: AuthService | None = None


def _get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# ---------------------------------------------------------------------------
# Shared helpers (imported by session_middleware, auth_password, auth_authing)
# ---------------------------------------------------------------------------

def is_bootstrap_token_required() -> bool:
    """Return True when CATSCAN_BOOTSTRAP_TOKEN is set (production mode)."""
    return bool(os.environ.get("CATSCAN_BOOTSTRAP_TOKEN", "").strip())


async def is_bootstrap_completed() -> bool:
    """Return True when bootstrap_completed == '1' in system_settings."""
    auth_svc = _get_auth_service()
    value = await auth_svc.get_setting("bootstrap_completed")
    return value == "1"


async def _auto_heal_bootstrap_status() -> None:
    """If users already exist but bootstrap_completed is not set, mark it.

    This prevents lockout on existing deployments that upgrade to a version
    with bootstrap guards.
    """
    auth_svc = _get_auth_service()
    user_count = await auth_svc.count_users()
    if user_count > 0 and not await is_bootstrap_completed():
        await auth_svc.set_setting("bootstrap_completed", "1", updated_by="auto_heal")
        logger.info(
            "Auto-healed bootstrap_completed flag (found %d existing users)",
            user_count,
        )


# ---------------------------------------------------------------------------
# Bootstrap endpoint
# ---------------------------------------------------------------------------

class BootstrapRequest(BaseModel):
    bootstrap_token: str
    email: EmailStr
    password: str | None = None
    display_name: str | None = None


@router.post("/bootstrap")
async def bootstrap_first_admin(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
):
    """Create the first sudo user using the bootstrap token.

    Requires:
    - CATSCAN_BOOTSTRAP_TOKEN env var is set
    - No users exist yet (bootstrap not completed)
    - Token in request matches env var
    """
    expected_token = os.environ.get("CATSCAN_BOOTSTRAP_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=403,
            detail="Bootstrap endpoint is disabled (no CATSCAN_BOOTSTRAP_TOKEN configured).",
        )

    if await is_bootstrap_completed():
        raise HTTPException(
            status_code=403,
            detail="Bootstrap already completed. Use normal login.",
        )

    auth_svc = _get_auth_service()
    user_count = await auth_svc.count_users()
    if user_count > 0:
        # Mark bootstrap as completed so we don't get stuck
        await auth_svc.set_setting("bootstrap_completed", "1", updated_by="auto_heal")
        raise HTTPException(
            status_code=403,
            detail="Users already exist. Bootstrap is no longer available.",
        )

    # Constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(payload.bootstrap_token, expected_token):
        logger.warning("Bootstrap attempt with invalid token from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=403, detail="Invalid bootstrap token.")

    # Create first sudo user
    email = payload.email.lower().strip()
    user_id = str(uuid.uuid4())
    display_name = payload.display_name or email.split("@")[0].replace(".", " ").title()

    user = await auth_svc.create_user(
        user_id=user_id,
        email=email,
        display_name=display_name,
        role="sudo",
    )

    # If password provided, store it
    if payload.password:
        from api.auth_password import hash_password, _set_user_password_hash
        password_hash = hash_password(payload.password)
        await _set_user_password_hash(user_id, password_hash)

    # Mark bootstrap as completed
    await auth_svc.set_setting("bootstrap_completed", "1", updated_by=user_id)

    # Create session
    session_id = str(uuid.uuid4())
    await auth_svc.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        duration_days=30,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        secure=request.url.scheme == "https",
    )

    logger.info("Bootstrap completed: first admin %s created", email)

    return {
        "status": "ok",
        "message": "First sudo user created successfully.",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
    }
