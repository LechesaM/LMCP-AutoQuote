from __future__ import annotations

import io
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


EXPECTED_GLYPH_ORDER = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890")


@dataclass
class HandwritingPlacement:
    page: int
    text: str
    x: float
    y: float
    max_width: Optional[float] = None
    max_height: Optional[float] = None
    scale: float = 1.0
    jitter_x: float = 0.0
    jitter_y: float = 0.0
    char_spacing: int = 8
    baseline_jitter: int = 2
    rotate_jitter: float = 0.0
    force_uppercase: bool = True


class HandwritingRenderer:
    """
    Builds a glyph library from a handwritten sample image and renders text
    using the extracted glyphs.

    Recommended sample:
    - black ink on white paper
    - uppercase A-Z
    - digits 1-9 and 0
    - letters separated enough to segment
    """

    def __init__(
        self,
        sample_image_path: str,
        expected_order: Optional[Sequence[str]] = None,
        threshold: int = 180,
        min_row_gap: int = 12,
        min_col_gap: int = 8,
        seed: int = 42,
    ) -> None:
        self.sample_image_path = sample_image_path
        self.expected_order = list(expected_order or EXPECTED_GLYPH_ORDER)
        self.threshold = threshold
        self.min_row_gap = min_row_gap
        self.min_col_gap = min_col_gap
        self.random = random.Random(seed)
        self.glyphs: Dict[str, Image.Image] = {}

        self._load_and_segment()

    def render_text_image(
        self,
        text: str,
        char_spacing: int = 8,
        baseline_jitter: int = 2,
        rotate_jitter: float = 0.0,
        force_uppercase: bool = True,
        padding: int = 8,
        scale: float = 1.0,
    ) -> Image.Image:
        """Returns a transparent RGBA image containing rendered handwritten text."""
        if force_uppercase:
            text = text.upper()

        glyph_entries: List[Tuple[str, Optional[Image.Image], int, int, float]] = []
        total_width = padding
        max_height = 0

        for ch in text:
            glyph = self._glyph_for_char(ch)
            if glyph is None:
                adv = max(14, int(18 * scale)) if ch == " " else max(10, int(14 * scale))
                glyph_entries.append((ch, None, adv, 0, 0.0))
                total_width += adv
                continue

            rendered = glyph.copy()

            if scale != 1.0:
                new_w = max(1, int(rendered.width * scale))
                new_h = max(1, int(rendered.height * scale))
                rendered = rendered.resize((new_w, new_h), Image.LANCZOS)

            angle = 0.0
            if rotate_jitter:
                angle = self.random.uniform(-rotate_jitter, rotate_jitter)
                rendered = rendered.rotate(angle, resample=Image.BICUBIC, expand=True)

            dy = self.random.randint(-baseline_jitter, baseline_jitter) if baseline_jitter else 0
            glyph_entries.append((ch, rendered, rendered.width + char_spacing, dy, angle))
            total_width += rendered.width + char_spacing
            max_height = max(max_height, rendered.height + abs(dy))

        total_width += padding
        total_height = max_height + (padding * 2) + 10
        total_width = max(total_width, 10)
        total_height = max(total_height, 10)

        out = Image.new("RGBA", (total_width, total_height), (255, 255, 255, 0))
        cursor_x = padding
        baseline_y = padding + max_height // 2

        for _ch, rendered, advance, dy, _angle in glyph_entries:
            if rendered is None:
                cursor_x += advance
                continue

            top_y = baseline_y - rendered.height // 2 + dy
            out.alpha_composite(rendered, (cursor_x, top_y))
            cursor_x += advance

        return self._trim_transparent(out)

    def stamp_text_on_pdf(
        self,
        input_pdf_path: str,
        output_pdf_path: str,
        placements: Sequence[HandwritingPlacement],
    ) -> str:
        """
        Stamps handwritten text onto an existing PDF.
        Coordinates are in PDF points, origin bottom-left.
        Page numbering is zero-based.
        """
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        placements_by_page: Dict[int, List[HandwritingPlacement]] = {}
        for item in placements:
            placements_by_page.setdefault(item.page, []).append(item)

        for page_index, page in enumerate(reader.pages):
            overlay_bytes = io.BytesIO()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            c = canvas.Canvas(overlay_bytes, pagesize=(page_width, page_height))

            for placement in placements_by_page.get(page_index, []):
                text_image = self.render_text_image(
                    text=placement.text,
                    char_spacing=placement.char_spacing,
                    baseline_jitter=placement.baseline_jitter,
                    rotate_jitter=placement.rotate_jitter,
                    force_uppercase=placement.force_uppercase,
                    scale=placement.scale,
                )

                draw_w = float(text_image.width)
                draw_h = float(text_image.height)

                if placement.max_width and draw_w > placement.max_width:
                    ratio = placement.max_width / draw_w
                    draw_w *= ratio
                    draw_h *= ratio

                if placement.max_height and draw_h > placement.max_height:
                    ratio = placement.max_height / draw_h
                    draw_w *= ratio
                    draw_h *= ratio

                x = placement.x + self.random.uniform(-placement.jitter_x, placement.jitter_x)
                y = placement.y + self.random.uniform(-placement.jitter_y, placement.jitter_y)

                img_reader = ImageReader(text_image)
                c.drawImage(
                    img_reader,
                    x,
                    y,
                    width=draw_w,
                    height=draw_h,
                    mask="auto",
                    preserveAspectRatio=True,
                    anchor="sw",
                )

            c.save()

            overlay_bytes.seek(0)
            overlay_pdf = PdfReader(overlay_bytes)
            if overlay_pdf.pages:
                page.merge_page(overlay_pdf.pages[0])

            writer.add_page(page)

        os.makedirs(os.path.dirname(output_pdf_path) or ".", exist_ok=True)
        with open(output_pdf_path, "wb") as f:
            writer.write(f)

        return output_pdf_path

    def _load_and_segment(self) -> None:
        source = Image.open(self.sample_image_path).convert("L")
        source = ImageOps.autocontrast(source)
        binary = source.point(lambda p: 255 if p < self.threshold else 0, mode="L")

        row_boxes = self._find_row_boxes(binary)
        extracted: List[Image.Image] = []

        for row_box in row_boxes:
            row_img = binary.crop(row_box)
            char_boxes = self._find_char_boxes_in_row(row_img, row_box)
            for box in char_boxes:
                glyph = self._extract_glyph(binary, box)
                if glyph is not None:
                    extracted.append(glyph)

        if len(extracted) != len(self.expected_order):
            raise ValueError(
                f"Handwriting sample segmentation failed. "
                f"Expected {len(self.expected_order)} glyphs, found {len(extracted)}. "
                f"Please use a cleaner sample with clear spacing."
            )

        for ch, glyph in zip(self.expected_order, extracted):
            self.glyphs[ch] = glyph

    def _find_row_boxes(self, binary: Image.Image) -> List[Tuple[int, int, int, int]]:
        width, height = binary.size
        rows_with_ink: List[int] = []

        for y in range(height):
            row = binary.crop((0, y, width, y + 1))
            bbox = row.getbbox()
            if bbox:
                rows_with_ink.append(y)

        groups = self._group_indices(rows_with_ink, self.min_row_gap)
        boxes: List[Tuple[int, int, int, int]] = []

        for start_y, end_y in groups:
            crop = binary.crop((0, start_y, width, end_y + 1))
            bbox = crop.getbbox()
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            boxes.append((x1, start_y + y1, x2, start_y + y2))

        boxes.sort(key=lambda b: b[1])
        return boxes

    def _find_char_boxes_in_row(
        self,
        row_img: Image.Image,
        original_row_box: Tuple[int, int, int, int],
    ) -> List[Tuple[int, int, int, int]]:
        row_bbox = row_img.getbbox()
        if not row_bbox:
            return []

        row_img = row_img.crop(row_bbox)
        row_offset_x = original_row_box[0] + row_bbox[0]
        row_offset_y = original_row_box[1] + row_bbox[1]

        width, height = row_img.size
        cols_with_ink: List[int] = []

        for x in range(width):
            col = row_img.crop((x, 0, x + 1, height))
            bbox = col.getbbox()
            if bbox:
                cols_with_ink.append(x)

        groups = self._group_indices(cols_with_ink, self.min_col_gap)
        boxes: List[Tuple[int, int, int, int]] = []

        for start_x, end_x in groups:
            crop = row_img.crop((start_x, 0, end_x + 1, height))
            bbox = crop.getbbox()
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            boxes.append(
                (
                    row_offset_x + start_x + x1,
                    row_offset_y + y1,
                    row_offset_x + start_x + x2,
                    row_offset_y + y2,
                )
            )

        boxes.sort(key=lambda b: b[0])
        return boxes

    def _extract_glyph(self, binary: Image.Image, box: Tuple[int, int, int, int]) -> Optional[Image.Image]:
        glyph = binary.crop(box)
        bbox = glyph.getbbox()
        if not bbox:
            return None

        glyph = glyph.crop(bbox)
        w, h = glyph.size
        rgba = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        alpha = glyph.copy()
        rgba.putalpha(alpha)

        black_layer = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        rgba = Image.composite(black_layer, rgba, alpha)
        return self._trim_transparent(rgba)

    def _glyph_for_char(self, ch: str) -> Optional[Image.Image]:
        if ch in self.glyphs:
            return self.glyphs[ch].copy()
        if ch.upper() in self.glyphs:
            return self.glyphs[ch.upper()].copy()

        synthetic = self._render_synthetic_char(ch)
        if synthetic is not None:
            return synthetic
        return None

    def _render_synthetic_char(self, ch: str) -> Optional[Image.Image]:
        canvas_w = 36
        canvas_h = 52
        stroke = 4

        img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        if ch == "-":
            draw.line((6, 28, 30, 28), fill=(0, 0, 0, 255), width=stroke)
        elif ch == "/":
            draw.line((8, 42, 28, 8), fill=(0, 0, 0, 255), width=stroke)
        elif ch == ".":
            draw.ellipse((14, 36, 22, 44), fill=(0, 0, 0, 255))
        elif ch == ",":
            draw.ellipse((14, 34, 22, 42), fill=(0, 0, 0, 255))
            draw.line((18, 41, 14, 48), fill=(0, 0, 0, 255), width=stroke - 1)
        elif ch == ":":
            draw.ellipse((14, 16, 22, 24), fill=(0, 0, 0, 255))
            draw.ellipse((14, 34, 22, 42), fill=(0, 0, 0, 255))
        elif ch == "(":
            draw.arc((8, 6, 28, 46), start=90, end=270, fill=(0, 0, 0, 255), width=stroke)
        elif ch == ")":
            draw.arc((8, 6, 28, 46), start=-90, end=90, fill=(0, 0, 0, 255), width=stroke)
        elif ch == "'":
            draw.line((18, 8, 15, 20), fill=(0, 0, 0, 255), width=stroke - 1)
        elif ch == "&":
            draw.arc((8, 6, 28, 24), start=20, end=320, fill=(0, 0, 0, 255), width=stroke)
            draw.line((24, 24, 12, 40), fill=(0, 0, 0, 255), width=stroke)
            draw.arc((10, 26, 28, 44), start=180, end=20, fill=(0, 0, 0, 255), width=stroke)
        else:
            return None

        return self._trim_transparent(img)

    @staticmethod
    def _group_indices(indices: Sequence[int], min_gap: int) -> List[Tuple[int, int]]:
        if not indices:
            return []

        groups: List[Tuple[int, int]] = []
        start = indices[0]
        prev = indices[0]

        for idx in indices[1:]:
            if idx - prev > min_gap:
                groups.append((start, prev))
                start = idx
            prev = idx

        groups.append((start, prev))
        return groups

    @staticmethod
    def _trim_transparent(img: Image.Image) -> Image.Image:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        bbox = img.getbbox()
        if not bbox:
            return img
        return img.crop(bbox)


def build_handwriting_renderer(sample_image_path: str) -> HandwritingRenderer:
    return HandwritingRenderer(sample_image_path=sample_image_path)


def stamp_handwriting_on_pdf(
    input_pdf_path: str,
    output_pdf_path: str,
    sample_image_path: str,
    placements: Sequence[HandwritingPlacement],
) -> str:
    renderer = build_handwriting_renderer(sample_image_path)
    return renderer.stamp_text_on_pdf(
        input_pdf_path=input_pdf_path,
        output_pdf_path=output_pdf_path,
        placements=placements,
    )


def render_handwriting_preview(
    sample_image_path: str,
    text: str,
    output_image_path: str,
    char_spacing: int = 8,
    baseline_jitter: int = 2,
    rotate_jitter: float = 1.4,
    force_uppercase: bool = True,
    scale: float = 1.0,
) -> str:
    renderer = build_handwriting_renderer(sample_image_path)
    img = renderer.render_text_image(
        text=text,
        char_spacing=char_spacing,
        baseline_jitter=baseline_jitter,
        rotate_jitter=rotate_jitter,
        force_uppercase=force_uppercase,
        scale=scale,
    )
    os.makedirs(os.path.dirname(output_image_path) or ".", exist_ok=True)
    img.save(output_image_path)
    return output_image_path

