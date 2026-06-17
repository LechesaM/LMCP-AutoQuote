from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request, Response


class RequestIdMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response.headers["X-Request-ID"] = request_id
        return response
