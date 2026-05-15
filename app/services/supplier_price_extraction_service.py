from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SupplierPriceExtractionError(Exception):
    pass


@dataclass
class ExtractedLineItem:
    description: str
    quantity: Optional[float]
    unit_price: Optional[float]
    line_total: Optional[float]
    raw_line: str
    confidence: float


@dataclass
class ExtractedPriceResult:
    source_pdf: str
    supplier_name: Optional[str]
    currency: str
    subtotal: Optional[float]
    vat: Optional[float]
    total_including_vat: Optional[float]
    total_excluding_vat: Optional[float]
    vat_rate_percent: Optional[float]
    quotation_number: Optional[str]
    rfq_number: Optional[str]
    line_items: List[ExtractedLineItem]
    detected_amounts: List[float]
    confidence: float
    extraction_method: str
    notes: List[str]
    raw_text_preview: str


class SupplierPriceExtractionService:
    """
    Extract pricing data from supplier quotation PDFs.

    Main goals:
    - read PDF text safely
    - find total / subtotal / VAT
    - attempt line-item extraction
    - provide structured result for quote comparison
    """

    CURRENCY_DEFAULT = "ZAR"

    MONEY_PATTERN = re.compile(
        r"""
        (?:
            R\s*
        )?
        (?P<amount>
            -?
            (?:
                \d{1,3}(?:[ ,]\d{3})+(?:\.\d{2})?
                |
                \d+(?:\.\d{2})?
            )
        )
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    QUOTATION_NUMBER_PATTERNS = [
        re.compile(r"\b(?:quotation|quote)\s*(?:number|no|#)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)\b", re.IGNORECASE),
        re.compile(r"\bquote\s*ref(?:erence)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)\b", re.IGNORECASE),
    ]

    RFQ_NUMBER_PATTERNS = [
        re.compile(r"\bRFQ\s*(?:number|no|#)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)\b", re.IGNORECASE),
        re.compile(r"\benquiry\s*(?:number|no|#)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)\b", re.IGNORECASE),
        re.compile(r"\breference\s*(?:number|no|#)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)\b", re.IGNORECASE),
    ]

    SUPPLIER_NAME_PATTERNS = [
        re.compile(r"\bfrom\s*[:\-]?\s*(.+)", re.IGNORECASE),
        re.compile(r"\bsupplier\s*[:\-]?\s*(.+)", re.IGNORECASE),
        re.compile(r"\bcompany\s*name\s*[:\-]?\s*(.+)", re.IGNORECASE),
    ]

    TOTAL_LABEL_PATTERNS = [
        re.compile(r"\bgrand\s+total\b", re.IGNORECASE),
        re.compile(r"\btotal\s+incl(?:uding)?\.?\s+vat\b", re.IGNORECASE),
        re.compile(r"\btotal\s+including\s+vat\b", re.IGNORECASE),
        re.compile(r"\bamount\s+due\b", re.IGNORECASE),
        re.compile(r"\bamount\s+payable\b", re.IGNORECASE),
        re.compile(r"\binvoice\s+total\b", re.IGNORECASE),
        re.compile(r"\bquotation\s+total\b", re.IGNORECASE),
        re.compile(r"\btotal\b", re.IGNORECASE),
    ]

    SUBTOTAL_LABEL_PATTERNS = [
        re.compile(r"\bsub[\s\-]?total\b", re.IGNORECASE),
        re.compile(r"\btotal\s+excl(?:uding)?\.?\s+vat\b", re.IGNORECASE),
        re.compile(r"\btotal\s+excluding\s+vat\b", re.IGNORECASE),
        re.compile(r"\bnet\s+amount\b", re.IGNORECASE),
    ]

    VAT_LABEL_PATTERNS = [
        re.compile(r"\bvat\b", re.IGNORECASE),
        re.compile(r"\btax\b", re.IGNORECASE),
    ]

    LINE_ITEM_SPLIT_PATTERN = re.compile(r"\s{2,}|\t+")

    @classmethod
    def _clean_text(cls, text: str) -> str:
        text = text.replace("\x00", " ")
        text = text.replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _normalize_amount_string(cls, raw: str) -> Optional[float]:
        if not raw:
            return None

        cleaned = raw.strip()
        cleaned = cleaned.replace("R", "").replace(" ", "")

        # Handle "1,234.56"
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        # Handle "1 234,56" already space-stripped above, so this becomes "1234,56"
        elif "," in cleaned and "." not in cleaned:
            # Determine if comma is decimal or thousands separator
            if cleaned.count(",") == 1 and len(cleaned.split(",")[-1]) in {2}:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        try:
            return float(Decimal(cleaned))
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def _extract_pdf_text(cls, pdf_path: str) -> Tuple[str, str, List[str]]:
        """
        Returns:
        - extracted text
        - extraction method used
        - notes
        """
        path = Path(pdf_path)
        if not path.exists():
            raise SupplierPriceExtractionError(f"PDF not found: {pdf_path}")

        notes: List[str] = []

        # Prefer pdfplumber if available
        try:
            import pdfplumber  # type: ignore

            pages_text: List[str] = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        pages_text.append(page_text)
            text = "\n\n".join(pages_text).strip()
            if text:
                return cls._clean_text(text), "pdfplumber", notes
            notes.append("pdfplumber extracted little or no text.")
        except Exception as exc:
            notes.append(f"pdfplumber unavailable or failed: {exc}")

        # Fallback to pypdf
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text).strip()
            if text:
                return cls._clean_text(text), "pypdf", notes
            notes.append("pypdf extracted little or no text.")
        except Exception as exc:
            notes.append(f"pypdf unavailable or failed: {exc}")

        raise SupplierPriceExtractionError(
            "Unable to extract text from PDF. The file may be scanned/image-based and may require OCR."
        )

    @classmethod
    def _extract_first_match(cls, text: str, patterns: List[re.Pattern[str]]) -> Optional[str]:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                value = re.sub(r"\s{2,}", " ", value)
                return value
        return None

    @classmethod
    def _find_amounts_in_line(cls, line: str) -> List[float]:
        values: List[float] = []
        for match in cls.MONEY_PATTERN.finditer(line):
            amount = cls._normalize_amount_string(match.group("amount"))
            if amount is not None:
                values.append(amount)
        return values

    @classmethod
    def _all_detected_amounts(cls, text: str) -> List[float]:
        values: List[float] = []
        for match in cls.MONEY_PATTERN.finditer(text):
            amount = cls._normalize_amount_string(match.group("amount"))
            if amount is not None:
                # ignore tiny accidental matches unless they look like money
                if amount >= 1:
                    values.append(amount)
        return values

    @classmethod
    def _line_looks_like_total(cls, line: str) -> bool:
        return any(pattern.search(line) for pattern in cls.TOTAL_LABEL_PATTERNS)

    @classmethod
    def _line_looks_like_subtotal(cls, line: str) -> bool:
        return any(pattern.search(line) for pattern in cls.SUBTOTAL_LABEL_PATTERNS)

    @classmethod
    def _line_looks_like_vat(cls, line: str) -> bool:
        return any(pattern.search(line) for pattern in cls.VAT_LABEL_PATTERNS)

    @classmethod
    def _extract_vat_rate(cls, text: str) -> Optional[float]:
        match = re.search(r"\bVAT\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)\s*%\b", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None

        # South Africa common fallback
        if re.search(r"\bVAT\b", text, re.IGNORECASE):
            return 15.0

        return None

    @classmethod
    def _best_amount_from_labelled_lines(
        cls, lines: List[str]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], List[str]]:
        subtotal = None
        vat = None
        total = None
        notes: List[str] = []

        for line in lines:
            amounts = cls._find_amounts_in_line(line)
            if not amounts:
                continue

            if cls._line_looks_like_subtotal(line):
                candidate = max(amounts)
                subtotal = candidate if subtotal is None else max(subtotal, candidate)

            elif cls._line_looks_like_vat(line):
                candidate = max(amounts)
                vat = candidate if vat is None else max(vat, candidate)

            elif cls._line_looks_like_total(line):
                candidate = max(amounts)
                total = candidate if total is None else max(total, candidate)

        # Basic sanity correction:
        if subtotal is not None and vat is not None and total is None:
            computed = round(subtotal + vat, 2)
            total = computed
            notes.append("Computed total from subtotal + VAT.")

        if total is not None and vat is not None and subtotal is None:
            computed = round(total - vat, 2)
            subtotal = computed
            notes.append("Computed subtotal from total - VAT.")

        return subtotal, vat, total, notes

    @classmethod
    def _extract_line_items(cls, lines: List[str]) -> List[ExtractedLineItem]:
        line_items: List[ExtractedLineItem] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            lower = line.lower()
            if any(
                phrase in lower
                for phrase in [
                    "subtotal",
                    "sub total",
                    "vat",
                    "grand total",
                    "amount due",
                    "amount payable",
                    "invoice total",
                    "quotation total",
                ]
            ):
                continue

            amounts = cls._find_amounts_in_line(line)
            if len(amounts) < 1:
                continue

            # Ignore very short lines that are probably not useful
            if len(line) < 8:
                continue

            qty = None
            unit_price = None
            line_total = None
            confidence = 0.3

            # Try tabular split first
            parts = [part.strip() for part in cls.LINE_ITEM_SPLIT_PATTERN.split(line) if part.strip()]

            if len(parts) >= 2:
                part_amounts = [cls._normalize_amount_string(part) for part in parts]
                numeric_parts = [value for value in part_amounts if value is not None]

                if len(numeric_parts) >= 2:
                    line_total = numeric_parts[-1]
                    unit_price = numeric_parts[-2]

                    # Attempt quantity from previous numeric field if it exists and is not a money-looking decimal
                    if len(numeric_parts) >= 3:
                        candidate_qty = numeric_parts[-3]
                        if candidate_qty is not None and candidate_qty <= 100000:
                            qty = candidate_qty

                    description_parts = []
                    for part in parts:
                        if cls._normalize_amount_string(part) is None:
                            description_parts.append(part)
                    description = " ".join(description_parts).strip()
                    confidence = 0.8 if description and line_total is not None else 0.55
                else:
                    description = parts[0]
                    line_total = amounts[-1]
                    confidence = 0.45
            else:
                description = re.sub(cls.MONEY_PATTERN, "", line).strip(" -:\t")
                line_total = amounts[-1]
                confidence = 0.4 if description else 0.25

            if description:
                line_items.append(
                    ExtractedLineItem(
                        description=description[:300],
                        quantity=qty,
                        unit_price=unit_price,
                        line_total=line_total,
                        raw_line=raw_line[:500],
                        confidence=confidence,
                    )
                )

        # Deduplicate similar raw lines
        unique_items: List[ExtractedLineItem] = []
        seen = set()
        for item in line_items:
            key = (item.description.lower().strip(), item.line_total)
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)

        return unique_items

    @classmethod
    def _infer_total_from_detected_amounts(
        cls, detected_amounts: List[float], subtotal: Optional[float], vat: Optional[float]
    ) -> Tuple[Optional[float], List[str]]:
        notes: List[str] = []

        if subtotal is not None and vat is not None:
            return round(subtotal + vat, 2), notes

        if not detected_amounts:
            return None, notes

        # Use the largest plausible amount as fallback total
        candidate_total = max(detected_amounts)
        notes.append("Used largest detected amount as fallback total.")
        return candidate_total, notes

    @classmethod
    def _compute_confidence(
        cls,
        subtotal: Optional[float],
        vat: Optional[float],
        total: Optional[float],
        line_items: List[ExtractedLineItem],
        quotation_number: Optional[str],
        rfq_number: Optional[str],
    ) -> float:
        score = 0.0

        if total is not None:
            score += 0.40
        if subtotal is not None:
            score += 0.15
        if vat is not None:
            score += 0.10
        if line_items:
            score += min(0.20, 0.03 * len(line_items))
        if quotation_number:
            score += 0.08
        if rfq_number:
            score += 0.07

        return round(min(score, 0.99), 2)

    @classmethod
    def extract_prices_from_pdf(cls, pdf_path: str) -> Dict[str, Any]:
        text, extraction_method, notes = cls._extract_pdf_text(pdf_path)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        supplier_name = cls._extract_first_match(text, cls.SUPPLIER_NAME_PATTERNS)
        quotation_number = cls._extract_first_match(text, cls.QUOTATION_NUMBER_PATTERNS)
        rfq_number = cls._extract_first_match(text, cls.RFQ_NUMBER_PATTERNS)

        subtotal, vat, total_including_vat, labelled_notes = cls._best_amount_from_labelled_lines(lines)
        notes.extend(labelled_notes)

        detected_amounts = cls._all_detected_amounts(text)
        vat_rate = cls._extract_vat_rate(text)

        if total_including_vat is None:
            inferred_total, inference_notes = cls._infer_total_from_detected_amounts(
                detected_amounts=detected_amounts,
                subtotal=subtotal,
                vat=vat,
            )
            total_including_vat = inferred_total
            notes.extend(inference_notes)

        total_excluding_vat = subtotal
        if total_excluding_vat is None and total_including_vat is not None and vat is not None:
            total_excluding_vat = round(total_including_vat - vat, 2)

        if vat is None and total_including_vat is not None and total_excluding_vat is not None:
            vat = round(total_including_vat - total_excluding_vat, 2)

        if vat is None and total_including_vat is not None and total_excluding_vat is None and vat_rate:
            total_excluding_vat = round(total_including_vat / (1 + (vat_rate / 100.0)), 2)
            vat = round(total_including_vat - total_excluding_vat, 2)
            notes.append("Estimated VAT and subtotal from total and VAT rate.")

        line_items = cls._extract_line_items(lines)

        confidence = cls._compute_confidence(
            subtotal=total_excluding_vat,
            vat=vat,
            total=total_including_vat,
            line_items=line_items,
            quotation_number=quotation_number,
            rfq_number=rfq_number,
        )

        result = ExtractedPriceResult(
            source_pdf=str(pdf_path),
            supplier_name=supplier_name,
            currency=cls.CURRENCY_DEFAULT,
            subtotal=total_excluding_vat,
            vat=vat,
            total_including_vat=total_including_vat,
            total_excluding_vat=total_excluding_vat,
            vat_rate_percent=vat_rate,
            quotation_number=quotation_number,
            rfq_number=rfq_number,
            line_items=line_items,
            detected_amounts=detected_amounts[:50],
            confidence=confidence,
            extraction_method=extraction_method,
            notes=notes,
            raw_text_preview=text[:2000],
        )

        return {
            **asdict(result),
            "line_items": [asdict(item) for item in line_items],
        }

    @classmethod
    def extract_prices_from_folder(cls, folder_path: str) -> Dict[str, Any]:
        folder = Path(folder_path)
        if not folder.exists():
            raise SupplierPriceExtractionError(f"Folder not found: {folder_path}")

        pdf_files = sorted(folder.glob("supplier_quote_*.pdf"))
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for pdf_file in pdf_files:
            try:
                results.append(cls.extract_prices_from_pdf(str(pdf_file)))
            except Exception as exc:
                errors.append(
                    {
                        "pdf": str(pdf_file),
                        "error": str(exc),
                    }
                )

        return {
            "folder": str(folder),
            "processed_pdfs": len(results),
            "failed_pdfs": len(errors),
            "results": results,
            "errors": errors,
        }

    @classmethod
    def update_quote_comparison_json(cls, folder_path: str) -> Dict[str, Any]:
        folder = Path(folder_path)
        comparison_file = folder / "quote_comparison.json"

        if not comparison_file.exists():
            raise SupplierPriceExtractionError(
                f"quote_comparison.json not found in folder: {folder_path}"
            )

        existing = json.loads(comparison_file.read_text(encoding="utf-8"))
        extraction_result = cls.extract_prices_from_folder(folder_path)

        extracted_by_file = {
            Path(item["source_pdf"]).name: item
            for item in extraction_result.get("results", [])
        }

        suppliers = existing.get("suppliers") or []

        for supplier in suppliers:
            attachments = supplier.get("attachments") or []
            matched_extraction: Optional[Dict[str, Any]] = None

            for attachment in attachments:
                saved_path = attachment.get("saved_path", "")
                file_name = Path(saved_path).name
                if file_name in extracted_by_file:
                    matched_extraction = extracted_by_file[file_name]
                    break

            if matched_extraction:
                supplier["quoted_total"] = matched_extraction.get("total_including_vat")
                supplier["quoted_subtotal"] = matched_extraction.get("total_excluding_vat")
                supplier["vat_amount"] = matched_extraction.get("vat")
                supplier["vat_rate_percent"] = matched_extraction.get("vat_rate_percent")
                supplier["currency"] = matched_extraction.get("currency", "ZAR")
                supplier["quotation_number"] = matched_extraction.get("quotation_number")
                supplier["rfq_number"] = matched_extraction.get("rfq_number")
                supplier["line_items"] = matched_extraction.get("line_items", [])
                supplier["price_extraction_confidence"] = matched_extraction.get("confidence")
                supplier["price_extraction_method"] = matched_extraction.get("extraction_method")
                supplier["price_extraction_notes"] = matched_extraction.get("notes", [])

        valid_suppliers = [
            supplier for supplier in suppliers
            if supplier.get("quoted_total") is not None
        ]

        recommended_supplier = None
        if valid_suppliers:
            recommended_supplier = min(
                valid_suppliers,
                key=lambda supplier: float(supplier.get("quoted_total") or 0.0),
            ).get("email")

        existing["suppliers"] = suppliers
        existing["recommended_supplier"] = recommended_supplier
        existing["comparison_status"] = "prices_extracted"
        existing["price_extraction_summary"] = {
            "processed_pdfs": extraction_result.get("processed_pdfs", 0),
            "failed_pdfs": extraction_result.get("failed_pdfs", 0),
        }

        comparison_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "success": True,
            "folder": str(folder),
            "recommended_supplier": recommended_supplier,
            "comparison_file": str(comparison_file),
            "processed_pdfs": extraction_result.get("processed_pdfs", 0),
            "failed_pdfs": extraction_result.get("failed_pdfs", 0),
            "results": extraction_result.get("results", []),
            "errors": extraction_result.get("errors", []),
        }
