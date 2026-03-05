"""RTBcat Creative Intelligence - API Module.

This module provides the FastAPI application for the
creative intelligence REST API.
"""

from __future__ import annotations

__all__ = ["app", "create_app"]


def __getattr__(name: str):
    """Lazily import app factory to avoid heavy side effects at package import time."""
    if name in {"app", "create_app"}:
        from .main import app, create_app
        return app if name == "app" else create_app
    raise AttributeError(f"module 'api' has no attribute '{name}'")
