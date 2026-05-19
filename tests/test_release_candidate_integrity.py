from __future__ import annotations

from pathlib import Path

from app.api.router_registry import iter_router_specs
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths


def _docs_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "docs"


def test_legacy_routers_disabled_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("LMCP_ENABLE_LEGACY_ROUTERS", raising=False)
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()

    config = get_runtime_config()
    selected_names = {spec.name for spec in iter_router_specs(include_legacy=config.enable_legacy_routers)}

    assert config.enable_legacy_routers is False
    assert "portal_submission_v47_router" not in selected_names


def test_release_candidate_docs_preserve_governance_language() -> None:
    docs_dir = _docs_dir()
    production = (docs_dir / "production_release_candidate.md").read_text(encoding="utf-8").lower()
    freeze = (docs_dir / "release_freeze_checklist.md").read_text(encoding="utf-8").lower()
    notes = (docs_dir / "release_notes_v1.md").read_text(encoding="utf-8")
    go_live = (docs_dir / "production_go_live_recommendation.md").read_text(encoding="utf-8").lower()
    risks = docs_dir / "known_operational_risks.md"
    regression = (docs_dir / "final_regression_report.md").read_text(encoding="utf-8")

    assert "manual approval remains mandatory" in production
    assert "review_ready" in production
    assert "proof capture" in production
    assert "final submission remains manual-only" in production
    assert "manual approval" in freeze
    assert "review_ready" in freeze
    assert "proof capture" in freeze
    assert "final submission remains manual-only" in freeze
    assert "conditional_go" in go_live
    assert risks.exists()
    assert "AI-Governed Procurement Operations Platform" in notes
    assert "Autonomous Tender Submission Platform" in notes
    assert "9 passed" in regression
    assert "18 passed" in regression


def test_release_docs_do_not_claim_autonomous_final_submission_enabled() -> None:
    docs_dir = _docs_dir()
    release_docs = [
        "production_release_candidate.md",
        "release_freeze_checklist.md",
        "final_regression_report.md",
        "known_operational_risks.md",
        "production_go_live_recommendation.md",
        "release_notes_v1.md",
    ]
    combined = "\n".join((docs_dir / name).read_text(encoding="utf-8").lower() for name in release_docs)

    assert "autonomous final submission is enabled" not in combined
    assert "autonomous final submission enabled" not in combined
