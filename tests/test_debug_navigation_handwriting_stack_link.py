from __future__ import annotations

from pathlib import Path


def test_debug_navigation_includes_handwriting_stack_target() -> None:
    page_source = Path("/Users/cash/Documents/frontend/command-centre/src/pages/DebugNavigationPage.tsx").read_text(encoding="utf-8")

    assert "Handwriting Stack" in page_source
    assert "HANDWRITING_STACK_STATUS_URL" in page_source
