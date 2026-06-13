from __future__ import annotations

from collections import Counter
from enum import Enum
from typing import Iterable, Sequence

from fastapi import FastAPI
from fastapi.routing import APIRoute


class RouteCategory(str, Enum):
    RECOVERY_SAFE_READONLY = "RECOVERY_SAFE_READONLY"
    RECOVERY_SAFE_ADVISORY = "RECOVERY_SAFE_ADVISORY"
    RECOVERY_RESTRICTED = "RECOVERY_RESTRICTED"
    RECOVERY_FORBIDDEN = "RECOVERY_FORBIDDEN"
    FULL_RUNTIME_ONLY = "FULL_RUNTIME_ONLY"


READONLY_PATHS = {
    "/",
    "/auth/me",
    "/auth/permissions",
    "/dashboard",
    "/dashboard/health",
    "/dashboard/queues",
    "/dashboard/refusals",
    "/dashboard/summary",
    "/dashboard/workflows",
    "/health",
    "/health/operational-report",
    "/health/system",
    "/health/workflows",
    "/operations",
    "/operations/backup-validation",
    "/operations/runtime-metrics",
    "/pilot/readiness",
    "/pilot/signoffs",
    "/pilot/summary",
    "/pricing-evidence",
    "/review",
    "/review-efficiency",
    "/governance",
    "/governance/compliance-controls",
    "/governance/compliance-report",
    "/audit-defensibility",
    "/compliance-reporting",
    "/operator-assignments",
    "/governance-compliance",
    "/telemetry/dashboard",
    "/mission-control/ai-scoring",
    "/mission-control/recommendations",
    "/mission-control/snapshot",
    "/telemetry/operational-health",
    "/telemetry/review-queue",
    "/telemetry/source-health",
    "/system/recovery-policy",
    "/operator-auth/session",
    "/operator-auth/status",
    "/supplier-quotes/status",
    "/supplier-quotes/auto-ingest/status",
    "/supplier-quotes/intelligence/status",
    "/observability/uptime",
    "/observability/sla",
    "/observability/anomalies",
    "/productivity/review-efficiency",
    "/productivity/focus-sessions",
    "/stabilization/runtime",
    "/stabilization/fallback-health",
    "/business/executive-summary",
    "/business/profitability",
    "/governance/policies",
}

ADVISORY_PATHS = {
    "/auth/login",
    "/auth/logout",
    "/operator-auth/login",
    "/operator-auth/logout",
    "/telemetry/qualification",
}

RESTRICTED_PATH_PREFIXES = (
    "/api/rfq/",
    "/dashboard/archive",
    "/dashboard/operator-note",
    "/dashboard/refuse",
    "/dashboard/acknowledge-warning",
    "/governance/",
    "/observability",
    "/operator/action/",
    "/operator/actions",
    "/operator/assignments",
    "/operator/capacity",
    "/operator/notifications",
    "/operator/timeline",
    "/operational-analytics",
    "/runtime-operations",
    "/runtime-anomalies",
    "/runtime-reliability",
    "/sla-monitoring",
    "/stabilization-operations",
    "/source-health",
)

FORBIDDEN_TERMS = (
    "autonomous",
    "full_autonomous",
    "safe_autonomous",
    "submit",
    "submission",
    "scheduler",
    "worker",
    "orchestration",
    "mutation",
)

ADVISORY_MUTATION_METHODS = {"POST"}

RECOVERY_POLICY_INTROSPECTION_MANIFEST: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("/dashboard/archive", ("POST",)),
    ("/dashboard/refuse", ("POST",)),
    ("/dashboard/operator-note", ("POST",)),
    ("/dashboard/acknowledge-warning", ("POST",)),
    ("/governance/legal-hold/register", ("POST",)),
    ("/governance/legal-hold/release", ("POST",)),
    ("/governance/attestation/generate", ("POST",)),
    ("/api/full_autonomous_cycle", ("POST",)),
    ("/submission/execute", ("POST",)),
    ("/harvest/execute", ("POST",)),
)


def _normalize_path(path: str) -> str:
    cleaned = str(path or "").strip()
    if not cleaned:
        return "/"
    if cleaned != "/":
        cleaned = cleaned.rstrip("/") or "/"
    return cleaned


def _normalize_methods(methods: Iterable[str] | None) -> set[str]:
    return {str(method or "").upper() for method in (methods or []) if str(method or "").strip()}


def _matches_prefix(path: str, prefixes: Sequence[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def classify_route_path(path: str, methods: Iterable[str] | None = None) -> RouteCategory:
    normalized_path = _normalize_path(path)
    normalized_methods = _normalize_methods(methods)
    lowered = normalized_path.lower()

    if normalized_path.startswith("/operations/rfqs/") and "submission-execution" in lowered:
        return RouteCategory.FULL_RUNTIME_ONLY

    if any(term in lowered for term in FORBIDDEN_TERMS):
        return RouteCategory.RECOVERY_FORBIDDEN

    if normalized_path in ADVISORY_PATHS and normalized_methods & ADVISORY_MUTATION_METHODS:
        return RouteCategory.RECOVERY_SAFE_ADVISORY

    if normalized_path == "/telemetry/qualification" and normalized_methods <= {"GET", "HEAD", "OPTIONS"}:
        return RouteCategory.RECOVERY_SAFE_ADVISORY

    if normalized_path in READONLY_PATHS and normalized_methods <= {"GET", "HEAD", "OPTIONS"}:
        return RouteCategory.RECOVERY_SAFE_READONLY

    if _matches_prefix(normalized_path, RESTRICTED_PATH_PREFIXES):
        return RouteCategory.RECOVERY_RESTRICTED

    if normalized_methods and normalized_methods <= {"GET", "HEAD", "OPTIONS"}:
        if normalized_path.startswith("/telemetry/"):
            return RouteCategory.RECOVERY_RESTRICTED
        return RouteCategory.FULL_RUNTIME_ONLY

    if normalized_path in ADVISORY_PATHS:
        return RouteCategory.RECOVERY_SAFE_ADVISORY

    if normalized_methods and normalized_methods & {"POST", "PUT", "PATCH", "DELETE"}:
        return RouteCategory.RECOVERY_RESTRICTED

    return RouteCategory.FULL_RUNTIME_ONLY


def classify_apiroute(route: APIRoute) -> RouteCategory:
    return classify_route_path(route.path, route.methods)


def build_route_policy_report(routes: Iterable[object]) -> dict:
    categorized: list[dict[str, object]] = []
    counts: Counter[str] = Counter()

    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        category = classify_apiroute(route)
        counts[category.value] += 1
        categorized.append(
            {
                "path": _normalize_path(route.path),
                "name": getattr(route, "name", ""),
                "methods": sorted(str(method).upper() for method in (route.methods or []) if str(method or "").strip()),
                "category": category.value,
            }
        )

    return {
        "routes": categorized,
        "counts": dict(counts),
        "allowed_recovery_categories": [
            RouteCategory.RECOVERY_SAFE_READONLY.value,
            RouteCategory.RECOVERY_SAFE_ADVISORY.value,
        ],
    }


def policy_visibility_for_category(category: RouteCategory) -> str:
    if category == RouteCategory.RECOVERY_SAFE_READONLY:
        return "read-only"
    if category == RouteCategory.RECOVERY_SAFE_ADVISORY:
        return "advisory"
    if category == RouteCategory.RECOVERY_RESTRICTED:
        return "restricted"
    return "full-runtime-only"


def policy_rationale_for_route(path: str, category: RouteCategory) -> str:
    if category == RouteCategory.RECOVERY_SAFE_READONLY:
        return f"{path} is informational and does not mutate state."
    if category == RouteCategory.RECOVERY_SAFE_ADVISORY:
        return f"{path} supports supervised recovery workflows without enabling runtime mutation."
    if category == RouteCategory.RECOVERY_RESTRICTED:
        return f"{path} depends on mutable runtime control surfaces and stays out of recovery mode."
    return f"{path} belongs to the full runtime and is excluded from recovery mode."


def _route_identity(route: APIRoute) -> tuple[str, tuple[str, ...]]:
    return _normalize_path(route.path), tuple(
        sorted(str(method).upper() for method in (route.methods or []) if str(method or "").strip())
    )


def build_recovery_policy_introspection(routes: Iterable[object]) -> dict:
    mounted_routes = {
        _route_identity(route): route
        for route in routes
        if isinstance(route, APIRoute)
    }
    catalog_routes: list[APIRoute] = list(mounted_routes.values())
    for path, methods in RECOVERY_POLICY_INTROSPECTION_MANIFEST:
        catalog_routes.append(
            APIRoute(
                endpoint=lambda: None,
                path=path,
                methods=set(methods),
                name=path.strip("/").replace("/", "_") or "root",
            )
        )

    entries: list[dict[str, object]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for route in catalog_routes:
        route_id = _route_identity(route)
        if route_id in seen:
            continue
        seen.add(route_id)
        category = classify_apiroute(route)
        entries.append(
            {
                "path": _normalize_path(route.path),
                "methods": sorted(str(method).upper() for method in (route.methods or []) if str(method or "").strip()),
                "category": category.value,
                "policy_class": category.value,
                "mounted_in_recovery": route_id in mounted_routes,
                "rationale": policy_rationale_for_route(route.path, category),
                "visibility": policy_visibility_for_category(category),
            }
        )

    entries.sort(key=lambda item: (str(item["path"]), tuple(item["methods"])))
    return {
        "mode": "recovery",
        "routes": entries,
        "mounted_route_count": sum(1 for item in entries if item["mounted_in_recovery"]),
        "catalog_route_count": len(entries),
        "allowed_recovery_categories": [
            RouteCategory.RECOVERY_SAFE_READONLY.value,
            RouteCategory.RECOVERY_SAFE_ADVISORY.value,
        ],
    }


def filter_routes_for_recovery(routes: Sequence[object]) -> list[object]:
    allowed = {
        RouteCategory.RECOVERY_SAFE_READONLY,
        RouteCategory.RECOVERY_SAFE_ADVISORY,
    }
    filtered: list[object] = []
    for route in routes:
        if not isinstance(route, APIRoute):
            filtered.append(route)
            continue
        if classify_apiroute(route) in allowed:
            filtered.append(route)
    return filtered


def apply_recovery_route_policy(app: FastAPI) -> dict:
    report = build_route_policy_report(app.routes)
    app.router.routes = filter_routes_for_recovery(app.router.routes)
    return report
