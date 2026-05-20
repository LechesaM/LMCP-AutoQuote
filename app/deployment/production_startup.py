from __future__ import annotations

from app.deployment.deployment_profiles import get_deployment_profile
from app.deployment.rate_limit import RateLimitMiddleware
from app.deployment.request_id import RequestIdMiddleware
from app.deployment.security_headers import SecurityHeadersMiddleware
from app.observability.sentry_integration import get_sentry_config


def configure_production_app(app) -> None:
    from app.stabilization.deployment_stability_checks import build_deployment_stability_report
    from app.startup.production_blockers import strict_production_startup_enabled
    from app.startup.startup_health_report import build_startup_health_report

    profile = get_deployment_profile()
    startup_health = build_startup_health_report()
    app.state.deployment_profile = profile.to_jsonable_dict()
    app.state.infrastructure_profile = {
        "database_backend": profile.database_backend,
        "queue_backend": profile.queue_backend,
    }
    sentry = get_sentry_config()
    app.state.observability_profile = {
        "enabled": True,
        "sentry_enabled": sentry.enabled,
        "sentry_configured": bool(sentry.dsn),
        "metrics_export_enabled": True,
    }
    app.state.stabilization_profile = build_deployment_stability_report(limit=25)
    app.state.startup_health_report = startup_health
    app.state.production_blockers = startup_health.get("production_blockers", {})
    if strict_production_startup_enabled() and startup_health.get("blockers"):
        raise RuntimeError(f"Strict production startup blocked by: {startup_health.get('blockers', [])}")
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if profile.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            enabled=True,
            max_requests=profile.rate_limit_per_minute,
            window_seconds=60,
        )
