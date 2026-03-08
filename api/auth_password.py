"""Password-based authentication for Cat-Scan.

This module provides traditional username/password authentication:
- /auth/login: Login with email and password
- /auth/register: Register new user (sudo only or first user)

Password hashing uses bcrypt via passlib.
"""

import os
import uuid
import logging
import threading
import time
import hashlib
import hmac
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from api.auth_bootstrap import is_bootstrap_token_required, is_bootstrap_completed, get_bootstrap_token
from api.auth_providers import is_password_login_enabled
from api.request_trust import get_client_ip, is_secure_request
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Session cookie name (must match other auth modules)
SESSION_COOKIE_NAME = "rtbcat_session"

router = APIRouter(prefix="/auth", tags=["Password Authentication"])


# ==================== Password Hashing ====================

try:
    from passlib.context import CryptContext
    from passlib.exc import UnknownHashError
except ImportError:
    raise RuntimeError(
        "passlib is required for secure password hashing. Install dependency: passlib[bcrypt]."
    )


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def _looks_like_legacy_pbkdf2_hash(hashed_password: str) -> bool:
    parts = hashed_password.split(":")
    if len(parts) != 2:
        return False
    salt_hex, digest_hex = parts
    return len(salt_hex) == 64 and len(digest_hex) == 64


def _verify_legacy_password(plain_password: str, hashed_password: str) -> bool:
    """Verify the pre-bcrypt PBKDF2 format used before passlib was available."""
    if not _looks_like_legacy_pbkdf2_hash(hashed_password):
        return False
    try:
        salt_hex, digest_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, 100000).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def verify_password(plain_password: str, hashed_password: str) -> tuple[bool, bool]:
    """Verify a password and report whether the stored hash should be upgraded."""
    try:
        return pwd_context.verify(plain_password, hashed_password), False
    except UnknownHashError:
        if _verify_legacy_password(plain_password, hashed_password):
            return True, True
        return False, False


# ==================== Request/Response Models ====================

class LoginRequest(BaseModel):
    """Login request with email and password."""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Register request for new user."""
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class AuthResponse(BaseModel):
    """Authentication response."""
    status: str
    message: str
    user: Optional[dict] = None


# ==================== Helper Functions ====================

# Singleton AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from trusted request metadata."""
    return get_client_ip(request)


def _is_secure_request(request: Request) -> bool:
    """Resolve HTTPS state using trusted proxy policy."""
    return is_secure_request(request)


def _is_single_user_mode() -> bool:
    """Single-user mode is secure default unless explicitly disabled."""
    raw = os.environ.get("CATSCAN_SINGLE_USER_MODE", "true").strip().lower()
    return raw in ("1", "true", "yes")


def _parse_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


_LOGIN_RATE_LIMIT_MAX_ATTEMPTS = _parse_positive_int("CATSCAN_LOGIN_MAX_ATTEMPTS", 10)
_LOGIN_RATE_LIMIT_WINDOW_SECONDS = _parse_positive_int("CATSCAN_LOGIN_WINDOW_SECONDS", 900)
_LOGIN_RATE_LIMIT_LOCKOUT_SECONDS = _parse_positive_int("CATSCAN_LOGIN_LOCKOUT_SECONDS", 900)
_login_rate_limit_lock = threading.Lock()
_login_attempts: dict[str, list[float]] = {}
_login_lockouts: dict[str, float] = {}


def _login_rate_limit_keys(email: str, client_ip: Optional[str]) -> tuple[str, str]:
    return f"email:{email}", f"ip:{client_ip or 'unknown'}"


def _prune_login_rate_limit_state(now: float) -> None:
    cutoff = now - _LOGIN_RATE_LIMIT_WINDOW_SECONDS

    for key in list(_login_attempts.keys()):
        recent = [ts for ts in _login_attempts[key] if ts >= cutoff]
        if recent:
            _login_attempts[key] = recent
        else:
            _login_attempts.pop(key, None)

    for key in list(_login_lockouts.keys()):
        if _login_lockouts[key] <= now:
            _login_lockouts.pop(key, None)


def _check_login_rate_limit(email: str, client_ip: Optional[str]) -> None:
    now = time.time()
    with _login_rate_limit_lock:
        _prune_login_rate_limit_state(now)
        lockout_until = max(
            (_login_lockouts.get(key, 0.0) for key in _login_rate_limit_keys(email, client_ip)),
            default=0.0,
        )

    if lockout_until > now:
        retry_after = max(1, int(lockout_until - now))
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _record_login_failure(email: str, client_ip: Optional[str]) -> None:
    now = time.time()
    with _login_rate_limit_lock:
        _prune_login_rate_limit_state(now)
        for key in _login_rate_limit_keys(email, client_ip):
            attempts = _login_attempts.setdefault(key, [])
            attempts.append(now)
            if len(attempts) >= _LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
                _login_lockouts[key] = now + _LOGIN_RATE_LIMIT_LOCKOUT_SECONDS
                _login_attempts.pop(key, None)


def _clear_login_failures(email: str, client_ip: Optional[str]) -> None:
    with _login_rate_limit_lock:
        for key in _login_rate_limit_keys(email, client_ip):
            _login_attempts.pop(key, None)
            _login_lockouts.pop(key, None)


# ==================== Auth Endpoints ====================

@router.post("/login", response_model=AuthResponse)
async def login(request: Request, response: Response, login_data: LoginRequest):
    """Login with email and password.

    Returns session cookie on success.
    """
    if not is_password_login_enabled():
        raise HTTPException(status_code=404, detail="Password login is disabled")

    auth_svc = get_auth_service()
    email = login_data.email.lower().strip()
    client_ip = _get_client_ip(request)

    _check_login_rate_limit(email, client_ip)

    # Find user by email
    user = await auth_svc.get_user_by_email(email)

    if not user:
        _record_login_failure(email, client_ip)
        # Don't reveal whether email exists
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if user has a password set
    # Get password hash from user record (need to extend auth_repo)
    password_hash = await _get_user_password_hash(user.id)

    if not password_hash:
        raise HTTPException(
            status_code=401,
            detail="This account uses external authentication (Google or Authing). Please use those login methods."
        )

    # Verify password
    password_valid, needs_upgrade = verify_password(login_data.password, password_hash)
    if not password_valid:
        _record_login_failure(email, client_ip)
        # Log failed attempt
        await auth_svc.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_failed",
            user_id=user.id,
            resource_type="auth",
            details="invalid_password",
            ip_address=client_ip,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if needs_upgrade:
        await _set_user_password_hash(user.id, hash_password(login_data.password))
        logger.info("Upgraded legacy password hash for %s during login", email)

    _clear_login_failures(email, client_ip)

    # Update last login
    await auth_svc.update_last_login(user.id)

    # Create session
    session_id = str(uuid.uuid4())
    await auth_svc.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent"),
        duration_days=30,
    )

    # Log audit
    await auth_svc.log_audit(
        audit_id=str(uuid.uuid4()),
        action="login",
        user_id=user.id,
        resource_type="auth",
        details="password",
        ip_address=client_ip,
    )

    # Set session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=_is_secure_request(request),
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # 30 days
    )

    return AuthResponse(
        status="success",
        message="Login successful",
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_admin": user.role == "sudo",
        },
    )


@router.post("/register", response_model=AuthResponse)
async def register(request: Request, response: Response, register_data: RegisterRequest):
    """Register a new user with email and password.

    First user becomes sudo. Subsequent registrations require sudo approval
    (via admin user management) or can be done by sudo users.
    """
    if not is_password_login_enabled():
        raise HTTPException(status_code=404, detail="Password login is disabled")

    auth_svc = get_auth_service()
    email = register_data.email.lower().strip()

    # Check if user already exists
    existing_user = await auth_svc.get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate password strength
    if len(register_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Check if this is the first user (becomes sudo)
    user_count = await auth_svc.count_users()
    is_first_user = user_count == 0

    if is_first_user and is_bootstrap_token_required() and not await is_bootstrap_completed():
        if not get_bootstrap_token():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Server bootstrap is required but not configured. "
                    "Set CATSCAN_BOOTSTRAP_TOKEN and create the first admin via /auth/bootstrap."
                ),
            )
        raise HTTPException(
            status_code=403,
            detail="First admin must be created via /auth/bootstrap with the bootstrap token.",
        )


    if _is_single_user_mode() and not is_first_user:
        raise HTTPException(
            status_code=403,
            detail="Single-user mode is enabled. Additional users are disabled.",
        )

    if not is_first_user:
        # Check if requester is sudo
        if hasattr(request.state, "user") and request.state.user:
            if request.state.user.role != "sudo":
                raise HTTPException(
                    status_code=403,
                    detail="Only sudo users can register new users. Please contact an administrator."
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="Registration is disabled. Please contact an administrator."
            )

    # Create user
    user_id = str(uuid.uuid4())
    role = "sudo" if is_first_user else "read"
    display_name = register_data.display_name or email.split("@")[0].replace(".", " ").title()

    user = await auth_svc.create_user(
        user_id=user_id,
        email=email,
        display_name=display_name,
        role=role,
    )

    # Store password hash
    password_hash = hash_password(register_data.password)
    await _set_user_password_hash(user_id, password_hash)

    logger.info(f"Registered user: {email} (role={role}, first_user={is_first_user})")

    # Log audit
    await auth_svc.log_audit(
        audit_id=str(uuid.uuid4()),
        action="register",
        user_id=user.id,
        resource_type="auth",
        details=f"role={role}",
        ip_address=_get_client_ip(request),
    )

    # Auto-login for first user
    if is_first_user:
        session_id = str(uuid.uuid4())
        await auth_svc.create_session(
            session_id=session_id,
            user_id=user.id,
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            duration_days=30,
        )

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=_is_secure_request(request),
            samesite="lax",
            max_age=30 * 24 * 60 * 60,
        )

    return AuthResponse(
        status="success",
        message="Registration successful" + (" - you are now logged in as sudo" if is_first_user else ""),
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_admin": user.role == "sudo",
        },
    )


@router.post("/set-password", response_model=AuthResponse)
async def set_password(request: Request, password_data: dict):
    """Set or update password for authenticated user.

    Allows users who logged in via OAuth to set a password for direct login.
    """
    if not is_password_login_enabled():
        raise HTTPException(status_code=404, detail="Password login is disabled")

    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = request.state.user
    new_password = password_data.get("password")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Hash and store password
    password_hash = hash_password(new_password)
    await _set_user_password_hash(user.id, password_hash)

    auth_svc = get_auth_service()
    await auth_svc.log_audit(
        audit_id=str(uuid.uuid4()),
        action="password_set",
        user_id=user.id,
        resource_type="auth",
        ip_address=_get_client_ip(request),
    )

    return AuthResponse(
        status="success",
        message="Password set successfully. You can now login with email and password.",
    )


# ==================== Password Storage ====================
# These functions interact with the database to store/retrieve password hashes.
# Password hashes are stored in a separate table for security.

from storage.postgres import pg_transaction_async


async def _get_user_password_hash(user_id: str) -> Optional[str]:
    """Get password hash for a user."""
    def _query(conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM user_passwords WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    return await pg_transaction_async(_query)


async def _set_user_password_hash(user_id: str, password_hash: str) -> None:
    """Set or update password hash for a user."""
    def _query(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_passwords (user_id, password_hash, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    updated_at = NOW()
                """,
                (user_id, password_hash),
            )

    await pg_transaction_async(_query)
