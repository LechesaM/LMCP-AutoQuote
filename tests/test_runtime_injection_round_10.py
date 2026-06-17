from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from reportlab.pdfgen import canvas

from app.services import handwriting_form_overlay_service as overlay


def test_handwriting_form_overlay_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    input_pdf = tmp_path / "input.pdf"
    c = canvas.Canvas(str(input_pdf))
    c.drawString(100, 700, "Base document")
    c.showPage()
    c.save()

    result = overlay.overlay_handwriting_on_existing_pdf(
        {
            "buyer_rfq_number": "RFQ-1",
            "input_pdf": str(input_pdf),
            "fields": [
                {
                    "page": 1,
                    "x": 50,
                    "y": 700,
                    "text": "Test signature",
                }
            ],
        },
        runtime_dir=str(runtime_dir),
    )

    assert result["status"] == "ok"
    assert str(runtime_dir / "handwriting_simulation" / "real_form_outputs") in result["output_file"]
    assert Path(result["output_file"]).exists()
