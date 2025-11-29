"""RTBcat Creative Intelligence - API Module.

This module provides the FastAPI application for the
creative intelligence REST API.
"""

from .main import app, create_app

__all__ = ["app", "create_app"]
