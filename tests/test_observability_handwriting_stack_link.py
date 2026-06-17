from __future__ import annotations

from pathlib import Path


def test_observability_uptime_panel_includes_handwriting_stack_link() -> None:
    panel_source = Path("/Users/cash/Documents/frontend/command-centre/src/components/observability/UptimeMonitorPanel.tsx").read_text(encoding="utf-8")
    page_source = Path("/Users/cash/Documents/frontend/command-centre/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert "Handwriting Stack" in panel_source
    assert "handwritingStackUrl" in panel_source
    assert "HANDWRITING_STACK_STATUS_URL" in panel_source
    assert "HANDWRITING_STACK_STATUS_URL" in page_source
