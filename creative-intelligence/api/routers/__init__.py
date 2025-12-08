"""API Routers for Cat-Scan Creative Intelligence."""

from .system import router as system_router
from .creatives import router as creatives_router
from .seats import router as seats_router

__all__ = [
    "system_router",
    "creatives_router",
    "seats_router",
]
