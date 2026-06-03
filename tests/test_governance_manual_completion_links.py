from __future__ import annotations

from pathlib import Path


def test_governance_page_includes_manual_completion_links() -> None:
    template = Path("/Users/cash/Documents/frontend/command-centre/src/pages/GovernancePage.tsx").read_text(encoding="utf-8")

    assert "Governance and Release Controls" in template
    assert "Manual Completion and Proof" in template
    assert "operator-led at the end of the chain" in template
    assert "prepare the pack, capture the manual completion record, generate proof" in template
    assert "keep final portal submission blocked unless a human uploads it" in template

    expected_links = {
        "Quote Compilation Status": "/quote-compilation/status",
        "Submission Proof Status": "/submission-proof/status",
        "Portal Submission Status": "/portal-submission/status",
    }

    for label, href in expected_links.items():
        assert template.count(label) == 1
        assert template.count(href) == 1
        assert f'href="{href}"' in template
