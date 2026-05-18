from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:
    cv2 = None
    np = None


@dataclass
class DetectedSignatureField:
    page: int
    signer_type: str
    x: float
    y: float
    width: float
    height: float
    label_text: str = ""
    confidence: float = 0.0
    source: str = "unknown"


class AISignatureDetector:
    """
    Local-first signature field detector.

    It is intentionally hybrid:
    1. Reads text anchors from PDF text.
    2. Renders pages to images locally.
    3. Uses simple visual detection of horizontal lines/cells near anchors.
    4. Returns candidate signature boxes for rule validation.

    No external API calls.
    """

    DIRECTOR_LABELS = {
        "signature",
        "signature:",
        "signature of bidder",
        "signature of bidder:",
        "signature of tenderer",
        "signature of tenderer:",
        "signature(s) of tenderer(s)",
        "signature(s) of tenderer(s):",
        "signature(s) of tenderers",
        "bidder signature",
        "tenderer signature",
        "tenderer's signature",
        "tenderers signature",
        "authorised signature",
        "authorized signature",
        "signature of official responsible for completing assessment form",
        "designation (only director or relevant representative may sign this form)",
        "designation only director or relevant representative may sign this form",
        "sign here",
        "deponent signature",
        "applicant signature",
    }

    WITNESS_1_LABELS = {
        "witness 1",
        "witness1",
        "first witness",
        "signature of witness 1",
        "signature of first witness",
    }

    WITNESS_2_LABELS = {
        "witness 2",
        "witness2",
        "second witness",
        "signature of witness 2",
        "signature of second witness",
    }

    BODY_BLOCKERS = [
        "all pages must be signed",
        "signed where necessary",
        "must be completed and signed",
        "completed and signed bid document",
        "signed copies",
        "failure to complete and submit",
        "signing of documents",
        "digitally signed",
    ]

    def __init__(self, dpi: int = 160) -> None:
        self.dpi = dpi

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, pdf_path: str) -> List[DetectedSignatureField]:
        text_map = self._extract_text_map(pdf_path)
        page_images = self._render_pdf_pages(pdf_path)
        results: List[DetectedSignatureField] = []

        for item in text_map:
            normalized = self._normalize_text(item["text"])
            if not normalized:
                continue
            if any(blocker in normalized for blocker in self.BODY_BLOCKERS):
                continue

            signer_type = self._classify_label(normalized)
            if signer_type is None:
                continue

            page_index = int(item["page"])
            page_image = page_images.get(page_index)
            line_box = None
            if page_image is not None:
                line_box = self._detect_horizontal_line_near_anchor(
                    image=page_image,
                    anchor=item,
                )

            field = self._build_field_from_anchor(item, signer_type, line_box)
            results.append(field)

        return self._dedupe_fields(results)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_label(self, normalized: str) -> Optional[str]:
        if normalized in self.WITNESS_1_LABELS:
            return "witness_1"
        if normalized in self.WITNESS_2_LABELS:
            return "witness_2"
        if normalized in self.DIRECTOR_LABELS:
            return "director"
        return None

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text_map(self, pdf_path: str) -> List[Dict[str, Any]]:
        reader = PdfReader(pdf_path)
        text_map: List[Dict[str, Any]] = []

        for page_index, page in enumerate(reader.pages):
            page_height = float(page.mediabox.height)
            page_width = float(page.mediabox.width)
            visitor_items: List[Dict[str, Any]] = []

            try:
                def visitor_text(text, cm, tm, font_dict, font_size):
                    raw_text = str(text or "")
                    cleaned = raw_text.strip()
                    if not cleaned:
                        return

                    x = 72.0
                    y = page_height - 72.0
                    try:
                        if tm and len(tm) >= 6:
                            x = float(tm[4])
                            y = float(tm[5])
                    except Exception:
                        pass

                    if y < 0:
                        y = page_height + y

                    visitor_items.append(
                        {
                            "page": page_index,
                            "text": cleaned,
                            "x": max(10.0, float(x)),
                            "y": max(10.0, float(y)),
                            "page_width": page_width,
                            "page_height": page_height,
                        }
                    )

                page.extract_text(visitor_text=visitor_text)
            except Exception:
                visitor_items = []

            if visitor_items:
                text_map.extend(self._merge_nearby_text_items(visitor_items))
                continue

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            y = page_height - 72.0
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                text_map.append(
                    {
                        "page": page_index,
                        "text": line,
                        "x": 72.0,
                        "y": y,
                        "page_width": page_width,
                        "page_height": page_height,
                    }
                )
                y -= 15.0

        return text_map

    def _merge_nearby_text_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        for item in items:
            key = (int(item["page"]), int(round(float(item["y"]) / 6.0)))
            grouped.setdefault(key, []).append(item)

        merged: List[Dict[str, Any]] = []
        for _, row_items in grouped.items():
            row_items.sort(key=lambda r: float(r["x"]))
            current_parts: List[Dict[str, Any]] = []

            for row_item in row_items:
                if not current_parts:
                    current_parts = [row_item]
                    continue

                previous = current_parts[-1]
                previous_right = float(previous["x"]) + max(8.0, len(str(previous["text"])) * 4.5)
                gap = float(row_item["x"]) - previous_right

                if gap <= 28.0:
                    current_parts.append(row_item)
                else:
                    merged.append(self._combine_parts(current_parts))
                    current_parts = [row_item]

            if current_parts:
                merged.append(self._combine_parts(current_parts))

        merged.sort(key=lambda r: (r["page"], -float(r["y"]), float(r["x"])))
        return merged

    def _combine_parts(self, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        text = " ".join(str(p["text"]).strip() for p in parts if str(p["text"]).strip())
        first = parts[0]
        return {
            "page": int(first["page"]),
            "text": text.strip(),
            "x": float(min(float(p["x"]) for p in parts)),
            "y": float(sum(float(p["y"]) for p in parts) / max(len(parts), 1)),
            "page_width": float(first["page_width"]),
            "page_height": float(first["page_height"]),
        }

    # ------------------------------------------------------------------
    # Page rendering
    # ------------------------------------------------------------------

    def _render_pdf_pages(self, pdf_path: str) -> Dict[int, Any]:
        pages: Dict[int, Any] = {}

        if fitz is not None:
            doc = fitz.open(pdf_path)
            zoom = self.dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img_bytes = pix.tobytes("png")
                if cv2 is not None and np is not None:
                    arr = np.frombuffer(img_bytes, dtype=np.uint8)
                    pages[i] = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                else:
                    pages[i] = img_bytes
            return pages

        if convert_from_path is not None:
            pil_pages = convert_from_path(pdf_path, dpi=self.dpi)
            for i, pil_img in enumerate(pil_pages):
                if cv2 is not None and np is not None:
                    pages[i] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            return pages

        return pages

    # ------------------------------------------------------------------
    # Visual line detection
    # ------------------------------------------------------------------

    def _detect_horizontal_line_near_anchor(
        self,
        image: Any,
        anchor: Dict[str, Any],
    ) -> Optional[Dict[str, float]]:
        if cv2 is None or np is None or image is None:
            return None

        page_width = float(anchor["page_width"])
        page_height = float(anchor["page_height"])

        img_h, img_w = image.shape[:2]
        scale_x = img_w / max(page_width, 1.0)
        scale_y = img_h / max(page_height, 1.0)

        ax = int(float(anchor["x"]) * scale_x)
        ay_pdf = float(anchor["y"])
        ay = int((page_height - ay_pdf) * scale_y)

        # Search to the right and slightly below the anchor for a line.
        x1 = max(0, ax - 20)
        x2 = min(img_w, ax + int(img_w * 0.55))
        y1 = max(0, ay - 50)
        y2 = min(img_h, ay + 80)

        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)

        # Emphasize horizontal strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        horiz = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_len = 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 70 or h > 8:
                continue
            if w > best_len:
                best_len = w
                best = (x, y, w, h)

        if best is None:
            return None

        bx, by, bw, bh = best
        pdf_x = (x1 + bx) / scale_x
        pdf_y = page_height - ((y1 + by) / scale_y)
        pdf_w = bw / scale_x

        return {
            "x": pdf_x,
            "y": pdf_y,
            "line_width": pdf_w,
        }

    # ------------------------------------------------------------------
    # Placement building
    # ------------------------------------------------------------------

    def _build_field_from_anchor(
        self,
        anchor: Dict[str, Any],
        signer_type: str,
        line_box: Optional[Dict[str, float]],
    ) -> DetectedSignatureField:
        page_width = float(anchor["page_width"])
        page_height = float(anchor["page_height"])
        anchor_x = float(anchor["x"])
        anchor_y = float(anchor["y"])

        if signer_type == "director":
            sig_width = 180.0
            sig_height = 60.0
        else:
            sig_width = 150.0
            sig_height = 48.0

        if line_box is not None:
            width = min(sig_width, max(120.0, float(line_box["line_width"]) * 0.82))
            x = max(24.0, min(float(line_box["x"]) + 4.0, page_width - width - 24.0))
            y = max(18.0, min(float(line_box["y"]) + 2.0, page_height - sig_height - 18.0))
            return DetectedSignatureField(
                page=int(anchor["page"]),
                signer_type=signer_type,
                x=x,
                y=y,
                width=width,
                height=sig_height,
                label_text=str(anchor["text"]),
                confidence=0.90,
                source="vision_line",
            )

        # Cell/right-side fallback
        x = anchor_x + 85.0
        y = anchor_y - 6.0
        x = max(24.0, min(x, page_width - sig_width - 24.0))
        y = max(18.0, min(y, page_height - sig_height - 18.0))

        if anchor_y < page_height * 0.35:
            y = max(y, page_height * 0.22)

        return DetectedSignatureField(
            page=int(anchor["page"]),
            signer_type=signer_type,
            x=x,
            y=y,
            width=sig_width,
            height=sig_height,
            label_text=str(anchor["text"]),
            confidence=0.65,
            source="anchor_cell_fallback",
        )

    def _dedupe_fields(self, fields: List[DetectedSignatureField]) -> List[DetectedSignatureField]:
        out: List[DetectedSignatureField] = []
        seen = set()
        for f in fields:
            key = (
                f.page,
                f.signer_type,
                int(round(f.x / 10.0)),
                int(round(f.y / 10.0)),
                int(round(f.width / 10.0)),
                int(round(f.height / 10.0)),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

    def _normalize_text(self, text: str) -> str:
        text = (text or "").lower()
        text = text.replace("&", " and ")
        text = text.replace("’", "'").replace("‘", "'")
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^a-z0-9\.\' _\-\:\(\)~=]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

