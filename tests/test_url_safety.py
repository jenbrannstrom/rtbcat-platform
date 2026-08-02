"""SSRF regression tests for DNS-pinned public HTTP requests."""

from __future__ import annotations

import socket

import pytest

import services.url_safety as url_safety
from services.url_safety import PublicHTTPResponse, UnsafePublicURL


def _dns_result(ip: str, port: int) -> list[tuple]:
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sockaddr = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)]


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "192.0.2.1",
        "::1",
        "fe80::1",
    ],
)
def test_is_safe_public_http_url_rejects_non_global_addresses(
    monkeypatch: pytest.MonkeyPatch,
    ip: str,
) -> None:
    monkeypatch.setattr(
        url_safety.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _dns_result(ip, port),
    )

    assert url_safety.is_safe_public_http_url("https://model.example/score") is False


def test_is_safe_public_http_url_requires_every_resolved_address_to_be_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        url_safety.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            *_dns_result("93.184.216.34", port),
            *_dns_result("127.0.0.1", port),
        ],
    )

    assert url_safety.is_safe_public_http_url("https://model.example/score") is False


def test_request_uses_the_validated_numeric_socket_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connected_to: list[tuple] = []

    class _Socket:
        def settimeout(self, timeout: float) -> None:
            assert timeout == 7

        def connect(self, sockaddr: tuple) -> None:
            connected_to.append(sockaddr)

        def close(self) -> None:
            pass

    def _unexpected_dns(*args, **kwargs):
        raise AssertionError("socket.connect must not perform another hostname lookup")

    monkeypatch.setattr(url_safety.socket, "socket", lambda *args: _Socket())
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", _unexpected_dns)
    addresses = tuple(
        (family, socktype, proto, sockaddr)
        for family, socktype, proto, _canonname, sockaddr in _dns_result(
            "93.184.216.34", 443
        )
    )

    sock = url_safety._connect_resolved_addresses(addresses, 7)

    assert sock is not None
    assert connected_to == [("93.184.216.34", 443)]


def test_request_revalidates_and_blocks_a_private_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[str] = []

    def _getaddrinfo(host: str, port: int, **kwargs):
        ip = "93.184.216.34" if host == "public.example" else "169.254.169.254"
        return _dns_result(ip, port)

    def _request_once(target, **kwargs):
        requests.append(target.parsed.geturl())
        return PublicHTTPResponse(
            status=302,
            body=b"",
            headers={"location": "http://metadata.example/latest"},
            url=target.parsed.geturl(),
        )

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(url_safety, "_request_once", _request_once)

    with pytest.raises(UnsafePublicURL, match="non-public"):
        url_safety.request_public_http_url("https://public.example/score")

    assert requests == ["https://public.example/score"]


def test_cross_origin_redirect_drops_authorization_and_re_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_hosts: list[str] = []
    requests: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    def _getaddrinfo(host: str, port: int, **kwargs):
        resolved_hosts.append(host)
        return _dns_result("93.184.216.34", port)

    def _request_once(target, **kwargs):
        requests.append(
            (
                target.parsed.geturl(),
                kwargs["method"],
                kwargs["data"],
                dict(kwargs["headers"]),
            )
        )
        if len(requests) == 1:
            return PublicHTTPResponse(
                status=307,
                body=b"",
                headers={"location": "https://other.example/v2/score"},
                url=target.parsed.geturl(),
            )
        return PublicHTTPResponse(
            status=200,
            body=b"{}",
            headers={},
            url=target.parsed.geturl(),
        )

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(url_safety, "_request_once", _request_once)

    response = url_safety.request_public_http_url(
        "https://model.example/score",
        method="POST",
        data=b"payload",
        headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
    )

    assert response.status == 200
    assert resolved_hosts == ["model.example", "other.example"]
    assert requests[1][1:3] == ("POST", b"payload")
    assert "Authorization" not in requests[1][3]
    assert requests[1][3]["Content-Type"] == "application/json"
