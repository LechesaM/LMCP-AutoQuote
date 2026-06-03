from __future__ import annotations

from app.api.router_registry import (
    LEGACY_ROUTER_SPECS,
    PRODUCTION_ROUTER_SPECS,
    iter_router_specs,
    versioned_router_names,
)


def _names(specs) -> list[str]:
    return [spec.name for spec in specs]


def test_production_router_names_are_unique() -> None:
    names = _names(PRODUCTION_ROUTER_SPECS)
    assert len(names) == len(set(names))


def test_legacy_router_names_are_unique() -> None:
    names = _names(LEGACY_ROUTER_SPECS)
    assert len(names) == len(set(names))


def test_selected_router_names_are_unique() -> None:
    names = _names(iter_router_specs(include_legacy=True))
    assert len(names) == len(set(names))


def test_legacy_routers_are_excluded_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LMCP_ENABLE_LEGACY_ROUTERS", raising=False)
    selected_names = set(_names(iter_router_specs()))
    legacy_names = set(_names(LEGACY_ROUTER_SPECS))
    assert selected_names.isdisjoint(legacy_names)


def test_legacy_routers_are_included_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "true")
    selected_names = set(_names(iter_router_specs()))
    legacy_names = set(_names(LEGACY_ROUTER_SPECS))
    production_names = set(_names(PRODUCTION_ROUTER_SPECS))
    assert production_names.issubset(selected_names)
    assert legacy_names.issubset(selected_names)


def test_versioned_routers_are_legacy_only() -> None:
    production_names = set(_names(PRODUCTION_ROUTER_SPECS))
    assert production_names.isdisjoint(set(versioned_router_names()))


def test_production_router_statuses_are_production() -> None:
    assert all(spec.status == "production" for spec in PRODUCTION_ROUTER_SPECS)


def test_legacy_router_statuses_are_not_production() -> None:
    assert all(spec.status != "production" for spec in LEGACY_ROUTER_SPECS)


def test_no_active_production_router_has_obvious_duplicate_purpose() -> None:
    production_names = set(_names(PRODUCTION_ROUTER_SPECS))
    overlapping_router_groups = {
        "submission_execution": {
            "portal_submission_router",
            "portal_submission_v47_router",
            "auto_submission_v46_router",
            "final_submission_v47_5_router",
        },
        "autonomous_execution": {
            "autonomous_api",
            "full_autonomous_cycle_router",
            "final_automation_router",
            "safe_autonomous_scheduler_router",
            "full_autonomous_v48_router",
        },
        "system_surface": {
            "system_api",
            "system_control_router",
            "system_stable_router",
            "system_stability_router",
        },
        "manual_submission_pipeline": {
            "submission_pipeline_router",
            "submission_scheduler_router",
            "submission_retry_router",
            "quote_compilation_router",
        },
    }

    justified = {
        "submission_execution": {"portal_submission_router"},
        "autonomous_execution": set(),
        "system_surface": {"system_stable_router"},
        "manual_submission_pipeline": {"quote_compilation_router"},
        }

    for group_name, members in overlapping_router_groups.items():
        active_members = production_names & members
        assert active_members == justified[group_name], f"{group_name}: {sorted(active_members)}"


def test_supplier_quote_routes_are_split_between_status_and_actions() -> None:
    production_names = set(_names(PRODUCTION_ROUTER_SPECS))

    assert "supplier_quotes_status_router" in production_names
    assert "supplier_quotes_router" in production_names
