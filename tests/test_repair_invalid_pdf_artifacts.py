from __future__ import annotations

from pathlib import Path

from scripts.repair_invalid_pdf_artifacts import repair_invalid_pdfs


def test_repair_invalid_pdfs_rewrites_non_pdf_bytes(tmp_path: Path) -> None:
    pdf_path = tmp_path / "bundle" / "broken.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"quote pack placeholder")

    repaired = repair_invalid_pdfs(tmp_path)

    assert repaired == [pdf_path]
    assert pdf_path.read_bytes().startswith(b"%PDF")
