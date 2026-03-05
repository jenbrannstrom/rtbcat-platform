# Authentication

Cat-Scan supports three login methods. All three produce the same session cookie (`rtbcat_session`) so the rest of the app works identically regardless of how the user logged in.

## Login methods

| Method | How it works | When to use |
|--------|-------------|-------------|
| **Email / Password** | POST to `/api/auth/login` | Default for most users |
| **Google (OAuth2 Proxy)** | Redirects through `/oauth2/sign_in` | Teams already on Google Workspace |
| **Authing (OIDC)** | Redirects through `/api/auth/authing/login` | Teams using Authing identity pool |

The login page at `/login` discovers enabled providers from `GET /api/auth/providers` at runtime and shows only valid options.

## Who can log in?

- **Email/Password** -- only users who have been registered (see below).
- **Google** -- any user whose email domain is in the OAuth2 Proxy `email_domains` list. On VM2 this is currently `rtb.cat`. Users are auto-created on first Google login.
- **Authing** -- any user who can authenticate with the configured Authing pool. Users are auto-created on first Authing login.

## How to register a new user

### First user (bootstrap)

#### Production (secure default)

Set `CATSCAN_REQUIRE_BOOTSTRAP_TOKEN=true` (default) and configure `CATSCAN_BOOTSTRAP_TOKEN`.
The first admin **must** be created via `/auth/bootstrap`:

```bash
# 1. Get the token from the VM
sudo grep CATSCAN_BOOTSTRAP_TOKEN /etc/catscan.env

# 2. Create the first admin
curl -X POST https://vm2.scan.rtb.cat/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"bootstrap_token": "<token>", "email": "admin@rtb.cat", "password": "securepassword", "display_name": "Admin"}'
```

While bootstrap is incomplete:
- Google OAuth login will not auto-create users
- Authing OIDC login will not auto-create users
- Password registration (`/auth/register`) will be blocked

#### Local development (legacy mode)

If you explicitly set `CATSCAN_REQUIRE_BOOTSTRAP_TOKEN=false`, legacy behavior is enabled:
the first user to register or log in via any method becomes **admin**.

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@rtb.cat", "password": "securepassword", "display_name": "Admin"}'
```

Or navigate to `/login`, click "Sign in with Email", and register (only shown when no users exist).

#### Existing deployments (upgrade path)

When upgrading to a version with bootstrap guards, the app auto-heals: if users already exist, `bootstrap_completed` is automatically set to `1` on startup. No manual action required.

### Subsequent users

After the first user exists, registration is **restricted to admins only**:

- An admin can register users via the API:
  ```bash
  curl -X POST https://vm2.scan.rtb.cat/api/auth/register \
    -H "Content-Type: application/json" \
    -H "Cookie: rtbcat_session=<admin-session-id>" \
    -d '{"email": "newuser@rtb.cat", "password": "securepassword"}'
  ```
- Or via the admin user management page at `/admin/users`.
- Non-admin users trying to register get: `403 Registration is disabled. Please contact an administrator.`

### Google / Authing users

Users logging in via Google or Authing are **auto-created** on first login -- no registration step needed. The first user (if no users exist yet) gets admin; subsequent users get the `user` role.

## Limiting registration

Registration is already locked down by default:

| Control | How |
|---------|-----|
| **Disable self-registration** | Automatic -- after the first user, only admins can call `/api/auth/register` |
| **Restrict Google login domains** | Edit `email_domains` in `/etc/oauth2-proxy.cfg` on the VM (currently `["rtb.cat"]`) |
| **Restrict Authing login** | Configure allowed users/groups in your Authing application settings |
| **Disable a login method entirely** | Set `CATSCAN_ENABLE_AUTHING_LOGIN=false`, `CATSCAN_ENABLE_GOOGLE_LOGIN=false`, or `CATSCAN_ENABLE_PASSWORD_LOGIN=false` |
| **Deactivate a specific user** | Set `is_active = false` via admin panel at `/admin/users` -- they'll get `403 Account is deactivated` |

## Password requirements

- Minimum 8 characters
- Hashed with bcrypt (via passlib)

## Session details

- Cookie name: `rtbcat_session`
- Duration: 30 days
- HttpOnly, Secure (on HTTPS), SameSite=Lax

## Setting a password for OAuth users

Users who logged in via Google or Authing can add a password for direct login:

```bash
curl -X POST https://vm2.scan.rtb.cat/api/auth/set-password \
  -H "Content-Type: application/json" \
  -H "Cookie: rtbcat_session=<session-id>" \
  -d '{"password": "newpassword"}'
```

## Architecture (VM2)

```
Browser
  |
  v
Nginx (TLS termination)
  |-- /login, /            --> Dashboard (Next.js :3000)
  |-- /api/auth/*           --> API :8000 (public, no auth layer)
  |-- /api/*                --> API :8000 (session cookie validated by app)
  |-- /oauth2/*             --> OAuth2 Proxy :4180 (Google SSO)
  |-- /health               --> API :8000 (public)
  v
API (FastAPI)
  |-- session_middleware.py   validates rtbcat_session cookie
  |-- auth_password.py        email/password login + registration
  |-- auth_authing.py         Authing OIDC flow
  |-- auth_oauth_proxy.py     Google via OAuth2 Proxy headers
```

The nginx config is stored in the repo at `terraform/gcp_sg_vm2/nginx-catscan.conf`.

## Environment variables

| Variable | Required for | Example |
|----------|-------------|---------|
| `CATSCAN_ENABLE_PASSWORD_LOGIN` | Password login toggle | `true` |
| `CATSCAN_ENABLE_GOOGLE_LOGIN` | Google login toggle | `true` |
| `CATSCAN_ENABLE_AUTHING_LOGIN` | Authing login toggle | `true` |
| `CATSCAN_DEFAULT_LOGIN_METHOD` | Preferred default when multiple enabled | `authing` |
| `CATSCAN_REQUIRE_BOOTSTRAP_TOKEN` | Enforce secure first-admin bootstrap flow | `true` |
| `CATSCAN_BOOTSTRAP_TOKEN` | Token used by `/auth/bootstrap` | `<random-secret>` |
| `OAUTH2_PROXY_ENABLED` | Google login | `true` |
| `OAUTH2_PROXY_TRUSTED_IPS` | Trusted proxy source IPs/CIDRs for auth headers | `127.0.0.1,::1` |
| `AUTHING_APP_ID` | Authing login | `6abc...` |
| `AUTHING_APP_SECRET` | Authing login | `secret...` |
| `AUTHING_ISSUER` | Authing login | `https://catscan.authing.cn/oidc` |

See `.env.example` for the full list.
