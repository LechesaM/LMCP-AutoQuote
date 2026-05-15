from __future__ import annotations

import os
from io import BytesIO
from typing import Optional, Sequence

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.services.stamp_service import StampService


class PdfStampInjector:
    """
    Overlay a PNG stamp onto one or more PDF pages.
    Intended for SBD, MBD, and buyer forms only.
    """

    @staticmethod
    def _build_overlay_page(
        page_width: float,
        page_height: float,
        stamp_image_path: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> BytesIO:
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        c.drawImage(
            ImageReader(stamp_image_path),
            x,
            y,
            width=width,
            height=height,
            mask="auto",
            preserveAspectRatio=True,
        )
        c.save()
        packet.seek(0)
        return packet

    @classmethod
    def stamp_pdf(
        cls,
        input_pdf_path: str,
        output_pdf_path: Optional[str] = None,
        stamp_image_path: Optional[str] = None,
        page_numbers: Optional[Sequence[int]] = None,
        x: float = 380,
        y: float = 90,
        width: float = 140,
        height: float = 52,
    ) -> str:
        """
        Apply stamp overlay to specified PDF pages.

        Args:
            input_pdf_path: Source PDF path
            output_pdf_path: Destination PDF path. Defaults to *_stamped.pdf
            stamp_image_path: Stamp PNG path. Defaults to company default stamp
            page_numbers: 0-based page indexes. Defaults to last page only
            x, y, width, height: PDF positioning in points

        Returns:
            str: output PDF path
        """
        if not input_pdf_path or not os.path.exists(input_pdf_path):
            raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

        if not stamp_image_path:
            stamp_image_path = StampService.ensure_default_stamp()

        if not os.path.exists(stamp_image_path):
            raise FileNotFoundError(f"Stamp image not found: {stamp_image_path}")

        if not output_pdf_path:
            root, ext = os.path.splitext(input_pdf_path)
            output_pdf_path = f"{root}_stamped{ext}"

        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        if len(reader.pages) == 0:
            raise ValueError("Input PDF has no pages.")

        target_pages = set(page_numbers) if page_numbers is not None else {len(reader.pages) - 1}

        for page_index, page in enumerate(reader.pages):
            if page_index in target_pages:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                overlay_stream = cls._build_overlay_page(
                    page_width=page_width,
                    page_height=page_height,
                    stamp_image_path=stamp_image_path,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                )
                overlay_pdf = PdfReader(overlay_stream)
                overlay_page = overlay_pdf.pages[0]
                page.merge_page(overlay_page)

            writer.add_page(page)

        os.makedirs(os.path.dirname(output_pdf_path) or ".", exist_ok=True)

        with open(output_pdf_path, "wb") as output_file:
            writer.write(output_file)

        return output_pdf_path
