"""Trusted proxy helpers for request metadata.

Centralizes safe handling of forwarded headers so auth/session code can use
consistent trust boundaries.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Optional

from fastapi import Request


def is_trusted_proxy_request(request: Request) -> bool:
    """Return True for loopback or explicitly trusted proxy IPs/CIDRs."""
    if not request.client or not request.client.host:
        return False
    try:
        client_ip = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False

    trusted = os.environ.get("OAUTH2_PROXY_TRUSTED_IPS", "").strip()
    if trusted:
        for entry in trusted.split(","):
            token = entry.strip()
            if not token:
                continue
            try:
                if "/" in token:
                    if client_ip in ipaddress.ip_network(token, strict=False):
                        return True
                else:
                    if client_ip == ipaddress.ip_address(token):
                        return True
            except ValueError:
                continue
        return False

    return client_ip.is_loopback


def get_client_ip(request: Request) -> Optional[str]:
    """Get end-user IP from trusted forwarding chain or direct client."""
    if is_trusted_proxy_request(request):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass
    if request.client:
        return request.client.host
    return None


def get_request_scheme(request: Request) -> str:
    """Resolve scheme, honoring forwarded proto only from trusted proxies."""
    scheme = request.url.scheme
    if is_trusted_proxy_request(request):
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            proto = forwarded_proto.split(",")[0].strip().lower()
            if proto in {"http", "https"}:
                scheme = proto
    return scheme


def is_secure_request(request: Request) -> bool:
    """True when request should be treated as HTTPS for cookie policy."""
    return get_request_scheme(request) == "https"
