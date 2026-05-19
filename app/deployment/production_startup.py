from __future__ import annotations

from app.deployment.deployment_profiles import get_deployment_profile
from app.deployment.rate_limit import RateLimitMiddleware
from app.deployment.request_id import RequestIdMiddleware
from app.deployment.security_headers import SecurityHeadersMiddleware


def configure_production_app(app) -> None:
    profile = get_deployment_profile()
    app.state.deployment_profile = profile.to_jsonable_dict()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if profile.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            enabled=True,
            max_requests=profile.rate_limit_per_minute,
            window_seconds=60,
        )

