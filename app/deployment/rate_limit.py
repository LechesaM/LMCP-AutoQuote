from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import Request, Response


class RateLimitMiddleware:
    def __init__(self, app, *, enabled: bool = True, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.app = app
        self.enabled = enabled
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if not self.enabled:
            return await call_next(request)
        key = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._requests[key]
        while window and now - window[0] >= self.window_seconds:
            window.popleft()
        if len(window) >= self.max_requests:
            return Response(content='{"detail":"rate limit exceeded"}', media_type="application/json", status_code=429)
        window.append(now)
        return await call_next(request)
