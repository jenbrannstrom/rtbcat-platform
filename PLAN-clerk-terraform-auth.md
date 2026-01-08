# Plan: Secure User Setup with Clerk + Terraform

## Problem Statement

Fresh installations are vulnerable to credential exposure because:
1. Users may deploy services before auth is properly configured
2. Installation sequence can be messed up, exposing the platform
3. Custom auth system requires careful setup (admin env vars, bcrypt, sessions)
4. If ports are exposed before auth middleware runs, services are accessible

**The user wants**: A simple, foolproof solution where Clerk credentials are provided at Terraform deployment time, preventing ANY exposure during installation.

---

## Proposed Solution: "No Clerk = No Service" Architecture

### Core Principle
Make Clerk credentials **mandatory Terraform inputs**. The application literally cannot start or serve requests without valid Clerk configuration.

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT SEQUENCE                          │
├─────────────────────────────────────────────────────────────────┤
│  1. User creates Clerk account → Gets API keys                  │
│  2. User runs: terraform apply -var="clerk_secret_key=sk_..."   │
│  3. Terraform validates Clerk keys are non-empty               │
│  4. VM starts, injects Clerk env vars                          │
│  5. App starts with Clerk middleware BLOCKING all requests      │
│  6. User visits app → Clerk login page (hosted by Clerk)        │
│  7. Clerk handles auth, returns session → App serves content    │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight**: The app never serves unprotected content because Clerk middleware runs BEFORE any route handler.

---

## Implementation Plan

### Phase 1: Terraform Changes (Mandatory Clerk Variables)

**File: `terraform/gcp/variables.tf`** (and AWS equivalent)

```terraform
variable "clerk_publishable_key" {
  description = "Clerk publishable key (pk_live_xxx or pk_test_xxx)"
  type        = string
  sensitive   = false  # Not secret, embedded in frontend

  validation {
    condition     = can(regex("^pk_(live|test)_", var.clerk_publishable_key))
    error_message = "Clerk publishable key must start with pk_live_ or pk_test_"
  }
}

variable "clerk_secret_key" {
  description = "Clerk secret key (sk_live_xxx or sk_test_xxx)"
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^sk_(live|test)_", var.clerk_secret_key))
    error_message = "Clerk secret key must start with sk_live_ or sk_test_"
  }
}
```

**Why this works**: Terraform won't even start deployment without valid-looking Clerk keys.

---

### Phase 2: Startup Script Injection

**File: `terraform/gcp/startup.sh`**

Add to the `.env` file creation:

```bash
# Clerk auth (REQUIRED - app won't start without these)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${clerk_publishable_key}
CLERK_SECRET_KEY=${clerk_secret_key}

# Clerk URLs
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/
```

---

### Phase 3: Dashboard Changes (Next.js + Clerk)

**3.1 Install Clerk SDK**

```bash
npm install @clerk/nextjs
```

**3.2 Add Clerk Provider**

**File: `dashboard/src/app/layout.tsx`**

```tsx
import { ClerkProvider } from '@clerk/nextjs'

export default function RootLayout({ children }) {
  return (
    <ClerkProvider>
      <html>
        <body>{children}</body>
      </html>
    </ClerkProvider>
  )
}
```

**3.3 Add Middleware (THE KEY PROTECTION)**

**File: `dashboard/src/middleware.ts`**

```typescript
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

// ONLY these routes are public - everything else requires auth
const isPublicRoute = createRouteMatcher([
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/api/health',  // Health check for load balancers
])

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect()  // Redirects to Clerk sign-in if not authenticated
  }
})

export const config = {
  matcher: [
    // Match all routes except static files
    '/((?!_next|[^?]*\\.(?:html?|css|js|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
```

**Why this is foolproof**:
- Middleware runs BEFORE any page or API route
- If Clerk env vars are missing, Clerk SDK throws error (app crashes, nothing exposed)
- If Clerk is configured, all routes require authentication by default
- No "window of vulnerability" during setup

---

### Phase 4: API Backend Changes (FastAPI + Clerk)

**4.1 Install Clerk Python SDK**

```bash
pip install clerk-backend-api
```

**4.2 Replace Custom Auth with Clerk Verification**

**File: `api/clerk_middleware.py`** (new file)

```python
import os
from fastapi import Request, HTTPException
from clerk_backend_api import Clerk
from clerk_backend_api.jwks import verify_token

clerk = Clerk(bearer_auth=os.environ.get("CLERK_SECRET_KEY"))

PUBLIC_PATHS = ["/health", "/docs", "/openapi.json"]

async def clerk_auth_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Get session token from cookie or Authorization header
    session_token = request.cookies.get("__session") or \
                    request.headers.get("Authorization", "").replace("Bearer ", "")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # Verify JWT with Clerk's JWKS
        claims = verify_token(
            token=session_token,
            options={"secret_key": os.environ["CLERK_SECRET_KEY"]}
        )
        request.state.user_id = claims["sub"]
        request.state.user_email = claims.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    return await call_next(request)
```

---

### Phase 5: Remove Custom Auth (Simplification)

Delete or deprecate:
- `api/auth_v2.py` - Custom login/logout endpoints
- `api/session_middleware.py` - Custom session validation
- `dashboard/src/contexts/auth-context.tsx` - Custom auth context
- `dashboard/src/app/login/page.tsx` - Custom login page
- Database tables: `user_sessions`, `login_attempts` (keep `users` for app-level roles)

**Keep**:
- `users` table (for app-specific roles: admin/user)
- `audit_log` table (still useful for tracking actions)
- Service account permissions (Clerk handles auth, app handles authorization)

---

## Security Guarantees

| Risk | Mitigation |
|------|------------|
| Deploy without Clerk | Terraform validation rejects empty/invalid keys |
| Services start before auth | Clerk middleware blocks ALL requests until auth |
| Env vars leaked | Clerk secret is marked `sensitive=true`, excluded from logs |
| Port exposure | Already fixed in GCP Terraform (no 3000/8000 rules) |
| Password brute force | Clerk handles rate limiting, MFA, breach detection |
| Session management | Clerk manages sessions, tokens, expiry |

---

## User Experience

### Before (Complex, Error-Prone)
1. Deploy infrastructure
2. Set `RTBCAT_ADMIN_EMAIL` and `RTBCAT_ADMIN_PASSWORD`
3. Wait for admin user creation
4. Navigate to /login
5. Enter credentials
6. Hope you didn't expose anything during setup

### After (Simple, Foolproof)
1. Create Clerk account (free tier: 10k MAU)
2. Copy API keys from Clerk dashboard
3. Run `terraform apply -var="clerk_secret_key=sk_..." -var="clerk_publishable_key=pk_..."`
4. Visit your domain → Clerk login/signup page
5. Done. Auth was active from millisecond one.

---

## Migration Path for Existing Users

For users with existing custom auth:
1. Clerk supports user import via API or CSV
2. Add Clerk alongside existing auth during transition
3. Migrate users, then switch middleware
4. Remove old auth code

---

## Files to Create/Modify

### New Files
- [ ] `dashboard/src/middleware.ts` - Clerk route protection
- [ ] `api/clerk_middleware.py` - Backend JWT verification

### Modified Files
- [ ] `terraform/gcp/variables.tf` - Add Clerk variables with validation
- [ ] `terraform/gcp/main.tf` - Pass Clerk vars to startup script
- [ ] `terraform/gcp/startup.sh` - Inject Clerk env vars
- [ ] `terraform/variables.tf` (AWS) - Same Clerk variables
- [ ] `terraform/main.tf` (AWS) - Pass Clerk vars to user data
- [ ] `terraform/user_data.sh` (AWS) - Inject Clerk env vars
- [ ] `dashboard/package.json` - Add @clerk/nextjs
- [ ] `dashboard/src/app/layout.tsx` - Add ClerkProvider
- [ ] `api/requirements.txt` - Add clerk-backend-api
- [ ] `api/main.py` - Use clerk_middleware instead of session_middleware

### Files to Deprecate (Later)
- [ ] `api/auth_v2.py` - Custom auth endpoints
- [ ] `api/session_middleware.py` - Custom session handling
- [ ] `dashboard/src/contexts/auth-context.tsx` - Custom auth context
- [ ] `dashboard/src/app/login/page.tsx` - Custom login page

---

## Estimated Complexity

| Component | Effort |
|-----------|--------|
| Terraform variables | Simple - 20 lines |
| Startup script changes | Simple - 10 lines |
| Clerk middleware (Next.js) | Simple - 30 lines |
| Clerk middleware (FastAPI) | Medium - 50 lines |
| Remove old auth | Optional - can keep for fallback |

**Total**: ~100-150 lines of code for complete Clerk integration

---

## Alternative Considered: Basic Auth in Nginx

**Rejected because**:
- Still requires managing passwords
- No session management, user management, or MFA
- Every request prompts for credentials (poor UX)
- Doesn't solve the "proper sequence" problem

---

## Questions for User

1. **Free tier OK?** Clerk free tier supports 10,000 monthly active users. Is this sufficient?
2. **Sign-up allowed?** Should anyone be able to sign up, or only invited users?
3. **Social login?** Clerk supports Google, GitHub, etc. - want these enabled?
4. **Keep old auth as fallback?** Or remove it entirely for simplicity?

---

## Recommendation

**Implement this plan.** It's:
- ✅ Ultra simple (100 lines of code)
- ✅ Foolproof (app crashes without Clerk = no exposure)
- ✅ Terraform-native (credentials provided at deploy time)
- ✅ Sequence-enforced (can't deploy without valid Clerk keys)
- ✅ Production-ready (Clerk handles security, compliance, MFA)
- ✅ Free for most use cases (10k MAU)
