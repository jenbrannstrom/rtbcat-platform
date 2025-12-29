# Multi-User Accounts Feature Plan

## Overview

Transform RTBCat from a single-user application to a multi-user system where:
- Multiple users can log in with their own credentials
- Each user sees only the accounts (service accounts / buyer seats) assigned to them
- Admins can manage users and assign account permissions

---

## Current State Analysis

### What Exists Today
| Component | Current State |
|-----------|---------------|
| Users | None - single hardcoded login hash in `login.html` |
| Authentication | Client-side hash check, API key for backend |
| Authorization | None - all data visible to anyone authenticated |
| Service Accounts | Multi-account support exists (Google credentials) |
| Buyer Seats | Linked to service accounts, already multi-seat |
| Admin Panel | None |

### Key Files to Modify
- `/api/auth.py` - Replace API key auth with session/JWT
- `/storage/schema.py` - Add user tables
- `/storage/database.py` - Add user-aware queries
- `/login.html` - Integrate with real auth backend
- `/dashboard/src/` - Add admin panel pages

---

## Phase 1: Database Schema

### 1.1 New Tables

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- UUID
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,      -- bcrypt hash
    display_name TEXT,
    role TEXT DEFAULT 'user',         -- 'admin' or 'user'
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    last_login_at TEXT
);

-- User sessions (for session-based auth)
CREATE TABLE user_sessions (
    id TEXT PRIMARY KEY,              -- UUID session token
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- User-to-ServiceAccount permissions
CREATE TABLE user_service_account_permissions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    service_account_id TEXT NOT NULL,
    permission_level TEXT DEFAULT 'read',  -- 'read', 'write', 'admin'
    granted_by TEXT,                        -- user_id of admin who granted
    granted_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (service_account_id) REFERENCES service_accounts(id) ON DELETE CASCADE,
    UNIQUE(user_id, service_account_id)
);

-- Audit log for compliance
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,             -- 'login', 'logout', 'view', 'create', 'update', 'delete'
    resource_type TEXT,               -- 'user', 'service_account', 'buyer_seat', etc.
    resource_id TEXT,
    details TEXT,                     -- JSON with additional context
    ip_address TEXT,
    created_at TEXT NOT NULL
);
```

### 1.2 Indexes
```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_user_sa_perms_user ON user_service_account_permissions(user_id);
CREATE INDEX idx_user_sa_perms_sa ON user_service_account_permissions(service_account_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
```

### 1.3 Migration Strategy
1. Add schema version 41 with new tables
2. Create first admin user from environment variable or setup wizard
3. Existing service accounts remain, just no user permissions initially
4. Admin must assign users to accounts after migration

---

## Phase 2: Backend Authentication

### 2.1 New Auth Module (`/api/auth_v2.py`)

**Components:**
- Password hashing with bcrypt
- Session token generation (UUID + secure random)
- Session validation middleware
- Login/logout endpoints
- Password reset flow (future)

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Authenticate user, create session |
| POST | `/auth/logout` | Invalidate session |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/change-password` | Change own password |

### 2.2 Authentication Flow
```
1. User submits email/password to POST /auth/login
2. Backend validates credentials against users table
3. Create session in user_sessions table
4. Return session token as HTTP-only cookie
5. All subsequent requests include cookie
6. Middleware validates session on each request
7. Session expiry: 24 hours (configurable)
8. Sliding expiry: Reset on activity
```

### 2.3 Middleware Changes
- Replace `APIKeyAuthMiddleware` with `SessionAuthMiddleware`
- Add `get_current_user()` dependency for routes
- Add `require_admin()` dependency for admin routes
- Keep API key auth as fallback for programmatic access

### 2.4 Session Security
- HTTP-only cookies (prevent XSS access)
- Secure flag in production (HTTPS only)
- SameSite=Strict (CSRF protection)
- Session tokens: 256-bit random + UUID
- Rate limiting on login attempts

---

## Phase 3: Backend Authorization

### 3.1 Permission Model

**Roles:**
| Role | Capabilities |
|------|--------------|
| `admin` | All operations, manage users, assign accounts |
| `user` | View/edit only assigned accounts |

**Permission Levels (per service account):**
| Level | Capabilities |
|-------|--------------|
| `read` | View data, no modifications |
| `write` | View + modify creatives, campaigns, settings |
| `admin` | Write + manage account settings, delete data |

### 3.2 Data Filtering Strategy

**Before (current):**
```python
async def list_creatives(store: SQLiteStore):
    return await store.get_all_creatives()  # Returns everything
```

**After (with user context):**
```python
async def list_creatives(
    store: SQLiteStore,
    current_user: User = Depends(get_current_user)
):
    # Get user's permitted service accounts
    permitted_accounts = await store.get_user_service_accounts(current_user.id)

    # Filter creatives to only those accounts
    return await store.get_creatives_for_accounts(permitted_accounts)
```

### 3.3 Key Query Changes

Every data query must be filtered by user's permitted accounts:

| Table | Filter By |
|-------|-----------|
| `creatives` | `buyer_seat_id` → `service_account_id` |
| `rtb_daily` | `account_id` or `buyer_seat_id` |
| `buyer_seats` | `service_account_id` |
| `pretargeting_configs` | `account_id` |
| `campaigns` | `account_id` |
| `rtb_endpoints` | `account_id` |

### 3.4 Repository Changes

Add new repository: `/storage/repositories/user_repository.py`
- `create_user()`
- `get_user_by_email()`
- `get_user_by_id()`
- `update_user()`
- `delete_user()`
- `get_user_permissions()`
- `grant_permission()`
- `revoke_permission()`

Modify existing repositories to accept `user_id` parameter for filtered queries.

---

## Phase 4: Admin Panel (Backend)

### 4.1 Admin API Endpoints

**User Management:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List all users |
| POST | `/admin/users` | Create new user |
| GET | `/admin/users/{id}` | Get user details |
| PUT | `/admin/users/{id}` | Update user |
| DELETE | `/admin/users/{id}` | Deactivate user |
| POST | `/admin/users/{id}/reset-password` | Admin reset password |

**Permission Management:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users/{id}/permissions` | Get user's account access |
| POST | `/admin/users/{id}/permissions` | Grant account access |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Revoke account access |
| GET | `/admin/service-accounts/{id}/users` | List users with access |

**Audit Log:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/audit-log` | Query audit events |

### 4.2 Admin Route Protection
```python
from fastapi import Depends

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != 'admin':
        raise HTTPException(403, "Admin access required")
    return current_user

@router.get("/admin/users")
async def list_users(admin: User = Depends(require_admin)):
    ...
```

---

## Phase 5: Admin Panel (Frontend)

### 5.1 New Pages

| Route | Purpose |
|-------|---------|
| `/admin` | Admin dashboard overview |
| `/admin/users` | User list with search/filter |
| `/admin/users/new` | Create new user form |
| `/admin/users/[id]` | Edit user, manage permissions |
| `/admin/audit-log` | View system audit log |

### 5.2 User List Page (`/admin/users`)

**Features:**
- Table with columns: Email, Display Name, Role, Status, Last Login, Actions
- Search by email/name
- Filter by role (admin/user) and status (active/inactive)
- Quick actions: Edit, Reset Password, Deactivate
- "Add User" button

### 5.3 User Edit Page (`/admin/users/[id]`)

**Sections:**

1. **User Details**
   - Email (editable for new, read-only for existing)
   - Display Name
   - Role dropdown (admin/user)
   - Active/Inactive toggle

2. **Account Permissions**
   - List of all service accounts with checkboxes
   - For each: permission level dropdown (read/write/admin)
   - "Grant Access" / "Revoke Access" buttons
   - Show buyer seats under each service account for reference

3. **Security**
   - Reset password button
   - View login history
   - Force logout (invalidate all sessions)

### 5.4 UI Components

**New Components:**
- `UserTable` - Paginated user list
- `UserForm` - Create/edit user form
- `PermissionManager` - Account assignment interface
- `AuditLogTable` - Audit event viewer
- `AdminSidebar` - Admin navigation

**Reusable:**
- Existing `Table`, `Button`, `Form` components
- Existing sidebar pattern

### 5.5 Navigation Changes

**Sidebar Modifications:**
- Add "Admin" section (visible only to admins)
- Links: Users, Audit Log
- User dropdown in header: Profile, Logout

---

## Phase 6: Login Page Integration

### 6.1 Replace `login.html`

Convert standalone HTML to Next.js page at `/login`:

**Features:**
- Email/password form
- "Remember me" option (longer session)
- Error messages for invalid credentials
- Redirect to dashboard on success
- Forgot password link (future)

### 6.2 Auth Context

New React context: `/dashboard/src/contexts/auth-context.tsx`

```typescript
interface AuthContext {
  user: User | null;
  isLoading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
```

### 6.3 Protected Routes

Wrap pages with auth check:
```typescript
// /dashboard/src/components/ProtectedRoute.tsx
function ProtectedRoute({ children, requireAdmin = false }) {
  const { user, isLoading, isAdmin } = useAuth();

  if (isLoading) return <LoadingSpinner />;
  if (!user) redirect('/login');
  if (requireAdmin && !isAdmin) redirect('/');

  return children;
}
```

---

## Phase 7: Data Migration & First Admin

### 7.1 Initial Setup

**Option A: Environment Variable**
```bash
RTBCAT_ADMIN_EMAIL=admin@example.com
RTBCAT_ADMIN_PASSWORD=changeme123
```
On first startup, create admin user if not exists.

**Option B: Setup Wizard**
Extend existing `/setup` page with "Create Admin User" step when no users exist.

### 7.2 Migration Steps

1. Run schema migration (v40 → v41)
2. Create first admin user
3. Admin logs in
4. Admin creates additional users
5. Admin assigns accounts to users
6. Users can now log in and see only their accounts

---

## Implementation Order

### Sprint 1: Core Auth (Backend)
1. Add user tables to schema (v41)
2. Implement password hashing utilities
3. Create user repository
4. Add login/logout endpoints
5. Implement session middleware
6. Add `get_current_user` dependency
7. Create first admin via env var

### Sprint 2: Authorization (Backend)
1. Add permission tables
2. Implement permission repository
3. Add user filtering to existing queries
4. Create admin user management endpoints
5. Create permission management endpoints
6. Add audit logging

### Sprint 3: Login & Auth (Frontend)
1. Convert login.html to Next.js /login page
2. Create auth context
3. Add ProtectedRoute wrapper
4. Add logout functionality
5. Update sidebar with user info

### Sprint 4: Admin Panel (Frontend)
1. Create /admin layout
2. Build user list page
3. Build user create/edit form
4. Build permission manager component
5. Build audit log viewer
6. Add admin navigation

### Sprint 5: Polish & Security
1. Rate limiting on auth endpoints
2. Session management (force logout)
3. Password strength requirements
4. Comprehensive error handling
5. Test multi-user scenarios
6. Documentation

---

## API Changes Summary

### New Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Login |
| POST | `/auth/logout` | User | Logout |
| GET | `/auth/me` | User | Current user |
| POST | `/auth/change-password` | User | Change password |
| GET | `/admin/users` | Admin | List users |
| POST | `/admin/users` | Admin | Create user |
| GET | `/admin/users/{id}` | Admin | Get user |
| PUT | `/admin/users/{id}` | Admin | Update user |
| DELETE | `/admin/users/{id}` | Admin | Deactivate user |
| GET | `/admin/users/{id}/permissions` | Admin | Get permissions |
| POST | `/admin/users/{id}/permissions` | Admin | Grant permission |
| DELETE | `/admin/users/{id}/permissions/{sa}` | Admin | Revoke permission |
| GET | `/admin/audit-log` | Admin | Query audit log |

### Modified Endpoints (all existing data endpoints)
All existing endpoints that return data will be modified to:
1. Require authenticated user (session cookie)
2. Filter results to user's permitted accounts only

---

## Security Considerations

### Authentication
- bcrypt for password hashing (cost factor 12)
- Secure session tokens (256-bit entropy)
- HTTP-only, Secure, SameSite cookies
- Session expiry and sliding window
- Rate limiting on login (5 attempts/minute)

### Authorization
- Server-side permission checks on every request
- No client-side permission bypasses
- Admin operations require explicit role check
- Audit log all sensitive operations

### Data Isolation
- All queries filtered by user permissions
- No way to access unassigned accounts
- API responses never include unauthorized data

### Password Policy (Recommended)
- Minimum 12 characters
- Must include: uppercase, lowercase, number
- No password reuse (last 5)
- Optional: MFA in future phase

---

## Testing Strategy

### Unit Tests
- Password hashing/verification
- Session token generation
- Permission checking logic
- Query filtering functions

### Integration Tests
- Login flow (valid/invalid credentials)
- Session validation and expiry
- Permission enforcement on endpoints
- Admin user management operations

### E2E Tests
- Full login → dashboard → logout flow
- Admin creates user → user logs in
- Admin assigns account → user sees data
- Permission revocation → data no longer visible

---

## Future Enhancements (Out of Scope)

- Multi-factor authentication (MFA)
- SSO/SAML integration
- OAuth providers (Google, Microsoft)
- Password reset via email
- User groups/teams
- Fine-grained permissions (per buyer seat)
- API keys per user (for automation)
- Login notifications
- Session management UI (view active sessions)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing single-user workflows | First admin auto-created, maintains compatibility |
| Performance impact of permission checks | Cache permissions in session, indexed queries |
| Complex permission model | Start simple (account-level only), extend later |
| Migration downtime | Schema changes are additive, no data loss |
| Security vulnerabilities | Follow OWASP guidelines, security review |

---

## Success Criteria

1. Multiple users can log in independently
2. Users only see accounts assigned to them
3. Admins can create/edit/deactivate users
4. Admins can assign accounts to users
5. Audit log captures all significant actions
6. No unauthorized data access possible
7. Existing functionality preserved for assigned accounts
