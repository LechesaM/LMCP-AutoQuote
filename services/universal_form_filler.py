from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


class UniversalFormFillerError(Exception):
    pass


class UniversalFormFiller:
    """
    Multi-signature relaxed precision mode.

    Goals:
    - keep working text-fill layer
    - detect more real signature rows across the whole PDF
    - still avoid random floating placements
    - allow relaxed matching for dotted/underscored lines near signature labels
    """

    TEXT_FIELD_MAP = {
        "name of bidder": ["name_of_bidder", "bidder_name", "company_name", "client_name"],
        "name of tenderer": ["name_of_bidder", "bidder_name", "company_name", "client_name"],
        "surname and name": ["surname_and_name", "director_name", "signatory_name"],
        "name": ["surname_and_name", "director_name", "signatory_name", "name_of_bidder"],
        "capacity": ["capacity", "designation", "position"],
        "designation": ["designation", "capacity", "position"],
        "position": ["position", "designation", "capacity"],
        "email": ["email", "email_address"],
        "email address": ["email_address", "email"],
        "telephone": ["telephone", "phone", "cellphone_number"],
        "tel": ["telephone", "phone", "cellphone_number"],
        "cell": ["cellphone_number", "telephone"],
        "mobile": ["cellphone_number", "telephone"],
        "postal address": ["postal_address", "address", "street_address"],
        "physical address": ["street_address", "address", "postal_address"],
        "address": ["address", "street_address", "postal_address"],
        "tax reference number": ["tax_reference_number", "tcs_pin"],
        "sars pin tax reference number": ["tcs_pin", "tax_reference_number"],
        "csd registration number": ["csd_number", "csd_registration_number"],
        "date": ["date_signed"],
        "date signed": ["date_signed"],
        "place": ["signed_place", "address"],
    }

    DIRECTOR_ALLOWED_LABELS = {
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
        "authorized signature",
        "authorised signature",
        "signature of official responsible for completing assessment form",
        "deponent signature",
        "applicant signature",
        "sign here",
    }

    WITNESS_1_ALLOWED_LABELS = {
        "witness 1",
        "witness1",
        "first witness",
        "signature of witness 1",
        "signature of first witness",
    }

    WITNESS_2_ALLOWED_LABELS = {
        "witness 2",
        "witness2",
        "second witness",
        "signature of witness 2",
        "signature of second witness",
    }

    BODY_TEXT_BLOCKERS = [
        "all pages must be signed",
        "signed where necessary",
        "must be completed and signed",
        "completed and signed bid document",
        "signed copies",
        "failure to complete and submit",
        "signing of documents",
        "period of validity",
        "digitally signed",
        "must remain valid",
        "bids submitted are to hold good",
        "the bid document must be completed",
    ]

    LINE_PATTERNS = [
        r"\.{5,}",
        r"_{5,}",
        r"-{5,}",
        r"={5,}",
        r"~{5,}",
    ]

    def __init__(self, output_dir: str | None = None) -> None:
        if output_dir is None:
            output_dir = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "generated_forms")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fill_form(
        self,
        input_path: str,
        data: Dict[str, Any],
        signature_path: Optional[str] = None,
        witness_1_signature_path: Optional[str] = None,
        witness_2_signature_path: Optional[str] = None,
        handwriting_sample_path: Optional[str] = None,
        enable_handwriting: bool = False,
        convert_to_pdf: bool = False,
    ) -> Dict[str, Any]:
        if not os.path.exists(input_path):
            raise UniversalFormFillerError(f"Input file not found: {input_path}")

        output_path = str(self.output_dir / "filled_output.pdf")

        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

        text_fill_count = self._fill_text_fields(
            input_pdf_path=output_path,
            output_pdf_path=output_path,
            data=data,
        )

        stamp_result = self._stamp_all_signatures(
            input_pdf_path=output_path,
            output_pdf_path=output_path,
            signature_path=signature_path,
            witness_1_signature_path=witness_1_signature_path,
            witness_2_signature_path=witness_2_signature_path,
        )

        return {
            "status": "success",
            "output_path": output_path,
            "text_fill_count": text_fill_count,
            "relaxed_precision_mode": True,
            **stamp_result,
        }

    # ------------------------------------------------------------------
    # Text filling
    # ------------------------------------------------------------------

    def _fill_text_fields(
        self,
        input_pdf_path: str,
        output_pdf_path: str,
        data: Dict[str, Any],
    ) -> int:
        reader = PdfReader(input_pdf_path)
        text_map = self._extract_text_map(reader)
        placements = self._detect_text_field_placements(text_map, data)
        if not placements:
            return 0

        writer = PdfWriter()
        fill_count = 0

        for page_index, page in enumerate(reader.pages):
            overlay_stream = io.BytesIO()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            c = canvas.Canvas(overlay_stream, pagesize=(page_width, page_height))

            page_has_content = False
            for item in placements:
                if item["page"] != page_index:
                    continue
                c.setFont("Helvetica", float(item.get("font_size", 9.0)))
                c.drawString(float(item["x"]), float(item["y"]), str(item["value"]))
                fill_count += 1
                page_has_content = True

            c.save()
            overlay_stream.seek(0)
            overlay_pdf = PdfReader(overlay_stream)
            if page_has_content and overlay_pdf.pages:
                page.merge_page(overlay_pdf.pages[0])

            writer.add_page(page)

        with open(output_pdf_path, "wb") as f:
            writer.write(f)

        return fill_count

    def _detect_text_field_placements(
        self,
        text_map: List[Dict[str, Any]],
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        placements: List[Dict[str, Any]] = []
        seen = set()

        for item in text_map:
            normalized = self._normalize_text(item["text"])
            if not normalized:
                continue

            for label, data_keys in self.TEXT_FIELD_MAP.items():
                if label not in normalized:
                    continue

                value = self._pick_value(data, data_keys)
                if not value:
                    continue

                placement = self._build_text_placement(item, str(value))
                key = (
                    int(placement["page"]),
                    int(round(placement["x"] / 8.0)),
                    int(round(placement["y"] / 8.0)),
                    label,
                )
                if key in seen:
                    continue
                seen.add(key)
                placements.append(placement)

        return placements

    def _pick_value(self, data: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _build_text_placement(self, anchor_item: Dict[str, Any], value: str) -> Dict[str, Any]:
        page_width = float(anchor_item.get("page_width", 600.0))
        page_height = float(anchor_item.get("page_height", 800.0))
        anchor_x = float(anchor_item.get("x", 72.0))
        anchor_y = float(anchor_item.get("y", 100.0))
        label_text = str(anchor_item.get("text", ""))

        est_label_width = min(max(len(label_text) * 4.6, 45.0), page_width * 0.40)
        x = anchor_x + est_label_width + 10.0
        y = anchor_y - 2.0

        if x > page_width * 0.72:
            x = max(24.0, min(anchor_x, page_width - 180.0))
            y = anchor_y - 14.0

        x = max(24.0, min(x, page_width - 180.0))
        y = max(18.0, min(y, page_height - 18.0))

        return {
            "page": int(anchor_item["page"]),
            "x": x,
            "y": y,
            "value": value,
            "font_size": 9.0,
        }

    # ------------------------------------------------------------------
    # Signature stamping
    # ------------------------------------------------------------------

    def _stamp_all_signatures(
        self,
        input_pdf_path: str,
        output_pdf_path: str,
        signature_path: Optional[str],
        witness_1_signature_path: Optional[str],
        witness_2_signature_path: Optional[str],
    ) -> Dict[str, int]:
        reader = PdfReader(input_pdf_path)

        director_placements = self._detect_signature_placements(reader, signer_type="director")
        witness_1_placements = self._detect_signature_placements(reader, signer_type="witness_1")
        witness_2_placements = self._detect_signature_placements(reader, signer_type="witness_2")

        writer = PdfWriter()
        director_stamped = witness_1_stamped = witness_2_stamped = 0

        for page_index, page in enumerate(reader.pages):
            overlay_stream = io.BytesIO()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            c = canvas.Canvas(overlay_stream, pagesize=(page_width, page_height))
            drawn = False

            if signature_path and os.path.exists(signature_path):
                for placement in director_placements:
                    if placement["page"] != page_index:
                        continue
                    c.drawImage(
                        ImageReader(signature_path),
                        placement["x"],
                        placement["y"],
                        width=placement["width"],
                        height=placement["height"],
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    director_stamped += 1
                    drawn = True

            if witness_1_signature_path and os.path.exists(witness_1_signature_path):
                for placement in witness_1_placements:
                    if placement["page"] != page_index:
                        continue
                    c.drawImage(
                        ImageReader(witness_1_signature_path),
                        placement["x"],
                        placement["y"],
                        width=placement["width"],
                        height=placement["height"],
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    witness_1_stamped += 1
                    drawn = True

            if witness_2_signature_path and os.path.exists(witness_2_signature_path):
                for placement in witness_2_placements:
                    if placement["page"] != page_index:
                        continue
                    c.drawImage(
                        ImageReader(witness_2_signature_path),
                        placement["x"],
                        placement["y"],
                        width=placement["width"],
                        height=placement["height"],
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    witness_2_stamped += 1
                    drawn = True

            c.save()
            overlay_stream.seek(0)
            overlay_pdf = PdfReader(overlay_stream)
            if drawn and overlay_pdf.pages:
                page.merge_page(overlay_pdf.pages[0])

            writer.add_page(page)

        with open(output_pdf_path, "wb") as f:
            writer.write(f)

        return {
            "director_detected_count": len(director_placements),
            "witness_1_detected_count": len(witness_1_placements),
            "witness_2_detected_count": len(witness_2_placements),
            "director_stamped_count": director_stamped,
            "witness_1_stamped_count": witness_1_stamped,
            "witness_2_stamped_count": witness_2_stamped,
        }

    def _detect_signature_placements(
        self,
        reader: PdfReader,
        signer_type: str,
    ) -> List[Dict[str, float]]:
        text_map = self._extract_text_map(reader)
        page_lines = self._extract_page_text_lines(reader)

        results: List[Dict[str, float]] = []
        seen = set()

        for item in text_map:
            raw_text = str(item.get("text", "") or "").strip()
            normalized = self._normalize_text(raw_text)
            if not normalized:
                continue

            if any(blocker in normalized for blocker in self.BODY_TEXT_BLOCKERS):
                continue

            if signer_type == "director":
                if normalized in self.WITNESS_1_ALLOWED_LABELS or normalized in self.WITNESS_2_ALLOWED_LABELS:
                    continue
                is_match = normalized in self.DIRECTOR_ALLOWED_LABELS
            elif signer_type == "witness_1":
                is_match = normalized in self.WITNESS_1_ALLOWED_LABELS
            elif signer_type == "witness_2":
                is_match = normalized in self.WITNESS_2_ALLOWED_LABELS
            else:
                is_match = False

            if not is_match:
                continue

            line_item = self._find_line_near_anchor(item, page_lines, signer_type)
            if line_item is None:
                continue

            placement = self._placement_from_line(item, line_item, signer_type)
            key = (
                int(placement["page"]),
                int(round(placement["x"] / 8.0)),
                int(round(placement["y"] / 8.0)),
                int(round(placement["width"] / 8.0)),
                int(round(placement["height"] / 8.0)),
            )
            if key in seen:
                continue
            seen.add(key)
            results.append(placement)

        return results

    def _find_line_near_anchor(
        self,
        anchor_item: Dict[str, Any],
        page_lines: Dict[int, List[Dict[str, Any]]],
        signer_type: str,
    ) -> Optional[Dict[str, float]]:
        page_index = int(anchor_item["page"])
        lines = page_lines.get(page_index, [])
        if not lines:
            return None

        anchor_y = float(anchor_item["y"])
        anchor_x = float(anchor_item["x"])
        anchor_text = self._normalize_text(anchor_item["text"])

        best = None
        best_score = float("inf")

        # Primary pass: nearby explicit dotted/underscore lines
        for row in lines:
            row_text = str(row["text"] or "")
            extracted = self._extract_line_from_text(row_text)
            if extracted is None:
                continue

            prefix_len, line_len = extracted
            row_y = float(row["y"])
            row_x = float(row["x"])

            delta_y = abs(row_y - anchor_y)
            if delta_y > 70.0:
                continue

            line_x = row_x + (prefix_len * 5.0)
            line_width = max(90.0, line_len * 6.0)

            delta_x_penalty = 0.0
            if line_x < anchor_x - 35.0:
                delta_x_penalty = 70.0

            score = delta_y + delta_x_penalty
            if score < best_score:
                best = {
                    "x": line_x,
                    "y": row_y,
                    "line_width": line_width,
                }
                best_score = score

        if best is not None:
            return best

        # Relaxed fallback for explicit short row labels / form rows
        if anchor_text in {
            "signature", "signature:", "signature of bidder", "signature of bidder:",
            "signature of tenderer", "signature of tenderer:", "signature(s) of tenderer(s)",
            "witness 1", "witness1", "witness 2", "witness2",
        }:
            width = 180.0 if signer_type == "director" else 145.0
            return {
                "x": anchor_x + 80.0,
                "y": anchor_y,
                "line_width": width,
            }

        # Relaxed centered-title fallback for labels printed underneath a dotted line
        # e.g. "Signature" centered under the actual dotted line above it.
        if anchor_text in {"signature", "date", "capacity", "name of bidder"}:
            return {
                "x": max(24.0, anchor_x - 85.0),
                "y": anchor_y + 28.0,
                "line_width": 170.0 if signer_type == "director" else 145.0,
            }

        return None

    def _extract_line_from_text(self, text: str) -> Optional[Tuple[int, int]]:
        matches = []
        for pattern in self.LINE_PATTERNS:
            matches.extend(list(re.finditer(pattern, text or "")))
        if not matches:
            return None
        longest = max(matches, key=lambda m: len(m.group(0)))
        return longest.start(), len(longest.group(0))

    def _placement_from_line(
        self,
        anchor_item: Dict[str, Any],
        line_item: Dict[str, float],
        signer_type: str,
    ) -> Dict[str, float]:
        page_width = float(anchor_item.get("page_width", 600.0))
        page_height = float(anchor_item.get("page_height", 800.0))

        if signer_type == "director":
            max_width = 175.0
            sig_height = 56.0
        else:
            max_width = 145.0
            sig_height = 44.0

        line_x = float(line_item["x"])
        line_y = float(line_item["y"])
        line_width = float(line_item["line_width"])

        width = min(max_width, max(110.0, line_width * 0.80))
        x = max(24.0, min(line_x + 2.0, page_width - width - 24.0))

        # relaxed placement: slightly above the line, but not floating far away
        y = line_y - (sig_height * 0.32)
        y = max(18.0, min(y, page_height - sig_height - 18.0))

        return {
            "page": int(anchor_item["page"]),
            "x": x,
            "y": y,
            "width": width,
            "height": sig_height,
        }

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text_map(self, reader: PdfReader) -> List[Dict[str, Any]]:
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
            except TypeError:
                visitor_items = []
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

    def _extract_page_text_lines(self, reader: PdfReader) -> Dict[int, List[Dict[str, Any]]]:
        page_lines: Dict[int, List[Dict[str, Any]]] = {}
        for page_index, page in enumerate(reader.pages):
            page_height = float(page.mediabox.height)
            page_width = float(page.mediabox.width)

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            lines: List[Dict[str, Any]] = []
            y = page_height - 72.0
            for line in text.split("\n"):
                if line.strip():
                    lines.append(
                        {
                            "text": line.rstrip(),
                            "x": 72.0,
                            "y": y,
                            "page_width": page_width,
                            "page_height": page_height,
                        }
                    )
                y -= 15.0

            page_lines[page_index] = lines
        return page_lines

    def _merge_nearby_text_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []

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
                    merged.append(self._combine_text_parts(current_parts))
                    current_parts = [row_item]

            if current_parts:
                merged.append(self._combine_text_parts(current_parts))

        merged.sort(key=lambda r: (r["page"], -float(r["y"]), float(r["x"])))
        return merged

    def _combine_text_parts(self, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not parts:
            return {}

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

    def _normalize_text(self, text: str) -> str:
        text = (text or "").lower()
        text = text.replace("&", " and ")
        text = text.replace("’", "'").replace("‘", "'")
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^a-z0-9\.\' _\-\:\(\)~=]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def build_lmcp_default_form_data(
    tender_data: Optional[Dict[str, Any]] = None,
    company_data: Optional[Dict[str, Any]] = None,
    director_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tender_data = tender_data or {}
    company_data = company_data or {}
    director_data = director_data or {}

    merged = {
        "client_name": tender_data.get("client_name", "LMCP"),
        "date_signed": tender_data.get("date_signed", ""),
        "rfq_number": tender_data.get("rfq_number", ""),
        "name_of_bidder": tender_data.get("name_of_bidder", tender_data.get("client_name", "LMCP")),
        "bidder_name": tender_data.get("bidder_name", tender_data.get("client_name", "LMCP")),
        "company_name": company_data.get("company_name", tender_data.get("client_name", "LMCP")),
        "director_name": director_data.get("director_name", "Lechesa Manaba"),
        "signatory_name": director_data.get("signatory_name", "Lechesa Manaba"),
        "surname_and_name": tender_data.get("surname_and_name", "Lechesa Manaba"),
        "designation": tender_data.get("designation", "Director"),
        "capacity": tender_data.get("capacity", "Director"),
        "position": tender_data.get("position", "Director"),
        "address": tender_data.get("address", ""),
        "street_address": tender_data.get("street_address", tender_data.get("address", "")),
        "postal_address": tender_data.get("postal_address", tender_data.get("address", "")),
        "telephone": tender_data.get("telephone", ""),
        "phone": tender_data.get("phone", tender_data.get("telephone", "")),
        "cellphone_number": tender_data.get("cellphone_number", tender_data.get("telephone", "")),
        "email": tender_data.get("email", ""),
        "email_address": tender_data.get("email_address", tender_data.get("email", "")),
        "tax_reference_number": tender_data.get("tax_reference_number", ""),
        "tcs_pin": tender_data.get("tcs_pin", ""),
        "csd_number": tender_data.get("csd_number", ""),
        "csd_registration_number": tender_data.get("csd_registration_number", ""),
        "signed_place": tender_data.get("signed_place", ""),
    }

    merged.update(company_data)
    merged.update(director_data)
    merged.update(tender_data)
    return merged
