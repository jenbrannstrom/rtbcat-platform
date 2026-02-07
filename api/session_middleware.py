"""Session-based authentication middleware for Cat-Scan.

This middleware validates session cookies and attaches user information to requests.
It works alongside the existing API key middleware for backward compatibility.

For open-source single-user mode, authentication can be disabled via settings.

OAuth2 Proxy Support:
When deployed behind OAuth2 Proxy (e.g., on GCP), the X-Email header from
OAuth2 Proxy is trusted for authentication. Users are auto-created on first access.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from services.auth_service import AuthService, User

logger = logging.getLogger(__name__)

# Session cookie name (must match auth_oauth_proxy.py)
SESSION_COOKIE_NAME = "rtbcat_session"

# OAuth2 Proxy header (set by nginx auth_request)
OAUTH2_PROXY_EMAIL_HEADER = "X-Email"
OAUTH2_PROXY_USER_HEADER = "X-User"

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/check",
    "/auth/me",
    "/auth/login",  # Password login
    "/auth/register",  # First user registration
    "/auth/authing/login",  # Authing OIDC login redirect
    "/auth/authing/callback",  # Authing OIDC callback
    "/gmail/import/scheduled",  # Cloud Scheduler (uses secret header)
    "/precompute/refresh/scheduled",  # Cloud Scheduler (uses secret header)
    "/precompute/health",  # Monitoring (uses secret header)
}

# Path prefixes that are public
PUBLIC_PREFIXES = [
    "/docs",
    "/redoc",
]


def is_public_path(path: str) -> bool:
    """Check if the path is public (no auth required)."""
    if path in PUBLIC_PATHS:
        return True

    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


# Singleton AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def is_oauth2_proxy_enabled() -> bool:
    """Check if OAuth2 Proxy authentication is enabled.

    Returns True if we're behind OAuth2 Proxy (GCP deployment).
    """
    # Trust X-Email header when OAUTH2_PROXY_ENABLED env var is set
    # or when running in GCP (detected by presence of Google metadata)
    return os.environ.get("OAUTH2_PROXY_ENABLED", "").lower() in ("1", "true", "yes")


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce session-based authentication.

    This middleware:
    1. Checks for OAuth2 Proxy headers (X-Email) - trusted in GCP deployment
    2. Falls back to session cookie validation
    3. Attaches the user to request.state.user

    For API key authentication (backward compatibility), it also checks
    the Authorization header if no session cookie is present.

    In single-user mode (multi_user_enabled=0), authentication is optional.
    """

    def __init__(self, app, require_auth: bool = True):
        """Initialize middleware.

        Args:
            app: FastAPI application.
            require_auth: Whether to require authentication (default True).
                         Set to False for open-source single-user mode.
        """
        super().__init__(app)
        self.require_auth = require_auth
        self._multi_user_checked = False
        self._multi_user_enabled = True

    async def _check_multi_user_mode(self) -> bool:
        """Check if multi-user mode is enabled (cached)."""
        if self._multi_user_checked:
            return self._multi_user_enabled

        try:
            auth_svc = get_auth_service()
            self._multi_user_enabled = await auth_svc.is_multi_user_enabled()
            self._multi_user_checked = True
        except Exception as e:
            logger.warning(f"Failed to check multi-user mode: {e}")
            self._multi_user_enabled = True

        return self._multi_user_enabled

    async def _validate_session(self, session_id: str) -> Optional[User]:
        """Validate session and return user if valid."""
        try:
            auth_svc = get_auth_service()
            return await auth_svc.validate_session(session_id)
        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            return None

    async def _get_or_create_oauth2_user(self, email: str, request: Request) -> Optional[User]:
        """Get or create a user from OAuth2 Proxy authentication.

        When behind OAuth2 Proxy, we trust the X-Email header.
        Users are auto-created on first access with admin role.

        On DB failure, sets request.state.auth_error so /auth/check can
        return 503 instead of silently claiming "not authenticated".
        """
        try:
            auth_svc = get_auth_service()
            email = email.lower().strip()

            # Try to find existing user
            user = await auth_svc.get_user_by_email(email)
            if user:
                return user

            # Auto-create user from OAuth2 Proxy
            user_id = str(uuid.uuid4())
            display_name = email.split("@")[0].replace(".", " ").title()

            # First user gets admin role, others get user role
            user_count = await auth_svc.count_users()
            role = "admin" if user_count == 0 else "user"

            user = await auth_svc.create_user(
                user_id=user_id,
                email=email,
                display_name=display_name,
                role=role,
            )

            logger.info(f"Auto-created user from OAuth2 Proxy: {email} (role={role})")
            return user

        except Exception as e:
            logger.error(f"Failed to get/create OAuth2 user: {e}")
            # Propagate DB error so /auth/check returns 503, not "unauthenticated"
            request.state.auth_error = "database_unavailable"
            request.state.auth_error_detail = str(e)
            return None

    async def dispatch(self, request: Request, call_next):
        # Allow public paths without authentication
        if is_public_path(request.url.path):
            # Still attach user if available (for /auth/check, /auth/me etc.)
            oauth2_email = request.headers.get(OAUTH2_PROXY_EMAIL_HEADER)
            if oauth2_email and is_oauth2_proxy_enabled():
                user = await self._get_or_create_oauth2_user(oauth2_email, request)
                if user:
                    request.state.user = user
                    request.state.oauth2_authenticated = True
            elif request.cookies.get(SESSION_COOKIE_NAME):
                user = await self._validate_session(request.cookies[SESSION_COOKIE_NAME])
                if user:
                    request.state.user = user
            return await call_next(request)

        # Check for OAuth2 Proxy authentication first (GCP deployment)
        oauth2_email = request.headers.get(OAUTH2_PROXY_EMAIL_HEADER)
        if oauth2_email and is_oauth2_proxy_enabled():
            user = await self._get_or_create_oauth2_user(oauth2_email, request)
            if user:
                request.state.user = user
                request.state.oauth2_authenticated = True
                return await call_next(request)

        # Check multi-user mode
        multi_user_enabled = await self._check_multi_user_mode()

        # In single-user mode, authentication is optional
        if not multi_user_enabled:
            # Still try to attach user if session exists (for audit logging)
            session_id = request.cookies.get(SESSION_COOKIE_NAME)
            if session_id:
                user = await self._validate_session(session_id)
                if user:
                    request.state.user = user
            return await call_next(request)

        # Multi-user mode: require authentication
        session_id = request.cookies.get(SESSION_COOKIE_NAME)

        if not session_id:
            # Check for API key authentication (backward compatibility)
            from api.auth import get_api_key
            import secrets

            api_key = get_api_key()
            if api_key:
                auth_header = request.headers.get("Authorization")
                if auth_header:
                    parts = auth_header.split()
                    if len(parts) == 2 and parts[0].lower() == "bearer":
                        if secrets.compare_digest(parts[1], api_key):
                            # API key auth successful - allow without user context
                            return await call_next(request)

            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required. Please log in."},
            )

        # Validate session
        user = await self._validate_session(session_id)

        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Session expired or invalid. Please log in again."},
            )

        # Attach user to request state
        request.state.user = user

        return await call_next(request)
