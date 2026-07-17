from __future__ import annotations

from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import re


REQUIREMENT_PACK_VERSION = "RFQ_REQUIREMENT_PACK_V1"

SOURCE_PRIORITY = {
    "formal_buyer_pricing_schedule": 100,
    "buyer_returnable_pricing_form": 95,
    "standalone_boq": 90,
    "embedded_pricing_schedule": 85,
    "spreadsheet_pricing_schedule": 80,
    "specification_table": 70,
    "main_document_table": 60,
    "portal_structured_items": 55,
    "manual_verified_rows": 50,
    "unknown_buyer_table": 10,
}

SOURCE_TYPES = set(SOURCE_PRIORITY)

LINE_NUMBER_KEYS = ("buyer_line_number", "line_number", "line_no", "item_no", "item_number", "number", "row_no")
LINE_INDEX_KEYS = ("buyer_line_index", "line_index", "row_index", "source_row_index")
MATERIAL_KEYS = ("material", "material_no", "material_number")
ITEM_CODE_KEYS = ("item_code", "code", "stock_code")
PART_NUMBER_KEYS = ("part_no", "part_number")
DESCRIPTION_KEYS = ("description", "item_description", "product_description")
SPECIFICATION_KEYS = ("specification", "spec")
QUANTITY_KEYS = ("quantity", "qty")
UNIT_KEYS = ("unit", "uom", "unit_of_measure")
BUYER_RATE_KEYS = ("buyer_rate", "rate", "unit_rate", "unit_price", "price", "unit_price_excl_vat")
BUYER_AMOUNT_KEYS = ("buyer_amount", "amount", "total", "total_price", "line_total", "total_incl_vat", "total_excl_vat")
BRAND_KEYS = ("brand", "brand_name", "brand_required")

NON_ITEM_TERMS = (
    "subtotal",
    "sub total",
    "grand total",
    "total price",
    "total amount",
    "vat",
    "signature",
    "name of bidder",
    "company name",
    "official stamp",
    "contact information",
    "declaration",
    "sbd",
    "tax compliance",
    "central supplier database",
)

HEADER_TERMS = ("description", "quantity", "unit price", "total price", "amount")
LUMP_SUM_TERMS = ("lump sum", "lumpsum", "ls", "lot")
TRANSPORT_TERMS = ("transport", "delivery charge", "freight", "courier")
DATASHEET_TERMS = ("datasheet", "data sheet", "manufacturer datasheet", "manufacturer's datasheet")
BRAND_TERMS = ("brand name", "brand offered", "specific brand", "brand required")
SAMPLE_TERMS = ("sample", "samples may be required", "sample may be required")
STANDARD_PATTERN = re.compile(r"\b(?:SANS|ISO)\s*[A-Z0-9:/._-]+\b", flags=re.I)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).replace("\x00", " ").strip()
    except Exception:
        return ""


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_str(value)).strip()


def _safe_lower(value: Any) -> str:
    return _clean_text(value).lower()


def _first_value(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _safe_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _safe_str(value)
    if not text:
        return None
    text = text.replace(",", "")
    text = re.sub(r"^(?:R|ZAR)\s*", "", text, flags=re.I)
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    try:
        return float(text)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    number = _safe_number(value)
    if number is None:
        return None
    try:
        return int(number)
    except Exception:
        return None


def _normalise_source_type(source_type: Any) -> str:
    source = _safe_lower(source_type).replace("-", "_").replace(" ", "_")
    if source in SOURCE_TYPES:
        return source
    if "formal" in source and "pricing" in source:
        return "formal_buyer_pricing_schedule"
    if "returnable" in source and "pricing" in source:
        return "buyer_returnable_pricing_form"
    if "specification" in source:
        return "specification_table"
    if "pricing" in source or "schedule" in source:
        return "embedded_pricing_schedule"
    if "docx" in source or "main_document" in source:
        return "main_document_table"
    if "spreadsheet" in source or "xlsx" in source or "csv" in source:
        return "spreadsheet_pricing_schedule"
    if "portal" in source:
        return "portal_structured_items"
    if "manual" in source:
        return "manual_verified_rows"
    if "boq" in source or "bill_of_quantities" in source:
        return "standalone_boq"
    return "unknown_buyer_table"


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_lower(value) in {"1", "true", "yes", "y", "required", "compulsory"}


def _normalize_description(value: str) -> str:
    text = _safe_lower(value)
    text = re.sub(r"\b(?:brand name offered|brand offered|unit price|total price|price quoted excl\.? of vat)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _standards(*values: Any) -> List[str]:
    hits: List[str] = []
    for value in values:
        hits.extend(match.group(0).upper().replace("  ", " ") for match in STANDARD_PATTERN.finditer(_safe_str(value)))
    return _dedupe_strings(hits)


def _commercial_flags(row: Dict[str, Any], description: str, specification: str, unit: str) -> Dict[str, bool]:
    marker = _safe_lower(" ".join([
        description,
        specification,
        unit,
        _safe_str(row.get("line_type")),
        _safe_str(row.get("basis")),
        _safe_str(row.get("pricing_basis")),
    ]))
    return {
        "optional": "optional" in marker,
        "alternative": "alternative" in marker,
        "provisional": "provisional" in marker,
        "lump_sum": any(re.search(rf"\b{re.escape(term)}\b", marker) for term in LUMP_SUM_TERMS),
        "transport": any(term in marker for term in TRANSPORT_TERMS),
    }


def _is_non_item(description: str, specification: str, row: Dict[str, Any]) -> bool:
    material = _clean_text(_first_value(row, MATERIAL_KEYS))
    part_number = _clean_text(_first_value(row, PART_NUMBER_KEYS))
    blob = _safe_lower(" ".join([description, specification, material, part_number]))
    if not blob:
        return True
    if any(term in blob for term in NON_ITEM_TERMS):
        return True
    if all(term in blob for term in HEADER_TERMS) and len(blob) < 140:
        return True
    return False


def _evidence(row: Dict[str, Any], extra_evidence: Optional[Iterable[Any]] = None) -> List[str]:
    evidence: List[str] = []
    raw = row.get("evidence")
    if isinstance(raw, list):
        evidence.extend(_clean_text(v) for v in raw if _clean_text(v))
    elif raw:
        evidence.append(_clean_text(raw))
    for key in ("reason", "raw_text"):
        value = _clean_text(row.get(key))
        if value:
            evidence.append(value[:500])
    if extra_evidence:
        evidence.extend(_clean_text(v) for v in extra_evidence if _clean_text(v))
    return _dedupe_strings(evidence)


def _stable_requirement_id(
    reference_number: str,
    source_document: str,
    source_page: Any,
    source_table: Any,
    source_row: Any,
    buyer_line_index: Any,
    material_number: str,
    part_number: str,
    description: str,
    quantity: Any,
) -> str:
    basis = "|".join(
        _safe_str(v)
        for v in (
            reference_number,
            source_document,
            source_page,
            source_table,
            source_row,
            buyer_line_index,
            material_number,
            part_number,
            description,
            quantity,
        )
    )
    return "REQ-" + sha256(basis.encode("utf-8")).hexdigest()[:16]


def normalize_requirement_row(
    row: Dict[str, Any],
    source_type: str = "unknown_buyer_table",
    source_document: str = "",
    source_page: Any = None,
    source_table: Any = None,
    default_confidence: float = 0.0,
    evidence: Optional[Iterable[Any]] = None,
    reference_number: str = "",
    buyer_line_index: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        return None

    description = _clean_text(_first_value(row, DESCRIPTION_KEYS))
    specification = _clean_text(_first_value(row, SPECIFICATION_KEYS))
    material_number = _clean_text(_first_value(row, MATERIAL_KEYS))
    part_number = _clean_text(_first_value(row, PART_NUMBER_KEYS))
    if not description and specification:
        description = specification

    if _is_non_item(description, specification, row):
        return None

    quantity = _safe_number(_first_value(row, QUANTITY_KEYS))
    unit = _clean_text(_first_value(row, UNIT_KEYS))
    item_code = _clean_text(_first_value(row, ITEM_CODE_KEYS))
    buyer_line_number = _clean_text(_first_value(row, LINE_NUMBER_KEYS))
    if buyer_line_index is None:
        buyer_line_index = _safe_int(_first_value(row, LINE_INDEX_KEYS))
    buyer_rate = _safe_number(_first_value(row, BUYER_RATE_KEYS))
    buyer_amount = _safe_number(_first_value(row, BUYER_AMOUNT_KEYS))
    confidence = _safe_number(row.get("confidence"))
    if confidence is None:
        confidence = default_confidence

    if not source_document:
        source_document = _clean_text(row.get("source_document") or row.get("document_path") or row.get("input_pdf"))
    if source_page is None:
        source_page = row.get("source_page") if row.get("source_page") is not None else row.get("page")
    if source_table is None:
        source_table = row.get("source_table") if row.get("source_table") is not None else row.get("source")
    source_row = row.get("source_row")
    if source_row is None:
        source_row = row.get("row_index")

    source = _normalise_source_type(row.get("source_type") or source_type or row.get("source"))
    flags = _commercial_flags(row, description, specification, unit)
    if flags["lump_sum"] and not unit:
        unit = "lump sum"

    brand_text = _safe_lower(" ".join([_safe_str(_first_value(row, BRAND_KEYS)), description, specification]))
    brand_required = _as_bool(row.get("brand_required")) or any(term in brand_text for term in BRAND_TERMS)
    datasheet_required = _as_bool(row.get("datasheet_required")) or any(term in brand_text for term in DATASHEET_TERMS)
    sample_may_be_required = _as_bool(row.get("sample_may_be_required")) or any(term in brand_text for term in SAMPLE_TERMS)
    standards = _dedupe_strings((row.get("standards") or []) if isinstance(row.get("standards"), list) else [])
    standards = _dedupe_strings(standards + _standards(description, specification, row.get("raw_text")))

    verified = bool(
        (description or specification or material_number or part_number)
        and ((quantity is not None and quantity > 0 and unit) or flags["lump_sum"])
    )

    review_reasons: List[str] = []
    if quantity is None and not flags["lump_sum"]:
        review_reasons.append("missing_quantity")
    if not unit and not flags["lump_sum"]:
        review_reasons.append("missing_unit")
    if confidence < 0.5:
        review_reasons.append("low_confidence")

    row_evidence = _evidence(row, evidence)
    if quantity is not None and quantity > 0:
        row_evidence.append("quantity_present")
    if unit:
        row_evidence.append("unit_present")
    if flags["lump_sum"]:
        row_evidence.append("lump_sum_basis")
    if brand_required:
        row_evidence.append("brand_required")
    if datasheet_required:
        row_evidence.append("datasheet_required")

    requirement_row_id = _clean_text(row.get("requirement_row_id")) or _stable_requirement_id(
        reference_number,
        source_document,
        source_page,
        source_table,
        source_row,
        buyer_line_index,
        material_number,
        part_number,
        description,
        quantity,
    )

    return {
        "requirement_row_id": requirement_row_id,
        "buyer_line_index": buyer_line_index,
        "buyer_line_number": buyer_line_number,
        "line_number": buyer_line_number,
        "material_number": material_number,
        "item_code": item_code,
        "part_number": part_number,
        "description": description,
        "normalized_description": _normalize_description(description or specification),
        "specification": specification if specification != description else "",
        "quantity": quantity,
        "unit": unit,
        "brand_required": brand_required,
        "datasheet_required": datasheet_required,
        "sample_may_be_required": sample_may_be_required,
        "standards": standards,
        "buyer_rate": buyer_rate,
        "buyer_amount": buyer_amount,
        "source_type": source,
        "source_document": source_document,
        "source_page": source_page,
        "source_table": source_table,
        "source_row": source_row,
        "source_priority": int(SOURCE_PRIORITY.get(source, 0)),
        "confidence": round(float(confidence or 0.0), 4),
        "review_required": not verified,
        "review_reasons": _dedupe_strings(review_reasons),
        "review_flags": _dedupe_strings(review_reasons),
        "evidence": _dedupe_strings(row_evidence),
        "commercial_flags": flags,
    }


def _physical_duplicate_key(row: Dict[str, Any]) -> Optional[Tuple[str, str, str, str, str, str, str]]:
    source_document = _safe_str(row.get("source_document"))
    source_page = _safe_str(row.get("source_page"))
    source_table = _safe_str(row.get("source_table"))
    source_row = _safe_str(row.get("source_row"))
    if not (source_document and source_table and source_row):
        return None
    return (
        source_document,
        source_page,
        source_table,
        source_row,
        _safe_lower(row.get("material_number") or row.get("part_number") or row.get("item_code")),
        _safe_lower(row.get("description"))[:160],
        _safe_str(row.get("quantity")),
    )


def normalize_requirement_rows(
    rows: Iterable[Dict[str, Any]],
    source_type: str = "unknown_buyer_table",
    source_document: str = "",
    default_confidence: float = 0.0,
    evidence: Optional[Iterable[Any]] = None,
    reference_number: str = "",
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen_physical = set()
    for index, row in enumerate(rows or [], start=1):
        clean = normalize_requirement_row(
            row,
            source_type=source_type,
            source_document=source_document,
            default_confidence=default_confidence,
            evidence=evidence,
            reference_number=reference_number,
            buyer_line_index=index,
        )
        if not clean:
            continue
        duplicate_key = _physical_duplicate_key(clean)
        if duplicate_key is not None:
            if duplicate_key in seen_physical:
                continue
            seen_physical.add(duplicate_key)
        if clean.get("buyer_line_index") is None:
            clean["buyer_line_index"] = len(normalized) + 1
        if not clean.get("buyer_line_number"):
            clean["buyer_line_number"] = str(clean["buyer_line_index"])
            clean["line_number"] = clean["buyer_line_number"]
        normalized.append(clean)
    return normalized


def _same_product_key(row: Dict[str, Any]) -> Tuple[str, str]:
    material = _safe_lower(row.get("material_number"))
    part = _safe_lower(row.get("part_number"))
    description = _safe_lower(row.get("normalized_description"))
    unit = _safe_lower(row.get("unit"))
    standards = ",".join(sorted(row.get("standards") or []))
    if material:
        return ("material", material)
    if part:
        return ("part", part)
    if description and unit:
        return ("description", f"{description}|{unit}|{standards}")
    return ("row", _safe_str(row.get("requirement_row_id")))


def _compatible_specification(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    spec_a = _safe_lower(a.get("specification"))
    spec_b = _safe_lower(b.get("specification"))
    if not spec_a or not spec_b:
        return True
    return spec_a == spec_b or spec_a in spec_b or spec_b in spec_a


def build_supplier_sourcing_groups(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    index: Dict[Tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("review_required"):
            continue
        key = _same_product_key(row)
        group_idx = index.get(key)
        if group_idx is not None and not _compatible_specification(groups[group_idx], row):
            group_idx = None
        if group_idx is None:
            group = {
                "supplier_group_id": "SUP-" + sha256("|".join([key[0], key[1]]).encode("utf-8")).hexdigest()[:12],
                "material_number": _safe_str(row.get("material_number")),
                "item_code": _safe_str(row.get("item_code")),
                "part_number": _safe_str(row.get("part_number")),
                "description": _safe_str(row.get("description")),
                "specification": _safe_str(row.get("specification")),
                "unit": _safe_str(row.get("unit")),
                "total_quantity": 0.0,
                "buyer_requirement_row_ids": [],
                "buyer_line_numbers": [],
                "buyer_line_indexes": [],
                "standards": [],
                "brand_required": False,
                "datasheet_required": False,
                "sample_may_be_required": False,
                "confidence": 0.0,
                "review_required": False,
                "review_reasons": [],
            }
            groups.append(group)
            group_idx = len(groups) - 1
            index[key] = group_idx
        group = groups[group_idx]
        quantity = _safe_number(row.get("quantity")) or (1.0 if (row.get("commercial_flags") or {}).get("lump_sum") else 0.0)
        group["total_quantity"] = round(float(group.get("total_quantity") or 0.0) + float(quantity), 6)
        group["buyer_requirement_row_ids"].append(row.get("requirement_row_id"))
        group["buyer_line_numbers"].append(row.get("buyer_line_number"))
        group["buyer_line_indexes"].append(row.get("buyer_line_index"))
        group["standards"] = _dedupe_strings(list(group.get("standards") or []) + list(row.get("standards") or []))
        group["brand_required"] = bool(group.get("brand_required") or row.get("brand_required"))
        group["datasheet_required"] = bool(group.get("datasheet_required") or row.get("datasheet_required"))
        group["sample_may_be_required"] = bool(group.get("sample_may_be_required") or row.get("sample_may_be_required"))
        group["confidence"] = round(max(float(group.get("confidence") or 0.0), float(row.get("confidence") or 0.0)), 4)
    return groups


def _conflict_product_match(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if _safe_lower(a.get("material_number")) and _safe_lower(a.get("material_number")) == _safe_lower(b.get("material_number")):
        return True
    if _safe_lower(a.get("part_number")) and _safe_lower(a.get("part_number")) == _safe_lower(b.get("part_number")):
        return True
    desc_a = _safe_lower(a.get("normalized_description"))
    desc_b = _safe_lower(b.get("normalized_description"))
    return bool(desc_a and desc_b and desc_a == desc_b)


def _different_authoritative_source(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        _safe_str(a.get("source_type")) != _safe_str(b.get("source_type"))
        or _safe_str(a.get("source_document")) != _safe_str(b.get("source_document"))
        or _safe_str(a.get("source_table")) != _safe_str(b.get("source_table"))
    )


def _recommended_row(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return sorted(rows, key=lambda r: (int(r.get("source_priority") or 0), float(r.get("confidence") or 0.0)), reverse=True)[0]


def detect_requirement_conflicts(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    seen = set()
    clean_rows = [row for row in rows if isinstance(row, dict)]
    for i, left in enumerate(clean_rows):
        for right in clean_rows[i + 1:]:
            if not _conflict_product_match(left, right):
                continue
            if not _different_authoritative_source(left, right):
                continue
            conflict_types: List[str] = []
            if left.get("quantity") is not None and right.get("quantity") is not None and float(left["quantity"]) != float(right["quantity"]):
                conflict_types.append("quantity_mismatch")
            if left.get("unit") and right.get("unit") and _safe_lower(left.get("unit")) != _safe_lower(right.get("unit")):
                conflict_types.append("unit_mismatch")
            if left.get("specification") and right.get("specification") and not _compatible_specification(left, right):
                conflict_types.append("specification_mismatch")
            if not conflict_types:
                continue
            rec = _recommended_row([left, right])
            conflict_type = conflict_types[0]
            key = tuple(sorted([left.get("requirement_row_id"), right.get("requirement_row_id")])) + (conflict_type,)
            if key in seen:
                continue
            seen.add(key)
            values = []
            for row in (left, right):
                values.append({
                    "quantity": row.get("quantity"),
                    "unit": row.get("unit"),
                    "source_type": row.get("source_type"),
                    "source_document": row.get("source_document"),
                    "source_page": row.get("source_page"),
                    "source_table": row.get("source_table"),
                    "requirement_row_id": row.get("requirement_row_id"),
                })
            conflicts.append({
                "conflict_id": "CONFLICT-" + sha256("|".join(_safe_str(v) for v in key).encode("utf-8")).hexdigest()[:12],
                "conflict_type": conflict_type,
                "material_number": left.get("material_number") or right.get("material_number") or "",
                "item_code": left.get("item_code") or right.get("item_code") or "",
                "part_number": left.get("part_number") or right.get("part_number") or "",
                "normalized_description": left.get("normalized_description") or right.get("normalized_description") or "",
                "values": values,
                "recommended_value": rec.get("quantity") if conflict_type == "quantity_mismatch" else rec.get("unit"),
                "recommended_source": rec.get("source_type"),
                "recommendation_reason": "highest_authoritative_source_priority",
                "operator_review_required": True,
            })
    return conflicts


def _extract_requirement_notes(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    technical: List[Dict[str, Any]] = []
    commercial: List[Dict[str, Any]] = []
    delivery: List[Dict[str, Any]] = []
    for row in rows:
        blob = " ".join([_safe_str(row.get("description")), _safe_str(row.get("specification"))])
        if row.get("brand_required"):
            technical.append(_requirement_note("technical", "Brand name required", "Brand names must be supplied.", row, "brand_required"))
        if row.get("datasheet_required"):
            technical.append(_requirement_note("technical", "Manufacturer datasheet required", "Manufacturer datasheets must be supplied.", row, "datasheet_required"))
        if row.get("sample_may_be_required"):
            technical.append(_requirement_note("technical", "Sample may be required", "Buyer may request product samples.", row, "sample_may_be_required"))
        for standard in row.get("standards") or []:
            technical.append(_requirement_note("technical", standard, f"Comply with {standard}.", row, "standard_detected"))
        if (row.get("commercial_flags") or {}).get("transport"):
            commercial.append(_requirement_note("commercial", "Transport line", "Buyer included transport as a pricing row.", row, "transport_line"))
        if "delivery" in _safe_lower(blob):
            delivery.append(_requirement_note("delivery", "Delivery requirement", blob[:240], row, "delivery_text"))
    return {
        "technical_requirements": _dedupe_requirement_notes(technical),
        "commercial_requirements": _dedupe_requirement_notes(commercial),
        "delivery_requirements": _dedupe_requirement_notes(delivery),
    }


def _requirement_note(requirement_type: str, name: str, description: str, row: Dict[str, Any], evidence: str) -> Dict[str, Any]:
    return {
        "requirement_type": requirement_type,
        "name": name,
        "description": description,
        "compulsory": True,
        "source_document": row.get("source_document") or "",
        "source_page": row.get("source_page"),
        "confidence": row.get("confidence") or 0.0,
        "evidence": [evidence],
    }


def _dedupe_requirement_notes(notes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for note in notes:
        key = (note.get("requirement_type"), note.get("name"), note.get("source_document"), note.get("source_page"))
        if key in seen:
            continue
        seen.add(key)
        out.append(note)
    return out


def _metadata_requirements(metadata: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    values = metadata.get(key)
    if not isinstance(values, list):
        return []
    out: List[Dict[str, Any]] = []
    for value in values:
        if isinstance(value, dict):
            out.append({
                "requirement_type": _safe_str(value.get("requirement_type") or key),
                "name": _safe_str(value.get("name") or value.get("description")),
                "description": _safe_str(value.get("description") or value.get("name")),
                "compulsory": _as_bool(value.get("compulsory")),
                "source_document": _safe_str(value.get("source_document")),
                "source_page": value.get("source_page"),
                "confidence": _safe_number(value.get("confidence")) or 0.0,
                "evidence": value.get("evidence") if isinstance(value.get("evidence"), list) else [],
            })
        elif _safe_str(value):
            out.append({
                "requirement_type": key,
                "name": _safe_str(value),
                "description": _safe_str(value),
                "compulsory": True,
                "source_document": "",
                "source_page": None,
                "confidence": 0.75,
                "evidence": ["metadata_requirement"],
            })
    return out


def _pricing_basis(rows: Sequence[Dict[str, Any]], conflicts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    verified = [row for row in rows if not row.get("review_required")]
    if not verified:
        return {
            "status": "unavailable",
            "selected_source_type": "",
            "selected_source_document": "",
            "selection_reason": "no_verified_requirement_rows",
        }
    selected = _recommended_row(verified)
    return {
        "status": "review_required" if conflicts else "selected",
        "selected_source_type": selected.get("source_type") or "",
        "selected_source_document": selected.get("source_document") or "",
        "selection_reason": "highest_authoritative_source_priority" if not conflicts else "highest_authoritative_source_priority_with_unresolved_conflicts",
    }


def build_requirement_pack(
    rows: Iterable[Dict[str, Any]],
    rfq_id: str = "",
    reference_number: str = "",
    buyer_name: str = "",
    title: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = metadata or {}
    buyer_rows = normalize_requirement_rows(rows, reference_number=reference_number)
    conflicts = detect_requirement_conflicts(buyer_rows)
    supplier_groups = build_supplier_sourcing_groups(buyer_rows)
    source_types = sorted({row.get("source_type") for row in buyer_rows if row.get("source_type")})
    source_documents = sorted({row.get("source_document") for row in buyer_rows if row.get("source_document")})
    verified_rows = [row for row in buyer_rows if not row.get("review_required")]
    review_rows = [row for row in buyer_rows if row.get("review_required")]
    confidences = [float(row.get("confidence") or 0.0) for row in buyer_rows]
    notes = _extract_requirement_notes(buyer_rows)
    review_flags = sorted({
        reason
        for row in buyer_rows
        for reason in (row.get("review_reasons") or [])
    } | ({"requirement_conflict"} if conflicts else set()))

    quantities_verified = bool(buyer_rows) and all(
        (row.get("quantity") is not None and float(row.get("quantity") or 0) > 0) or (row.get("commercial_flags") or {}).get("lump_sum")
        for row in buyer_rows
    )
    units_verified = bool(buyer_rows) and all(
        bool(row.get("unit")) or (row.get("commercial_flags") or {}).get("lump_sum")
        for row in buyer_rows
    )
    operator_review_required = bool(review_rows or conflicts)
    pricing_ready = bool(verified_rows) and not operator_review_required and quantities_verified and units_verified

    pack = {
        "requirement_pack_version": REQUIREMENT_PACK_VERSION,
        "rfq_id": _clean_text(rfq_id),
        "buyer_name": _clean_text(buyer_name),
        "reference_number": _clean_text(reference_number),
        "title": _clean_text(title),
        "buyer_rows": buyer_rows,
        "buyer_row_count": len(buyer_rows),
        "verified_buyer_row_count": len(verified_rows),
        "review_buyer_row_count": len(review_rows),
        "supplier_sourcing_groups": supplier_groups,
        "supplier_group_count": len(supplier_groups),
        "requirement_conflicts": conflicts,
        "requirement_conflict_count": len(conflicts),
        "technical_requirements": notes["technical_requirements"] + _metadata_requirements(metadata, "technical_requirements"),
        "commercial_requirements": notes["commercial_requirements"] + _metadata_requirements(metadata, "commercial_requirements"),
        "mandatory_returnables": _metadata_requirements(metadata, "mandatory_returnables"),
        "submission_requirements": _metadata_requirements(metadata, "submission_requirements"),
        "evaluation_requirements": _metadata_requirements(metadata, "evaluation_requirements"),
        "delivery_requirements": notes["delivery_requirements"] + _metadata_requirements(metadata, "delivery_requirements"),
        "source_documents": source_documents,
        "source_types": source_types,
        "embedded_pricing_schedule_detected": any(t in source_types for t in ("embedded_pricing_schedule", "formal_buyer_pricing_schedule", "buyer_returnable_pricing_form")),
        "standalone_boq_detected": "standalone_boq" in source_types,
        "specification_table_detected": "specification_table" in source_types,
        "quantities_verified": quantities_verified,
        "units_verified": units_verified,
        "pricing_ready_from_requirements": pricing_ready,
        "operator_review_required": operator_review_required,
        "pricing_basis": _pricing_basis(buyer_rows, conflicts),
        "review_flags": review_flags,
        "confidence": round(sum(confidences) / max(len(confidences), 1), 4) if confidences else 0.0,
    }
    # Backward-compatible aliases from the first requirement-pack repair.
    pack.update({
        "rows": buyer_rows,
        "row_count": pack["buyer_row_count"],
        "verified_row_count": pack["verified_buyer_row_count"],
        "review_row_count": pack["review_buyer_row_count"],
        "pricing_schedule_detected": pack["embedded_pricing_schedule_detected"],
        "status": "pricing_ready" if pricing_ready else ("review_required" if buyer_rows else "no_requirement_rows"),
    })
    return pack


def build_pricing_workspace_contract(requirement_pack: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rows = requirement_pack.get("buyer_rows") if isinstance(requirement_pack.get("buyer_rows"), list) else []
    conflicts = requirement_pack.get("requirement_conflicts") if isinstance(requirement_pack.get("requirement_conflicts"), list) else []
    blocking_reviews = []
    for conflict in conflicts:
        blocking_reviews.append({
            "type": "quantity_conflict" if conflict.get("conflict_type") == "quantity_mismatch" else conflict.get("conflict_type"),
            "message": "Requirement conflict requires operator review.",
            "recommended_action": "Confirm buyer quantity or approve formal pricing schedule as the pricing basis",
            "conflict_id": conflict.get("conflict_id"),
        })
    for row in buyer_rows:
        if row.get("review_required"):
            blocking_reviews.append({
                "type": "requirement_row_review",
                "message": f"Buyer row {row.get('buyer_line_number') or row.get('buyer_line_index')} requires review.",
                "recommended_action": "Confirm missing quantity, unit, or low-confidence row evidence",
                "conflict_id": "",
            })
    return {
        "buyer_pricing_rows": buyer_rows,
        "supplier_sourcing_groups": requirement_pack.get("supplier_sourcing_groups") or [],
        "requirement_conflicts": conflicts,
        "mandatory_returnables": requirement_pack.get("mandatory_returnables") or [],
        "technical_evidence_required": requirement_pack.get("technical_requirements") or [],
        "pricing_ready": bool(requirement_pack.get("pricing_ready_from_requirements")),
        "operator_review_required": bool(requirement_pack.get("operator_review_required")),
        "blocking_reviews": blocking_reviews,
    }


def attach_requirement_pack_fields(payload: Dict[str, Any], pack: Dict[str, Any]) -> Dict[str, Any]:
    rows = pack.get("buyer_rows") if isinstance(pack.get("buyer_rows"), list) else []
    payload["requirement_pack_version"] = pack.get("requirement_pack_version", REQUIREMENT_PACK_VERSION)
    payload["rfq_requirement_pack"] = pack
    payload["requirement_pack"] = pack
    payload["rfq_requirement_rows"] = rows
    payload["rfq_requirement_rows_count"] = int(pack.get("buyer_row_count") or 0)
    payload["verified_requirement_rows_count"] = int(pack.get("verified_buyer_row_count") or 0)
    payload["requirement_rows_review_count"] = int(pack.get("review_buyer_row_count") or 0)
    payload["pricing_ready_from_requirements"] = bool(pack.get("pricing_ready_from_requirements"))
    payload["operator_review_required"] = bool(pack.get("operator_review_required"))
    payload["requirement_conflict_count"] = int(pack.get("requirement_conflict_count") or 0)
    payload["requirement_pack_status"] = str(pack.get("status") or "")
    return payload
