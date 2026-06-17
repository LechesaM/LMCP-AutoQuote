from __future__ import annotations

from pathlib import Path


def test_control_panel_includes_handwriting_stack_links() -> None:
    template = Path("/Users/cash/Documents/app/templates/control_panel.html").read_text(encoding="utf-8")

    assert "Handwriting Stack" in template
    assert "Combined status and direct entry points for the handwriting glyph, line-ink, simulation, and form overlay services." in template
    assert "Open Stack Status" in template
    assert "Glyph Status" in template
    assert "Line Ink Status" in template
    assert "Simulation Status" in template
    assert "/handwriting-stack/status" in template
    assert "/handwriting-glyph/status" in template
    assert "/handwriting-line-ink-v5/status" in template
    assert "/handwriting-simulation/status" in template
