from __future__ import annotations

import json
import logging
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.persistence import jsonl_compat

logger = logging.getLogger(__name__)

try:
    from app.services.universal_form_filler import (
        UniversalFormFiller,
        build_lmcp_default_form_data,
    )
except Exception:  # pragma: no cover
    UniversalFormFiller = None  # type: ignore
    build_lmcp_default_form_data = None  # type: ignore


DIRECTOR_SIGNATURE_PATH = "app/assets/signatures/Director.png"
WITNESS_1_SIGNATURE_PATH = "app/assets/signatures/Witness_1.png"
WITNESS_2_SIGNATURE_PATH = "app/assets/signatures/Witness_2.png"

FORM_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm"}
QUOTE_BLOCK_TOKENS = (
    "quote",
    "quotation",
    "proforma",
    "invoice",
    "tax-invoice",
    "tax_invoice",
)
DEFAULT_ESTIMATED_MARGIN_RATE = float(
    str(os.getenv("DEFAULT_ESTIMATED_MARGIN_RATE", "0.25")).strip() or "0.25"
)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        cleaned = (
            str(value)
            .replace("R", "")
            .replace("ZAR", "")
            .replace("zar", "")
            .replace(",", "")
            .strip()
        )
        return float(cleaned)
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_filename_part(value: str, default: str = "UNKNOWN", max_len: int = 80) -> str:
    text = _safe_str(value, default)

    # Decode common HTML entities and normalize known noisy tender text artifacts.
    text = (
        text.replace("&amp;", "and")
        .replace("&#8211;", "-")
        .replace("&nbsp;", " ")
        .replace("\xa0", " ")
    )

    cleaned = "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "-"
        for ch in text
    ).strip("-._")

    if not cleaned:
        cleaned = default

    # Hard-cap filename/path component length to prevent quote pack generation
    # failures on very long RFQ titles and document references.
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip("-._")

    return cleaned or default


def _dedupe_strings(values: List[Any]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values:
        text = _safe_str(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


class QuotePackService:
    DEFAULT_VAT_RATE = 0.15

    @classmethod
    def _normalize_item_row(cls, item: Dict[str, Any], idx: int) -> Dict[str, Any]:
        quantity = _to_float(item.get("quantity") or item.get("qty") or 1, 1.0)
        if quantity <= 0:
            quantity = 1.0

        description = _safe_str(
            item.get("description")
            or item.get("item_description")
            or item.get("name")
            or f"Item {idx}"
        )
        unit = _safe_str(
            item.get("unit")
            or item.get("uom")
            or item.get("unit_of_measure")
            or "Each"
        )
        item_code = _safe_str(item.get("item_code") or item.get("code"))

        unit_price = _to_float(
            item.get("unit_price")
            or item.get("rate_excl_vat")
            or item.get("selling_unit_price_excl_vat")
            or item.get("price")
            or item.get("rate")
            or 0,
            0.0,
        )

        line_total = _to_float(
            item.get("line_total")
            or item.get("amount_excl_vat")
            or item.get("line_total_excl_vat")
            or item.get("amount")
            or 0,
            0.0,
        )

        vat_amount = _to_float(item.get("vat_amount"), 0.0)
        amount_incl_vat = _to_float(
            item.get("amount_incl_vat")
            or item.get("line_total_incl_vat")
            or 0,
            0.0,
        )

        if line_total <= 0 and unit_price > 0:
            line_total = round(unit_price * quantity, 2)
        if unit_price <= 0 and line_total > 0 and quantity > 0:
            unit_price = round(line_total / quantity, 2)
        if amount_incl_vat <= 0 and line_total > 0:
            amount_incl_vat = round(line_total + vat_amount, 2)

        return {
            "line_number": _safe_str(item.get("line_number") or item.get("row_no") or idx),
            "description": description,
            "item_code": item_code,
            "unit": unit,
            "quantity": round(quantity, 2),
            "unit_price": round(unit_price, 2),
            "line_total": round(line_total, 2),
            "vat_amount": round(vat_amount, 2),
            "amount_incl_vat": round(amount_incl_vat, 2),
            "source": _safe_str(item.get("source")),
            "quote_reference": _safe_str(item.get("quote_reference")),
        }

    @classmethod
    def _normalize_buyer_schedule(cls, buyer_schedule: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx, row in enumerate(buyer_schedule or [], start=1):
            if not isinstance(row, dict):
                continue
            rows.append(
                cls._normalize_item_row(
                    {
                        "line_number": row.get("row_no") or idx,
                        "description": row.get("description"),
                        "item_code": row.get("item_code"),
                        "unit": row.get("unit"),
                        "quantity": row.get("quantity"),
                        "unit_price": row.get("rate_excl_vat"),
                        "line_total": row.get("amount_excl_vat"),
                        "vat_amount": row.get("vat_amount"),
                        "amount_incl_vat": row.get("amount_incl_vat"),
                        "source": row.get("source"),
                        "quote_reference": row.get("quote_reference"),
                    },
                    idx,
                )
            )
        return rows

    @classmethod
    def _extract_best_items(cls, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        pricing_result = payload.get("pricing_result") or {}
        buyer_schedule = pricing_result.get("buyer_schedule") or payload.get("buyer_schedule") or []

        if isinstance(buyer_schedule, list) and buyer_schedule:
            return cls._normalize_buyer_schedule(buyer_schedule)

        for key in ("items", "line_items", "buyer_pricing_schedule", "pricing_schedule_items", "pricing_schedule"):
            values = payload.get(key)
            if isinstance(values, list) and values:
                normalized = [
                    cls._normalize_item_row(item, idx)
                    for idx, item in enumerate(values, start=1)
                    if isinstance(item, dict)
                ]
                if normalized:
                    return normalized

        title = _safe_str(payload.get("title") or payload.get("description") or "Supply and delivery item")
        return [
            {
                "line_number": "1",
                "description": title,
                "item_code": "",
                "unit": "Each",
                "quantity": 1.0,
                "unit_price": 0.0,
                "line_total": 0.0,
                "vat_amount": 0.0,
                "amount_incl_vat": 0.0,
                "source": "",
                "quote_reference": "",
            }
        ]

    @classmethod
    def _extract_totals(cls, payload: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, float]:
        pricing_summary = payload.get("pricing_summary") or {}
        if isinstance(pricing_summary, dict) and pricing_summary:
            subtotal = _to_float(pricing_summary.get("total_sell_excl_vat"), 0.0)
            vat_amount = _to_float(pricing_summary.get("total_vat"), 0.0)
            total_incl = _to_float(pricing_summary.get("total_sell_incl_vat"), 0.0)
            if subtotal > 0 or total_incl > 0:
                return {
                    "subtotal_excl_vat": round(subtotal, 2),
                    "vat_amount": round(vat_amount, 2),
                    "total_incl_vat": round(total_incl, 2),
                }

        subtotal = round(sum(_to_float(item.get("line_total"), 0.0) for item in items), 2)
        vat_amount = round(sum(_to_float(item.get("vat_amount"), 0.0) for item in items), 2)
        if vat_amount <= 0 and subtotal > 0:
            vat_amount = round(subtotal * cls.DEFAULT_VAT_RATE, 2)
        total_incl = round(subtotal + vat_amount, 2)

        return {
            "subtotal_excl_vat": subtotal,
            "vat_amount": vat_amount,
            "total_incl_vat": total_incl,
        }

    @classmethod
    def _build_financials(cls, payload: Dict[str, Any], totals: Dict[str, float]) -> Dict[str, float]:
        estimated_revenue = _to_float(
            payload.get("estimated_revenue")
            or payload.get("quotation_total")
            or payload.get("grand_total")
            or payload.get("total_including_vat")
            or totals.get("total_incl_vat"),
            0.0,
        )
        if estimated_revenue <= 0:
            estimated_revenue = _to_float(totals.get("total_incl_vat"), 0.0)

        estimated_cost = _to_float(payload.get("estimated_cost"), 0.0)
        estimated_profit = _to_float(payload.get("estimated_profit"), 0.0)
        estimated_margin = _to_float(payload.get("estimated_margin"), 0.0)

        default_margin = DEFAULT_ESTIMATED_MARGIN_RATE if DEFAULT_ESTIMATED_MARGIN_RATE > 0 else 0.25

        if estimated_cost <= 0 and estimated_profit > 0 and estimated_revenue > 0:
            estimated_cost = max(0.0, estimated_revenue - estimated_profit)

        if estimated_profit <= 0 and estimated_cost > 0 and estimated_revenue > 0:
            estimated_profit = max(0.0, estimated_revenue - estimated_cost)

        if estimated_cost <= 0 and estimated_profit <= 0 and estimated_revenue > 0:
            estimated_cost = round(estimated_revenue / (1.0 + default_margin), 2)
            estimated_profit = round(estimated_revenue - estimated_cost, 2)

        if estimated_margin <= 0 and estimated_revenue > 0 and estimated_profit > 0:
            estimated_margin = estimated_profit / estimated_revenue

        return {
            "estimated_revenue": round(estimated_revenue, 2),
            "estimated_cost": round(estimated_cost, 2),
            "estimated_profit": round(estimated_profit, 2),
            "estimated_margin": round(estimated_margin, 4),
        }

    @classmethod
    def _build_output_dir(cls, payload: Dict[str, Any]) -> Path:
        quote_folder = _safe_str(payload.get("quote_folder") or payload.get("monthly_quote_folder"))
        if quote_folder:
            return Path(quote_folder)

        base_dir = Path("/app") if Path("/app").exists() else Path(".")
        buyer_rfq_number = _safe_str(
            payload.get("_locked_buyer_rfq_number")
            or payload.get("buyer_rfq_number")
            or payload.get("rfq_number")
            or "RFQ-UNKNOWN"
        )
        quote_number = _safe_str(payload.get("quote_number") or f"LMCP-{buyer_rfq_number}")
        month_folder = datetime.utcnow().strftime("%Y-%m")
        safe_rfq = _sanitize_filename_part(buyer_rfq_number, "RFQ-UNKNOWN")
        safe_quote = _sanitize_filename_part(quote_number, "LMCP-RFQ-UNKNOWN")
        return base_dir / "monthly_quotes" / month_folder / f"{safe_rfq}__{safe_quote}"

    @classmethod
    def _write_minimal_pdf(cls, pdf_path: Path, payload: Dict[str, Any], items: List[Dict[str, Any]], totals: Dict[str, float]) -> None:
        buyer_name = _safe_str(payload.get("buyer_name"), "Buyer / Issuing Entity")
        quote_number = _safe_str(payload.get("quote_number"), "LMCP-QUOTE")
        buyer_rfq_number = _safe_str(
            payload.get("_locked_buyer_rfq_number")
            or payload.get("buyer_rfq_number")
            or payload.get("rfq_number"),
            "RFQ-UNKNOWN",
        )
        title = _safe_str(payload.get("title"), "Supply and delivery item")

        lines = [
            "LECHESA MANABA CONSULTING AND PROJECTS (PTY) LTD",
            "QUOTATION",
            "",
            f"Quote Number: {quote_number}",
            f"Buyer RFQ Number: {buyer_rfq_number}",
            f"Buyer / Issuing Entity: {buyer_name}",
            f"Quotation Title: {title}",
            "",
            "Items:",
        ]

        for item in items:
            lines.append(
                f"{item['line_number']}. {item['description']} | "
                f"Qty: {item['quantity']:.2f} {item['unit']} | "
                f"Rate Excl VAT: R {item['unit_price']:,.2f} | "
                f"Amount Excl VAT: R {item['line_total']:,.2f}"
            )

        lines.extend(
            [
                "",
                f"Subtotal Excl VAT: R {totals['subtotal_excl_vat']:,.2f}",
                f"VAT: R {totals['vat_amount']:,.2f}",
                f"Total Incl VAT: R {totals['total_incl_vat']:,.2f}",
                "",
                "This quote is valid for 30 days from the date issued.",
                "For queries please contact us at 0826338492 or lechesam@me.com",
                "Prepared by Lechesa Manaba Consulting and Projects (Pty) Ltd",
            ]
        )

        safe_lines: List[str] = []
        for line in lines:
            text = _safe_str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            safe_lines.append(text)

        content_lines = ["BT", "/F1 11 Tf", "50 780 Td"]
        first = True
        for line in safe_lines:
            if first:
                content_lines.append(f"({line}) Tj")
                first = False
            else:
                content_lines.append("0 -16 Td")
                content_lines.append(f"({line}) Tj")
        content_lines.append("ET")

        stream = "\n".join(content_lines).encode("latin-1", errors="replace")

        objects: List[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )

        pdf = bytearray()
        pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{i} 0 obj\n".encode("latin-1"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")

        xref_pos = len(pdf)
        pdf.extend(f"xref\n0 {len(objects)+1}\n".encode("latin-1"))
        pdf.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

        pdf.extend(
            (
                f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n"
            ).encode("latin-1")
        )

        pdf_path.write_bytes(pdf)

    @classmethod
    def _is_fillable_form_document(cls, path_value: Any) -> bool:
        path_text = _safe_str(path_value)
        if not path_text:
            return False

        path = Path(path_text)
        ext = path.suffix.lower()
        if ext not in FORM_EXTENSIONS:
            return False

        name = path.name.lower()
        if any(token in name for token in QUOTE_BLOCK_TOKENS):
            return False

        return os.path.exists(path_text)

    @classmethod
    def _append_candidate_path(cls, bucket: List[str], value: Any) -> None:
        if isinstance(value, str):
            text = _safe_str(value)
            if text:
                bucket.append(text)
            return

        if isinstance(value, dict):
            for key in ("local_path", "path", "file_path", "output_path", "input_path"):
                maybe = _safe_str(value.get(key))
                if maybe:
                    bucket.append(maybe)
                    break

    @classmethod
    def _collect_form_documents(cls, payload: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []

        for key in (
            "supporting_documents",
            "documents",
            "attachments",
            "submission_attachments",
            "buyer_documents",
            "rfq_documents",
            "downloaded_files",
            "form_documents",
        ):
            raw = payload.get(key)
            if isinstance(raw, list):
                for item in raw:
                    cls._append_candidate_path(candidates, item)

        pricing_result = payload.get("pricing_result") or {}
        if isinstance(pricing_result, dict):
            for key in ("supporting_documents", "documents", "attachments", "downloaded_files"):
                raw = pricing_result.get(key)
                if isinstance(raw, list):
                    for item in raw:
                        cls._append_candidate_path(candidates, item)

        filtered = [item for item in candidates if cls._is_fillable_form_document(item)]
        return _dedupe_strings(filtered)

    @classmethod
    def _build_form_fill_data(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if build_lmcp_default_form_data is None:
            return {}

        tender_data: Dict[str, Any] = {
            "date_signed": _safe_str(payload.get("date_signed") or payload.get("submission_date") or datetime.utcnow().strftime("%Y-%m-%d")),
            "rfq_number": _safe_str(
                payload.get("_locked_buyer_rfq_number")
                or payload.get("buyer_rfq_number")
                or payload.get("rfq_number")
            ),
            "client_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "name_of_bidder": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "bidder_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "surname_and_name": "Lechesa Manaba",
            "capacity": "Director",
            "designation": "Director",
            "position": "Director",
            "address": "Bloemfontein, Free State, South Africa",
            "street_address": "Bloemfontein, Free State, South Africa",
            "postal_address": "Bloemfontein, Free State, South Africa",
            "telephone": "0826338492",
            "phone": "0826338492",
            "cellphone_number": "0826338492",
            "email": "lechesam@me.com",
            "email_address": "lechesam@me.com",
            "signed_place": "BLOEMFONTEIN",
            "witness_1_name": "Nobuhle Cath",
            "witness_2_name": "Charlie Champion Moeng",
            "tcs_pin": _safe_str(payload.get("tcs_pin")),
            "csd_number": _safe_str(payload.get("csd_number")),
        }

        if isinstance(payload.get("form_fill_data"), dict):
            tender_data.update(payload["form_fill_data"])

        return build_lmcp_default_form_data(tender_data=tender_data)

    @classmethod
    def _fill_and_attach_supporting_forms(cls, quote_pack_result: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(quote_pack_result)

        if UniversalFormFiller is None or build_lmcp_default_form_data is None:
            result["form_fill_status"] = "unavailable"
            result["filled_form_outputs"] = []
            result["filled_form_pdfs"] = []
            result["filled_form_results"] = []
            return result

        form_paths = cls._collect_form_documents(result)
        if not form_paths:
            result["form_fill_status"] = "no_forms_found"
            result["filled_form_outputs"] = []
            result["filled_form_pdfs"] = []
            result["filled_form_results"] = []
            return result

        filler = UniversalFormFiller()
        form_data = cls._build_form_fill_data(result)

        filled_form_outputs: List[str] = []
        filled_form_pdfs: List[str] = []
        filled_form_results: List[Dict[str, Any]] = []

        for form_path in form_paths:
            try:
                fill_result = filler.fill_form(
                    input_path=form_path,
                    data=form_data,
                    signature_path=DIRECTOR_SIGNATURE_PATH,
                    witness_1_signature_path=WITNESS_1_SIGNATURE_PATH,
                    witness_2_signature_path=WITNESS_2_SIGNATURE_PATH,
                    enable_handwriting=False,
                    convert_to_pdf=True,
                )

                output_path = _safe_str(fill_result.get("output_path"))
                output_pdf_path = _safe_str(fill_result.get("output_pdf_path"))

                if output_path:
                    filled_form_outputs.append(output_path)
                if output_pdf_path:
                    filled_form_pdfs.append(output_pdf_path)

                filled_form_results.append(
                    {
                        "input_path": form_path,
                        "status": _safe_str(fill_result.get("status"), "unknown"),
                        "output_path": output_path,
                        "output_pdf_path": output_pdf_path,
                        "text_fill_count": fill_result.get("text_fill_count", 0),
                        "director_detected_count": fill_result.get("director_detected_count", 0),
                        "witness_1_detected_count": fill_result.get("witness_1_detected_count", 0),
                        "witness_2_detected_count": fill_result.get("witness_2_detected_count", 0),
                        "director_stamped_count": fill_result.get("director_stamped_count", 0),
                        "witness_1_stamped_count": fill_result.get("witness_1_stamped_count", 0),
                        "witness_2_stamped_count": fill_result.get("witness_2_stamped_count", 0),
                    }
                )
            except Exception as exc:
                logger.exception("Form fill failed for %s: %s", form_path, exc)
                filled_form_results.append(
                    {
                        "input_path": form_path,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        result["form_fill_status"] = "completed"
        result["filled_form_outputs"] = _dedupe_strings(filled_form_outputs)
        result["filled_form_pdfs"] = _dedupe_strings(filled_form_pdfs)
        result["filled_form_results"] = filled_form_results
        result["supporting_documents"] = _dedupe_strings(
            (result.get("supporting_documents") if isinstance(result.get("supporting_documents"), list) else [])
            + result["filled_form_outputs"]
            + result["filled_form_pdfs"]
        )
        result["submission_attachments"] = _dedupe_strings(
            (result.get("submission_attachments") if isinstance(result.get("submission_attachments"), list) else [])
            + result["filled_form_outputs"]
            + result["filled_form_pdfs"]
        )
        return result

    @classmethod
    def generate_quote_pack(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = deepcopy(payload if isinstance(payload, dict) else {})
        items = cls._extract_best_items(source)
        totals = cls._extract_totals(source, items)
        financials = cls._build_financials(source, totals)

        buyer_schedule = source.get("pricing_result", {}).get("buyer_schedule") or source.get("buyer_schedule") or []
        normalized_buyer_schedule = cls._normalize_buyer_schedule(buyer_schedule) if buyer_schedule else deepcopy(items)

        output_dir = cls._build_output_dir(source)
        output_dir.mkdir(parents=True, exist_ok=True)

        buyer_rfq_number = _safe_str(
            source.get("_locked_buyer_rfq_number")
            or source.get("buyer_rfq_number")
            or source.get("rfq_number")
            or "RFQ-UNKNOWN"
        )
        quote_number = _safe_str(source.get("quote_number") or f"LMCP-{buyer_rfq_number}")
        safe_pdf_name = f"{_sanitize_filename_part(buyer_rfq_number)}__{_sanitize_filename_part(quote_number)}.pdf"
        pdf_path = output_dir / safe_pdf_name

        metadata_path = output_dir / f"{_sanitize_filename_part(buyer_rfq_number)}__{_sanitize_filename_part(quote_number)}__quote_pack.json"

        cls._write_minimal_pdf(pdf_path, source, items, totals)

        quote_pack_result: Dict[str, Any] = deepcopy(source)
        quote_pack_result["quote_generated"] = True
        quote_pack_result["pdf_generated"] = True
        quote_pack_result["pdf_path"] = str(pdf_path)
        quote_pack_result["final_pdf_path"] = str(pdf_path)
        quote_pack_result["quote_pack_metadata_path"] = str(metadata_path)
        quote_pack_result["quote_pack_dir"] = str(output_dir)
        quote_pack_result["quote_folder"] = str(output_dir)
        quote_pack_result["monthly_quote_folder"] = str(output_dir)
        quote_pack_result["pricing_schedule_source"] = "pricing_engine" if source.get("pricing_result") else "payload"
        quote_pack_result["buyer_schedule"] = deepcopy(normalized_buyer_schedule)
        quote_pack_result["buyer_pricing_schedule"] = deepcopy(normalized_buyer_schedule)
        quote_pack_result["items"] = deepcopy(items)
        quote_pack_result["line_items"] = deepcopy(items)
        quote_pack_result["totals"] = {
            **deepcopy(totals),
            **financials,
        }
        quote_pack_result["financials"] = deepcopy(financials)
        quote_pack_result["estimated_revenue"] = financials["estimated_revenue"]
        quote_pack_result["estimated_cost"] = financials["estimated_cost"]
        quote_pack_result["estimated_profit"] = financials["estimated_profit"]
        quote_pack_result["estimated_margin"] = financials["estimated_margin"]
        quote_pack_result["subtotal"] = totals["subtotal_excl_vat"]
        quote_pack_result["vat_amount"] = totals["vat_amount"]
        quote_pack_result["grand_total"] = totals["total_incl_vat"]
        quote_pack_result["quotation_total"] = totals["total_incl_vat"]
        quote_pack_result["supporting_documents"] = _dedupe_strings(
            quote_pack_result.get("supporting_documents") if isinstance(quote_pack_result.get("supporting_documents"), list) else []
        )
        quote_pack_result["submission_attachments"] = _dedupe_strings(
            ([str(pdf_path)] + (
                quote_pack_result.get("submission_attachments")
                if isinstance(quote_pack_result.get("submission_attachments"), list)
                else []
            ))
        )

        quote_pack_result = cls._fill_and_attach_supporting_forms(quote_pack_result)

        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "generated_at": _now_iso(),
                    "quote_number": quote_number,
                    "buyer_rfq_number": buyer_rfq_number,
                    "buyer_name": _safe_str(source.get("buyer_name")),
                    "title": _safe_str(source.get("title")),
                    "items": items,
                    "buyer_schedule": normalized_buyer_schedule,
                    "totals": {
                        **totals,
                        **financials,
                    },
                    "financials": financials,
                    "estimated_revenue": financials["estimated_revenue"],
                    "estimated_cost": financials["estimated_cost"],
                    "estimated_profit": financials["estimated_profit"],
                    "estimated_margin": financials["estimated_margin"],
                    "pdf_path": str(pdf_path),
                    "supporting_documents": quote_pack_result["supporting_documents"],
                    "submission_attachments": quote_pack_result["submission_attachments"],
                    "form_fill_status": quote_pack_result.get("form_fill_status"),
                    "filled_form_outputs": quote_pack_result.get("filled_form_outputs", []),
                    "filled_form_pdfs": quote_pack_result.get("filled_form_pdfs", []),
                    "filled_form_results": quote_pack_result.get("filled_form_results", []),
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )

        jsonl_compat.persist_quote_pack(
            {
                "tender_id": _safe_str(source.get("tender_id") or buyer_rfq_number),
                "workflow_stage": "quote_generated",
                "actor": _safe_str(source.get("operator_name") or source.get("actor")),
                "operator": _safe_str(source.get("operator_name") or source.get("actor")),
                "payload": {
                    "quote_number": quote_number,
                    "buyer_rfq_number": buyer_rfq_number,
                    "pdf_path": str(pdf_path),
                    "quote_pack_dir": str(output_dir),
                    "subtotal": totals["subtotal_excl_vat"],
                    "vat_amount": totals["vat_amount"],
                    "grand_total": totals["total_incl_vat"],
                    "items": items,
                },
            }
        )

        return quote_pack_result


def generate_quote_pack(payload: Dict[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    return QuotePackService.generate_quote_pack(payload)



