from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import urlparse

from app.core.runtime_config import env


@dataclass(frozen=True)
class RedisConfig:
    backend: str
    url: str
    host: str
    port: int
    db: int
    configured: bool = False
    production_warning: str = ""

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "configured": self.configured,
            "production_warning": self.production_warning,
        }


def parse_redis_url(redis_url: str) -> Dict[str, Any]:
    parsed = urlparse(str(redis_url or "").strip())
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or "",
        "port": int(parsed.port or 6379),
        "db": int((parsed.path or "/0").lstrip("/") or 0),
        "password": parsed.password or "",
    }


def get_redis_config() -> RedisConfig:
    backend = env("LMCP_QUEUE_BACKEND", "local").lower()
    redis_url = env("LMCP_REDIS_URL", "")
    if redis_url:
        parsed = parse_redis_url(redis_url)
        configured = backend == "redis" and bool(parsed["host"])
        host = parsed["host"]
        port = parsed["port"]
        db = parsed["db"]
    else:
        host = env("LMCP_REDIS_HOST", "localhost")
        port = int(env("LMCP_REDIS_PORT", "6379"))
        db = int(env("LMCP_REDIS_DB", "0"))
        redis_url = f"redis://{host}:{port}/{db}"
        configured = backend == "redis" and bool(host)
    profile_name = env("LMCP_DEPLOYMENT_PROFILE", "local_dev").lower()
    warning = ""
    if profile_name in {"production", "supervised_live"} and backend == "local":
        warning = "Local queue backend is configured in a supervised-live or production profile; Redis is recommended."
    return RedisConfig(backend=backend, url=redis_url, host=host, port=port, db=db, configured=configured, production_warning=warning)


def redis_connection_ready() -> bool:
    config = get_redis_config()
    return config.backend == "redis" and bool(config.configured)
