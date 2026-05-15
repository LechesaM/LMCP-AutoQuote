from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


class StampService:
    """
    LMCP Electronic Company Stamp Service

    Purpose:
    - Generate a transparent company stamp PNG
    - Use on SBD forms, MBD forms, and buyer forms only
    - Never use on quotation PDFs

    Rules:
    - No signature inside the stamp
    - No witness signatures inside the stamp
    - Stamp is separate from quote generation
    """

    COMPANY_NAME = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    REG_NUMBER = "Registration No: 2025/XXXXXX/07"  # TODO: replace with actual registration number
    PHONE = "082 633 8492"
    EMAIL = "lechesam@me.com"

    DEFAULT_STAMP_TEXT = "COMPANY STAMP"
    OUTPUT_DIR = "runtime/stamps"

    @classmethod
    def _ensure_output_dir(cls) -> None:
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)

    @staticmethod
    def _safe_font(size: int):
        """
        Try common system fonts first, then fall back safely.
        """
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        for font_path in font_candidates:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size=size)
            except Exception:
                continue

        return ImageFont.load_default()

    @staticmethod
    def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return max(0, bbox[2] - bbox[0])

    @classmethod
    def _center_x(cls, draw: ImageDraw.ImageDraw, text: str, font, canvas_width: int) -> int:
        return max(10, int((canvas_width - cls._text_width(draw, text, font)) / 2))

    @classmethod
    def generate_stamp_png(
        cls,
        extra_text: Optional[str] = None,
        date_text: Optional[str] = None,
        width: int = 900,
        height: int = 320,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a transparent PNG company stamp.

        Returns:
            str: absolute/relative path to saved stamp PNG
        """
        cls._ensure_output_dir()

        image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        red = (170, 0, 0, 255)

        outer_margin = 12
        inner_margin = 28

        draw.rounded_rectangle(
            [outer_margin, outer_margin, width - outer_margin, height - outer_margin],
            radius=18,
            outline=red,
            width=5,
        )
        draw.rounded_rectangle(
            [inner_margin, inner_margin, width - inner_margin, height - inner_margin],
            radius=14,
            outline=red,
            width=2,
        )

        title_font = cls._safe_font(34)
        body_font = cls._safe_font(22)
        small_font = cls._safe_font(20)

        lines = [
            cls.COMPANY_NAME,
            cls.REG_NUMBER,
            f"Tel: {cls.PHONE}",
            f"Email: {cls.EMAIL}",
            extra_text or cls.DEFAULT_STAMP_TEXT,
            f"Date: {date_text or datetime.now().strftime('%Y-%m-%d')}",
        ]

        y = 48
        line_spacing = [42, 34, 32, 34, 36, 0]

        for index, line in enumerate(lines):
            font = title_font if index == 0 else (small_font if index >= 4 else body_font)
            x = cls._center_x(draw, line, font, width)
            draw.text((x, y), line, fill=red, font=font)
            if index < len(line_spacing):
                y += line_spacing[index]

        if not filename:
            filename = f"stamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        output_path = os.path.join(cls.OUTPUT_DIR, filename)
        image.save(output_path)
        return output_path

    @classmethod
    def ensure_default_stamp(cls) -> str:
        """
        Return the default reusable stamp file.
        Creates it once if it does not exist.
        """
        cls._ensure_output_dir()
        output_path = os.path.join(cls.OUTPUT_DIR, "company_stamp.png")
        if os.path.exists(output_path):
            return output_path
        return cls.generate_stamp_png(filename="company_stamp.png")

    @classmethod
    def is_stamp_allowed_for_document(
        cls,
        document_type: Optional[str] = None,
        filename: Optional[str] = None,
        is_quote_document: bool = False,
    ) -> bool:
        """
        Allow stamp only for SBD/MBD/buyer forms.
        Explicitly block quotations and quote packs.
        """
        if is_quote_document:
            return False

        text = f"{document_type or ''} {filename or ''}".lower().strip()

        blocked_tokens = [
            "quote",
            "quotation",
            "quote pack",
            "pro forma",
            "invoice",
            "tax invoice",
        ]
        if any(token in text for token in blocked_tokens):
            return False

        allowed_tokens = [
            "sbd",
            "mbd",
            "buyer form",
            "pricing schedule",
            "declaration",
            "witness",
            "procurement form",
            "bid document",
            "municipal bid",
        ]
        return any(token in text for token in allowed_tokens)

    @classmethod
    def get_default_pdf_stamp_size(cls) -> Tuple[int, int]:
        """
        Suggested stamp render size for PDFs in points.
        """
        return (140, 52)


if __name__ == "__main__":
    stamp_path = StampService.ensure_default_stamp()
    print(f"Stamp created: {stamp_path}")
