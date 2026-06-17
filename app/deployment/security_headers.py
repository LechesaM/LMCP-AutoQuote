from __future__ import annotations

from typing import Callable

from fastapi import Request, Response


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
