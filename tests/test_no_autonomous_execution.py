from __future__ import annotations

from pathlib import Path

from app.api.router_registry import iter_router_specs
from app.auth.auth_models import AuthPermission
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TERMS = (
    "autonomous",
    "autonomous_submit",
    "auto_approve",
    "bypass_review_ready",
    "bypass_proof_capture",
    "full_autonomous",
    "safe_autonomous",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()


def test_default_router_registry_has_no_autonomous_execution_specs(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    loaded_names = [spec.name.lower() for spec in iter_router_specs()]

    assert not any(any(term in name for term in FORBIDDEN_TERMS) for name in loaded_names)


def test_loaded_application_routes_do_not_expose_autonomous_execution(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    import importlib

    app_main = importlib.import_module("app.main")
    app_main = importlib.reload(app_main)

    loaded_names = [str(item.get("name", "")).lower() for item in app_main.app.state.router_report["loaded"]]
    route_paths = [getattr(route, "path", "").lower() for route in app_main.app.routes]

    assert not any(any(term in name for term in FORBIDDEN_TERMS) for name in loaded_names)
    assert not any(any(term in path for term in FORBIDDEN_TERMS) for path in route_paths)


def test_authorization_model_excludes_autonomous_permissions() -> None:
    forbidden = {
        "autonomous_submit",
        "auto_approve",
        "bypass_review_ready",
        "bypass_proof_capture",
    }
    assert forbidden.isdisjoint({permission.value for permission in AuthPermission})


def test_no_autonomous_execution_certification_doc_exists_and_is_explicit() -> None:
    certification = _read("docs/no_autonomous_execution_certification.md")

    for phrase in [
        "no autonomous submission",
        "no autonomous approval",
        "no review bypass",
        "no proof-capture bypass",
        "human-controlled procurement operations only",
        "manual-only",
    ]:
        assert phrase in certification
