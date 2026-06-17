from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class DeploymentProfile:
    demo_users_enabled: bool
    auth_required: bool
    legacy_routers_enabled: bool
    allow_degraded_startup: bool = False


@lru_cache(maxsize=1)
def deployment_profiles() -> dict[str, DeploymentProfile]:
    return {
        "production": DeploymentProfile(demo_users_enabled=False, auth_required=True, legacy_routers_enabled=False),
        "supervised_live": DeploymentProfile(demo_users_enabled=False, auth_required=True, legacy_routers_enabled=False, allow_degraded_startup=True),
        "local_dev": DeploymentProfile(demo_users_enabled=True, auth_required=False, legacy_routers_enabled=True, allow_degraded_startup=True),
    }


@lru_cache(maxsize=8)
def get_deployment_profile(name: str) -> DeploymentProfile:
    return deployment_profiles()[name]
