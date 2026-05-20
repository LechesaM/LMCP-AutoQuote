from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

from app.core.runtime_config import env, env_bool, env_csv, get_runtime_config


@dataclass(frozen=True)
class DeploymentProfile:
    name: str
    debug: bool
    demo_users_enabled: bool
    auth_required: bool
    telemetry_fallback_enabled: bool
    rate_limit_enabled: bool
    rate_limit_per_minute: int
    cors_origins: Tuple[str, ...]
    legacy_routers_enabled: bool
    database_backend: str = "sqlite"
    queue_backend: str = "local"

    def to_jsonable_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "debug": self.debug,
            "demo_users_enabled": self.demo_users_enabled,
            "auth_required": self.auth_required,
            "telemetry_fallback_enabled": self.telemetry_fallback_enabled,
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "cors_origins": list(self.cors_origins),
            "legacy_routers_enabled": self.legacy_routers_enabled,
            "database_backend": self.database_backend,
            "queue_backend": self.queue_backend,
        }


def _profile(name: str) -> DeploymentProfile:
    runtime = get_runtime_config()
    name = name.lower()
    defaults = {
        "local_dev": DeploymentProfile("local_dev", True, True, False, True, False, 0, ("*",), False),
        "staging": DeploymentProfile("staging", False, False, True, True, True, 120, ("https://staging.lmcp.local",), False),
        "supervised_live": DeploymentProfile("supervised_live", False, False, True, True, True, 60, ("https://command-centre.lmcp.local",), False),
        "production": DeploymentProfile("production", False, False, True, False, True, 60, ("https://command-centre.lmcp.local",), False),
    }
    profile = defaults.get(name, defaults["local_dev"])
    cors = env_csv("LMCP_CORS_ORIGINS", ",".join(profile.cors_origins))
    return DeploymentProfile(
        name=profile.name,
        debug=env_bool("LMCP_DEBUG", profile.debug),
        demo_users_enabled=env_bool("LMCP_AUTH_ALLOW_DEMO_USERS", profile.demo_users_enabled),
        auth_required=env_bool("LMCP_AUTH_REQUIRED", profile.auth_required),
        telemetry_fallback_enabled=env_bool("LMCP_TELEMETRY_FALLBACK_ENABLED", profile.telemetry_fallback_enabled),
        rate_limit_enabled=env_bool("LMCP_RATE_LIMIT_ENABLED", profile.rate_limit_enabled),
        rate_limit_per_minute=int(env("LMCP_RATE_LIMIT_PER_MINUTE", str(profile.rate_limit_per_minute))),
        cors_origins=cors or profile.cors_origins,
        legacy_routers_enabled=runtime.enable_legacy_routers and profile.legacy_routers_enabled,
        database_backend=env("LMCP_DB_BACKEND", profile.database_backend).lower(),
        queue_backend=env("LMCP_QUEUE_BACKEND", profile.queue_backend).lower(),
    )


@lru_cache(maxsize=1)
def get_deployment_profile(name: str | None = None) -> DeploymentProfile:
    target = name or env("LMCP_DEPLOYMENT_PROFILE", "local_dev")
    return _profile(target)


def deployment_profiles() -> Dict[str, DeploymentProfile]:
    return {
        "local_dev": get_deployment_profile("local_dev"),
        "staging": get_deployment_profile("staging"),
        "supervised_live": get_deployment_profile("supervised_live"),
        "production": get_deployment_profile("production"),
    }
