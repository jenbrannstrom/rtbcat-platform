"""Password-based authentication for Cat-Scan.

This module provides traditional username/password authentication:
- /auth/login: Login with email and password
- /auth/register: Register new user (admin only or first user)

Password hashing uses bcrypt via passlib.
"""

import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Session cookie name (must match other auth modules)
SESSION_COOKIE_NAME = "rtbcat_session"

router = APIRouter(prefix="/auth", tags=["Password Authentication"])


# ==================== Password Hashing ====================

# Try to import passlib, fall back to hashlib if not available
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return pwd_context.verify(plain_password, hashed_password)

except ImportError:
    # Fallback to hashlib (less secure but works without extra deps)
    import hashlib

    def hash_password(password: str) -> str:
        """Hash a password using SHA-256 (fallback)."""
        salt = os.urandom(32)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return f"{salt.hex()}:{hash_obj.hex()}"

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash (fallback)."""
        try:
            salt_hex, hash_hex = hashed_password.split(":")
            salt = bytes.fromhex(salt_hex)
            hash_obj = hashlib.pbkdf2_hmac('sha256', plain_password.encode(), salt, 100000)
            return hash_obj.hex() == hash_hex
        except (ValueError, AttributeError):
            return False


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
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _is_secure_request(request: Request) -> bool:
    """Treat X-Forwarded-Proto=https as secure when behind a reverse proxy."""
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        proto = forwarded_proto.split(",")[0].strip().lower()
        if proto in {"http", "https"}:
            return proto == "https"
    return request.url.scheme == "https"


def _is_single_user_mode() -> bool:
    """Single-user mode is secure default unless explicitly disabled."""
    raw = os.environ.get("CATSCAN_SINGLE_USER_MODE", "true").strip().lower()
    return raw in ("1", "true", "yes")


# ==================== Auth Endpoints ====================

@router.post("/login", response_model=AuthResponse)
async def login(request: Request, response: Response, login_data: LoginRequest):
    """Login with email and password.

    Returns session cookie on success.
    """
    auth_svc = get_auth_service()
    email = login_data.email.lower().strip()

    # Find user by email
    user = await auth_svc.get_user_by_email(email)

    if not user:
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
    if not verify_password(login_data.password, password_hash):
        # Log failed attempt
        await auth_svc.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_failed",
            user_id=user.id,
            resource_type="auth",
            details="invalid_password",
            ip_address=_get_client_ip(request),
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Update last login
    await auth_svc.update_last_login(user.id)

    # Create session
    session_id = str(uuid.uuid4())
    await auth_svc.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=_get_client_ip(request),
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
        ip_address=_get_client_ip(request),
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
            "is_admin": user.role == "admin",
        },
    )


@router.post("/register", response_model=AuthResponse)
async def register(request: Request, response: Response, register_data: RegisterRequest):
    """Register a new user with email and password.

    First user becomes admin. Subsequent registrations require admin approval
    (via admin user management) or can be done by admins.
    """
    auth_svc = get_auth_service()
    email = register_data.email.lower().strip()

    # Check if user already exists
    existing_user = await auth_svc.get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate password strength
    if len(register_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Check if this is the first user (becomes admin)
    user_count = await auth_svc.count_users()
    is_first_user = user_count == 0

    if _is_single_user_mode() and not is_first_user:
        raise HTTPException(
            status_code=403,
            detail="Single-user mode is enabled. Additional users are disabled.",
        )

    if not is_first_user:
        # Check if requester is admin
        if hasattr(request.state, "user") and request.state.user:
            if request.state.user.role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="Only admins can register new users. Please contact an administrator."
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="Registration is disabled. Please contact an administrator."
            )

    # Create user
    user_id = str(uuid.uuid4())
    role = "admin" if is_first_user else "user"
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
        message="Registration successful" + (" - you are now logged in as admin" if is_first_user else ""),
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_admin": user.role == "admin",
        },
    )


@router.post("/set-password", response_model=AuthResponse)
async def set_password(request: Request, password_data: dict):
    """Set or update password for authenticated user.

    Allows users who logged in via OAuth to set a password for direct login.
    """
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
