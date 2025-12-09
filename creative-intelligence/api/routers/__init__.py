"""API Routers for Cat-Scan Creative Intelligence."""

from .system import router as system_router
from .creatives import router as creatives_router
from .seats import router as seats_router
from .settings import router as settings_router
from .uploads import router as uploads_router
from .analytics import router as analytics_router
from .config import router as config_router
from .gmail import router as gmail_router
from .recommendations import router as recommendations_router
from .retention import router as retention_router
from .qps import router as qps_router
from .performance import router as performance_router
from .troubleshooting import router as troubleshooting_router
from .collect import router as collect_router

__all__ = [
    "system_router",
    "creatives_router",
    "seats_router",
    "settings_router",
    "uploads_router",
    "analytics_router",
    "config_router",
    "gmail_router",
    "recommendations_router",
    "retention_router",
    "qps_router",
    "performance_router",
    "troubleshooting_router",
    "collect_router",
]
