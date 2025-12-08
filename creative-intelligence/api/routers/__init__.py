"""API Routers for Cat-Scan Creative Intelligence."""

from .system import router as system_router
from .creatives import router as creatives_router
from .seats import router as seats_router
from .settings import router as settings_router
from .analytics import router as analytics_router
from .performance import router as performance_router
from .qps import router as qps_router
from .gmail import router as gmail_router
from .retention import router as retention_router

__all__ = [
    "system_router",
    "creatives_router",
    "seats_router",
    "settings_router",
    "analytics_router",
    "performance_router",
    "qps_router",
    "gmail_router",
    "retention_router",
]
