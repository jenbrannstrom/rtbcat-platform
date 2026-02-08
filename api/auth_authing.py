"""Authing OIDC authentication for Cat-Scan.

This module provides OIDC-based authentication via Authing:
- /auth/authing/login: Redirects to Authing login page
- /auth/authing/callback: Handles Authing OIDC callback
- Token validation and user session creation

Environment variables:
- AUTHING_APP_ID: Authing application ID
- AUTHING_APP_SECRET: Authing application secret
- AUTHING_ISSUER: Authing OIDC issuer URL (e.g., https://catscan.authing.cn/oidc)
"""

import uuid
import logging
import secrets
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from services.auth_service import AuthService
from services.secrets_manager import get_secrets_manager

logger = logging.getLogger(__name__)

# Session cookie name (must match other auth modules)
SESSION_COOKIE_NAME = "rtbcat_session"

# State cookie for CSRF protection
STATE_COOKIE_NAME = "rtbcat_auth_state"

router = APIRouter(prefix="/auth/authing", tags=["Authing Authentication"])


# ==================== Configuration ====================

def get_authing_config() -> dict:
    """Get Authing configuration from environment variables."""
    secrets_mgr = get_secrets_manager()
    app_id = secrets_mgr.get("AUTHING_APP_ID")
    app_secret = secrets_mgr.get("AUTHING_APP_SECRET")
    issuer = secrets_mgr.get("AUTHING_ISSUER")

    if not all([app_id, app_secret, issuer]):
        raise HTTPException(
            status_code=500,
            detail="Authing not configured. Set AUTHING_APP_ID, AUTHING_APP_SECRET, and AUTHING_ISSUER."
        )

    return {
        "app_id": app_id,
        "app_secret": app_secret,
        "issuer": issuer.rstrip("/"),
        "authorization_endpoint": f"{issuer.rstrip('/')}/auth",
        "token_endpoint": f"{issuer.rstrip('/')}/token",
        "userinfo_endpoint": f"{issuer.rstrip('/')}/me",
    }


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


def _get_callback_url(request: Request) -> str:
    """Build the callback URL for Authing redirect."""
    # Use X-Forwarded headers if behind proxy
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("X-Forwarded-Host", request.url.netloc)

    return f"{scheme}://{host}/api/auth/authing/callback"


# ==================== Auth Endpoints ====================

@router.get("/login")
async def authing_login(request: Request, callback_url: str = "/"):
    """Redirect to Authing login page.

    Args:
        callback_url: URL to redirect to after successful login (default: /)
    """
    config = get_authing_config()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "client_id": config["app_id"],
        "redirect_uri": _get_callback_url(request),
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
    }

    auth_url = f"{config['authorization_endpoint']}?{urllib.parse.urlencode(params)}"

    # Set state cookie for CSRF validation
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=f"{state}:{callback_url}",
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=600,  # 10 minutes
    )

    return response


@router.get("/callback")
async def authing_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """Handle Authing OIDC callback.

    Exchanges authorization code for tokens, creates/updates user, creates session.
    """
    # Handle errors from Authing
    if error:
        logger.error(f"Authing error: {error} - {error_description}")
        return RedirectResponse(
            url=f"/login?error={urllib.parse.quote(error_description or error)}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url="/login?error=Invalid+callback+parameters",
            status_code=302,
        )

    # Validate state (CSRF protection)
    state_cookie = request.cookies.get(STATE_COOKIE_NAME)
    if not state_cookie or not state_cookie.startswith(state):
        logger.warning("Authing callback state mismatch")
        return RedirectResponse(
            url="/login?error=Invalid+state",
            status_code=302,
        )

    # Extract callback URL from state cookie
    callback_url = "/"
    if ":" in state_cookie:
        _, callback_url = state_cookie.split(":", 1)

    config = get_authing_config()

    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                config["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": config["app_id"],
                    "client_secret": config["app_secret"],
                    "code": code,
                    "redirect_uri": _get_callback_url(request),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                logger.error(f"Authing token error: {token_response.text}")
                return RedirectResponse(
                    url="/login?error=Failed+to+get+token",
                    status_code=302,
                )

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            if not access_token:
                logger.error("No access token in Authing response")
                return RedirectResponse(
                    url="/login?error=No+access+token",
                    status_code=302,
                )

            # Get user info from Authing
            userinfo_response = await client.get(
                config["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_response.status_code != 200:
                logger.error(f"Authing userinfo error: {userinfo_response.text}")
                return RedirectResponse(
                    url="/login?error=Failed+to+get+user+info",
                    status_code=302,
                )

            userinfo = userinfo_response.json()

    except Exception as e:
        logger.error(f"Authing callback error: {e}")
        return RedirectResponse(
            url="/login?error=Authentication+failed",
            status_code=302,
        )

    # Extract user info
    email = userinfo.get("email")
    if not email:
        # Try alternative field names
        email = userinfo.get("preferred_username") or userinfo.get("phone_number")

    if not email:
        logger.error(f"No email in Authing userinfo: {userinfo}")
        return RedirectResponse(
            url="/login?error=No+email+in+user+info",
            status_code=302,
        )

    email = email.lower().strip()
    display_name = userinfo.get("name") or userinfo.get("nickname") or email.split("@")[0]

    # Get or create user
    auth_svc = get_auth_service()

    user = await auth_svc.get_user_by_email(email)
    if not user:
        # Auto-create user (first user gets admin role)
        user_id = str(uuid.uuid4())
        user_count = await auth_svc.count_users()
        role = "admin" if user_count == 0 else "user"

        user = await auth_svc.create_user(
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
        )
        logger.info(f"Created user from Authing: {email} (role={role})")
    else:
        # Update last login
        await auth_svc.update_last_login(user.id)

    # Create session
    session_id = str(uuid.uuid4())
    await auth_svc.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        duration_days=30,
    )

    # Log audit
    await auth_svc.log_audit(
        audit_id=str(uuid.uuid4()),
        action="login",
        user_id=user.id,
        resource_type="auth",
        details="authing_oidc",
        ip_address=_get_client_ip(request),
    )

    # Redirect with session cookie
    redirect_response = RedirectResponse(url=callback_url, status_code=302)

    # Set session cookie
    redirect_response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # 30 days
    )

    # Clear state cookie
    redirect_response.delete_cookie(key=STATE_COOKIE_NAME)

    return redirect_response
