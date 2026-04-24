"""Per-IP rate limiting middleware (in-memory token bucket).

In prod you'd swap the backing store for Redis. This is fine for
single-process dev/staging.
"""

from __future__ import annotations

import time
from collections import defaultdict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = structlog.get_logger()


RATE_LIMITS: list[tuple[str, int]] = [
    ("/v1/events", 200),
    ("/v1/score", 50),
    ("/v1/cases", 30),
    ("/v1/analytics", 30),
    ("/v1/settings", 20),
]

DEFAULT_LIMIT = 100
WINDOW_SECONDS = 1.0  # sliding window size


class _TokenBucket:
    """Simple token bucket per client."""

    __slots__ = ("tokens", "capacity", "last_refill")

    def __init__(self, capacity: int):
        self.tokens = float(capacity)
        self.capacity = capacity
        self.last_refill = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.last_refill = now
        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.capacity)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter using token buckets."""

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        # buckets[client_key] → _TokenBucket
        self._buckets: dict[str, _TokenBucket] = defaultdict(lambda: _TokenBucket(DEFAULT_LIMIT))
        self._last_cleanup = time.monotonic()

    def _get_limit(self, path: str) -> int:
        for prefix, limit in RATE_LIMITS:
            if path.startswith(prefix):
                return limit
        return DEFAULT_LIMIT

    def _client_key(self, request: Request, path: str) -> str:
        # Use forwarded IP if behind a proxy, else direct client
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"
        limit = self._get_limit(path)
        return f"{ip}:{limit}"

    def _maybe_cleanup(self) -> None:
        """Evict stale buckets every 60s to avoid memory leak."""
        now = time.monotonic()
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        stale_cutoff = now - 120  # buckets idle for 2 min
        stale_keys = [
            k for k, b in self._buckets.items() if b.last_refill < stale_cutoff
        ]
        for k in stale_keys:
            del self._buckets[k]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Don't rate-limit health checks or metrics
        if path in ("/health", "/metrics", "/"):
            return await call_next(request)

        client_key = self._client_key(request, path)
        limit = self._get_limit(path)

        # Get or create bucket with the right capacity
        if client_key not in self._buckets:
            self._buckets[client_key] = _TokenBucket(limit)

        bucket = self._buckets[client_key]

        if not bucket.allow():
            log.warning("rate_limit.exceeded", client=client_key, path=path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": "1"},
            )

        self._maybe_cleanup()
        return await call_next(request)
