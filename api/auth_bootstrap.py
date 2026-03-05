"""Bootstrap endpoint for first-sudo provisioning.

By default, fresh deployments require a bootstrap token:
- set CATSCAN_BOOTSTRAP_TOKEN
- create first admin via POST /auth/bootstrap

Legacy auto-sudo behavior is only available when explicitly enabled with
CATSCAN_REQUIRE_BOOTSTRAP_TOKEN=false (local/dev workflows).
"""

import logging
import os
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from api.request_trust import get_client_ip, is_secure_request
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Bootstrap"])

SESSION_COOKIE_NAME = "rtbcat_session"

_auth_service: AuthService | None = None


def _get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_bootstrap_token() -> str:
    return os.environ.get("CATSCAN_BOOTSTRAP_TOKEN", "").strip()


def _parse_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


# Bootstrap endpoint brute-force throttling (IP-based)
_BOOTSTRAP_RATE_LIMIT_MAX_ATTEMPTS = _parse_positive_int("CATSCAN_BOOTSTRAP_MAX_ATTEMPTS", 5)
_BOOTSTRAP_RATE_LIMIT_WINDOW_SECONDS = _parse_positive_int("CATSCAN_BOOTSTRAP_WINDOW_SECONDS", 900)
_BOOTSTRAP_RATE_LIMIT_LOCKOUT_SECONDS = _parse_positive_int("CATSCAN_BOOTSTRAP_LOCKOUT_SECONDS", 1800)
_bootstrap_rate_limit_lock = threading.Lock()
_bootstrap_attempts: dict[str, list[float]] = {}
_bootstrap_lockouts: dict[str, float] = {}


def _prune_bootstrap_rate_limit_state(now: float) -> None:
    cutoff = now - _BOOTSTRAP_RATE_LIMIT_WINDOW_SECONDS

    for key in list(_bootstrap_attempts.keys()):
        recent = [ts for ts in _bootstrap_attempts[key] if ts >= cutoff]
        if recent:
            _bootstrap_attempts[key] = recent
        else:
            _bootstrap_attempts.pop(key, None)

    for key in list(_bootstrap_lockouts.keys()):
        if _bootstrap_lockouts[key] <= now:
            _bootstrap_lockouts.pop(key, None)


def _bootstrap_rate_limit_key(request: Request) -> str:
    return get_client_ip(request) or "unknown"


def _enforce_bootstrap_rate_limit(client_key: str) -> None:
    now = time.time()
    with _bootstrap_rate_limit_lock:
        _prune_bootstrap_rate_limit_state(now)
        lockout_until = _bootstrap_lockouts.get(client_key, 0.0)

    if lockout_until > now:
        retry_after = max(1, int(lockout_until - now))
        raise HTTPException(
            status_code=429,
            detail="Too many bootstrap attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _record_bootstrap_failure(client_key: str) -> None:
    now = time.time()
    with _bootstrap_rate_limit_lock:
        _prune_bootstrap_rate_limit_state(now)
        attempts = _bootstrap_attempts.setdefault(client_key, [])
        attempts.append(now)
        if len(attempts) >= _BOOTSTRAP_RATE_LIMIT_MAX_ATTEMPTS:
            _bootstrap_lockouts[client_key] = now + _BOOTSTRAP_RATE_LIMIT_LOCKOUT_SECONDS
            _bootstrap_attempts.pop(client_key, None)


def _clear_bootstrap_failures(client_key: str) -> None:
    with _bootstrap_rate_limit_lock:
        _bootstrap_attempts.pop(client_key, None)
        _bootstrap_lockouts.pop(client_key, None)


# ---------------------------------------------------------------------------
# Shared helpers (imported by session_middleware, auth_password, auth_authing)
# ---------------------------------------------------------------------------

def is_bootstrap_token_required() -> bool:
    """Return True when first-user bootstrap guard is enabled."""
    return _env_enabled("CATSCAN_REQUIRE_BOOTSTRAP_TOKEN", True)


async def is_bootstrap_completed() -> bool:
    """Return True when bootstrap_completed == '1' in system_settings."""
    auth_svc = _get_auth_service()
    value = await auth_svc.get_setting("bootstrap_completed")
    return value == "1"


async def _auto_heal_bootstrap_status() -> None:
    """If users already exist but bootstrap_completed is not set, mark it.

    This prevents lockout on existing deployments that upgrade to a version
    with bootstrap guards.
    """
    auth_svc = _get_auth_service()
    user_count = await auth_svc.count_users()
    if user_count > 0 and not await is_bootstrap_completed():
        await auth_svc.set_setting("bootstrap_completed", "1", updated_by="auto_heal")
        logger.info(
            "Auto-healed bootstrap_completed flag (found %d existing users)",
            user_count,
        )


# ---------------------------------------------------------------------------
# Bootstrap endpoint
# ---------------------------------------------------------------------------

class BootstrapRequest(BaseModel):
    bootstrap_token: str
    email: EmailStr
    password: str | None = None
    display_name: str | None = None


@router.post("/bootstrap")
async def bootstrap_first_admin(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
):
    """Create the first sudo user using the bootstrap token.

    Requires:
    - bootstrap guard enabled and CATSCAN_BOOTSTRAP_TOKEN set
    - No users exist yet (bootstrap not completed)
    - Token in request matches env var
    """
    expected_token = get_bootstrap_token()
    if not expected_token:
        if is_bootstrap_token_required():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Bootstrap token is required but missing. "
                    "Set CATSCAN_BOOTSTRAP_TOKEN to initialize the first admin."
                ),
            )
        raise HTTPException(
            status_code=403,
            detail="Bootstrap endpoint is disabled (set CATSCAN_REQUIRE_BOOTSTRAP_TOKEN=true to enable).",
        )

    client_key = _bootstrap_rate_limit_key(request)
    _enforce_bootstrap_rate_limit(client_key)

    if await is_bootstrap_completed():
        raise HTTPException(
            status_code=403,
            detail="Bootstrap already completed. Use normal login.",
        )

    auth_svc = _get_auth_service()
    user_count = await auth_svc.count_users()
    if user_count > 0:
        # Mark bootstrap as completed so we don't get stuck
        await auth_svc.set_setting("bootstrap_completed", "1", updated_by="auto_heal")
        raise HTTPException(
            status_code=403,
            detail="Users already exist. Bootstrap is no longer available.",
        )

    # Constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(payload.bootstrap_token, expected_token):
        _record_bootstrap_failure(client_key)
        logger.warning("Bootstrap attempt with invalid token from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=403, detail="Invalid bootstrap token.")

    _clear_bootstrap_failures(client_key)

    # Create first sudo user
    email = payload.email.lower().strip()
    user_id = str(uuid.uuid4())
    display_name = payload.display_name or email.split("@")[0].replace(".", " ").title()

    user = await auth_svc.create_user(
        user_id=user_id,
        email=email,
        display_name=display_name,
        role="sudo",
    )

    # If password provided, store it
    if payload.password:
        from api.auth_password import hash_password, _set_user_password_hash
        password_hash = hash_password(payload.password)
        await _set_user_password_hash(user_id, password_hash)

    # Mark bootstrap as completed
    await auth_svc.set_setting("bootstrap_completed", "1", updated_by=user_id)

    # Create session
    session_id = str(uuid.uuid4())
    await auth_svc.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        duration_days=30,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        secure=is_secure_request(request),
    )

    logger.info("Bootstrap completed: first admin %s created", email)

    return {
        "status": "ok",
        "message": "First sudo user created successfully.",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
    }
