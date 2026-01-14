"""Shared dependencies for API routers."""

from typing import Optional, List
from fastapi import HTTPException, Request, Depends
from storage import SQLiteStore
from storage.database import init_database, DB_PATH
from storage.repositories.user_repository import UserRepository, User
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


# ==================== User Authentication Dependencies ====================

def _get_user_repo() -> UserRepository:
    """Get the user repository instance."""
    return UserRepository(DB_PATH)


# ==================== OAuth2 Proxy Authentication ====================
# When OAuth2 Proxy is enabled, nginx passes the authenticated user's email
# via the X-Email header. This is the primary authentication method.


async def get_google_user_email(request: Request) -> Optional[str]:
    """Get the authenticated user's email from OAuth2 Proxy header.

    OAuth2 Proxy sets X-Email header after validating the Google OAuth session.
    This is guaranteed to be set when running behind OAuth2 Proxy with nginx.

    Returns:
        The authenticated user's email, or None if not authenticated via OAuth2 Proxy.
    """
    return request.headers.get("X-Email")


async def require_google_auth(request: Request) -> str:
    """Require OAuth2 Proxy authentication.

    Use this dependency for endpoints that require Google authentication.
    When running behind OAuth2 Proxy, this will always succeed (proxy blocks
    unauthenticated requests). When running locally without proxy, this will fail.

    Returns:
        The authenticated user's email.

    Raises:
        HTTPException: If X-Email header is not present.
    """
    email = await get_google_user_email(request)
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. OAuth2 Proxy authentication required.",
        )
    return email


async def get_current_user(request: Request) -> User:
    """Get the currently authenticated user from request state.

    The SessionAuthMiddleware attaches the user to request.state.user
    after validating the session cookie.

    Raises:
        HTTPException: If user is not authenticated.
    """
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please log in.",
        )

    return user


async def get_current_user_optional(request: Request) -> Optional[User]:
    """Get the current user if authenticated, or None.

    Useful for endpoints that work for both authenticated and anonymous users.
    """
    return getattr(request.state, "user", None)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to have admin role.

    Args:
        user: Current authenticated user.

    Returns:
        The admin user.

    Raises:
        HTTPException: If user is not an admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return user


async def get_user_service_accounts(
    user: User = Depends(get_current_user),
) -> List[str]:
    """Get list of service account IDs the user can access.

    Admins can access all service accounts.
    Regular users can only access accounts they have permissions for.

    Args:
        user: Current authenticated user.

    Returns:
        List of service account IDs the user can access.
    """
    if user.role == "admin":
        # Admins can access all service accounts
        return []  # Empty list means "all accounts"

    repo = _get_user_repo()
    return await repo.get_user_service_account_ids(user.id)


async def get_allowed_service_account_ids(
    user: User = Depends(get_current_user),
) -> list[str]:
    """Get service account IDs allowed for the current user.

    Returns an empty list for admins to signal "all accounts".
    """
    if user.role == "admin":
        return []
    repo = _get_user_repo()
    return await repo.get_user_service_account_ids(user.id)


async def get_allowed_buyer_ids(
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> Optional[list[str]]:
    """Get buyer IDs allowed for the current user.

    Returns None for admins to signal "all buyers".
    """
    if user.role == "admin":
        return None

    repo = _get_user_repo()
    service_account_ids = await repo.get_user_service_account_ids(user.id)
    if not service_account_ids:
        return []
    return await store.get_buyer_ids_for_service_accounts(service_account_ids)


async def get_allowed_bidder_ids(
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> Optional[list[str]]:
    """Get bidder IDs allowed for the current user."""
    buyer_ids = await get_allowed_buyer_ids(store=store, user=user)
    if buyer_ids is None:
        return None
    if not buyer_ids:
        return []
    return await store.get_bidder_ids_for_buyer_ids(buyer_ids)


async def resolve_buyer_id(
    buyer_id: Optional[str],
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> Optional[str]:
    """Resolve buyer_id for a request based on user access.

    - Admins: return buyer_id as-is (may be None).
    - Non-admins: if buyer_id provided, must be allowed.
      If not provided, allow only when user has exactly one buyer_id.
    """
    allowed = await get_allowed_buyer_ids(store=store, user=user)
    if allowed is None:
        return buyer_id

    if buyer_id:
        if buyer_id not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this buyer account.",
            )
        return buyer_id

    if len(allowed) == 1:
        return allowed[0]

    raise HTTPException(
        status_code=400,
        detail="buyer_id is required for your account access.",
    )


async def require_buyer_access(
    buyer_id: str,
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> None:
    """Require access to a specific buyer_id."""
    allowed = await get_allowed_buyer_ids(store=store, user=user)
    if allowed is None:
        return
    if buyer_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this buyer account.",
        )


async def resolve_bidder_id(
    bidder_id: Optional[str],
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> Optional[str]:
    """Resolve bidder_id for a request based on user access."""
    allowed = await get_allowed_bidder_ids(store=store, user=user)
    if allowed is None:
        return bidder_id

    if bidder_id:
        if bidder_id not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this bidder account.",
            )
        return bidder_id

    if len(allowed) == 1:
        return allowed[0]

    raise HTTPException(
        status_code=400,
        detail="bidder_id is required for your account access.",
    )


async def check_service_account_access(
    service_account_id: str,
    user: User = Depends(get_current_user),
    required_level: str = "read",
) -> bool:
    """Check if user has access to a specific service account.

    Args:
        service_account_id: Service account to check.
        user: Current authenticated user.
        required_level: Required permission level (read, write, admin).

    Returns:
        True if user has access.

    Raises:
        HTTPException: If user doesn't have access.
    """
    if user.role == "admin":
        return True

    repo = _get_user_repo()
    has_access = await repo.check_user_permission(
        user.id,
        service_account_id,
        required_level,
    )

    if not has_access:
        raise HTTPException(
            status_code=403,
            detail=f"You don't have {required_level} access to this service account.",
        )

    return True
