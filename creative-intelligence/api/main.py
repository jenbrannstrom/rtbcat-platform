"""FastAPI application for Cat-Scan Creative Intelligence.

This module provides the main application setup and router configuration.
All route handlers are organized in the api/routers/ directory.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ConfigManager
from storage import SQLiteStore
from api.campaigns_router import router as campaigns_router
from api.routers import (
    system_router,
    creatives_router,
    seats_router,
    settings_router,
    uploads_router,
    analytics_router,
    config_router,
    gmail_router,
    recommendations_router,
    retention_router,
    qps_router,
    performance_router,
    troubleshooting_router,
    collect_router,
)
from api.dependencies import set_store, set_config_manager, startup_event

logger = logging.getLogger(__name__)

# Global instances
_store: Optional[SQLiteStore] = None
_config_manager: Optional[ConfigManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global _store, _config_manager

    # Initialize v40 database schema
    await startup_event()

    # Initialize on startup
    _config_manager = ConfigManager()
    _store = SQLiteStore()
    await _store.initialize()

    # Set dependencies for routers
    set_store(_store)
    set_config_manager(_config_manager)

    # Auto-populate buyer_seats from existing creatives if needed
    try:
        seats_created = await _store.populate_buyer_seats_from_creatives()
        if seats_created > 0:
            logger.info(f"Auto-populated {seats_created} buyer seats from existing creatives")
    except Exception as e:
        logger.warning(f"Failed to auto-populate buyer seats: {e}")

    logger.info("Cat-Scan API started")

    yield

    # Cleanup on shutdown
    logger.info("Cat-Scan API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    application = FastAPI(
        title="Cat-Scan Creative Intelligence",
        description="API for collecting and analyzing Authorized Buyers creative data",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application


app = create_app()

# =============================================================================
# Router Registration
# =============================================================================

# System routes (health, thumbnails, stats, sizes)
app.include_router(system_router)

# Core data routes
app.include_router(creatives_router)
app.include_router(seats_router)
app.include_router(campaigns_router)

# Settings and configuration
app.include_router(settings_router)
app.include_router(config_router)

# Analytics and optimization
app.include_router(analytics_router)
app.include_router(qps_router)
app.include_router(recommendations_router)

# Data import and collection
app.include_router(uploads_router)
app.include_router(performance_router)
app.include_router(collect_router)

# Integrations
app.include_router(gmail_router)
app.include_router(retention_router)
app.include_router(troubleshooting_router)
