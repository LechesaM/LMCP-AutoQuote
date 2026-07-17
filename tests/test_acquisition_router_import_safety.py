import importlib
import sys


ROUTERS = [
    ("app.api.smart_harvester_v31_api", "/v31-smart-harvester", {("GET", "/status"), ("POST", "/run-once")}, "app.services.smart_harvester_v31_service", "ensure_v31_runtime_dirs"),
    ("app.api.real_rfq_harvester_v32_api", "/v32-real-rfq-harvester", {("GET", "/status"), ("POST", "/run-once")}, "app.services.real_rfq_harvester_v32_service", "ensure_v32_runtime_dirs"),
    ("app.api.real_portal_rfq_extraction_v33_api", "/v33-real-portal-rfq", {("GET", "/status"), ("POST", "/run-once")}, "app.services.real_portal_rfq_extraction_v33_service", "ensure_v33_runtime_dirs"),
    ("app.api.structured_rfq_extractor_v34_api", "/v34-structured-rfq", {("GET", "/status"), ("POST", "/run-once")}, "app.services.structured_rfq_extractor_v34_service", "ensure_v34_runtime_dirs"),
    ("app.api.playwright_live_dom_extractor_v35_api", "/v35-playwright-rfq", {("GET", "/status"), ("POST", "/run-once")}, "app.services.playwright_live_dom_extractor_v35_service", "ensure_v35_runtime_dirs"),
    ("app.api.interactive_playwright_extractor_v36_api", "/v36-interactive-rfq", {("GET", "/status"), ("POST", "/run-once")}, "app.services.interactive_playwright_extractor_v36_service", "ensure_v36_runtime_dirs"),
    ("app.api.deep_rfq_link_extractor_v37_api", "/v37-deep-rfq", {("GET", "/status"), ("POST", "/run-from-v36")}, "app.services.deep_rfq_link_extractor_v37_service", "ensure_v37_runtime_dirs"),
    ("app.api.interactive_click_deep_extraction_v38_api", "/v38-click-deep-rfq", {("GET", "/status"), ("POST", "/run-from-v36")}, "app.services.interactive_click_deep_extraction_v38_service", "ensure_v38_runtime_dirs"),
    ("app.api.true_navigation_extraction_v39_api", "/v39-true-navigation", {("GET", "/status"), ("POST", "/run-from-v36")}, "app.services.true_navigation_extraction_v39_service", "ensure_v39_runtime_dirs"),
    ("app.api.tender_form_intelligence_api", "/tender-form-intelligence", {("GET", "/status"), ("POST", "/complete")}, "app.services.tender_form_intelligence_engine", "ensure_tender_form_runtime_dirs"),
    ("app.api.csd_persistent_session_api", "/csd-persistent-session", {("GET", "/status"), ("POST", "/refresh-report")}, "app.services.csd_persistent_session_service", "ensure_csd_persistent_runtime_dirs"),
    ("app.api.csd_monthly_refresh_api", "/csd-monthly-refresh", {("GET", "/status"), ("POST", "/run-if-due")}, "app.services.csd_monthly_refresh_service", "ensure_csd_monthly_runtime_dirs"),
    ("app.api.final_automation_layer_api", "/final-automation", {("GET", "/status"), ("POST", "/run-once")}, "app.services.final_automation_layer_service", "ensure_final_automation_runtime_dirs"),
    ("app.api.sbd_intelligence_api", "/sbd-intelligence", {("GET", "/status"), ("POST", "/complete")}, "app.services.tender_form_intelligence_engine", "ensure_tender_form_runtime_dirs"),
]


def _purge_modules() -> None:
    for name in list(sys.modules):
        if name == "app.core.runtime_paths":
            sys.modules.pop(name, None)
        elif name.startswith("app.api.") or name.startswith("app.services."):
            sys.modules.pop(name, None)


def _method_paths(router):
    pairs = set()
    for route in router.routes:
        for method in getattr(route, "methods", set()) or set():
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                pairs.add((method, route.path))
    return pairs


def test_router_imports_do_not_create_runtime_files(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(project_root / "runtime"))
    monkeypatch.setenv("LMCP_LOG_DIR", str(project_root / "runtime" / "logs"))
    _purge_modules()

    for module_name, prefix, expected_pairs, _service_module, _ensure_name in ROUTERS:
        module = importlib.import_module(module_name)
        assert module.router.prefix == prefix
        expected_full_paths = {(method, f"{prefix}{path}") for method, path in expected_pairs}
        assert expected_full_paths.issubset(_method_paths(module.router))

    assert list(project_root.iterdir()) == []


def test_explicit_runtime_ensures_create_directories_idempotently(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(project_root / "runtime"))
    monkeypatch.setenv("LMCP_LOG_DIR", str(project_root / "runtime" / "logs"))
    _purge_modules()

    for _module_name, _prefix, _expected_pairs, service_module, ensure_name in ROUTERS:
        service = importlib.import_module(service_module)
        ensure = getattr(service, ensure_name)
        ensure()
        ensure()

    assert (project_root / "runtime").is_dir()
    assert any((project_root / "runtime").iterdir())
