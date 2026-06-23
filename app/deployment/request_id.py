from __future__ import annotations

from time import perf_counter
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.operations.structured_logging import (
    clear_observability_context,
    generate_correlation_id,
    log_request_event,
    set_observability_context,
)
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        started = perf_counter()
        request_id = request.headers.get("x-request-id") or generate_correlation_id("req")
        trace_id = request.headers.get("x-trace-id") or request.headers.get("traceparent") or request_id
        set_observability_context(request_id=request_id, trace_id=trace_id)
        try:
            request.state.request_id = request_id
            request.state.trace_id = trace_id
            request.state.correlation_id = trace_id
        except Exception:
            pass
        try:
            response = await call_next(request)
        except Exception as exc:
            log_request_event(
                request.method,
                request.url.path,
                status_code=500,
                duration_ms=(perf_counter() - started) * 1000.0,
                request_id=request_id,
                trace_id=trace_id,
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            clear_observability_context()
            raise
        response.headers["X-Request-ID"] = request_id
        log_request_event(
            request.method,
            request.url.path,
            status_code=response.status_code,
            duration_ms=(perf_counter() - started) * 1000.0,
            request_id=request_id,
            trace_id=trace_id,
        )
        clear_observability_context()
        return response
