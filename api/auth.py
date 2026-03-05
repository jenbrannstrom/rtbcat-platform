"""API Key authentication for Cat-Scan.

Simple bearer token authentication for securing the API when exposed remotely.
The API key is read from CATSCAN_API_KEY environment variable.

Usage:
    # Set the API key on the server
    export CATSCAN_API_KEY="your-secret-key-here"

    # Client requests must include the header
    Authorization: Bearer your-secret-key-here
"""

import secrets
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from services.secrets_manager import get_secrets_manager

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/providers",
}


def get_api_key() -> Optional[str]:
    """Get the API key from environment variable."""
    return get_secrets_manager().get("CATSCAN_API_KEY")


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


def is_public_path(path: str) -> bool:
    """Check if the path is public (no auth required)."""
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce API key authentication.

    If CATSCAN_API_KEY is not set, authentication is disabled (local mode).
    If set, all requests (except public paths) must include valid Bearer token.
    """

    async def dispatch(self, request: Request, call_next):
        api_key = get_api_key()

        # If no API key configured, allow all requests (local mode)
        if not api_key:
            return await call_next(request)

        # Allow public paths without auth
        if is_public_path(request.url.path):
            return await call_next(request)

        # If an upstream auth middleware already authenticated the user,
        # do not force API key auth for browser/session traffic.
        if getattr(request.state, "user", None) or getattr(request.state, "oauth2_authenticated", False):
            return await call_next(request)

        # Check for Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header. Use: Authorization: Bearer <api-key>"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header format. Use: Authorization: Bearer <api-key>"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = parts[1]

        # Validate token
        if not secrets.compare_digest(token, api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
