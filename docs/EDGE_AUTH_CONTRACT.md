# Edge Auth Contract

This contract keeps nginx, Caddy, OAuth2 Proxy, and FastAPI from drifting into
different auth models.

## Ownership

The app owns auth decisions. Edge proxies own TLS, routing, upload limits, and
optional identity header injection.

## Required Proxy Behavior

All deployment proxies must follow these rules:

- `/login` reaches the Next.js dashboard.
- `/api/auth/*` reaches FastAPI without an edge OAuth redirect.
- `/oauth2/*` may route to OAuth2 Proxy.
- `/api/*` reaches FastAPI. FastAPI validates session cookies, API keys, and
  route-level webhook/scheduler secrets.
- OAuth2 Proxy may inject `X-Email` and `X-User` for authenticated Google users,
  but it must not be the only gate unless the deployment is intentionally
  Google-only.
- Proxies must not trust client-supplied `X-Email`; only internal proxy traffic
  may set it for FastAPI.

## Source Of Truth

Public paths and prefixes live in `api/auth_public_paths.py`.

The API-key middleware and session middleware import that module. Do not copy
public route lists into individual middleware files.

The GCP nginx site is written by `scripts/apply_gcp_nginx_auth_contract.sh`.
The startup script and deploy workflow both use that script so existing VMs and
newly provisioned VMs receive the same edge behavior. On hosts with Certbot
certificates for the configured domain, the script owns the HTTPS server block
and disables stale `/etc/nginx/sites-enabled/catscan.conf` files with a backup
so TLS traffic cannot bypass the repo-owned contract.

The outside-agent API has an optional extra edge gate. If
`CATSCAN_AGENT_API_HTPASSWD` is present in the runtime environment or
`/etc/catscan.env`, nginx adds Basic Auth to `/api/agent/v1/*` before the
request reaches FastAPI. FastAPI still requires the buyer-scoped
`cat_agent_...` bearer token.

## Guardrails

Run these before deploying edge/auth changes:

```bash
.venv/bin/pytest tests/test_api_key_service_user.py tests/test_auth_guardrails_static.py tests/test_auth_bootstrap.py
bash -n terraform/gcp/startup.sh
bash -n scripts/apply_gcp_nginx_auth_contract.sh
git diff --check
```

The guardrails assert that:

- password/bootstrap/OIDC login entrypoints bypass the generic API-key gate;
- both FastAPI auth middlewares use the shared public route contract;
- GCP nginx treats OAuth2 Proxy as an optional identity source;
- GCP nginx can add Basic Auth in front of the outside-agent API;
- GCP nginx owns the TLS site and disables stale alternate site files;
- Caddy leaves auth decisions to FastAPI.
