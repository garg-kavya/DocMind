"""Token-bucket rate limiting middleware."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# requests per minute per client IP by path prefix
_LIMITS: dict[str, int] = {
    "/api/v1/documents": 10,
    "/api/v1/query": 30,
    "/api/v1/sessions": 60,
}
_WINDOW = 60  # seconds


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        # {(client_ip, path_prefix): [timestamps]}
        self._buckets: dict[tuple, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        limit = None
        prefix = ""
        for p, l in _LIMITS.items():
            if path.startswith(p):
                limit = l
                prefix = p
                break

        if limit is None:
            return await call_next(request)

        key = (client_ip, prefix)
        now = time.monotonic()

        async with self._lock:
            # Slide window
            timestamps = [t for t in self._buckets[key] if now - t < _WINDOW]
            if len(timestamps) >= limit:
                retry_after = int(_WINDOW - (now - timestamps[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded. Try again in {retry_after}s."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            timestamps.append(now)
            self._buckets[key] = timestamps

        return await call_next(request)
