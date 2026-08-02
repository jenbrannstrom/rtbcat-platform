"""URL safety checks and DNS-pinned requests for network fetch operations."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_DEFAULT_MAX_REDIRECTS = 5
_DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class UnsafePublicURL(ValueError):
    """Raised when an outbound URL could reach a non-public destination."""


@dataclass(frozen=True)
class PublicHTTPResponse:
    """Bounded response returned by :func:`request_public_http_url`."""

    status: int
    body: bytes
    headers: Mapping[str, str]
    url: str


@dataclass(frozen=True)
class _ResolvedTarget:
    parsed: ParseResult
    port: int
    addresses: tuple[tuple[int, int, int, tuple], ...]


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # ``is_global`` also rejects special-use ranges such as carrier-grade NAT
    # and documentation networks. Multicast is reported as global on some
    # Python versions, so keep that rejection explicit.
    return ip.is_global and not ip.is_multicast


def _resolve_host(
    hostname: str,
    port: int,
) -> tuple[tuple[int, int, int, tuple], ...]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafePublicURL("URL hostname could not be resolved") from exc

    addresses: list[tuple[int, int, int, tuple]] = []
    seen: set[tuple[int, int, int, tuple]] = set()
    for family, socktype, proto, _canonname, sockaddr in infos:
        address = sockaddr[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafePublicURL(
                "URL hostname resolved to an invalid address"
            ) from exc
        if not _is_public_ip(ip):
            raise UnsafePublicURL("URL hostname resolves to a non-public address")
        resolved = (family, socktype, proto, sockaddr)
        if resolved not in seen:
            addresses.append(resolved)
            seen.add(resolved)

    if not addresses:
        raise UnsafePublicURL("URL hostname did not resolve to a public address")
    return tuple(addresses)


def _resolve_public_target(url: str) -> _ResolvedTarget:
    if not url:
        raise UnsafePublicURL("URL is required")

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafePublicURL("URL scheme must be http or https")
    if parsed.username or parsed.password:
        raise UnsafePublicURL("URL must not include user information")
    if not parsed.hostname:
        raise UnsafePublicURL("URL hostname is required")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafePublicURL("URL port is invalid") from exc

    return _ResolvedTarget(
        parsed=parsed,
        port=port,
        addresses=_resolve_host(parsed.hostname, port),
    )


def is_safe_public_http_url(url: str) -> bool:
    """Allow only public http/https URLs (blocks local/private/internal hosts)."""
    try:
        _resolve_public_target(url)
    except (UnsafePublicURL, UnicodeError):
        return False
    return True


def _connect_resolved_addresses(
    addresses: Sequence[tuple[int, int, int, tuple]],
    timeout: float,
    source_address: Optional[tuple[str, int]] = None,
) -> socket.socket:
    """Connect only to a previously validated numeric socket address."""
    last_error: Optional[OSError] = None
    for family, socktype, proto, sockaddr in addresses:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()

    if last_error is not None:
        raise last_error
    raise OSError("No validated public address was available")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(
        self,
        host: str,
        port: int,
        addresses: Sequence[tuple[int, int, int, tuple]],
        timeout: float,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._addresses = addresses
        self._timeout_seconds = timeout

    def connect(self) -> None:
        self.sock = _connect_resolved_addresses(
            self._addresses,
            self._timeout_seconds,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        addresses: Sequence[tuple[int, int, int, tuple]],
        timeout: float,
    ) -> None:
        context = ssl.create_default_context()
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            context=context,
        )
        self._addresses = addresses
        self._timeout_seconds = timeout
        self._ssl_context = context

    def connect(self) -> None:
        raw_socket = _connect_resolved_addresses(
            self._addresses,
            self._timeout_seconds,
        )
        try:
            self.sock = self._ssl_context.wrap_socket(
                raw_socket, server_hostname=self.host
            )
        except Exception:
            raw_socket.close()
            raise


def _request_target(parsed: ParseResult) -> str:
    return urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))


def _request_once(
    target: _ResolvedTarget,
    *,
    method: str,
    data: Optional[bytes],
    headers: Mapping[str, str],
    timeout: float,
    max_response_bytes: int,
) -> PublicHTTPResponse:
    connection_class = (
        _PinnedHTTPSConnection
        if target.parsed.scheme == "https"
        else _PinnedHTTPConnection
    )
    connection = connection_class(
        target.parsed.hostname or "",
        target.port,
        target.addresses,
        timeout,
    )
    try:
        connection.request(
            method,
            _request_target(target.parsed),
            body=data,
            headers=dict(headers),
        )
        response = connection.getresponse()
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise ValueError("Public HTTP response exceeded the size limit")
        return PublicHTTPResponse(
            status=int(response.status),
            body=body,
            headers={key.lower(): value for key, value in response.getheaders()},
            url=target.parsed.geturl(),
        )
    finally:
        connection.close()


def _origin(parsed: ParseResult) -> tuple[str, str, int]:
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, (parsed.hostname or "").lower(), port


def _without_header(headers: Mapping[str, str], name: str) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() != name.lower()}


def request_public_http_url(
    url: str,
    *,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = 10,
    max_redirects: int = _DEFAULT_MAX_REDIRECTS,
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> PublicHTTPResponse:
    """Request a public URL without DNS-rebinding or redirect SSRF gaps.

    Every hop is resolved immediately before connection, all resolved addresses
    must be globally routable, and the socket connects to one of those exact
    numeric addresses. Redirects are followed manually so their destinations
    receive the same validation.
    """
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_redirects < 0:
        raise ValueError("max_redirects must not be negative")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be greater than zero")

    current_url = str(url or "").strip()
    current_method = str(method or "GET").upper()
    current_data = data
    current_headers = dict(headers or {})
    redirects_followed = 0

    while True:
        # This resolution is coupled to the numeric addresses used by the
        # connection below; no hostname lookup happens inside socket.connect.
        target = _resolve_public_target(current_url)
        response = _request_once(
            target,
            method=current_method,
            data=current_data,
            headers=current_headers,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        location = response.headers.get("location")
        if response.status not in _REDIRECT_STATUSES or not location:
            return response
        if redirects_followed >= max_redirects:
            raise ValueError("Public HTTP request exceeded the redirect limit")

        next_url = urljoin(current_url, location)
        next_parsed = urlparse(next_url.strip())
        if _origin(target.parsed) != _origin(next_parsed):
            current_headers = _without_header(current_headers, "Authorization")

        if response.status in {301, 302, 303} and current_method != "HEAD":
            current_method = "GET"
            current_data = None
            current_headers = _without_header(current_headers, "Content-Type")
            current_headers = _without_header(current_headers, "Content-Length")

        current_url = next_url
        redirects_followed += 1
