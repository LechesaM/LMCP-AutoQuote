from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.metrics_service import increment_metric


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = False, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.max_requests = max(1, int(max_requests or 60))
        self.window_seconds = max(1, int(window_seconds or 60))
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)
        key = request.headers.get("X-Forwarded-For") or (request.client.host if request.client else "unknown")
        now = time.time()
        bucket = self._hits[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            increment_metric("rate_limit_events")
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "rate_limited", "detail": "Too many requests."}, status_code=429)
        bucket.append(now)
        return await call_next(request)
