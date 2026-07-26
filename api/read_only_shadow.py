"""Hard guard for migration shadow deployments backed by a read-only database."""

from __future__ import annotations

import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def read_only_shadow_enabled() -> bool:
    """Return whether the process is an explicitly read-only migration shadow."""

    return os.getenv("CATSCAN_READ_ONLY_SHADOW", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class ReadOnlyShadowMiddleware(BaseHTTPMiddleware):
    """Reject state-changing HTTP requests before route code can execute."""

    async def dispatch(self, request: Request, call_next):
        if read_only_shadow_enabled() and request.method.upper() not in SAFE_METHODS:
            return JSONResponse(
                status_code=405,
                content={
                    "detail": (
                        "State-changing requests are disabled on the read-only "
                        "migration shadow."
                    )
                },
                headers={"X-CatScan-Shadow": "read-only"},
            )
        response = await call_next(request)
        if read_only_shadow_enabled():
            response.headers["X-CatScan-Shadow"] = "read-only"
        return response
