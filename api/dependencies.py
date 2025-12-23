"""Shared dependencies for API routers."""

from typing import Optional
from fastapi import HTTPException
from storage import SQLiteStore
from storage.database import init_database
from config import ConfigManager

# Global instances - set by main.py lifespan
_store: Optional[SQLiteStore] = None
_config_manager: Optional[ConfigManager] = None


def set_store(store: SQLiteStore) -> None:
    """Set the global store instance (called from main.py lifespan)."""
    global _store
    _store = store


def set_config_manager(config_manager: ConfigManager) -> None:
    """Set the global config manager instance (called from main.py lifespan)."""
    global _config_manager
    _config_manager = config_manager


def get_store() -> SQLiteStore:
    """Dependency for getting the SQLite store.

    DEPRECATED: Use storage.database functions directly instead.
    Kept for backward compatibility during migration.
    """
    if _store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _store


def get_config() -> ConfigManager:
    """Dependency for getting the config manager."""
    if _config_manager is None:
        raise HTTPException(status_code=503, detail="Config not initialized")
    return _config_manager


async def startup_event():
    """Called when FastAPI starts up.

    Initializes the v40 database schema if needed.
    """
    await init_database()
