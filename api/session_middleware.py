"""Session-based authentication middleware for Cat-Scan.

This middleware validates session cookies and attaches user information to requests.
It works alongside the existing API key middleware for backward compatibility.

For open-source single-user mode, authentication can be disabled via settings.
"""

import asyncio
import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from storage.database import DB_PATH
from storage.repositories.user_repository import UserRepository, User

logger = logging.getLogger(__name__)

# Session cookie name (must match auth_v2.py)
SESSION_COOKIE_NAME = "rtbcat_session"

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login",
    "/auth/check",
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


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce session-based authentication.

    This middleware:
    1. Checks for a session cookie
    2. Validates the session in the database
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
            repo = UserRepository(DB_PATH)
            self._multi_user_enabled = await repo.is_multi_user_enabled()
            self._multi_user_checked = True
        except Exception as e:
            logger.warning(f"Failed to check multi-user mode: {e}")
            self._multi_user_enabled = True

        return self._multi_user_enabled

    async def _validate_session(self, session_id: str) -> Optional[User]:
        """Validate session and return user if valid."""
        try:
            repo = UserRepository(DB_PATH)
            return await repo.validate_session(session_id)
        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            return None

    async def dispatch(self, request: Request, call_next):
        # Allow public paths without authentication
        if is_public_path(request.url.path):
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
