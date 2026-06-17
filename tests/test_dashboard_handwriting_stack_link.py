from __future__ import annotations

from pathlib import Path


def test_dashboard_includes_handwriting_stack_links() -> None:
    template = Path("/Users/cash/Documents/frontend/command-centre/src/pages/DashboardPage.tsx").read_text(encoding="utf-8")

    assert "Handwriting Stack" in template
    assert "Quick access to the combined handwriting stack and the underlying glyph, line-ink, and simulation services." in template
    assert "Open Stack Status" in template
    assert "Glyph Service" in template
    assert "Line Ink V5" in template
    assert "Handwriting Simulation" in template
    assert "handwritingStackUrl" in template
    assert "/handwriting-glyph/status" in template
    assert "/handwriting-line-ink-v5/status" in template
    assert "/handwriting-simulation/status" in template
