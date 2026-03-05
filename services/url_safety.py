"""URL safety checks for network fetch operations."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        address = info[4][0]
        try:
            ips.append(ipaddress.ip_address(address))
        except ValueError:
            continue
    return ips


def is_safe_public_http_url(url: str) -> bool:
    """Allow only public http/https URLs (blocks local/private/internal hosts)."""
    if not url:
        return False

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False
    if not parsed.hostname:
        return False

    ips = _resolve_host_ips(parsed.hostname)
    if not ips:
        return False

    return all(_is_public_ip(ip) for ip in ips)
