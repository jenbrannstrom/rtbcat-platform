"""FastAPI application for Cat-Scan Creative Intelligence.

This module provides the main application setup and router configuration.
All route handlers are organized in the api/routers/ directory.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI


def get_allowed_origins() -> list[str]:
    """Get allowed CORS origins from environment or defaults.

    Set ALLOWED_ORIGINS env var as comma-separated list for production:
    ALLOWED_ORIGINS=https://scan.rtb.cat,https://yourdomain.com
    """
    env_origins = os.environ.get("ALLOWED_ORIGINS", "")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]

    # Development defaults - restrict in production via ALLOWED_ORIGINS
    return [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]


def get_version() -> str:
    """Get app version from VERSION file or environment variable."""
    # First check environment variable (set in Docker)
    if version := os.environ.get("APP_VERSION"):
        return version

    # Try to read from VERSION file (for local development)
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    # Fallback
    return "0.9.0"


from fastapi.middleware.cors import CORSMiddleware

from api.auth import APIKeyAuthMiddleware
from api.session_middleware import SessionAuthMiddleware
from api.auth_oauth_proxy import router as auth_router, cleanup_sessions
from api.auth_authing import router as authing_router
from api.auth_password import router as password_router
from config import ConfigManager
from storage.postgres_store import PostgresStore
from storage.serving_database import configure_serving_database
from api.campaigns_router import router as campaigns_router
from api.routers import (
    system_router,
    creatives_router,
    creatives_live_router,
    creative_cache_router,
    creative_language_router,
    seats_router,
    settings_router,
    uploads_router,
    config_router,
    gmail_router,
    recommendations_router,
    retention_router,
    precompute_router,
    performance_router,
    troubleshooting_router,
    collect_router,
    admin_router,
    # Analytics sub-routers (refactored from monolithic analytics.py)
    waste_router,
    rtb_bidstream_router,
    home_router,
    analytics_qps_router,
    traffic_router,
    spend_router,
)
from api.dependencies import set_store, set_config_manager, startup_event
from services.secrets_health_service import get_secrets_health

logger = logging.getLogger(__name__)

# Global instances - Postgres only
_store: Optional[PostgresStore] = None
_config_manager: Optional[ConfigManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global _store, _config_manager

    # Initialize v40 database schema
    await startup_event()

    # Initialize on startup
    _config_manager = ConfigManager()
    try:
        config = _config_manager.load()
    except Exception:
        config = None
    serving_dsn = config.database.serving_postgres_dsn if config else os.getenv("POSTGRES_SERVING_DSN")
    if not serving_dsn:
        raise RuntimeError(
            "POSTGRES_SERVING_DSN must be set for serving queries."
        )
    configure_serving_database(serving_dsn)

    logger.info("Using PostgresStore for state storage")
    _store = PostgresStore()
    await _store.initialize()

    # Set dependencies for routers
    set_store(_store)
    set_config_manager(_config_manager)

    # Validate required secrets for enabled features at startup
    secrets_health = get_secrets_health()
    if secrets_health["healthy"]:
        logger.info(
            "Secrets health check passed (backend=%s, enabled_features=%s)",
            secrets_health["backend"],
            secrets_health["summary"]["enabled_features"],
        )
    else:
        missing = ", ".join(secrets_health["missing_required_keys"])
        if secrets_health["strict_mode"]:
            raise RuntimeError(
                "Missing required secrets for enabled features: "
                f"{missing}. Set SECRETS_HEALTH_STRICT=false to downgrade to warning."
            )
        logger.warning(
            "Secrets health check failed (strict=false). Missing required keys: %s",
            missing,
        )

    # Auto-populate buyer_seats from existing creatives if needed
    try:
        seats_created = await _store.populate_buyer_seats_from_creatives()
        if seats_created > 0:
            logger.info(f"Auto-populated {seats_created} buyer seats from existing creatives")
    except Exception as e:
        logger.warning(f"Failed to auto-populate buyer seats: {e}")

    # Cleanup expired sessions on startup
    try:
        cleanup_result = await cleanup_sessions()
        if cleanup_result.get("sessions_deleted", 0) > 0:
            logger.info(f"Cleaned up {cleanup_result['sessions_deleted']} expired sessions")
    except Exception as e:
        logger.warning(f"Failed to cleanup sessions: {e}")

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
        version=get_version(),
        lifespan=lifespan,
    )

    # Configure CORS - use explicit origins, never wildcards with credentials
    # Set ALLOWED_ORIGINS env var in production (comma-separated)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )

    # API key middleware is inner. Session middleware runs first and can
    # authenticate browser/OAuth traffic before API-key checks.
    application.add_middleware(APIKeyAuthMiddleware)

    # Session-based authentication (multi-user mode)
    application.add_middleware(SessionAuthMiddleware)

    return application


app = create_app()

# =============================================================================
# Router Registration
# =============================================================================

# Authentication routes (must be first for login/logout)
app.include_router(auth_router)
app.include_router(authing_router)
app.include_router(password_router)

# System routes (health, thumbnails, stats, sizes)
app.include_router(system_router)

# Core data routes
app.include_router(creatives_router)
app.include_router(creatives_live_router)
app.include_router(creative_cache_router)
app.include_router(creative_language_router)
app.include_router(seats_router)
app.include_router(campaigns_router)

# Settings and configuration
app.include_router(settings_router)
app.include_router(config_router)

# Analytics and optimization (refactored into sub-routers)
app.include_router(waste_router)
app.include_router(rtb_bidstream_router)
app.include_router(home_router)
app.include_router(analytics_qps_router)
app.include_router(traffic_router)
app.include_router(spend_router)
app.include_router(recommendations_router)

# Data import and collection
app.include_router(uploads_router)
app.include_router(performance_router)
app.include_router(collect_router)

# Integrations
app.include_router(gmail_router)
app.include_router(retention_router)
app.include_router(precompute_router)
app.include_router(troubleshooting_router)

# Admin routes (user management, audit logs)
app.include_router(admin_router)
