"""In-process token-bucket limiting keyed only by token digests."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    """Continuously refill one fixed-capacity bucket per bearer-token hash."""

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be at least 1.")
        self.capacity = float(requests_per_minute)
        self._refill_per_second = self.capacity / 60.0
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    @staticmethod
    def token_key(token: str) -> str:
        """Return the non-reversible key used for bucket storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @property
    def bucket_keys(self) -> frozenset[str]:
        """Expose digest keys for diagnostics without exposing credentials."""
        return frozenset(self._buckets)

    def consume(self, token: str) -> float | None:
        """Consume one request or return seconds until capacity is available."""
        now = self._clock()
        key = self.token_key(token)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self.capacity, updated_at=now)
            self._buckets[key] = bucket
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(
                self.capacity,
                bucket.tokens + elapsed * self._refill_per_second,
            )
            bucket.updated_at = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return None
        return (1.0 - bucket.tokens) / self._refill_per_second
