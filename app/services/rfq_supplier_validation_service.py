from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services import live_rfq_store
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
SUPPLIER_VALIDATION_DIR = RUNTIME_DIR / "supplier_validation"
RETURNABLES_REVIEW_DIR = RUNTIME_DIR / "returnables_review"

SCHEMA_VERSION = "rfq_supplier_validation_v1"
RETURNABLES_SCHEMA_VERSION = "rfq_returnables_review_v1"

RETURNABLE_REQUIRED_COMPANY_DOCUMENT = "REQUIRED_COMPANY_DOCUMENT"
RETURNABLE_BUYER_FORM_COMPLETION = "BUYER_FORM_COMPLETION"
RETURNABLE_PRICING_RULE = "PRICING_COMMERCIAL_RULE"
RETURNABLE_ELIGIBILITY_DECLARATION = "ELIGIBILITY_DECLARATION"
RETURNABLE_SUBMISSION_FORMAT = "SUBMISSION_FORMAT_REQUIREMENT"
RETURNABLE_DEADLINE_RULE = "DEADLINE_SUBMISSION_RULE"
RETURNABLE_CONDITIONAL = "CONDITIONAL_REQUIREMENT"
RETURNABLE_TECHNICAL_EVIDENCE = "SUPPORTING_TECHNICAL_EVIDENCE"
RETURNABLE_GENERAL_INSTRUCTION = "GENERAL_BUYER_INSTRUCTION"
RETURNABLE_MANUAL_CLASSIFICATION = "REQUIRES_MANUAL_CLASSIFICATION"

# Backwards-compatible alias for older tests/imports. New code should use
# REQUIRED_COMPANY_DOCUMENT because not every returnable is an uploaded file.
RETURNABLE_REQUIRED_UPLOAD = RETURNABLE_REQUIRED_COMPANY_DOCUMENT


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "").replace("R", "").strip())
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("._")
    return cleaned or "rfq"


def _tokens(value: Any) -> List[str]:
    return [part for part in re.sub(r"[^a-z0-9]+", " ", _safe_text(value).lower()).split() if len(part) > 2]


def _similarity(left: Any, right: Any) -> float:
    a = set(_tokens(left))
    b = set(_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if value in (None, ""):
        return []
    return [value]


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


class RfqSupplierValidationService:
    """RFQ-level supplier comparison and returnables review without external contact."""

    def __init__(
        self,
        *,
        supplier_validation_dir: Optional[Path] = None,
        returnables_review_dir: Optional[Path] = None,
        lifecycle_service: Optional[RfqLifecycleService] = None,
    ) -> None:
        self.supplier_validation_dir = Path(supplier_validation_dir or SUPPLIER_VALIDATION_DIR)
        self.returnables_review_dir = Path(returnables_review_dir or RETURNABLES_REVIEW_DIR)
        self.lifecycle_service = lifecycle_service or RfqLifecycleService()

    def _supplier_path(self, rfq_id: str, create: bool = False) -> Path:
        if create:
            self.supplier_validation_dir.mkdir(parents=True, exist_ok=True)
        root = self.supplier_validation_dir.resolve()
        path = (root / f"{_slug(rfq_id)}.json").resolve()
        if root not in path.parents and path != root:
            raise ValueError("Unsafe supplier validation path")
        return path

    def _returnables_path(self, rfq_id: str, create: bool = False) -> Path:
        if create:
            self.returnables_review_dir.mkdir(parents=True, exist_ok=True)
        root = self.returnables_review_dir.resolve()
        path = (root / f"{_slug(rfq_id)}.json").resolve()
        if root not in path.parents and path != root:
            raise ValueError("Unsafe returnables review path")
        return path

    def _find_active_rfq(self, rfq_id: str) -> Optional[Dict[str, Any]]:
        selector = _safe_text(rfq_id).upper()
        for item in live_rfq_store.list_active_rfqs().get("items", []):
            if not isinstance(item, dict):
                continue
            values = {
                _safe_text(item.get("rfq_id")),
                _safe_text(item.get("id")),
                _safe_text(item.get("rfq_number")),
                _safe_text(item.get("reference_number")),
                _safe_text(item.get("buyer_rfq_number")),
            }
            if selector in {value.upper() for value in values if value}:
                return deepcopy(item)
        return None

    def _pricing_rows(self, rfq_id: str, rfq: Dict[str, Any]) -> List[Dict[str, Any]]:
        workspace = self.lifecycle_service.get_manual_pricing(rfq_id)
        candidates = [
            workspace.get("line_items"),
            workspace.get("pricing_rows"),
            rfq.get("pricing_rows"),
            rfq.get("line_items"),
            rfq.get("boq_items"),
            (rfq.get("pricing_schedule") or {}).get("rows") if isinstance(rfq.get("pricing_schedule"), dict) else None,
        ]
        rows: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            for index, row in enumerate(_as_list(candidate), start=1):
                if not isinstance(row, dict):
                    continue
                key = self._line_key(row, index)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(self._normalize_buyer_row(row, index))
            if rows:
                break
        return rows

    def _line_key(self, row: Dict[str, Any], index: int) -> str:
        return _safe_text(
            row.get("row_id")
            or row.get("item_number")
            or row.get("material_number")
            or row.get("buyer_line_number")
            or row.get("line_number")
            or row.get("item_no")
            or index
        )

    def _normalize_buyer_row(self, row: Dict[str, Any], index: int) -> Dict[str, Any]:
        key = self._line_key(row, index)
        return {
            "row_id": key,
            "item_number": _safe_text(row.get("item_number") or row.get("material_number") or row.get("buyer_line_number") or key),
            "material_number": _safe_text(row.get("material_number") or row.get("item_number")),
            "buyer_line_number": _safe_text(row.get("buyer_line_number") or row.get("line_number") or row.get("item_no")),
            "description": _safe_text(row.get("description") or row.get("item_description") or row.get("name")),
            "specification": _safe_text(row.get("specification") or row.get("technical_specification")),
            "quantity": _safe_float(row.get("quantity") or row.get("qty"), 0.0),
            "unit": _safe_text(row.get("unit") or row.get("uom") or "each"),
            "provisional_unit_cost": _safe_float(row.get("unit_cost") or row.get("cost_price") or row.get("supplier_rate"), 0.0),
            "provisional_selling_rate": _safe_float(row.get("selling_price") or row.get("selling_rate") or row.get("unit_price"), 0.0),
            "manual_override": _safe_bool(row.get("manual_override") or row.get("selling_rate_manual_override")),
            "source_page": row.get("source_page"),
            "pricing_source": _safe_text(row.get("pricing_source") or "operator_provisional_estimate"),
        }

    def _normalize_quote_line(self, quote: Dict[str, Any], line: Dict[str, Any], index: int) -> Dict[str, Any]:
        quantity = _safe_float(line.get("quantity_quoted") or line.get("quantity") or line.get("qty"), 0.0)
        unit_cost = _safe_float(line.get("unit_cost") or line.get("supplier_rate") or line.get("price"), 0.0)
        extended = _safe_float(line.get("extended_cost") or line.get("line_total"), 0.0)
        if extended <= 0 and quantity > 0 and unit_cost > 0:
            extended = round(quantity * unit_cost, 2)
        return {
            "supplier_name": _safe_text(quote.get("supplier_name")),
            "supplier_quote_reference": _safe_text(quote.get("supplier_quote_reference") or quote.get("quote_reference") or quote.get("quote_number")),
            "quote_date": _safe_text(quote.get("quote_date")),
            "validity_date": _safe_text(quote.get("validity_date")),
            "currency": _safe_text(quote.get("currency") or "ZAR"),
            "vat_treatment": _safe_text(quote.get("vat_treatment") or line.get("vat_treatment") or "unknown"),
            "delivery_cost": _safe_float(quote.get("delivery_cost"), 0.0),
            "lead_time": _safe_text(line.get("lead_time") or quote.get("lead_time")),
            "stock_availability": _safe_text(line.get("stock_availability") or quote.get("stock_availability")),
            "brand_offered": _safe_text(line.get("brand_offered") or quote.get("brand_offered")),
            "equivalent_product_status": _safe_text(line.get("equivalent_product_status") or line.get("equivalent_status") or "unknown"),
            "datasheet_attached": _safe_bool(line.get("datasheet_attached") or quote.get("datasheet_attached")),
            "compliance_certificate_attached": _safe_bool(line.get("compliance_certificate_attached") or quote.get("compliance_certificate_attached")),
            "item_number": _safe_text(line.get("item_number") or line.get("material_number") or line.get("buyer_line_number")),
            "description": _safe_text(line.get("description") or line.get("item_description")),
            "quantity_quoted": quantity,
            "unit": _safe_text(line.get("unit") or line.get("uom")),
            "unit_cost": round(unit_cost, 2),
            "extended_cost": round(extended, 2),
            "notes": _safe_text(line.get("notes") or quote.get("notes")),
            "source_document": _safe_text(line.get("source_document") or quote.get("source_document")),
            "extraction_confidence": _safe_float(line.get("extraction_confidence") or quote.get("extraction_confidence"), 1.0),
            "operator_review_state": _safe_text(line.get("operator_review_state") or "REVIEW_REQUIRED"),
            "line_index": index,
        }

    def _normalize_quotes(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for quote_index, quote in enumerate(_as_list(payload.get("supplier_quotes") or payload.get("quotes")), start=1):
            if not isinstance(quote, dict):
                continue
            lines = _as_list(quote.get("line_items") or quote.get("items") or quote.get("quote_lines"))
            if not lines:
                lines = [quote]
            for line_index, line in enumerate(lines, start=1):
                if not isinstance(line, dict):
                    continue
                row = self._normalize_quote_line(quote, line, line_index)
                row["quote_index"] = quote_index
                normalized.append(row)
        return normalized

    def match_quote_line(self, buyer_rows: List[Dict[str, Any]], quote_line: Dict[str, Any]) -> Dict[str, Any]:
        explicit = _safe_text(quote_line.get("item_number"))
        if explicit:
            matches = [
                row for row in buyer_rows
                if explicit.upper() in {
                    _safe_text(row.get("item_number")).upper(),
                    _safe_text(row.get("material_number")).upper(),
                    _safe_text(row.get("buyer_line_number")).upper(),
                    _safe_text(row.get("row_id")).upper(),
                }
            ]
            if len(matches) == 1:
                return {"status": "matched", "row_id": matches[0]["row_id"], "confidence": 1.0, "method": "item_number"}
            if len(matches) > 1:
                return {"status": "ambiguous", "row_id": None, "confidence": 0.0, "method": "item_number"}

        scored = sorted(
            [
                (row, _similarity(quote_line.get("description"), f"{row.get('description')} {row.get('specification')}"))
                for row in buyer_rows
            ],
            key=lambda pair: pair[1],
            reverse=True,
        )
        if not scored or scored[0][1] < 0.35:
            return {"status": "unmatched", "row_id": None, "confidence": scored[0][1] if scored else 0.0, "method": "description"}
        if len(scored) > 1 and scored[1][1] >= 0.35 and abs(scored[0][1] - scored[1][1]) < 0.12:
            return {"status": "ambiguous", "row_id": None, "confidence": scored[0][1], "method": "description"}
        return {"status": "matched", "row_id": scored[0][0]["row_id"], "confidence": scored[0][1], "method": "description"}

    def _line_compliant(self, line: Dict[str, Any]) -> Tuple[bool, List[str]]:
        missing: List[str] = []
        if line.get("unit_cost", 0) <= 0:
            missing.append("missing_unit_cost")
        if not line.get("datasheet_attached"):
            missing.append("missing_datasheet")
        if not line.get("compliance_certificate_attached"):
            missing.append("missing_compliance_certificate")
        if _safe_text(line.get("stock_availability")).lower() in {"", "unknown", "out of stock", "no stock"}:
            missing.append("stock_unverified")
        if not _safe_text(line.get("lead_time")):
            missing.append("missing_lead_time")
        if _safe_text(line.get("equivalent_product_status")).lower() in {"rejected", "non-compliant", "not compliant"}:
            missing.append("brand_or_equivalent_non_compliant")
        return not missing, missing

    def _build_comparison(self, buyer_rows: List[Dict[str, Any]], quote_lines: List[Dict[str, Any]], selections: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        quote_lines_by_row: Dict[str, List[Dict[str, Any]]] = {}
        for line in quote_lines:
            match = line.get("match") or {}
            if match.get("status") == "matched" and match.get("row_id"):
                quote_lines_by_row.setdefault(match["row_id"], []).append(line)

        for buyer in buyer_rows:
            candidates = []
            for line in quote_lines_by_row.get(buyer["row_id"], []):
                compliant, blockers = self._line_compliant(line)
                candidates.append({
                    **line,
                    "brand_specification_compliant": compliant,
                    "missing_documents": blockers,
                    "eligible_for_preference": compliant,
                })
            candidates.sort(key=lambda item: (not item.get("eligible_for_preference"), item.get("unit_cost") or 999999999))
            lowest_compliant = next((item for item in candidates if item.get("eligible_for_preference")), None)
            selected = selections.get(buyer["row_id"]) if isinstance(selections, dict) else None
            rows.append({
                "row_id": buyer["row_id"],
                "item_number": buyer["item_number"],
                "description": buyer["description"],
                "quantity": buyer["quantity"],
                "unit": buyer["unit"],
                "provisional_estimate": {
                    "unit_cost": buyer.get("provisional_unit_cost"),
                    "selling_rate": buyer.get("provisional_selling_rate"),
                    "pricing_source": buyer.get("pricing_source"),
                    "manual_override": buyer.get("manual_override"),
                },
                "supplier_quote_count": len(candidates),
                "supplier_quotes": candidates,
                "lowest_compliant_cost": lowest_compliant.get("unit_cost") if lowest_compliant else None,
                "recommended_supplier": lowest_compliant,
                "preferred_supplier": selected,
                "supplier_validation_status": "SUPPLIER_VALIDATED" if selected else "SUPPLIER_VALIDATION_REQUIRED",
            })
        return rows

    def get_supplier_validation_workspace(self, rfq_id: str) -> Dict[str, Any]:
        rfq = self._find_active_rfq(rfq_id)
        if not rfq:
            return {"status": "not_found", "rfq_id": rfq_id, "read_only": True}
        stored = _read_json(self._supplier_path(rfq_id), {})
        buyer_rows = self._pricing_rows(rfq_id, rfq)
        quote_lines = stored.get("supplier_quote_lines") if isinstance(stored.get("supplier_quote_lines"), list) else []
        comparison = self._build_comparison(buyer_rows, quote_lines, stored.get("preferred_suppliers") or {})
        return {
            "status": "ok",
            "rfq_id": rfq_id,
            "read_only": True,
            "schema_version": SCHEMA_VERSION,
            "supplier_quote_requests_policy": {
                "target_supplier_quote_count": 3,
                "supplier_mailbox": "lmcpaqsystem@gmail.com",
                "cc": "lechesam@me.com",
                "follow_up_after_days": 2,
                "email_sending_permitted": False,
                "gmail_draft_creation_permitted": False,
            },
            "line_items": buyer_rows,
            "comparison_rows": comparison,
            "supplier_quote_count": len({(line.get("supplier_name"), line.get("supplier_quote_reference")) for line in quote_lines}),
            "supplier_quote_line_count": len(quote_lines),
            "supplier_validation_required": any(row.get("supplier_validation_status") != "SUPPLIER_VALIDATED" for row in comparison),
            "quote_pack_generated": False,
            "submission_pack_generated": False,
            "external_connection_attempted": False,
        }

    def save_supplier_quotes(self, rfq_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        rfq = self._find_active_rfq(rfq_id)
        if not rfq:
            return {"status": "not_found", "rfq_id": rfq_id}
        buyer_rows = self._pricing_rows(rfq_id, rfq)
        normalized = self._normalize_quotes(payload)
        stored = _read_json(self._supplier_path(rfq_id), {})
        existing = stored.get("supplier_quote_lines") if isinstance(stored.get("supplier_quote_lines"), list) else []
        indexed = {
            (
                _safe_text(line.get("supplier_name")).lower(),
                _safe_text(line.get("supplier_quote_reference")).lower(),
                _safe_text(line.get("item_number")).lower(),
                _safe_text(line.get("description")).lower(),
            ): line
            for line in existing
            if isinstance(line, dict)
        }
        for line in normalized:
            line["match"] = self.match_quote_line(buyer_rows, line)
            key = (
                _safe_text(line.get("supplier_name")).lower(),
                _safe_text(line.get("supplier_quote_reference")).lower(),
                _safe_text(line.get("item_number")).lower(),
                _safe_text(line.get("description")).lower(),
            )
            indexed[key] = line
        record = {
            "schema_version": SCHEMA_VERSION,
            "rfq_id": rfq_id,
            "updated_at": _now_iso(),
            "supplier_quote_lines": list(indexed.values()),
            "preferred_suppliers": stored.get("preferred_suppliers") or {},
            "audit_history": stored.get("audit_history") or [],
            "safety": {
                "local_only": True,
                "external_connection_attempted": False,
                "gmail_draft_created": False,
                "quote_pack_generated": False,
                "submission_pack_generated": False,
            },
        }
        _atomic_write_json(self._supplier_path(rfq_id, create=True), record)
        workspace = self.get_supplier_validation_workspace(rfq_id)
        workspace["saved"] = True
        return workspace

    def select_preferred_supplier(self, rfq_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = _read_json(self._supplier_path(rfq_id), {})
        if not stored:
            return {"status": "not_found", "rfq_id": rfq_id, "message": "No supplier quotes captured."}
        workspace = self.get_supplier_validation_workspace(rfq_id)
        rows_by_id = {row["row_id"]: row for row in workspace.get("comparison_rows", [])}
        selections = stored.get("preferred_suppliers") if isinstance(stored.get("preferred_suppliers"), dict) else {}
        audit = stored.get("audit_history") if isinstance(stored.get("audit_history"), list) else []
        for selection in _as_list(payload.get("selections") or payload):
            if not isinstance(selection, dict):
                continue
            row_id = _safe_text(selection.get("row_id"))
            supplier_name = _safe_text(selection.get("supplier_name"))
            quote_ref = _safe_text(selection.get("supplier_quote_reference") or selection.get("quote_reference"))
            row = rows_by_id.get(row_id)
            if not row:
                continue
            candidate = next(
                (
                    item for item in row.get("supplier_quotes", [])
                    if _safe_text(item.get("supplier_name")) == supplier_name
                    and (not quote_ref or _safe_text(item.get("supplier_quote_reference")) == quote_ref)
                ),
                None,
            )
            if not candidate:
                continue
            selections[row_id] = {
                "row_id": row_id,
                "supplier_name": supplier_name,
                "supplier_quote_reference": _safe_text(candidate.get("supplier_quote_reference")),
                "unit_cost": candidate.get("unit_cost"),
                "selected_at": _now_iso(),
                "selected_by": _safe_text(selection.get("selected_by") or "operator"),
                "selection_note": _safe_text(selection.get("selection_note")),
                "pricing_source": "supplier_validated",
                "supplier_quote_received": True,
                "requires_supplier_validation": False,
                "manual_selling_override_preserved": bool(row.get("provisional_estimate", {}).get("manual_override")),
            }
            audit.append({
                "event": "preferred_supplier_selected",
                "row_id": row_id,
                "previous_pricing_source": row.get("provisional_estimate", {}).get("pricing_source"),
                "previous_unit_cost": row.get("provisional_estimate", {}).get("unit_cost"),
                "selected_supplier": supplier_name,
                "selected_quote_reference": _safe_text(candidate.get("supplier_quote_reference")),
                "created_at": _now_iso(),
            })
        stored["preferred_suppliers"] = selections
        stored["audit_history"] = audit
        stored["updated_at"] = _now_iso()
        _atomic_write_json(self._supplier_path(rfq_id, create=True), stored)
        result = self.get_supplier_validation_workspace(rfq_id)
        result["saved"] = True
        return result

    def _raw_returnables(self, rfq: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw = []
        for key in ("mandatory_returnables", "missing_returnables", "returnables", "returnable_requirements"):
            raw.extend(_as_list(rfq.get(key)))
        out: List[Dict[str, Any]] = []
        seen = set()
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                text = _safe_text(item.get("name") or item.get("requirement") or item.get("description") or item.get("document") or item.get("label"))
                source_page = item.get("source_page")
                mandatory = _safe_text(item.get("mandatory") or item.get("status") or item.get("requirement_type") or "mandatory")
            else:
                text = _safe_text(item)
                source_page = None
                mandatory = "mandatory"
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"returnable_id": f"ret-{index}", "requirement_text": text, "source_page": source_page, "mandatory_status": mandatory})
        return out

    def classify_returnable(self, text: str, mandatory_status: str = "") -> str:
        lower = _safe_text(text).lower()
        status = _safe_text(mandatory_status).lower()
        if not lower:
            return RETURNABLE_MANUAL_CLASSIFICATION
        if "joint venture" in lower or "jv agreement" in lower:
            return RETURNABLE_CONDITIONAL
        if any(term in lower for term in ("mbd", "bill of quantities", "boq", "specification")):
            return RETURNABLE_BUYER_FORM_COMPLETION
        if any(term in lower for term in ("briefing", "site briefing", "where applicable", "if applicable", "conditional")) or "conditional" in status:
            return RETURNABLE_CONDITIONAL
        if any(term in lower for term in ("datasheet", "data sheet", "reference letter", "proof of certification", "technical", "certification")):
            return RETURNABLE_TECHNICAL_EVIDENCE
        if any(term in lower for term in ("after closing", "closing date", "closing time", "closind date", "late quotation", "late submission")):
            return RETURNABLE_DEADLINE_RULE
        if any(term in lower for term in ("letterhead", "pdf", "ms word", "ms excel", "pictures are not allowed", "quotation must be on", "quotes should be on")):
            return RETURNABLE_SUBMISSION_FORMAT
        if any(term in lower for term in ("brand name", "brand names", "include all applicable taxes", "include taxes", "applicable taxes", "total quotation value", "vat")):
            return RETURNABLE_PRICING_RULE
        if any(term in lower for term in ("not be in the service of the state", "service of the state", "blacklisted", "national treasury", "declaration", "declare", "tax compliance", "pin")):
            return RETURNABLE_ELIGIBILITY_DECLARATION
        if any(term in lower for term in ("b-bbee", "bbbee", "bee", "sworn affidavit", "lease agreement", "municipal account", "company registration", "valid certificate", "copy of valid")):
            return RETURNABLE_REQUIRED_COMPANY_DOCUMENT
        if any(term in lower for term in ("certificate", "certified", "copy", "attached", "attach", "proof", "document", "registration", "brochure")):
            return RETURNABLE_REQUIRED_COMPANY_DOCUMENT
        if any(term in lower for term in ("must", "shall", "required")):
            return RETURNABLE_GENERAL_INSTRUCTION
        return RETURNABLE_MANUAL_CLASSIFICATION

    def _category_policy(self, category: str, closing_date: Any = None) -> Dict[str, Any]:
        if category == RETURNABLE_REQUIRED_COMPANY_DOCUMENT:
            return {
                "requires_evidence": True,
                "action_required": "Attach or reference company document evidence.",
                "blocker_key": "documents_missing",
            }
        if category == RETURNABLE_BUYER_FORM_COMPLETION:
            return {
                "requires_evidence": False,
                "requires_buyer_form_workflow": True,
                "action_required": "Complete or link the buyer form, MBD or BOQ workflow.",
                "blocker_key": "buyer_forms_incomplete",
            }
        if category == RETURNABLE_ELIGIBILITY_DECLARATION:
            return {
                "requires_evidence": False,
                "action_required": "Acknowledge or link the relevant declaration/MBD evidence.",
                "blocker_key": "declarations_unreviewed",
            }
        if category == RETURNABLE_PRICING_RULE:
            return {
                "requires_evidence": False,
                "action_required": "Confirm pricing complies with this buyer rule.",
                "blocker_key": "pricing_rules_unconfirmed",
            }
        if category == RETURNABLE_SUBMISSION_FORMAT:
            return {
                "requires_evidence": False,
                "action_required": "Acknowledge and validate package format before submission.",
                "blocker_key": "submission_rules_unconfirmed",
            }
        if category == RETURNABLE_DEADLINE_RULE:
            return {
                "requires_evidence": False,
                "action_required": "Acknowledge deadline and verify against the RFQ closing date.",
                "blocker_key": "deadline_rules_active",
                "evaluated_against_closing_date": _safe_text(closing_date),
            }
        if category == RETURNABLE_CONDITIONAL:
            return {
                "requires_evidence": False,
                "action_required": "Mark applicable, not applicable with reason, or requires clarification.",
                "blocker_key": "conditional_requirements_unresolved",
            }
        if category == RETURNABLE_TECHNICAL_EVIDENCE:
            return {
                "requires_evidence": True,
                "action_required": "Attach or reference datasheets, certifications or technical evidence.",
                "blocker_key": "technical_evidence_missing",
            }
        if category == RETURNABLE_GENERAL_INSTRUCTION:
            return {
                "requires_evidence": False,
                "action_required": "Operator acknowledgement required.",
                "blocker_key": "submission_rules_unconfirmed",
            }
        return {
            "requires_evidence": False,
            "action_required": "Manual category assignment required.",
            "blocker_key": "manual_classification_required",
        }

    def _deadline_is_open(self, closing_date: Any, *, now: Optional[datetime] = None) -> bool:
        parsed = _parse_datetime(closing_date)
        if parsed is None:
            return False
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return parsed > current.astimezone(timezone.utc)

    def _review_resolved(self, category: str, review: Dict[str, Any], policy: Dict[str, Any]) -> bool:
        status = _safe_text(review.get("review_status") or review.get("status")).upper()
        approval = _safe_text(review.get("approval_state")).upper()
        evidence = _safe_text(review.get("evidence_file") or review.get("evidence_location"))
        override = _safe_text(review.get("operator_override_justification"))
        note = _safe_text(review.get("review_note"))

        if category == RETURNABLE_DEADLINE_RULE:
            if _safe_bool(review.get("deadline_discrepancy")):
                return False
            if not self._deadline_is_open(policy.get("evaluated_against_closing_date")):
                return False
            return status in {"ACKNOWLEDGED", "CLOSING_DATE_VERIFIED", "REVIEWED", "APPROVED"} and approval not in {"REJECTED"}
        if category == RETURNABLE_CONDITIONAL:
            if status == "NOT_APPLICABLE":
                return bool(note)
            return status in {"APPLICABLE", "PRESENT", "REVIEWED", "APPROVED"} and approval not in {"", "UNREVIEWED", "REJECTED"}
        if category == RETURNABLE_MANUAL_CLASSIFICATION:
            return False
        if policy.get("requires_evidence"):
            return status in {"PRESENT", "REVIEWED", "APPROVED"} and bool(evidence or override) and approval not in {"", "UNREVIEWED", "REJECTED"}
        if policy.get("requires_buyer_form_workflow"):
            return status in {"COMPLETED", "REVIEWED", "APPROVED"} and bool(
                review.get("buyer_form_reference") or review.get("workflow_reference") or evidence or override
            )
        return status in {"ACKNOWLEDGED", "CONFIRMED", "REVIEWED", "APPROVED"} and approval not in {"REJECTED"}

    def _empty_readiness_counts(self) -> Dict[str, int]:
        return {
            "documents_missing": 0,
            "buyer_forms_incomplete": 0,
            "declarations_unreviewed": 0,
            "pricing_rules_unconfirmed": 0,
            "submission_rules_unconfirmed": 0,
            "deadline_rules_active": 0,
            "conditional_requirements_unresolved": 0,
            "technical_evidence_missing": 0,
            "manual_classification_required": 0,
        }

    def _progress_bucket(self, category: str) -> str:
        return {
            RETURNABLE_REQUIRED_COMPANY_DOCUMENT: "company_documents",
            RETURNABLE_BUYER_FORM_COMPLETION: "buyer_forms",
            RETURNABLE_ELIGIBILITY_DECLARATION: "declarations",
            RETURNABLE_PRICING_RULE: "pricing_rules",
            RETURNABLE_SUBMISSION_FORMAT: "submission_rules",
            RETURNABLE_DEADLINE_RULE: "deadline_rules",
            RETURNABLE_CONDITIONAL: "conditional_requirements",
            RETURNABLE_TECHNICAL_EVIDENCE: "technical_evidence",
            RETURNABLE_MANUAL_CLASSIFICATION: "manual_classification",
            RETURNABLE_GENERAL_INSTRUCTION: "submission_rules",
        }.get(category, "manual_classification")

    def _empty_progress(self) -> Dict[str, Dict[str, int]]:
        return {
            key: {"complete": 0, "total": 0}
            for key in (
                "company_documents",
                "buyer_forms",
                "declarations",
                "pricing_rules",
                "submission_rules",
                "deadline_rules",
                "conditional_requirements",
                "technical_evidence",
                "manual_classification",
            )
        }

    def get_returnables_review_workspace(self, rfq_id: str) -> Dict[str, Any]:
        rfq = self._find_active_rfq(rfq_id)
        if not rfq:
            return {"status": "not_found", "rfq_id": rfq_id, "read_only": True}
        saved = _read_json(self._returnables_path(rfq_id), {})
        saved_by_id = {
            _safe_text(item.get("returnable_id")): item
            for item in _as_list(saved.get("reviews"))
            if isinstance(item, dict)
        }
        items = []
        category_counts: Dict[str, int] = {}
        readiness_counts = self._empty_readiness_counts()
        progress = self._empty_progress()
        blockers: List[str] = []
        for raw in self._raw_returnables(rfq):
            category = self.classify_returnable(raw["requirement_text"], raw.get("mandatory_status", ""))
            review = saved_by_id.get(raw["returnable_id"], {})
            status = _safe_text(review.get("review_status") or "MISSING")
            approval = _safe_text(review.get("approval_state") or "UNREVIEWED")
            evidence = _safe_text(review.get("evidence_file") or review.get("evidence_location"))
            policy = self._category_policy(category, closing_date=rfq.get("closing_date") or rfq.get("closing_datetime"))
            resolved = self._review_resolved(category, review, policy)
            unresolved = not resolved
            progress_key = self._progress_bucket(category)
            progress[progress_key]["total"] += 1
            if resolved:
                progress[progress_key]["complete"] += 1
            blocker_key = policy.get("blocker_key")
            if blocker_key:
                if blocker_key == "deadline_rules_active":
                    if not resolved:
                        readiness_counts[blocker_key] = readiness_counts.get(blocker_key, 0) + 1
                elif unresolved:
                    readiness_counts[blocker_key] = readiness_counts.get(blocker_key, 0) + 1
            if unresolved:
                blockers.append(raw["returnable_id"])
            category_counts[category] = category_counts.get(category, 0) + 1
            items.append({
                **raw,
                "category": category,
                "closing_date": rfq.get("closing_date") or rfq.get("closing_datetime"),
                "review_status": status,
                "approval_state": approval,
                "evidence_file": evidence,
                "evidence_location": _safe_text(review.get("evidence_location")),
                "buyer_form_reference": _safe_text(review.get("buyer_form_reference") or review.get("workflow_reference")),
                "evidence_references": _as_list(review.get("evidence_references")),
                "review_note": _safe_text(review.get("review_note")),
                "reviewer": _safe_text(review.get("reviewer")),
                "reviewed_at": _safe_text(review.get("reviewed_at")),
                "override_used": bool(_safe_text(review.get("operator_override_justification"))),
                "override_reason": _safe_text(review.get("operator_override_justification")),
                "applicable_state": _safe_text(review.get("applicable_state") or review.get("review_status") or status),
                "action_history": _as_list(review.get("action_history")),
                "requires_evidence": bool(policy.get("requires_evidence")),
                "requires_buyer_form_workflow": bool(policy.get("requires_buyer_form_workflow")),
                "action_required": policy.get("action_required"),
                "blocker_key": blocker_key,
                "unresolved": unresolved,
            })
        total_requirements = len(items)
        total_unresolved = len(blockers)
        total_resolved = max(0, total_requirements - total_unresolved)
        supplier_workspace = self.get_supplier_validation_workspace(rfq_id)
        supplier_validation_complete = not bool(supplier_workspace.get("supplier_validation_required", True))
        manual_pricing = self.lifecycle_service.get_manual_pricing(rfq_id)
        manual_pricing_complete = bool(manual_pricing.get("saved")) and not bool(
            (manual_pricing.get("manual_pricing") or {}).get("totals", {}).get("supplier_validation_required")
        )
        human_approval_complete = False
        quote_prep_ready = (
            total_unresolved == 0
            and supplier_validation_complete
            and manual_pricing_complete
            and human_approval_complete
        )
        blocker_reasons = [
            key for key, value in readiness_counts.items() if int(value or 0) > 0
        ]
        if not supplier_validation_complete:
            blocker_reasons.append("supplier_validation_incomplete")
        if not manual_pricing_complete:
            blocker_reasons.append("manual_pricing_or_supplier_validation_incomplete")
        if not human_approval_complete:
            blocker_reasons.append("human_approval_pending")
        return {
            "status": "ok",
            "rfq_id": rfq_id,
            "read_only": True,
            "schema_version": RETURNABLES_SCHEMA_VERSION,
            "returnables": items,
            "returnable_count": len(items),
            "category_counts": category_counts,
            "readiness_counts": readiness_counts,
            "category_progress": progress,
            "company_documents_complete": progress["company_documents"]["complete"],
            "company_documents_total": progress["company_documents"]["total"],
            "buyer_forms_complete": progress["buyer_forms"]["complete"],
            "buyer_forms_total": progress["buyer_forms"]["total"],
            "declarations_complete": progress["declarations"]["complete"],
            "declarations_total": progress["declarations"]["total"],
            "pricing_rules_complete": progress["pricing_rules"]["complete"],
            "pricing_rules_total": progress["pricing_rules"]["total"],
            "submission_rules_complete": progress["submission_rules"]["complete"],
            "submission_rules_total": progress["submission_rules"]["total"],
            "deadline_rules_complete": progress["deadline_rules"]["complete"],
            "deadline_rules_total": progress["deadline_rules"]["total"],
            "conditional_requirements_complete": progress["conditional_requirements"]["complete"],
            "conditional_requirements_total": progress["conditional_requirements"]["total"],
            "technical_evidence_complete": progress["technical_evidence"]["complete"],
            "technical_evidence_total": progress["technical_evidence"]["total"],
            "manual_classification_complete": progress["manual_classification"]["complete"],
            "manual_classification_total": progress["manual_classification"]["total"],
            "total_requirements": total_requirements,
            "total_resolved": total_resolved,
            "total_unresolved": total_unresolved,
            "blocking_requirements": blockers,
            "readiness_percentage": round((total_resolved / total_requirements) * 100.0, 2) if total_requirements else 0.0,
            "supplier_validation_complete": supplier_validation_complete,
            "manual_pricing_complete": manual_pricing_complete,
            "human_approval_complete": human_approval_complete,
            "quote_prep_ready": quote_prep_ready,
            "missing_or_unverified_count": len(blockers),
            "documents_missing": readiness_counts["documents_missing"],
            "buyer_forms_incomplete": readiness_counts["buyer_forms_incomplete"],
            "declarations_unreviewed": readiness_counts["declarations_unreviewed"],
            "pricing_rules_unconfirmed": readiness_counts["pricing_rules_unconfirmed"],
            "submission_rules_unconfirmed": readiness_counts["submission_rules_unconfirmed"],
            "deadline_rules_active": readiness_counts["deadline_rules_active"],
            "conditional_requirements_unresolved": readiness_counts["conditional_requirements_unresolved"],
            "technical_evidence_missing": readiness_counts["technical_evidence_missing"],
            "manual_classification_required": readiness_counts["manual_classification_required"],
            "submission_blocked": bool(blockers) or not quote_prep_ready,
            "blockers": blockers,
            "blocker_reasons": blocker_reasons,
            "quote_pack_generated": False,
            "submission_pack_generated": False,
        }

    def _normalize_evidence_reference(self, raw: Dict[str, Any], index: int) -> Dict[str, Any]:
        evidence_id = _safe_text(raw.get("evidence_id") or raw.get("id") or f"evidence-{index}")
        return {
            "evidence_id": evidence_id,
            "evidence_type": _safe_text(raw.get("evidence_type") or raw.get("type") or "document_reference"),
            "file_name": _safe_text(raw.get("file_name") or raw.get("filename") or raw.get("name")),
            "file_path": _safe_text(raw.get("file_path") or raw.get("path") or raw.get("document_reference")),
            "document_reference": _safe_text(raw.get("document_reference") or raw.get("reference")),
            "source": _safe_text(raw.get("source") or "operator_reference"),
            "checksum": _safe_text(raw.get("checksum")),
            "linked_at": _safe_text(raw.get("linked_at") or raw.get("uploaded_at") or _now_iso()),
            "linked_by": _safe_text(raw.get("linked_by") or raw.get("uploaded_by") or raw.get("reviewer") or "operator"),
            "description": _safe_text(raw.get("description")),
            "document_date": _safe_text(raw.get("document_date")),
            "expiry_date": _safe_text(raw.get("expiry_date")),
            "verification_status": _safe_text(raw.get("verification_status") or "PENDING_REVIEW"),
            "reviewer": _safe_text(raw.get("reviewer")),
            "reviewed_at": _safe_text(raw.get("reviewed_at")),
            "review_note": _safe_text(raw.get("review_note")),
        }

    def _normalize_evidence_references(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw = payload.get("evidence_references")
        if raw is None:
            raw = payload.get("evidence") or payload.get("evidence_reference")
        refs: List[Dict[str, Any]] = []
        for index, item in enumerate(_as_list(raw), start=1):
            if isinstance(item, dict):
                refs.append(self._normalize_evidence_reference(item, index))
            elif item:
                refs.append(self._normalize_evidence_reference({"document_reference": item, "file_path": item}, index))
        return refs

    def _allowed_statuses(self, category: str) -> set:
        base = {"MISSING", "REJECTED", "REQUIRES_CLARIFICATION"}
        by_category = {
            RETURNABLE_REQUIRED_COMPANY_DOCUMENT: base | {"PRESENT", "REVIEWED", "APPROVED"},
            RETURNABLE_BUYER_FORM_COMPLETION: base | {"COMPLETED", "REVIEWED", "APPROVED"},
            RETURNABLE_ELIGIBILITY_DECLARATION: base | {"ACKNOWLEDGED", "REVIEWED", "APPROVED"},
            RETURNABLE_PRICING_RULE: base | {"CONFIRMED", "NON_COMPLIANT", "REVIEWED", "APPROVED"},
            RETURNABLE_SUBMISSION_FORMAT: base | {"ACKNOWLEDGED", "CONFIRMED", "NON_COMPLIANT", "REVIEWED", "APPROVED"},
            RETURNABLE_DEADLINE_RULE: base | {"ACKNOWLEDGED", "CLOSING_DATE_VERIFIED", "DATE_DISCREPANCY"},
            RETURNABLE_CONDITIONAL: base | {"APPLICABLE", "NOT_APPLICABLE", "PRESENT", "REVIEWED", "APPROVED"},
            RETURNABLE_TECHNICAL_EVIDENCE: base | {"PRESENT", "REVIEWED", "APPROVED"},
            RETURNABLE_GENERAL_INSTRUCTION: base | {"ACKNOWLEDGED", "REVIEWED", "APPROVED"},
            RETURNABLE_MANUAL_CLASSIFICATION: base | {"CLASSIFIED"},
        }
        return by_category.get(category, base)

    def _validate_review_payload(self, current: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        category = current.get("category")
        status = _safe_text(payload.get("review_status") or payload.get("status") or payload.get("action") or "MISSING").upper()
        approval = _safe_text(payload.get("approval_state") or ("REVIEWED" if status in {"ACKNOWLEDGED", "CONFIRMED", "CLOSING_DATE_VERIFIED"} else "UNREVIEWED")).upper()
        evidence_refs = self._normalize_evidence_references(payload)
        evidence = _safe_text(payload.get("evidence_file") or payload.get("evidence_location"))
        if evidence and not evidence_refs:
            evidence_refs = self._normalize_evidence_references({"evidence_reference": evidence})
        override = _safe_text(payload.get("operator_override_justification") or payload.get("override_reason"))
        review_note = _safe_text(payload.get("review_note") or payload.get("note"))
        reviewer = _safe_text(payload.get("reviewer") or payload.get("actor"))
        errors: List[str] = []

        if status not in self._allowed_statuses(category):
            errors.append("invalid_state_transition")
        if status in {"NON_COMPLIANT", "REJECTED", "DATE_DISCREPANCY"}:
            approval = "REJECTED"
        if category in {RETURNABLE_REQUIRED_COMPANY_DOCUMENT, RETURNABLE_TECHNICAL_EVIDENCE} and status in {"PRESENT", "REVIEWED", "APPROVED"} and not evidence_refs and not override:
            errors.append("mandatory_evidence_required")
        if category == RETURNABLE_BUYER_FORM_COMPLETION and status in {"COMPLETED", "REVIEWED", "APPROVED"} and not (
            _safe_text(payload.get("buyer_form_reference") or payload.get("workflow_reference")) or evidence_refs or override
        ):
            errors.append("buyer_form_workflow_reference_required")
        if category == RETURNABLE_CONDITIONAL and status == "NOT_APPLICABLE" and not review_note:
            errors.append("not_applicable_reason_required")
        if category == RETURNABLE_DEADLINE_RULE:
            if status in {"ACKNOWLEDGED", "CLOSING_DATE_VERIFIED"} and not self._deadline_is_open(current.get("closing_date")):
                errors.append("deadline_not_open_or_invalid")
            if _safe_bool(payload.get("deadline_discrepancy")) or status == "DATE_DISCREPANCY":
                errors.append("deadline_discrepancy_blocks_resolution")
        if category == RETURNABLE_MANUAL_CLASSIFICATION and not _safe_text(payload.get("assigned_category")):
            errors.append("manual_category_required")
        if status == "NOT_APPLICABLE" and not review_note:
            errors.append("review_note_required")
        if not reviewer:
            errors.append("reviewer_required")

        if errors:
            return None, errors

        normalized = {
            "returnable_id": current["returnable_id"],
            "requirement_text": current.get("requirement_text"),
            "category": _safe_text(payload.get("assigned_category") or category),
            "source_page": current.get("source_page"),
            "mandatory_status": current.get("mandatory_status"),
            "applicable_state": _safe_text(payload.get("applicable_state") or status),
            "review_status": status,
            "approval_state": approval,
            "evidence_references": evidence_refs,
            "evidence_file": evidence or (evidence_refs[0].get("file_path") if evidence_refs else ""),
            "evidence_location": _safe_text(payload.get("evidence_location") or (evidence_refs[0].get("file_path") if evidence_refs else "")),
            "buyer_form_reference": _safe_text(payload.get("buyer_form_reference") or payload.get("workflow_reference")),
            "review_note": review_note,
            "reviewer": reviewer,
            "reviewed_at": _now_iso(),
            "override_used": bool(override),
            "operator_override_justification": override,
            "override_reason": override,
            "deadline_discrepancy": _safe_bool(payload.get("deadline_discrepancy")) or status == "DATE_DISCREPANCY",
        }
        normalized["unresolved"] = not self._review_resolved(
            normalized["category"],
            normalized,
            self._category_policy(normalized["category"], closing_date=current.get("closing_date")),
        )
        normalized["blocker_reasons"] = [current.get("blocker_key")] if normalized["unresolved"] and current.get("blocker_key") else []
        return normalized, []

    def update_returnable_review(self, rfq_id: str, returnable_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        workspace = self.get_returnables_review_workspace(rfq_id)
        if workspace.get("status") != "ok":
            return workspace
        current = next((item for item in workspace.get("returnables", []) if item.get("returnable_id") == returnable_id), None)
        if not current:
            return {"status": "blocked", "rfq_id": rfq_id, "returnable_id": returnable_id, "errors": ["unknown_returnable_id"], "submission_blocked": True}

        stored = _read_json(self._returnables_path(rfq_id), {})
        existing_reviews = {
            _safe_text(item.get("returnable_id")): item
            for item in _as_list(stored.get("reviews"))
            if isinstance(item, dict)
        }
        previous = existing_reviews.get(returnable_id, {})
        normalized, errors = self._validate_review_payload(current, payload)
        if errors:
            return {"status": "blocked", "rfq_id": rfq_id, "returnable_id": returnable_id, "errors": errors, "submission_blocked": True}

        history = _as_list(previous.get("action_history"))
        comparable_previous = {
            key: previous.get(key)
            for key in (
                "category",
                "applicable_state",
                "review_status",
                "approval_state",
                "evidence_references",
                "buyer_form_reference",
                "review_note",
                "override_reason",
                "deadline_discrepancy",
            )
        }
        comparable_new = {
            key: normalized.get(key)
            for key in comparable_previous
        }
        if comparable_previous != comparable_new:
            history.append({
                "action": _safe_text(payload.get("action") or normalized.get("review_status") or "review_update"),
                "previous_state": comparable_previous,
                "new_state": comparable_new,
                "actor": normalized["reviewer"],
                "timestamp": normalized["reviewed_at"],
                "note": normalized.get("review_note"),
                "evidence_reference_ids": [ref.get("evidence_id") for ref in normalized.get("evidence_references", [])],
            })
        normalized["action_history"] = history
        existing_reviews[returnable_id] = normalized

        record = {
            "schema_version": RETURNABLES_SCHEMA_VERSION,
            "rfq_id": rfq_id,
            "updated_at": _now_iso(),
            "reviews": list(existing_reviews.values()),
            "safety": {
                "local_only": True,
                "quote_pack_generated": False,
                "submission_pack_generated": False,
                "submission_approved": False,
                "external_connection_attempted": False,
            },
        }
        _atomic_write_json(self._returnables_path(rfq_id, create=True), record)
        result = self.get_returnables_review_workspace(rfq_id)
        result["saved"] = True
        result["updated_returnable_id"] = returnable_id
        return result

    def save_returnables_review(self, rfq_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        workspace = self.get_returnables_review_workspace(rfq_id)
        if workspace.get("status") != "ok":
            return workspace
        raw_by_id = {item["returnable_id"]: item for item in workspace.get("returnables", [])}
        reviews: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []
        for review in _as_list(payload.get("reviews") or payload.get("items") or payload):
            if not isinstance(review, dict):
                continue
            returnable_id = _safe_text(review.get("returnable_id"))
            current = raw_by_id.get(returnable_id)
            if not current:
                errors.append(f"{returnable_id}:unknown_returnable")
                continue
            status = _safe_text(review.get("review_status") or review.get("status") or "MISSING").upper()
            approval = _safe_text(review.get("approval_state") or "UNREVIEWED").upper()
            evidence = _safe_text(review.get("evidence_file") or review.get("evidence_location"))
            override = _safe_text(review.get("operator_override_justification"))
            if current.get("requires_evidence") and status in {"PRESENT", "APPROVED", "REVIEWED"} and not evidence and not override:
                errors.append(f"{returnable_id}:mandatory_evidence_required")
                continue
            if current.get("category") == RETURNABLE_CONDITIONAL and status == "NOT_APPLICABLE" and not _safe_text(review.get("review_note")):
                errors.append(f"{returnable_id}:not_applicable_reason_required")
                continue
            if current.get("requires_buyer_form_workflow") and status in {"COMPLETED", "APPROVED", "REVIEWED"} and not (
                _safe_text(review.get("buyer_form_reference") or review.get("workflow_reference") or evidence or override)
            ):
                errors.append(f"{returnable_id}:buyer_form_workflow_reference_required")
                continue
            reviews[returnable_id] = {
                "returnable_id": returnable_id,
                "review_status": status,
                "approval_state": approval,
                "evidence_file": evidence,
                "evidence_location": _safe_text(review.get("evidence_location")),
                "buyer_form_reference": _safe_text(review.get("buyer_form_reference") or review.get("workflow_reference")),
                "review_note": _safe_text(review.get("review_note")),
                "reviewer": _safe_text(review.get("reviewer") or "operator"),
                "reviewed_at": _now_iso(),
                "operator_override_justification": override,
            }
        if errors:
            return {"status": "blocked", "rfq_id": rfq_id, "errors": errors, "submission_blocked": True}
        record = {
            "schema_version": RETURNABLES_SCHEMA_VERSION,
            "rfq_id": rfq_id,
            "updated_at": _now_iso(),
            "reviews": list(reviews.values()),
            "safety": {
                "local_only": True,
                "quote_pack_generated": False,
                "submission_pack_generated": False,
                "submission_approved": False,
            },
        }
        _atomic_write_json(self._returnables_path(rfq_id, create=True), record)
        result = self.get_returnables_review_workspace(rfq_id)
        result["saved"] = True
        return result
