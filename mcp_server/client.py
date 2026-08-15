"""Async HTTP client for the RTBcat Agent API."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import AgentAPIResponseError, AgentAPIUnavailableError


class AgentAPIClient:
    """Forward one caller bearer token on every Agent API request."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if transport is not None and client is not None:
            raise ValueError("Pass either transport or client, not both.")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            transport=transport,
            timeout=timeout_seconds,
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        token: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                json=json,
            )
        except httpx.RequestError as exc:
            raise AgentAPIUnavailableError from exc

        if response.is_error:
            try:
                payload = response.json()
            except ValueError:
                detail: Any = "RTBcat Agent API returned an HTTP error."
            else:
                detail = payload.get("detail", payload)
            raise AgentAPIResponseError(response.status_code, detail)

        try:
            payload = response.json()
        except ValueError as exc:
            raise AgentAPIUnavailableError from exc
        if not isinstance(payload, dict):
            raise AgentAPIUnavailableError
        return payload

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AgentAPIClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()
