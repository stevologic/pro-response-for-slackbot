"""A tiny in-process token-bucket rate limiter, keyed per user.

Slack apps are trivially easy to spam, and every request costs a model call.
This limiter caps how often a single user can trigger a rewrite. It's
deliberately dependency-free and in-memory: fine for a single-instance
deployment, and easy to swap for Redis later if you scale out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

__all__ = ["RateLimiter"]


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class RateLimiter:
    """Refilling token bucket, one bucket per key.

    Args:
        rate_per_minute: Sustained requests allowed per key per minute. A value
            of ``0`` (or less) disables limiting entirely.
        burst: Maximum tokens a bucket can hold. Defaults to ``rate_per_minute``
            so a fresh user can send a short burst up to their per-minute quota.
    """

    def __init__(self, rate_per_minute: int, *, burst: int | None = None) -> None:
        self.rate_per_minute = rate_per_minute
        self.capacity = float(burst if burst is not None else max(rate_per_minute, 1))
        self._refill_per_sec = rate_per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.rate_per_minute > 0

    def allow(self, key: str) -> bool:
        """Consume one token for ``key``; return whether it was available."""

        if not self.enabled:
            return True

        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                # New keys start full so first-time users aren't penalized.
                self._buckets[key] = _Bucket(tokens=self.capacity - 1, updated_at=now)
                return True

            elapsed = now - bucket.updated_at
            bucket.tokens = min(
                self.capacity, bucket.tokens + elapsed * self._refill_per_sec
            )
            bucket.updated_at = now
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True
            return False

    def reset(self, key: str | None = None) -> None:
        """Clear one key's bucket, or all buckets when ``key`` is ``None``."""

        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)
