"""Shared public route contract for auth and edge proxy behavior.

These paths bypass the generic session/API-key gates because they are either
login entrypoints or have their own endpoint-level secret/HMAC checks. Reverse
proxy configs must forward them to the app instead of forcing OAuth redirects.
"""

PUBLIC_PATHS = {
    "/health",
    "/auth/bootstrap",
    "/auth/providers",
    "/auth/check",
    "/auth/me",
    "/auth/login",
    "/auth/register",
    "/auth/authing/login",
    "/auth/authing/callback",
    "/gmail/import/scheduled",
    "/precompute/refresh/scheduled",
    "/precompute/health",
    "/creatives/cache/refresh/scheduled",
}

PUBLIC_PREFIXES = (
    "/agent/v1/",
    "/api/agent/v1/",
    "/conversions/appsflyer/postback",
    "/conversions/generic/postback",
    "/conversions/redtrack/postback",
    "/conversions/voluum/postback",
    "/conversions/pixel",
)


def is_public_path(path: str) -> bool:
    """Check whether a request path bypasses generic auth middleware."""
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)
