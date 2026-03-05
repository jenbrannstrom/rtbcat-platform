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
import ipaddress
import re
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from api.auth_bootstrap import is_bootstrap_token_required, is_bootstrap_completed
from api.auth_providers import is_authing_login_enabled
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


def _is_auto_user_provisioning_enabled() -> bool:
    """Whether unknown OIDC users may be auto-created after bootstrap."""
    return os.environ.get("CATSCAN_ALLOW_AUTO_USER_PROVISIONING", "").lower() in ("1", "true", "yes")


def _is_trusted_proxy_request(request: Request) -> bool:
    """Return True when request appears to come from a trusted local/private proxy."""
    if not request.client or not request.client.host:
        return False
    try:
        client_ip = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    return client_ip.is_loopback or client_ip.is_private


def _get_request_scheme(request: Request) -> str:
    """Resolve request scheme, honoring forwarded proto from trusted proxies only."""
    scheme = request.url.scheme
    if _is_trusted_proxy_request(request):
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            proto = forwarded_proto.split(",")[0].strip().lower()
            if proto in {"http", "https"}:
                scheme = proto
    return scheme


def _is_secure_request(request: Request) -> bool:
    return _get_request_scheme(request) == "https"


def _sanitize_callback_url(callback_url: str) -> str:
    """Allow only local relative redirects to prevent open redirects."""
    if not callback_url:
        return "/"
    value = urllib.parse.unquote(callback_url).strip()
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme or parsed.netloc:
        return "/"
    return value


def _normalize_host(value: str) -> Optional[str]:
    """Normalize and validate Host header style values."""
    host = (value or "").strip()
    if not host or "/" in host or "\\" in host or " " in host:
        return None
    if not re.fullmatch(r"[A-Za-z0-9.\-:]+", host):
        return None
    return host


def _get_callback_url(request: Request) -> str:
    """Build the callback URL for Authing redirect."""
    scheme = _get_request_scheme(request)
    host = _normalize_host(request.url.netloc) or request.url.netloc
    if _is_trusted_proxy_request(request):
        forwarded_host = request.headers.get("X-Forwarded-Host")
        if forwarded_host:
            # RFC7239-style forwarding can include multiple hosts; use left-most
            forwarded_value = forwarded_host.split(",")[0].strip()
            host = _normalize_host(forwarded_value) or host
    return f"{scheme}://{host}/api/auth/authing/callback"


# ==================== Auth Endpoints ====================

@router.get("/login")
async def authing_login(request: Request, callback_url: str = "/"):
    """Redirect to Authing login page.

    Args:
        callback_url: URL to redirect to after successful login (default: /)
    """
    if not is_authing_login_enabled():
        raise HTTPException(status_code=404, detail="Authing login is disabled")

    config = get_authing_config()
    safe_callback_url = _sanitize_callback_url(callback_url)

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
        value=f"{state}|{safe_callback_url}",
        httponly=True,
        secure=_is_secure_request(request),
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
    if not is_authing_login_enabled():
        return RedirectResponse(
            url="/login?error=Authing+login+is+disabled",
            status_code=302,
        )

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
    if not state_cookie or "|" not in state_cookie:
        logger.warning("Authing callback missing/invalid state cookie format")
        return RedirectResponse(
            url="/login?error=Invalid+state",
            status_code=302,
        )

    cookie_state, callback_url = state_cookie.split("|", 1)
    if not secrets.compare_digest(cookie_state, state):
        logger.warning("Authing callback state mismatch")
        return RedirectResponse(
            url="/login?error=Invalid+state",
            status_code=302,
        )

    callback_url = _sanitize_callback_url(callback_url)

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
        # Auto-create user (first user gets sudo role)
        user_id = str(uuid.uuid4())
        user_count = await auth_svc.count_users()
        if user_count == 0 and is_bootstrap_token_required() and not await is_bootstrap_completed():
            logger.warning(
                "Blocked Authing first-user auto-sudo for %s (CATSCAN_BOOTSTRAP_TOKEN is set, use /auth/bootstrap)",
                email,
            )
            return RedirectResponse(
                url="/login?error=First+admin+must+be+created+via+bootstrap+token.+See+server+logs.",
                status_code=302,
            )
        if user_count > 0 and not _is_auto_user_provisioning_enabled():
            logger.warning(
                "Blocked Authing auto-provisioning for %s (CATSCAN_ALLOW_AUTO_USER_PROVISIONING=false)",
                email,
            )
            return RedirectResponse(
                url="/login?error=User+provisioning+disabled.+Contact+administrator",
                status_code=302,
            )
        role = "sudo" if user_count == 0 else "read"

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
        secure=_is_secure_request(request),
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # 30 days
    )

    # Clear state cookie
    redirect_response.delete_cookie(key=STATE_COOKIE_NAME)

    return redirect_response
