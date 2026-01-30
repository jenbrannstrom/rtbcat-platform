"""Postgres-only repositories (SQL + row mapping only)."""

from .endpoints_repo import EndpointsRepository

__all__ = [
    "EndpointsRepository",
]
