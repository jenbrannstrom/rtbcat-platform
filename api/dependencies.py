"""Shared dependencies for API routers."""

from typing import Optional, List
from fastapi import HTTPException, Request, Depends
from storage.postgres_store import PostgresStore
from storage.postgres_database import init_postgres_database
from services.auth_service import AuthService, User
from config import ConfigManager

# Access level hierarchy for buyer seat permissions
_BUYER_ACCESS_LEVELS = ["read", "admin"]

StoreType = PostgresStore

# Global instances - set by main.py lifespan
_store: Optional[StoreType] = None
_config_manager: Optional[ConfigManager] = None

def set_store(store: StoreType) -> None:
    """Set the global store instance (called from main.py lifespan)."""
    global _store
    _store = store


def set_config_manager(config_manager: ConfigManager) -> None:
    """Set the global config manager instance (called from main.py lifespan)."""
    global _config_manager
    _config_manager = config_manager


def get_store() -> StoreType:
    """Dependency for getting the data store.

    Returns PostgresStore for all backends.
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
    await init_postgres_database()


# ==================== User Authentication Dependencies ====================

# Singleton AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


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
    """Require the current user to have admin role (sudo).

    Use for global/system admin actions only. For seat-scoped admin
    actions, use require_buyer_admin_access instead.

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


def is_sudo(user: User) -> bool:
    """Check if user has sudo (global admin) role."""
    return user.role == "admin"


async def get_user_buyer_access_map(
    user: User = Depends(get_current_user),
) -> Optional[dict[str, str]]:
    """Get buyer_id → access_level map for the current user.

    Returns None for sudo users (means all buyers, all levels).
    Returns dict mapping buyer_id to access_level ('read' or 'admin') for non-sudo.
    """
    if is_sudo(user):
        return None

    auth_svc = get_auth_service()
    perms = await auth_svc.get_user_buyer_seat_permissions(user.id)
    return {p.buyer_id: p.access_level for p in perms}


async def require_buyer_access_level(
    buyer_id: str,
    min_level: str,
    user: User,
) -> None:
    """Require user has at least min_level access to a specific buyer seat.

    Args:
        buyer_id: The buyer seat to check.
        min_level: Minimum required access level ('read' or 'admin').
        user: The current user.

    Raises:
        HTTPException: 403 if insufficient access.
    """
    if is_sudo(user):
        return

    min_index = _BUYER_ACCESS_LEVELS.index(min_level) if min_level in _BUYER_ACCESS_LEVELS else 0
    auth_svc = get_auth_service()
    perms = await auth_svc.get_user_buyer_seat_permissions(user.id)
    for p in perms:
        if p.buyer_id == buyer_id:
            level_index = _BUYER_ACCESS_LEVELS.index(p.access_level) if p.access_level in _BUYER_ACCESS_LEVELS else -1
            if level_index >= min_index:
                return
            break

    raise HTTPException(
        status_code=403,
        detail=f"You need '{min_level}' access to this buyer seat.",
    )


async def require_buyer_admin_access(
    buyer_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Require admin access to a specific buyer seat.

    Sudo users bypass this check. Non-sudo users must have
    access_level='admin' for the specified buyer seat.
    """
    await require_buyer_access_level(buyer_id, "admin", user)


async def require_seat_admin_or_sudo(
    user: User = Depends(get_current_user),
) -> User:
    """Require sudo or admin access to at least one buyer seat.

    Use for bidder-level / settings mutations where the operation
    isn't scoped to a single buyer_id but requires admin privileges.
    """
    if is_sudo(user):
        return user
    auth_svc = get_auth_service()
    admin_seats = await auth_svc.get_user_buyer_seat_ids(user.id, min_access_level="admin")
    if admin_seats:
        return user
    raise HTTPException(
        status_code=403,
        detail="Admin access to at least one seat is required.",
    )


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

    auth_svc = get_auth_service()
    return await auth_svc.get_user_service_account_ids(user.id)


async def get_allowed_service_account_ids(
    user: User = Depends(get_current_user),
) -> list[str]:
    """Get service account IDs allowed for the current user.

    Returns an empty list for admins to signal "all accounts".
    """
    if user.role == "admin":
        return []
    auth_svc = get_auth_service()
    return await auth_svc.get_user_service_account_ids(user.id)


async def get_allowed_buyer_ids(
    store: PostgresStore = Depends(get_store),
    user: User = Depends(get_current_user),
) -> Optional[list[str]]:
    """Get buyer IDs allowed for the current user.

    Returns None for admins to signal "all buyers".
    """
    if user.role == "admin":
        return None

    auth_svc = get_auth_service()

    # Prefer explicit buyer-seat assignments when present (Phase 3 RBAC path).
    # Fallback to legacy service-account-derived access during transition.
    explicit_buyer_ids = await auth_svc.get_user_buyer_seat_ids(user.id)
    if explicit_buyer_ids:
        return explicit_buyer_ids

    service_account_ids = await auth_svc.get_user_service_account_ids(user.id)
    if not service_account_ids:
        return []
    return await store.get_buyer_ids_for_service_accounts(service_account_ids)


async def get_allowed_bidder_ids(
    store: PostgresStore = Depends(get_store),
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
    store: PostgresStore = Depends(get_store),
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
    store: PostgresStore = Depends(get_store),
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
    store: PostgresStore = Depends(get_store),
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

    auth_svc = get_auth_service()
    has_access = await auth_svc.check_user_permission(
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
