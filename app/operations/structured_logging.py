from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Mapping, Optional


logger = logging.getLogger("lmcp.telemetry")

_REQUEST_ID: ContextVar[str] = ContextVar("lmcp_request_id", default="")
_TRACE_ID: ContextVar[str] = ContextVar("lmcp_trace_id", default="")
_RFQ_ID: ContextVar[str] = ContextVar("lmcp_rfq_id", default="")
_TENDER_ID: ContextVar[str] = ContextVar("lmcp_tender_id", default="")
_TASK_ID: ContextVar[str] = ContextVar("lmcp_task_id", default="")
_WORKER_ID: ContextVar[str] = ContextVar("lmcp_worker_id", default="")
_WORKFLOW_STAGE: ContextVar[str] = ContextVar("lmcp_workflow_stage", default="")
_OPERATOR_ID: ContextVar[str] = ContextVar("lmcp_operator_id", default="")


def generate_correlation_id(prefix: str | None = None) -> str:
    value = uuid.uuid4().hex
    return f"{prefix}-{value}" if prefix else value


def _clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
        return text if text else default
    except Exception:
        return default


def _current_context() -> Dict[str, str]:
    return {
        "request_id": _REQUEST_ID.get(""),
        "trace_id": _TRACE_ID.get(""),
        "rfq_id": _RFQ_ID.get(""),
        "tender_id": _TENDER_ID.get(""),
        "task_id": _TASK_ID.get(""),
        "worker_id": _WORKER_ID.get(""),
        "workflow_stage": _WORKFLOW_STAGE.get(""),
        "operator_id": _OPERATOR_ID.get(""),
    }


def get_observability_context() -> Dict[str, str]:
    return _current_context()


def get_request_id(default: str = "") -> str:
    return _REQUEST_ID.get(default)


def set_observability_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    rfq_id: str | None = None,
    tender_id: str | None = None,
    task_id: str | None = None,
    worker_id: str | None = None,
    workflow_stage: str | None = None,
    operator_id: str | None = None,
) -> Dict[str, str]:
    tokens = {}
    values = {
        _REQUEST_ID: request_id,
        _TRACE_ID: trace_id,
        _RFQ_ID: rfq_id,
        _TENDER_ID: tender_id,
        _TASK_ID: task_id,
        _WORKER_ID: worker_id,
        _WORKFLOW_STAGE: workflow_stage,
        _OPERATOR_ID: operator_id,
    }
    for var, value in values.items():
        if value is None:
            continue
        tokens[var.name] = var.set(_clean(value))
    return _current_context()


def clear_observability_context() -> None:
    for var in (_REQUEST_ID, _TRACE_ID, _RFQ_ID, _TENDER_ID, _TASK_ID, _WORKER_ID, _WORKFLOW_STAGE, _OPERATOR_ID):
        var.set("")


@contextmanager
def observability_context(**kwargs: Any) -> Iterator[Dict[str, str]]:
    previous = _current_context()
    set_observability_context(**kwargs)
    try:
        yield _current_context()
    finally:
        set_observability_context(**previous)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(payload: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(json.dumps(payload, default=str, sort_keys=True))
    return payload


def _event_payload(
    category: str,
    event_type: str,
    message: str,
    **fields: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "timestamp": _timestamp(),
        "category": _clean(category, "runtime"),
        "event_type": _clean(event_type, "event"),
        "message": _clean(message, "event"),
        "environment": _clean(fields.pop("environment", "") or fields.pop("env", "")),
        **{key: value for key, value in _current_context().items() if value},
    }
    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = value
    return payload


def log_operation_event(category: str, message: str, **fields: Any) -> Dict[str, Any]:
    return _emit(_event_payload(category, "operation", message, **fields))


def log_request_event(
    method: str,
    path: str,
    *,
    status_code: int | str,
    duration_ms: float | int | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    payload = _event_payload(
        "request",
        "http_request",
        f"{method} {path}",
        method=_clean(method, "GET"),
        path=_clean(path, "/"),
        status_code=status_code,
        duration_ms=round(float(duration_ms), 3) if duration_ms is not None else None,
        request_id=request_id or get_request_id(""),
        trace_id=trace_id or _TRACE_ID.get(""),
        error_type=_clean(error_type),
        error_message=_clean(error_message),
        **fields,
    )
    return _emit(payload)


def log_worker_event(
    event_type: str,
    message: str,
    *,
    worker_id: str | None = None,
    task_id: str | None = None,
    task_name: str | None = None,
    queue_name: str | None = None,
    status: str | None = None,
    retries: int | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    payload = _event_payload(
        "worker",
        event_type,
        message,
        worker_id=_clean(worker_id) or _WORKER_ID.get(""),
        task_id=_clean(task_id) or _TASK_ID.get(""),
        task_name=_clean(task_name),
        queue_name=_clean(queue_name),
        status=_clean(status),
        retries=retries,
        **fields,
    )
    return _emit(payload)


def log_rfq_lifecycle_event(
    event_type: str,
    message: str,
    *,
    rfq_id: str | None = None,
    tender_id: str | None = None,
    workflow_stage: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    payload = _event_payload(
        "rfq_lifecycle",
        event_type,
        message,
        rfq_id=_clean(rfq_id) or _RFQ_ID.get(""),
        tender_id=_clean(tender_id) or _TENDER_ID.get(""),
        workflow_stage=_clean(workflow_stage) or _WORKFLOW_STAGE.get(""),
        status=_clean(status),
        reason=_clean(reason),
        **fields,
    )
    return _emit(payload)


def log_runtime_diagnostic(
    event_type: str,
    message: str,
    **fields: Any,
) -> Dict[str, Any]:
    return _emit(_event_payload("runtime_diagnostic", event_type, message, **fields))


def build_celery_headers(
    *,
    task_name: str | None = None,
    queue_name: str | None = None,
    rfq_id: str | None = None,
    tender_id: str | None = None,
    workflow_stage: str | None = None,
    operator_id: str | None = None,
    extra_headers: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    context = _current_context()
    headers: Dict[str, Any] = {
        "request_id": context["request_id"] or generate_correlation_id("req"),
        "trace_id": context["trace_id"] or context["request_id"] or generate_correlation_id("trace"),
        "rfq_id": _clean(rfq_id) or context["rfq_id"],
        "tender_id": _clean(tender_id) or context["tender_id"],
        "workflow_stage": _clean(workflow_stage) or context["workflow_stage"],
        "operator_id": _clean(operator_id) or context["operator_id"],
        "task_name": _clean(task_name),
        "queue_name": _clean(queue_name),
    }
    if extra_headers:
        for key, value in extra_headers.items():
            if value is not None:
                headers[key] = value
    return {key: value for key, value in headers.items() if value not in (None, "")}


def apply_async_with_context(task: Any, *args: Any, **kwargs: Any) -> Any:
    if args and isinstance(args[0], tuple):
        task_args = tuple(args[0])
        task_kwargs = dict(args[1]) if len(args) > 1 and isinstance(args[1], dict) else {}
    else:
        task_args = tuple(args)
        task_kwargs = {}
    publish_kwargs = dict(kwargs)
    headers = dict(publish_kwargs.pop("headers", {}) or {})
    task_name = publish_kwargs.get("task_name") or getattr(task, "name", "")
    headers.update(build_celery_headers(task_name=task_name, queue_name=publish_kwargs.get("queue")))
    publish_kwargs["headers"] = headers
    if hasattr(task, "apply_async"):
        return task.apply_async(args=task_args, kwargs=task_kwargs, **publish_kwargs)
    if callable(task):
        return task(*task_args, **task_kwargs)
    raise TypeError(f"Unsupported task object: {type(task)!r}")
