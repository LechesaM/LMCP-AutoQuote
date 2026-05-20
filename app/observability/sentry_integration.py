from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from app.core.runtime_config import env, env_bool, get_runtime_config


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SentryConfig:
    enabled: bool
    dsn: str
    environment: str
    release: str
    sample_rate: float = 0.0

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dsn_configured": bool(self.dsn),
            "environment": self.environment,
            "release": self.release,
            "sample_rate": self.sample_rate,
        }


def get_sentry_config() -> SentryConfig:
    runtime = get_runtime_config()
    dsn = env("LMCP_SENTRY_DSN", "")
    enabled = env_bool("LMCP_ENABLE_SENTRY", False) and bool(dsn)
    sample_rate = float(env("LMCP_SENTRY_SAMPLE_RATE", "0.0") or 0.0)
    return SentryConfig(
        enabled=enabled,
        dsn=dsn,
        environment=runtime.environment,
        release=env("LMCP_RELEASE", runtime.project_root.name),
        sample_rate=sample_rate,
    )


def capture_runtime_exception(
    exception: Exception,
    *,
    request_id: str = "",
    correlation_id: str = "",
    tags: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    config = get_sentry_config()
    payload = {
        "status": "disabled" if not config.enabled else "captured",
        "generated_at": _now_iso(),
        "data_source": "runtime" if config.enabled else "fallback",
        "enabled": config.enabled,
        "request_id": str(request_id or ""),
        "correlation_id": str(correlation_id or ""),
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "tags": dict(tags or {}),
        "environment": config.environment,
        "release": config.release,
        "sample_rate": config.sample_rate,
    }
    try:
        if config.enabled:
            try:
                import sentry_sdk  # type: ignore
            except Exception:
                payload["status"] = "degraded"
                payload["sdk_available"] = False
            else:
                sentry_sdk.capture_exception(exception)
                payload["sdk_available"] = True
        else:
            payload["sdk_available"] = False
    except Exception as exc:
        payload["status"] = "degraded"
        payload["capture_error"] = str(exc)
    return payload


def build_sentry_status() -> Dict[str, Any]:
    config = get_sentry_config()
    return {
        "status": "ok" if config.enabled else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if config.enabled else "fallback",
        "sentry": config.to_jsonable_dict(),
    }
