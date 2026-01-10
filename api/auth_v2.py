"""Session-based authentication for Cat-Scan.

This module provides user authentication with:
- Session-based login (30-day cookie sessions)
- bcrypt password hashing
- Rate limiting (5 attempts = 1 hour lockout)
- Audit logging

For open-source single-user mode, set multi_user_enabled=0 in system_settings.
"""

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from storage.database import DB_PATH
from storage.repositories.user_repository import UserRepository, User

# Session cookie name
SESSION_COOKIE_NAME = "rtbcat_session"

# Session duration in days
SESSION_DURATION_DAYS = 30

# Rate limiting defaults
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 60

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==================== Password Hashing ====================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password.

    Returns:
        bcrypt hash string.

    Raises:
        RuntimeError: If bcrypt is not installed (required dependency).
    """
    try:
        import bcrypt
    except ImportError:
        raise RuntimeError(
            "bcrypt is required for password hashing. "
            "Install it with: pip install bcrypt"
        )
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password.
        password_hash: Stored hash.

    Returns:
        True if password matches.

    Raises:
        RuntimeError: If bcrypt is not installed (required dependency).

    Note:
        Legacy SHA-256 hashes (prefix "sha256:") are still verified for
        backward compatibility, but users should be prompted to reset
        their password to upgrade to bcrypt.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Handle legacy SHA-256 hashes (backward compatibility only)
    if password_hash.startswith("sha256:"):
        import hashlib
        logger.warning(
            "Legacy SHA-256 password hash detected. "
            "User should reset password to upgrade to bcrypt."
        )
        return password_hash == "sha256:" + hashlib.sha256(password.encode()).hexdigest()

    # Require bcrypt for all new hashes
    try:
        import bcrypt
    except ImportError:
        raise RuntimeError(
            "bcrypt is required for password verification. "
            "Install it with: pip install bcrypt"
        )
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length: Password length (default 16).

    Returns:
        Random password string.
    """
    return secrets.token_urlsafe(length)


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


# ==================== Request/Response Models ====================

class LoginRequest(BaseModel):
    """Login request with email and password."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Login response with user info."""
    status: str
    user: dict
    message: str


class UserInfo(BaseModel):
    """Current user information."""
    id: str
    email: str
    display_name: Optional[str]
    role: str
    is_admin: bool
    permissions: list[str]  # List of service account IDs


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class SetupRequest(BaseModel):
    """Initial setup request to create first admin."""
    email: str = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password (min 8 characters)")
    display_name: str = Field(default="Administrator", description="Display name")


class SetupStatusResponse(BaseModel):
    """Setup status response."""
    setup_required: bool
    setup_completed: bool
    has_users: bool


# ==================== Helper Functions ====================

def _get_user_repo() -> UserRepository:
    """Get the user repository instance."""
    return UserRepository(DB_PATH)


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    # Check X-Forwarded-For header first (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Fall back to client host
    if request.client:
        return request.client.host
    return None


def _get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


async def _create_initial_admin() -> Optional[User]:
    """Create initial admin user from environment variables if no users exist.

    Checks for RTBCAT_ADMIN_EMAIL and RTBCAT_ADMIN_PASSWORD env vars.
    Only creates admin if no users exist in the database.

    Returns:
        Created admin user or None.
    """
    admin_email = os.environ.get("RTBCAT_ADMIN_EMAIL")
    admin_password = os.environ.get("RTBCAT_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        return None

    repo = _get_user_repo()
    user_count = await repo.count_users()

    if user_count > 0:
        return None

    # Create admin user
    user_id = str(uuid.uuid4())
    password_hash = hash_password(admin_password)

    user = await repo.create_user(
        user_id=user_id,
        email=admin_email,
        password_hash=password_hash,
        display_name="Administrator",
        role="admin",
    )

    # Log the creation
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="create_initial_admin",
        user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        details=json.dumps({"email": admin_email}),
    )

    return user


# ==================== Auth Endpoints ====================

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    login_request: LoginRequest,
):
    """Authenticate user and create session.

    Sets an HTTP-only session cookie on success.

    - **email**: User email address
    - **password**: User password

    Returns user info and sets session cookie.
    """
    repo = _get_user_repo()
    email = login_request.email.lower().strip()
    ip_address = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    # Check rate limiting
    is_locked = await repo.is_locked_out(
        email=email,
        max_attempts=MAX_LOGIN_ATTEMPTS,
        lockout_minutes=LOCKOUT_MINUTES,
    )

    if is_locked:
        await repo.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_blocked",
            resource_type="auth",
            details=json.dumps({"email": email, "reason": "rate_limited"}),
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please try again in {LOCKOUT_MINUTES} minutes.",
        )

    # Find user
    user = await repo.get_user_by_email(email)

    if not user:
        # Record failed attempt
        await repo.record_login_attempt(email=email, ip_address=ip_address, success=False)
        await repo.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_failed",
            resource_type="auth",
            details=json.dumps({"email": email, "reason": "user_not_found"}),
            ip_address=ip_address,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        await repo.record_login_attempt(email=email, ip_address=ip_address, success=False)
        await repo.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_failed",
            user_id=user.id,
            resource_type="auth",
            details=json.dumps({"reason": "account_inactive"}),
            ip_address=ip_address,
        )
        raise HTTPException(status_code=401, detail="Account is deactivated")

    # Verify password
    if not verify_password(login_request.password, user.password_hash):
        await repo.record_login_attempt(email=email, ip_address=ip_address, success=False)
        await repo.log_audit(
            audit_id=str(uuid.uuid4()),
            action="login_failed",
            user_id=user.id,
            resource_type="auth",
            details=json.dumps({"reason": "invalid_password"}),
            ip_address=ip_address,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create session
    session_id = generate_session_token()
    await repo.create_session(
        session_id=session_id,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        duration_days=SESSION_DURATION_DAYS,
    )

    # Record successful login
    await repo.record_login_attempt(email=email, ip_address=ip_address, success=True)
    await repo.update_last_login(user.id)

    # Log successful login
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="login",
        user_id=user.id,
        resource_type="auth",
        ip_address=ip_address,
    )

    # Set session cookie (HTTP-only, secure in production)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_DURATION_DAYS * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )

    return LoginResponse(
        status="success",
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_admin": user.role == "admin",
            "must_change_password": user.must_change_password,
        },
        message="Login successful",
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and invalidate session.

    Clears the session cookie and removes the session from the database.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        repo = _get_user_repo()

        # Get user for audit log before deleting session
        user = await repo.validate_session(session_id)

        # Delete the session
        await repo.delete_session(session_id)

        # Log logout
        if user:
            await repo.log_audit(
                audit_id=str(uuid.uuid4()),
                action="logout",
                user_id=user.id,
                resource_type="auth",
                ip_address=_get_client_ip(request),
            )

    # Clear the cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )

    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(request: Request):
    """Get current authenticated user information.

    Returns user details and their permissions (service account access).
    Supports both session-based auth and OAuth2 Proxy authentication.
    """
    # Check for OAuth2 Proxy user (set by middleware)
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        repo = _get_user_repo()
        permissions = await repo.get_user_service_account_ids(user.id)
        return UserInfo(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_admin=user.role == "admin",
            permissions=permissions,
        )

    # Fall back to session cookie check
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    repo = _get_user_repo()
    user = await repo.validate_session(session_id)

    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # Get user permissions
    permissions = await repo.get_user_service_account_ids(user.id)

    return UserInfo(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_admin=user.role == "admin",
        permissions=permissions,
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    password_request: ChangePasswordRequest,
):
    """Change the current user's password.

    - **current_password**: Current password for verification
    - **new_password**: New password (minimum 8 characters)
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    repo = _get_user_repo()
    user = await repo.validate_session(session_id)

    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # Verify current password
    if not verify_password(password_request.current_password, user.password_hash):
        await repo.log_audit(
            audit_id=str(uuid.uuid4()),
            action="change_password_failed",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details=json.dumps({"reason": "invalid_current_password"}),
            ip_address=_get_client_ip(request),
        )
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Hash new password and update (also clears must_change_password flag)
    new_hash = hash_password(password_request.new_password)
    await repo.update_user(user.id, password_hash=new_hash, must_change_password=False)

    # Log password change
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="change_password",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=_get_client_ip(request),
    )

    return {"status": "success", "message": "Password changed successfully"}


@router.get("/check")
async def check_auth_status(request: Request):
    """Check if user is authenticated.

    Returns authentication status and user info if authenticated.
    Useful for frontend to check session validity without full user data.

    Supports both session-based auth and OAuth2 Proxy authentication.
    """
    # Check for OAuth2 Proxy user (set by middleware)
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        is_oauth2 = getattr(request.state, "oauth2_authenticated", False)
        return {
            "authenticated": True,
            "auth_method": "oauth2_proxy" if is_oauth2 else "session",
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "is_admin": user.role == "admin",
                "must_change_password": False if is_oauth2 else user.must_change_password,
            },
        }

    # Fall back to session cookie check
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        return {
            "authenticated": False,
            "user": None,
        }

    repo = _get_user_repo()
    user = await repo.validate_session(session_id)

    if not user:
        return {
            "authenticated": False,
            "user": None,
        }

    return {
        "authenticated": True,
        "auth_method": "session",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_admin": user.role == "admin",
            "must_change_password": user.must_change_password,
        },
    }


# ==================== Setup Endpoints ====================

@router.get("/setup/status", response_model=SetupStatusResponse)
async def get_setup_status():
    """Check if initial setup is required.

    Returns whether setup has been completed and if any users exist.
    This endpoint is always accessible, even without authentication.
    """
    repo = _get_user_repo()

    # Check if any users exist
    user_count = await repo.count_users()
    has_users = user_count > 0

    # Check if setup_completed setting exists and is true
    setup_completed_str = await repo.get_setting("setup_completed")
    setup_completed = setup_completed_str == "1" if setup_completed_str else False

    # Setup is required if no users exist
    setup_required = not has_users

    return SetupStatusResponse(
        setup_required=setup_required,
        setup_completed=setup_completed,
        has_users=has_users,
    )


@router.post("/setup")
async def initial_setup(request: Request, setup_request: SetupRequest):
    """Create the first admin user during initial setup.

    This endpoint only works if no users exist in the system.
    The created user will have must_change_password=True, requiring
    them to change their password before accessing sensitive features.

    - **email**: Admin email address
    - **password**: Admin password (minimum 8 characters)
    - **display_name**: Display name for the admin
    """
    repo = _get_user_repo()
    ip_address = _get_client_ip(request)

    # Check if users already exist
    user_count = await repo.count_users()
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Setup already completed. Users already exist in the system.",
        )

    # Validate email format (basic check)
    email = setup_request.email.lower().strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Create the admin user with must_change_password=True
    user_id = str(uuid.uuid4())
    password_hash = hash_password(setup_request.password)

    user = await repo.create_user(
        user_id=user_id,
        email=email,
        password_hash=password_hash,
        display_name=setup_request.display_name,
        role="admin",
        must_change_password=True,  # Force password change on first login
    )

    # Mark setup as completed
    await repo.set_setting("setup_completed", "1")

    # Log the setup
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="initial_setup",
        user_id=user_id,
        resource_type="system",
        resource_id="setup",
        details=json.dumps({"email": email}),
        ip_address=ip_address,
    )

    return {
        "status": "success",
        "message": "Initial setup completed. Please log in and change your password.",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
    }


# ==================== Startup Functions ====================

async def ensure_admin_exists():
    """Ensure at least one admin user exists.

    Called on application startup. Creates admin from env vars if needed.
    """
    await _create_initial_admin()


async def cleanup_sessions():
    """Cleanup expired sessions and old login attempts.

    Should be called periodically (e.g., daily cron).
    """
    repo = _get_user_repo()
    sessions_deleted = await repo.cleanup_expired_sessions()
    attempts_deleted = await repo.cleanup_old_login_attempts(older_than_days=7)
    return {
        "sessions_deleted": sessions_deleted,
        "attempts_deleted": attempts_deleted,
    }


async def cleanup_audit_logs():
    """Cleanup old audit logs based on retention setting.

    Should be called periodically (e.g., daily cron).
    """
    repo = _get_user_repo()

    # Get retention setting
    retention_str = await repo.get_setting("audit_retention_days")
    retention_days = int(retention_str) if retention_str else 60

    if retention_days <= 0:
        return {"deleted": 0, "message": "Retention set to unlimited"}

    deleted = await repo.cleanup_old_audit_logs(retention_days)
    return {"deleted": deleted, "retention_days": retention_days}
