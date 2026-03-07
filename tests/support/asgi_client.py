from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any

import httpx


def _ensure_async_override(override: Any) -> Any:
    if inspect.iscoroutinefunction(override):
        return override

    @functools.wraps(override)
    async def _async_override(*args: Any, **kwargs: Any) -> Any:
        return override(*args, **kwargs)

    return _async_override


class SyncASGIClient:
    """Minimal sync wrapper around httpx ASGITransport for test modules.

    This avoids Starlette TestClient teardown hangs in the current dependency
    stack while preserving a familiar `client.get()` / `client.post()` shape.
    Each request uses a short-lived AsyncClient, so callers do not need to
    manage client shutdown.
    """

    def __init__(self, app: Any, *, base_url: str = "http://testserver") -> None:
        self._app = app
        self._base_url = base_url
        overrides = getattr(app, "dependency_overrides", None)
        if isinstance(overrides, dict):
            for dependency, override in list(overrides.items()):
                overrides[dependency] = _ensure_async_override(override)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=self._app)
        async with httpx.AsyncClient(transport=transport, base_url=self._base_url) as client:
            return await client.request(method, url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
