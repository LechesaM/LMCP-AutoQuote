from __future__ import annotations

from pathlib import Path


def test_executive_summary_includes_handwriting_stack_link() -> None:
    panel_source = Path("/Users/cash/Documents/frontend/command-centre/src/components/business/ExecutiveSummaryPanel.tsx").read_text(encoding="utf-8")
    hook_source = Path("/Users/cash/Documents/frontend/command-centre/src/hooks/useExecutiveAnalytics.ts").read_text(encoding="utf-8")
    type_source = Path("/Users/cash/Documents/frontend/command-centre/src/types/executiveAnalytics.ts").read_text(encoding="utf-8")
    client_source = Path("/Users/cash/Documents/frontend/command-centre/src/api/executiveAnalyticsClient.ts").read_text(encoding="utf-8")
    normalize_source = Path("/Users/cash/Documents/frontend/command-centre/src/api/normalize.ts").read_text(encoding="utf-8")

    assert "Open Stack Status" in panel_source
    assert "HANDWRITING_STACK_STATUS_URL" in panel_source
    assert "handwritingStackUrl" in panel_source
    assert "handwritingStackUrl" in hook_source
    assert "handwritingStackUrl" in type_source
    assert "HANDWRITING_STACK_STATUS_URL" in hook_source
    assert "handwriting_stack_url" in client_source
    assert "HANDWRITING_STACK_STATUS_URL" in client_source
    assert "handwritingStackUrl" in normalize_source
    assert "HANDWRITING_STACK_STATUS_URL" in normalize_source
