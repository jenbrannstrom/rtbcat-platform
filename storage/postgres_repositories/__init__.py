"""Postgres-only repositories (SQL + row mapping only)."""

from .endpoints_repo import EndpointsRepository
from .snapshots_repo import SnapshotsRepository

__all__ = [
    "EndpointsRepository",
    "SnapshotsRepository",
]
