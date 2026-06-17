from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

from app.services import handwriting_simulation_service as simulation_service


def _make_blank_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path))
    c.setPageSize((595.0, 842.0))
    c.showPage()
    c.save()


def _make_line_asset(path: Path) -> None:
    img = Image.new("RGBA", (220, 70), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((10, 22, 210, 48), radius=10, fill=(20, 20, 24, 255))
    img.save(path)


def test_complete_handwriting_form_uses_line_ink_resolver(monkeypatch, tmp_path: Path) -> None:
    input_pdf = tmp_path / "input.pdf"
    output_pdf = tmp_path / "output.pdf"
    line_asset = tmp_path / "line_asset.png"

    _make_blank_pdf(input_pdf)
    _make_line_asset(line_asset)

    resolver_calls = {"count": 0}

    def fake_resolve_line_asset_v5(
        *,
        job_id: str = "REAL-HANDWRITING",
        text: str = "",
        line_index=None,
        prefer_normalized: bool = True,
    ):
        resolver_calls["count"] += 1
        return line_asset

    monkeypatch.setattr(simulation_service, "resolve_line_asset_v5", fake_resolve_line_asset_v5)
    monkeypatch.setattr(simulation_service, "resolve_line_asset_v7", None)

    identity = simulation_service.V13RealInkIdentity(
        writer_id="TEST-WRITER",
        job_id="TEST-JOB",
        persist_identity=False,
    )
    renderer = simulation_service.RealInkReferenceRenderer(
        identity_engine=identity,
        reference_image_path=line_asset,
        line_ink_job_id="REAL-HANDWRITING",
    )

    selected = renderer._select_line_asset("Director")
    assert selected is not None
    assert resolver_calls["count"] > 0

    overlay_calls = {"line_ink_job_id": None}

    def fake_overlay_pdf_with_handwriting(
        *,
        input_pdf,
        output_pdf,
        fields,
        identity_engine,
        ink_color,
        reference_image_path=None,
        line_ink_job_id=None,
        debug=False,
        payload=None,
    ):
        overlay_calls["line_ink_job_id"] = line_ink_job_id
        return 1, None

    monkeypatch.setattr(simulation_service, "_overlay_pdf_with_handwriting", fake_overlay_pdf_with_handwriting)

    result = simulation_service.complete_handwriting_form(
        {
            "buyer_rfq_number": "TEST-LINE-INK-INTEGRATION-001",
            "input_pdf": str(input_pdf),
            "output_pdf": str(output_pdf),
            "line_ink_job_id": "REAL-HANDWRITING",
            "persist_identity": False,
            "fields": [
                {
                    "page": 1,
                    "x": 120,
                    "y": 720,
                    "text": "Director",
                    "font_size": 13,
                }
            ],
            "debug": False,
        }
    )

    assert result["status"] == "ok"
    assert overlay_calls["line_ink_job_id"] == "REAL-HANDWRITING"
