from __future__ import annotations

from pathlib import Path


def test_runtime_operations_banner_includes_handwriting_stack_link() -> None:
    banner_source = Path("/Users/cash/Documents/frontend/command-centre/src/components/runtime/OperationalStatusBanner.tsx").read_text(encoding="utf-8")
    runtime_page_source = Path("/Users/cash/Documents/frontend/command-centre/src/pages/RuntimeOperationsPage.tsx").read_text(encoding="utf-8")
    observability_page_source = Path("/Users/cash/Documents/frontend/command-centre/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert "Handwriting Stack" in banner_source
    assert "handwritingStackUrl" in banner_source
    assert "HANDWRITING_STACK_STATUS_URL" in banner_source
    assert "HANDWRITING_STACK_STATUS_URL" in runtime_page_source
    assert "HANDWRITING_STACK_STATUS_URL" in observability_page_source
