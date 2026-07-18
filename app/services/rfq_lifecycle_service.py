from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.services.rfq_recovery_service import RfqRecoveryService, classify_failure
from app.services.rfq_state_store import PROJECT_ROOT, RfqStateStore, utc_now_iso


LIFECYCLE_STATES = [
    "DISCOVERED",
    "QUALIFIED",
    "DOCUMENTS_ACQUIRED",
    "DOCUMENTS_PARSED",
    "PRICED",
    "SBD_COMPLETED",
    "QUOTE_PACK_READY",
    "SUBMISSION_READY",
    "SUBMITTED",
    "PROOF_CAPTURED",
    "ARCHIVED",
    "FAILED",
    "REVIEW_REQUIRED",
    "READY_FOR_RETRY",
    "REJECTED",
]

ADVANCE_ORDER = [
    "DISCOVERED",
    "QUALIFIED",
    "DOCUMENTS_ACQUIRED",
    "DOCUMENTS_PARSED",
    "PRICED",
    "SBD_COMPLETED",
    "QUOTE_PACK_READY",
    "SUBMISSION_READY",
]

EXCLUDED_KEYWORDS = {
    "catering",
    "medical consumables",
    "medical",
    "pharmaceutical",
    "it equipment",
    "information technology",
    "computer equipment",
    "laptop",
    "petrol",
    "diesel",
    "fuel",
}
SUPPLY_TERMS = {"supply", "delivery", "deliver", "goods", "consumables", "stationery", "ppe", "office"}
MIN_MARGIN = 25.0
MIN_PROFIT = 30000.0
MANUAL_PRICING_DIR = PROJECT_ROOT / "runtime" / "manual_pricing"

DISCOVERY_STORE_CANDIDATES = [
    PROJECT_ROOT / "runtime" / "live_rfqs.json",
    PROJECT_ROOT / "runtime" / "multi_portal_discovery" / "qualified_candidates_report.json",
    PROJECT_ROOT / "runtime" / "multi_portal_discovery" / "eligible_candidates_report.json",
    PROJECT_ROOT / "runtime" / "opportunity_extraction" / "high_confidence_opportunities.json",
]

DOCUMENT_URL_KEYS = (
    "document_url",
    "source_url",
    "detail_url",
    "pdf_url",
    "download_url",
    "attachment_url",
    "tender_document_url",
)

LIFECYCLE_QUEUE_MAP = {
    "DISCOVERED": "acquisition_queue",
    "QUALIFIED": "acquisition_queue",
    "DOCUMENTS_ACQUIRED": "parsing_queue",
    "DOCUMENTS_PARSED": "pricing_queue",
    "PRICED": "pricing_queue",
    "QUOTE_PACK_READY": "proof_queue",
    "SUBMISSION_READY": "proof_queue",
    "FAILED": "retry_queue",
    "REVIEW_REQUIRED": "retry_queue",
    "READY_FOR_RETRY": "retry_queue",
}

LIFECYCLE_QUEUE_CONCURRENCY = {
    "default": int(os.getenv("WORKER_CONCURRENCY", "2") or "2"),
    "acquisition_queue": int(os.getenv("ACQUISITION_WORKER_CONCURRENCY", "4") or "4"),
    "parsing_queue": int(os.getenv("PARSING_WORKER_CONCURRENCY", "3") or "3"),
    "pricing_queue": int(os.getenv("PRICING_WORKER_CONCURRENCY", "2") or "2"),
    "proof_queue": int(os.getenv("PROOF_WORKER_CONCURRENCY", "2") or "2"),
    "retry_queue": int(os.getenv("RETRY_WORKER_CONCURRENCY", "2") or "2"),
}

LIFECYCLE_QUEUE_WORKER_COUNT = {
    "default": int(os.getenv("QUEUE_WORKER_COUNT", "1") or "1"),
    "acquisition_queue": int(os.getenv("ACQUISITION_QUEUE_WORKER_COUNT", os.getenv("QUEUE_WORKER_COUNT", "1")) or "1"),
    "parsing_queue": int(os.getenv("PARSING_QUEUE_WORKER_COUNT", os.getenv("QUEUE_WORKER_COUNT", "1")) or "1"),
    "pricing_queue": int(os.getenv("PRICING_QUEUE_WORKER_COUNT", os.getenv("QUEUE_WORKER_COUNT", "1")) or "1"),
    "proof_queue": int(os.getenv("PROOF_QUEUE_WORKER_COUNT", os.getenv("QUEUE_WORKER_COUNT", "1")) or "1"),
    "retry_queue": int(os.getenv("RETRY_QUEUE_WORKER_COUNT", os.getenv("QUEUE_WORKER_COUNT", "1")) or "1"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _seconds_between(start: Any, end: Any) -> float:
    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)
    if not start_dt or not end_dt:
        return 0.0
    return round(max(0.0, (end_dt - start_dt).total_seconds()), 4)


def _extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "rfqs", "opportunities", "results", "documents"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _margin_percent(payload: Dict[str, Any]) -> float:
    margin = _safe_float(
        payload.get("estimated_margin")
        or payload.get("estimated_margin_pct")
        or payload.get("margin")
        or payload.get("margin_percent"),
        0.0,
    )
    if 0 < margin <= 1:
        return round(margin * 100.0, 4)
    return margin


def _profit_value(payload: Dict[str, Any]) -> float:
    explicit = _safe_float(
        payload.get("estimated_profit")
        or payload.get("profit")
        or payload.get("total_profit")
        or payload.get("profit_estimate")
        or payload.get("expected_profit"),
        0.0,
    )
    if explicit > 0:
        return explicit
    signal = payload.get("estimated_profit_signal")
    if isinstance(signal, dict):
        return _safe_float(signal.get("estimated_profit"), 0.0)
    return 0.0


def _http_urls_from_payload(payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for key in DOCUMENT_URL_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            urls.extend(str(v).strip() for v in value)
        elif value:
            urls.append(str(value).strip())
    for key in ("documents", "attachments", "supporting_documents", "links", "document_urls"):
        value = payload.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for inner_key in ("url", "href", "download_url", "document_url"):
                        if entry.get(inner_key):
                            urls.append(str(entry.get(inner_key)).strip())
                elif entry:
                    urls.append(str(entry).strip())
        elif isinstance(value, dict):
            for inner_key in ("url", "href", "download_url", "document_url"):
                if value.get(inner_key):
                    urls.append(str(value.get(inner_key)).strip())
    output: List[str] = []
    for url in urls:
        if url.startswith(("http://", "https://")) and url not in output:
            output.append(url)
    return output


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return text[:80] or "rfq"


def _stable_id(payload: Dict[str, Any]) -> str:
    explicit = payload.get("rfq_id") or payload.get("rfq_number") or payload.get("buyer_rfq_number") or payload.get("reference")
    if explicit:
        return _slug(str(explicit)).upper()
    blob = json.dumps(
        {
            "buyer": payload.get("buyer") or payload.get("buyer_name") or payload.get("department"),
            "title": payload.get("title") or payload.get("description"),
            "source": payload.get("source"),
        },
        sort_keys=True,
    )
    return "RFQ-" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12].upper()


class RfqLifecycleService:
    def __init__(self, store: RfqStateStore | None = None) -> None:
        self.store = store or RfqStateStore()
        self.recovery = RfqRecoveryService(self.store)

    def _policy_check(self, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        title = str(payload.get("title") or payload.get("description") or payload.get("name") or "")
        category = str(payload.get("category") or payload.get("classification") or "")
        blob = f"{title} {category} {payload.get('buyer') or payload.get('buyer_name') or ''}".lower()
        reasons: List[str] = []

        for keyword in EXCLUDED_KEYWORDS:
            if keyword in blob:
                reasons.append(f"excluded_keyword:{keyword}")

        briefing = payload.get("briefing_required")
        if briefing is True or "briefing session" in blob or "compulsory briefing" in blob:
            reasons.append("briefing_session_required")

        if not any(term in blob for term in SUPPLY_TERMS):
            reasons.append("not_supply_and_delivery")

        estimated_profit = _profit_value(payload)
        estimated_margin = _margin_percent(payload)
        if estimated_profit < MIN_PROFIT:
            reasons.append("below_minimum_profit")
        if estimated_margin < MIN_MARGIN:
            reasons.append("below_minimum_margin")

        return not reasons, reasons

    def _is_lifecycle_qualified(self, payload: Dict[str, Any]) -> bool:
        accepted, _ = self._policy_check(payload)
        if not accepted:
            return False
        if payload.get("qualified") is True:
            return True
        if payload.get("eligible") is True:
            return True
        if payload.get("quote_ready") is True:
            return True
        if str(payload.get("classification") or "").lower() == "highly_qualified":
            return True
        status = str(payload.get("pipeline_status") or payload.get("status") or "").lower()
        return any(token in status for token in ["eligible", "quote_ready", "qualified"])

    def _normalize_item(self, payload: Dict[str, Any], source: str = "api_ingest") -> Dict[str, Any]:
        now = utc_now_iso()
        rfq_id = _stable_id(payload)
        accepted, policy_reasons = self._policy_check(payload)
        current_state = str(payload.get("current_state") or ("DISCOVERED" if accepted else "REVIEW_REQUIRED")).upper()
        if current_state not in LIFECYCLE_STATES:
            current_state = "DISCOVERED" if accepted else "REVIEW_REQUIRED"

        item = {
            "rfq_id": rfq_id,
            "buyer_name": str(payload.get("buyer_name") or payload.get("buyer") or payload.get("department") or "Unknown Buyer"),
            "title": str(payload.get("title") or payload.get("description") or payload.get("name") or "Untitled RFQ"),
            "source": str(payload.get("source") or source),
            "current_state": current_state,
            "previous_state": str(payload.get("previous_state") or ""),
            "created_at": str(payload.get("created_at") or now),
            "updated_at": now,
            "retries": int(payload.get("retries") or 0),
            "max_retries": int(payload.get("max_retries") or 3),
            "failure_reason": str(payload.get("failure_reason") or ";".join(policy_reasons)),
            "failure_classification": classify_failure(";".join(policy_reasons)),
            "qualification_score": _safe_float(payload.get("qualification_score") or payload.get("confidence_score") or payload.get("ai_score")),
            "estimated_profit": _profit_value(payload),
            "estimated_margin": _margin_percent(payload),
            "document_paths": payload.get("document_paths") if isinstance(payload.get("document_paths"), list) else [],
            "document_urls": _http_urls_from_payload(payload),
            "quote_pack_path": str(payload.get("quote_pack_path") or ""),
            "submission_status": str(payload.get("submission_status") or "not_submitted"),
            "proof_path": str(payload.get("proof_path") or ""),
            "source_payload": {
                key: payload.get(key)
                for key in [
                    "rfq_number",
                    "buyer_rfq_number",
                    "reference_number",
                    "document_url",
                    "source_url",
                    "detail_url",
                    "documents",
                    "attachments",
                    "supporting_documents",
                    "links",
                    "items",
                    "line_items",
                    "closing_date",
                    "submission_method",
                ]
                if key in payload
            },
            "audit_log": payload.get("audit_log") if isinstance(payload.get("audit_log"), list) else [],
            "lifecycle_trace": payload.get("lifecycle_trace") if isinstance(payload.get("lifecycle_trace"), dict) else {
                "state_entered_at": {current_state: now},
                "stage_transition_timestamps": {current_state: now},
                "timeline_history": [],
                "retry_reasons": [],
                "recovery_reasons": [],
                "rejection_reasons": [],
            },
            "policy": {
                "supply_and_delivery_only": True,
                "excluded_categories": sorted(EXCLUDED_KEYWORDS),
                "minimum_margin_percent": MIN_MARGIN,
                "minimum_profit_zar": MIN_PROFIT,
                "final_submit_policy_control_required": True,
                "auto_final_submit_enabled": False,
                "policy_reasons": policy_reasons,
            },
        }
        audit_row = {
            "at": now,
            "event": "ingested",
            "rfq_id": item["rfq_id"],
            "state": item["current_state"],
            "source": item["source"],
            "policy_passed": accepted,
            "policy_reasons": policy_reasons,
        }
        item["audit_log"].append(audit_row)
        item["lifecycle_trace"]["timeline_history"].append(audit_row)
        return item

    def _append_audit(self, item: Dict[str, Any], event: str, **extra: Any) -> None:
        row = {"at": utc_now_iso(), "event": event, "rfq_id": item.get("rfq_id")}
        row.update(extra)
        item.setdefault("audit_log", []).append(row)
        trace = item.setdefault("lifecycle_trace", {})
        trace.setdefault("timeline_history", []).append(row)
        try:
            self.store.append_audit_events([row])
        except Exception:
            pass

    def _set_state(self, item: Dict[str, Any], state: str, reason: str = "") -> None:
        self._transition(item, state, reason=reason, event="advance_discovered")

    def _transition(self, item: Dict[str, Any], state: str, reason: str = "", event: str = "advance_lifecycle") -> None:
        previous = str(item.get("current_state") or "")
        now = utc_now_iso()
        trace = item.setdefault("lifecycle_trace", {})
        entered_at = trace.setdefault("state_entered_at", {})
        timestamps = trace.setdefault("stage_transition_timestamps", {})
        previous_entered_at = entered_at.get(previous) or item.get("updated_at") or item.get("created_at")
        stage_latency = _seconds_between(previous_entered_at, now)
        item["previous_state"] = previous
        item["current_state"] = state
        item["updated_at"] = now
        entered_at[state] = now
        timestamps[state] = now
        if state in {"FAILED", "REVIEW_REQUIRED"}:
            item["failure_reason"] = reason
            item["failure_classification"] = classify_failure(reason)
        if event in {"retry_ready", "golden_validation"} or "retry" in str(reason).lower():
            trace.setdefault("retry_reasons", []).append({"at": now, "state": state, "reason": reason})
        if event in {"review_recovery", "golden_validation"} and state not in {"REJECTED"}:
            trace.setdefault("recovery_reasons", []).append({"at": now, "from_state": previous, "to_state": state, "reason": reason})
        if state == "REJECTED":
            trace.setdefault("rejection_reasons", []).append({"at": now, "from_state": previous, "reason": reason})
        self._append_audit(
            item,
            event,
            from_state=previous,
            to_state=state,
            reason=reason,
            stage_latency_seconds=stage_latency,
            success=state not in {"FAILED", "REVIEW_REQUIRED", "REJECTED"},
        )

    def _live_store_index(self) -> Dict[str, Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            from app.services.live_rfq_store import read_live_rfqs

            rows.extend(_extract_items(read_live_rfqs()))
        except Exception:
            live_store = PROJECT_ROOT / "runtime" / "live_rfqs.json"
            if live_store.exists():
                try:
                    rows.extend(_extract_items(json.loads(live_store.read_text(encoding="utf-8"))))
                except Exception:
                    pass
        index: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in {
                _stable_id(row),
                str(row.get("rfq_id") or ""),
                str(row.get("rfq_number") or ""),
                str(row.get("buyer_rfq_number") or ""),
                str(row.get("reference_number") or ""),
                str(row.get("title") or ""),
            }:
                clean = key.strip()
                if clean:
                    index[clean.upper()] = row
        return index

    def _enrich_lifecycle_item(self, item: Dict[str, Any], live_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        keys = [
            str(item.get("rfq_id") or ""),
            str(item.get("title") or ""),
            str((item.get("source_payload") or {}).get("rfq_number") or ""),
            str((item.get("source_payload") or {}).get("buyer_rfq_number") or ""),
        ]
        source_row: Dict[str, Any] = {}
        for key in keys:
            source_row = live_index.get(key.strip().upper()) or {}
            if source_row:
                break
        enriched = dict(source_row)
        source_payload = item.get("source_payload") if isinstance(item.get("source_payload"), dict) else {}
        enriched.update(source_payload)
        enriched.update({k: v for k, v in item.items() if v not in (None, "", [])})
        enriched["rfq_id"] = item.get("rfq_id")
        enriched["buyer_name"] = item.get("buyer_name")
        enriched["title"] = item.get("title")
        return enriched

    def _manual_pricing_path(self, rfq_id: str, create: bool = False) -> Path:
        if create:
            MANUAL_PRICING_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", str(rfq_id or "").strip()).strip("-") or "rfq"
        path = (MANUAL_PRICING_DIR / f"{safe_name}.json").resolve()
        root = MANUAL_PRICING_DIR.resolve()
        if root not in path.parents and path != root:
            raise ValueError("Unsafe manual pricing path")
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _manual_pricing_file(self, rfq_id: str) -> Dict[str, Any]:
        try:
            path = self._manual_pricing_path(rfq_id)
            if path.exists() and path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _manual_pricing_line_item(self, row: Dict[str, Any], index: int, vat_rate: float = 15.0) -> Tuple[Dict[str, Any], List[str]]:
        issues: List[str] = []
        description = str(row.get("description") or row.get("item_description") or row.get("name") or "").strip()
        if not description:
            issues.append(f"line_{index}_missing_description")
            description = f"Line {index}"

        quantity = _safe_float(row.get("quantity") or row.get("qty") or row.get("line_quantity"), 0.0)
        if quantity <= 0:
            issues.append(f"line_{index}_invalid_quantity")
            quantity = 0.0

        unit = str(row.get("unit") or row.get("uom") or "each").strip() or "each"
        unit_cost = _safe_float(row.get("unit_cost") or row.get("cost") or row.get("buy_cost"), 0.0)
        if unit_cost < 0:
            issues.append(f"line_{index}_invalid_unit_cost")
            unit_cost = 0.0

        markup_percent = _safe_float(row.get("markup_percent") or row.get("markup") or row.get("markup_pct"), 0.0)
        selling_price = _safe_float(
            row.get("selling_price")
            or row.get("selling_price_ex_vat")
            or row.get("unit_price")
            or row.get("unit_price_ex_vat"),
            0.0,
        )
        if selling_price <= 0 and unit_cost > 0:
            selling_price = round(unit_cost * (1 + max(0.0, markup_percent) / 100.0), 2)
        if selling_price <= 0:
            issues.append(f"line_{index}_invalid_selling_price")
            selling_price = 0.0

        total_ex_vat = _safe_float(row.get("total") or row.get("total_ex_vat") or row.get("line_total"), 0.0)
        if total_ex_vat <= 0 and quantity > 0 and selling_price > 0:
            total_ex_vat = round(quantity * selling_price, 2)
        vat_rate_value = _safe_float(row.get("vat_rate"), vat_rate)
        vat_value = _safe_float(row.get("vat") or row.get("vat_amount"), 0.0)
        if vat_value <= 0 and total_ex_vat > 0:
            vat_value = round(total_ex_vat * max(0.0, vat_rate_value) / 100.0, 2)
        total_incl_vat = _safe_float(row.get("total_incl_vat"), 0.0)
        if total_incl_vat <= 0 and total_ex_vat > 0:
            total_incl_vat = round(total_ex_vat + vat_value, 2)

        unit_cost_total = round(unit_cost * quantity, 2)
        profit = round(total_ex_vat - unit_cost_total, 2)
        line_margin = round((profit / total_ex_vat) * 100.0, 2) if total_ex_vat > 0 else 0.0

        return (
            {
                "item_no": row.get("item_no") or row.get("line_no") or index,
                "description": description,
                "quantity": quantity,
                "unit": unit,
                "unit_cost": round(unit_cost, 2),
                "markup_percent": round(markup_percent, 2),
                "selling_price": round(selling_price, 2),
                "selling_price_ex_vat": round(selling_price, 2),
                "vat_rate": round(vat_rate_value, 2),
                "vat": round(vat_value, 2),
                "vat_amount": round(vat_value, 2),
                "total": round(total_ex_vat, 2),
                "total_ex_vat": round(total_ex_vat, 2),
                "total_incl_vat": round(total_incl_vat, 2),
                "supplier_source_note": str(row.get("supplier_source_note") or row.get("source_note") or row.get("note") or "").strip(),
                "unit_cost_total": unit_cost_total,
                "profit": round(profit, 2),
                "margin_percent": line_margin,
            },
            issues,
        )

    def _manual_pricing_totals(self, line_items: List[Dict[str, Any]], validation_issues: Optional[List[str]] = None) -> Dict[str, Any]:
        subtotal_ex_vat = round(sum(_safe_float(item.get("total_ex_vat") or item.get("total"), 0.0) for item in line_items), 2)
        vat_total = round(sum(_safe_float(item.get("vat_amount") or item.get("vat"), 0.0) for item in line_items), 2)
        grand_total_inc_vat = round(sum(_safe_float(item.get("total_incl_vat"), 0.0) for item in line_items), 2)
        total_cost = round(sum(_safe_float(item.get("unit_cost_total"), 0.0) for item in line_items), 2)
        estimated_profit = round(subtotal_ex_vat - total_cost, 2)
        margin_percent = round((estimated_profit / subtotal_ex_vat) * 100.0, 2) if subtotal_ex_vat > 0 else 0.0
        blockers: List[str] = list(validation_issues or [])
        if subtotal_ex_vat <= 0:
            blockers.append("missing_manual_pricing_total")
        if estimated_profit < MIN_PROFIT:
            blockers.append("below_minimum_profit")
        if margin_percent < MIN_MARGIN:
            blockers.append("below_minimum_margin")
        return {
            "subtotal_ex_vat": subtotal_ex_vat,
            "vat_total": vat_total,
            "grand_total_inc_vat": grand_total_inc_vat,
            "total_cost": total_cost,
            "estimated_profit": estimated_profit,
            "margin_percent": margin_percent,
            "minimum_profit_required": MIN_PROFIT,
            "minimum_margin_required": MIN_MARGIN,
            "verified": not blockers,
            "blockers": list(blockers),
        }

    def _manual_pricing_validation(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
        vat_rate = _safe_float(payload.get("vat_rate"), 15.0)
        raw_items = payload.get("line_items") or payload.get("items") or []
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        if not isinstance(raw_items, list):
            raw_items = []
        line_items: List[Dict[str, Any]] = []
        issues: List[str] = []
        for index, row in enumerate(raw_items, start=1):
            if not isinstance(row, dict):
                issues.append(f"line_{index}_invalid_structure")
                continue
            normalized, row_issues = self._manual_pricing_line_item(row, index, vat_rate=vat_rate)
            line_items.append(normalized)
            issues.extend(row_issues)

        totals = self._manual_pricing_totals(line_items, issues)
        deduped: List[str] = []
        for reason in list(totals.get("blockers") or []) + issues:
            clean = str(reason or "").strip()
            if clean and clean not in deduped:
                deduped.append(clean)
        totals["blockers"] = deduped
        totals["verified"] = not deduped
        return line_items, totals, deduped

    def _resolve_manual_pricing_item(self, rfq_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
        item = self.store.get_item(rfq_id)
        if item:
            return item, "lifecycle"

        selector = str(rfq_id or "").strip().upper()
        for row in self._live_store_index().values():
            values = {
                str(row.get("rfq_id") or ""),
                str(row.get("rfq_number") or ""),
                str(row.get("buyer_rfq_number") or ""),
                str(row.get("reference_number") or ""),
                str(row.get("id") or ""),
                str(row.get("title") or ""),
            }
            if any(selector == str(value).strip().upper() for value in values if value):
                return self._normalize_item(row, source="live_rfq_store"), "live"

        return None, ""

    def get_manual_pricing(self, rfq_id: str) -> Dict[str, Any]:
        item, _ = self._resolve_manual_pricing_item(rfq_id)
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        saved = self._manual_pricing_file(rfq_id)
        if not saved:
            return {
                "status": "ok",
                "rfq_id": rfq_id,
                "manual_pricing": {},
                "saved": False,
                "pricing_review_status": item.get("pricing_review_status", ""),
                "pricing_verification_status": item.get("pricing_verification_status", ""),
            }
        return {
            "status": "ok",
            "rfq_id": rfq_id,
            "manual_pricing": saved,
            "saved": True,
            "pricing_review_status": saved.get("pricing_review_status") or item.get("pricing_review_status", ""),
            "pricing_verification_status": saved.get("pricing_verification_status") or item.get("pricing_verification_status", ""),
        }

    def save_manual_pricing(self, rfq_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        item, item_source = self._resolve_manual_pricing_item(rfq_id)
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}

        line_items, totals, blockers = self._manual_pricing_validation(payload)
        now = utc_now_iso()
        manual_pricing_path = self._manual_pricing_path(rfq_id, create=True)
        record = {
            "version": "manual_pricing_v1",
            "rfq_id": rfq_id,
            "reference_number": item.get("rfq_id") or rfq_id,
            "buyer_name": item.get("buyer_name", ""),
            "title": item.get("title", ""),
            "pricing_review_status": "PRICING_VERIFIED" if totals.get("verified") else "REVIEW_REQUIRED_PRICING",
            "pricing_verification_status": "verified" if totals.get("verified") else "needs_review",
            "manual_pricing_required": not totals.get("verified"),
            "manual_pricing_required_reason": "" if totals.get("verified") else "pricing schedule requires manual completion",
            "pricing_action": "prepare manual pricing schedule" if not totals.get("verified") else "manual pricing verified",
            "pricing_review_action": "prepare manual pricing schedule" if not totals.get("verified") else "manual pricing verified",
            "pricing_verified_at": now if totals.get("verified") else "",
            "saved_at": now,
            "updated_at": now,
            "operator_note": str(payload.get("operator_note") or payload.get("note") or "").strip(),
            "line_items": line_items,
            "totals": totals,
            "validation": {
                "verified": bool(totals.get("verified")),
                "blockers": blockers,
                "minimum_margin_required": MIN_MARGIN,
                "minimum_profit_required": MIN_PROFIT,
            },
            "buyer_pack_path": item.get("buyer_pack_path", item.get("live_buyer_pack_path", "")),
            "technical_spec_files": item.get("technical_spec_files", []),
            "returnable_files": item.get("returnable_files", []),
            "safety": {
                "local_only": True,
                "not_submitted": True,
                "not_uploaded": True,
                "not_emailed": True,
                "final_submit_locked": True,
                "manual_only": True,
                "live_rfq_store_modified": False,
            },
        }
        manual_pricing_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

        try:
            item["manual_pricing_path"] = str(manual_pricing_path.relative_to(PROJECT_ROOT))
        except ValueError:
            item["manual_pricing_path"] = str(manual_pricing_path)
        item["manual_pricing_line_items"] = line_items
        item["manual_pricing_totals"] = totals
        item["manual_pricing_validation"] = record["validation"]
        item["pricing_totals"] = totals
        item["pricing_line_items"] = line_items
        item["pricing_verification_status"] = record["pricing_verification_status"]
        item["pricing_review_status"] = record["pricing_review_status"]
        item["manual_pricing_required"] = not totals.get("verified")
        item["manual_pricing_required_reason"] = record["manual_pricing_required_reason"]
        item["pricing_action"] = record["pricing_action"]
        item["pricing_review_action"] = record["pricing_review_action"]
        item["pricing_verified_at"] = record["pricing_verified_at"]
        item["quote_candidate_status"] = "quote_candidate" if totals.get("verified") else "manual_pricing_required"
        item["updated_at"] = now
        if item_source != "lifecycle":
            item.setdefault("source", "live_rfq_store")
            item.setdefault("created_at", now)
        if totals.get("verified"):
            self._transition(item, "PRICING_VERIFIED", reason="manual pricing validated and verified", event="manual_pricing_verified")
        else:
            self._append_audit(item, "manual_pricing_saved", reason="manual pricing requires review", blockers=blockers, success=False)

        self.store.upsert_item(item)
        return {
            "status": "ok" if totals.get("verified") else "needs_review",
            "rfq_id": rfq_id,
            "manual_pricing_path": item.get("manual_pricing_path", ""),
            "pricing_review_status": item.get("pricing_review_status", ""),
            "pricing_verification_status": item.get("pricing_verification_status", ""),
            "manual_pricing_required": bool(item.get("manual_pricing_required")),
            "manual_pricing_required_reason": item.get("manual_pricing_required_reason", ""),
            "pricing_action": item.get("pricing_action", ""),
            "pricing_review_action": item.get("pricing_review_action", ""),
            "verified": bool(totals.get("verified")),
            "line_items": line_items,
            "totals": totals,
            "blockers": blockers,
            "item": item,
            "safety": record["safety"],
        }

    def _split_reason_codes(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(row).strip() for row in value if str(row).strip()]
        return [part.strip() for part in str(value).split(";") if part.strip()]

    def _terminal_review_blocker_codes(self, item: Dict[str, Any], enriched: Dict[str, Any]) -> List[str]:
        reasons = set(self._split_reason_codes(item.get("failure_reason")))
        reasons.update(self._split_reason_codes(item.get("validation_terminal_reason")))
        decision = item.get("review_recovery_decision") if isinstance(item.get("review_recovery_decision"), dict) else {}
        reasons.update(self._split_reason_codes(decision.get("reason")))

        closing_ok, closing_reason = self._closing_date_status(enriched)
        if not closing_ok and closing_reason in {"missing_closing_date", "closing_date_passed"}:
            reasons.add(closing_reason)

        terminal: List[str] = []
        for code in ("not_supply_and_delivery", "closing_date_passed", "missing_closing_date"):
            if code in reasons:
                terminal.append(code)
        if "missing_documents" in reasons and "closing_date_passed" in reasons:
            terminal.append("expired_with_missing_documents")
        return terminal

    def reject_terminal_review_items(self, limit: int = 100) -> Dict[str, Any]:
        review_items = [item for item in self.store.list_items() if str(item.get("current_state") or "").upper() == "REVIEW_REQUIRED"]
        review_items = review_items[: max(1, int(limit))]
        live_index = self._live_store_index()
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        rejected_count = 0
        skipped_count = 0

        for item in review_items:
            rfq_id = str(item.get("rfq_id") or "")
            enriched = self._enrich_lifecycle_item(item, live_index)
            blocker_reasons = self._terminal_review_blocker_codes(item, enriched)
            if not blocker_reasons:
                skipped_count += 1
                processed.append({"rfq_id": rfq_id, "state": item.get("current_state"), "result": "skipped", "blocker_reasons": self._split_reason_codes(item.get("failure_reason"))})
                continue

            item["terminal_review_cleanup"] = {"action": "rejected", "blocker_reasons": blocker_reasons, "reviewed_at": utc_now_iso()}
            item["validation_terminal_reason"] = ";".join(blocker_reasons)
            self._transition(item, "REJECTED", ";".join(blocker_reasons), event="terminal_review_cleanup")
            rejected_count += 1
            changed_items.append(item)
            processed.append({"rfq_id": rfq_id, "state": item.get("current_state"), "result": "rejected", "blocker_reasons": blocker_reasons})

        if changed_items:
            self.store.update_many(changed_items, {"failed": 0})

        return {
            "status": "ok",
            "processed_count": len(processed),
            "rejected_count": rejected_count,
            "skipped_count": skipped_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }

    def validate_visible_opportunities(
        self,
        limit: int = 250,
        timeout_seconds: int = 8,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
        generate_local_pack: bool = False,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        live_items = list(self._live_store_index().values())[: max(1, int(limit))]
        lifecycle_items = self.store.list_items()
        lifecycle_index: Dict[str, Dict[str, Any]] = {}
        for current in lifecycle_items:
            for key in {
                str(current.get("rfq_id") or ""),
                str(current.get("title") or ""),
                str((current.get("source_payload") or {}).get("rfq_number") or ""),
                str((current.get("source_payload") or {}).get("buyer_rfq_number") or ""),
                str((current.get("source_payload") or {}).get("reference_number") or ""),
            }:
                clean = key.strip().upper()
                if clean:
                    lifecycle_index[clean] = current

        processed: List[Dict[str, Any]] = []
        promoted_count = 0
        blocked_count = 0
        for live_row in live_items:
            keys = [
                str(live_row.get("rfq_id") or ""),
                str(live_row.get("rfq_number") or ""),
                str(live_row.get("buyer_rfq_number") or ""),
                str(live_row.get("reference_number") or ""),
                str(live_row.get("title") or ""),
            ]
            lifecycle_item: Dict[str, Any] = {}
            for key in keys:
                lifecycle_item = lifecycle_index.get(key.strip().upper()) or {}
                if lifecycle_item:
                    break
            item = dict(lifecycle_item or self._normalize_item(live_row, source="visible_bulk_validation"))
            enriched = self._enrich_lifecycle_item(item, self._live_store_index())
            accepted, policy_reasons = self._policy_check(enriched)
            has_documents = bool(enriched.get("document_paths") or enriched.get("downloaded_documents") or _http_urls_from_payload(enriched))
            has_pricing = bool(
                enriched.get("manual_pricing_totals")
                or enriched.get("pricing_totals")
                or enriched.get("line_items")
                or enriched.get("items")
                or str(enriched.get("pricing_verification_status") or "").lower() == "verified"
            )
            promoted = bool(accepted and has_documents and has_pricing)
            promoted_count += 1 if promoted else 0
            blocked_count += 0 if promoted else 1
            processed.append(
                {
                    "rfq_id": item.get("rfq_id") or _stable_id(enriched),
                    "title": item.get("title") or enriched.get("title", ""),
                    "accepted_by_policy": accepted,
                    "policy_reasons": policy_reasons,
                    "document_present": has_documents,
                    "pricing_present": has_pricing,
                    "promoted_quote_ready": promoted,
                    "dry_run": bool(dry_run),
                    "recommended_action": "quote_ready_review" if promoted else "manual_review_required",
                }
            )

        return {
            "status": "ok",
            "compatibility_route": True,
            "dry_run": bool(dry_run),
            "generate_local_pack_requested": bool(generate_local_pack),
            "external_validation_executed": False,
            "live_rfq_store_modified": False,
            "lifecycle_store_modified": False,
            "requested_limit": int(limit),
            "processed_count": len(processed),
            "promoted_count": promoted_count,
            "blocked_count": blocked_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
            "compatibility_note": "Recovered route is read-only by default and does not perform historical live-store upserts.",
        }

    def _document_acquisition_step(
        self,
        enriched: Dict[str, Any],
        timeout_seconds: int,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        try:
            from app.services.rfq_document_acquisition_engine import acquire_rfq_documents

            return acquire_rfq_documents(
                enriched,
                timeout_seconds=timeout_seconds,
                max_concurrent_downloads=max_concurrent_downloads,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "downloaded_count": 0, "downloaded_files": []}

    def _document_parse_step(self, enriched: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
        try:
            from app.services.rfq_document_intelligence import analyse_rfq_documents

            return analyse_rfq_documents(enriched, timeout_seconds=timeout_seconds)
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "text_extraction": [], "document_intelligence": {}}

    def _price_step(self, enriched: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from app.services.real_profit_pricing_service import enrich_with_real_profit_pricing

            return enrich_with_real_profit_pricing(enriched)
        except Exception as exc:
            return {"status": "failed", "priced": False, "error": str(exc), "payload": enriched}

    def _normalise_v43_line_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = payload.get("line_items") or payload.get("items") or []
        if not isinstance(raw_items, list) or not raw_items:
            raw_items = [{"description": payload.get("title") or "Supply and delivery", "quantity": 1, "unit": "lot"}]

        profit = _profit_value(payload)
        margin = _margin_percent(payload) or MIN_MARGIN
        sell_excl = _safe_float((payload.get("pricing_summary") or {}).get("total_sell_excl_vat"), 0.0)
        if sell_excl <= 0 and profit > 0 and margin > 0:
            sell_excl = round(profit / (margin / 100.0), 2)
        if sell_excl <= 0:
            sell_excl = round(MIN_PROFIT / (MIN_MARGIN / 100.0), 2)

        quantities: List[float] = []
        for row in raw_items:
            if not isinstance(row, dict):
                quantities.append(1.0)
                continue
            qty = _safe_float(row.get("quantity") or row.get("qty"), 1.0)
            quantities.append(qty if qty > 0 else 1.0)
        total_qty = max(sum(quantities), 1.0)

        line_items: List[Dict[str, Any]] = []
        for idx, row in enumerate(raw_items, start=1):
            if not isinstance(row, dict):
                row = {"description": str(row)}
            qty = quantities[idx - 1]
            explicit_unit = _safe_float(row.get("unit_price_excl_vat") or row.get("unit_price") or row.get("price"), 0.0)
            unit_price = explicit_unit if explicit_unit > 0 else round(sell_excl / total_qty, 2)
            total_excl = round(unit_price * qty, 2)
            vat = round(total_excl * 0.15, 2)
            line_items.append(
                {
                    "item_no": row.get("item_no") or row.get("line_number") or idx,
                    "description": row.get("description") or row.get("name") or payload.get("title") or "Supply and delivery",
                    "original_description": row.get("original_description") or row.get("description") or "",
                    "quantity": qty,
                    "unit": row.get("unit") or "each",
                    "unit_price_excl_vat": unit_price,
                    "total_excl_vat": total_excl,
                    "vat_amount": vat,
                    "total_incl_vat": round(total_excl + vat, 2),
                    "currency": "ZAR",
                    "pricing_method": row.get("pricing_method") or "rfq_lifecycle_real_profit_pricing",
                    "confidence": row.get("confidence") or payload.get("qualification_score"),
                }
            )
        return line_items

    def _build_quote_pack_step(self, priced_payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from app.services.quote_pack_v44_service import generate_quote_pack_from_v43_payload

            return generate_quote_pack_from_v43_payload(
                priced_payload,
                buyer_rfq_number=priced_payload.get("buyer_rfq_number") or priced_payload.get("rfq_number") or priced_payload.get("rfq_id"),
                output_dir="runtime/rfq_lifecycle/quote_packs",
            )
        except Exception as exc:
            return {"status": "failed", "message": str(exc)}

    def _read_json_file(self, path_value: Any) -> Dict[str, Any]:
        try:
            path = Path(str(path_value or ""))
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if path.exists() and path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
        return {}

    def _controlled_submission_manifest(self, item: Dict[str, Any], proof_timestamp: str) -> Dict[str, Any]:
        artifacts = item.get("quote_pack_artifacts") if isinstance(item.get("quote_pack_artifacts"), dict) else {}
        quote_metadata = self._read_json_file(artifacts.get("metadata_json"))
        quote_manifest = self._read_json_file(artifacts.get("submission_manifest_json"))
        return {
            "rfq_id": item.get("rfq_id"),
            "rfq_number": item.get("rfq_id"),
            "buyer_name": item.get("buyer_name"),
            "title": item.get("title"),
            "quote_number": item.get("quote_number"),
            "quote_pack_path": item.get("quote_pack_path"),
            "quote_pack_artifacts": artifacts,
            "quote_pack_metadata": quote_metadata,
            "quote_pack_submission_manifest": quote_manifest,
            "estimated_profit": item.get("estimated_profit"),
            "estimated_margin": item.get("estimated_margin"),
            "submission_channel": "controlled_simulation",
            "submission_outcome": "simulated_ready_proof_captured",
            "proof_timestamp": proof_timestamp,
            "safety": {
                "dry_run_only": True,
                "email_send_executed": False,
                "portal_upload_executed": False,
                "portal_final_submit_executed": False,
                "final_submit_hard_blocked": True,
                "captcha_bypass": False,
                "policy_control_preserved": True,
            },
        }

    def _generate_controlled_proof_package(self, item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from app.services.submission_proof_artifact_service import build_submission_proof_artifacts

            proof_timestamp = utc_now_iso()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            rfq_id = str(item.get("rfq_id") or "RFQ")
            proof_root = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "proofs" / f"{_slug(rfq_id)}-{stamp}"
            proof_root.mkdir(parents=True, exist_ok=True)

            manifest = self._controlled_submission_manifest(item, proof_timestamp)
            manifest_path = proof_root / "controlled_submission_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            attempt_log = {
                "rfq_id": rfq_id,
                "started_at": proof_timestamp,
                "completed_at": utc_now_iso(),
                "mode": "controlled_submission_simulation",
                "steps": [
                    {"step": "load_submission_ready_rfq", "status": "ok"},
                    {"step": "load_quote_pack_metadata", "status": "ok"},
                    {"step": "generate_submission_manifest", "status": "ok", "path": str(manifest_path)},
                    {"step": "simulate_submission_outcome", "status": "ok", "outcome": "proof_captured_no_send_no_submit"},
                    {"step": "archive_proof_artifacts", "status": "ok"},
                ],
                "safety": manifest["safety"],
            }
            attempt_log_path = proof_root / "submission_attempt_log.json"
            attempt_log_path.write_text(json.dumps(attempt_log, indent=2, ensure_ascii=False), encoding="utf-8")

            artifacts = item.get("quote_pack_artifacts") if isinstance(item.get("quote_pack_artifacts"), dict) else {}
            proof_record = {
                "rfq_number": rfq_id,
                "buyer_rfq_number": rfq_id,
                "buyer_name": item.get("buyer_name"),
                "title": item.get("title"),
                "quote_number": item.get("quote_number"),
                "quote_reference": item.get("quote_number") or rfq_id,
                "status": "controlled_simulation",
                "submission_status": "controlled_submission_simulated_proof_captured",
                "submission_method": "controlled_simulation",
                "recipient_email": "",
                "submitted_at": proof_timestamp,
                "submission_message": "Controlled submission simulation only. No email sent and no portal final submit executed.",
                "total_profit": item.get("estimated_profit"),
                "submission_email_ready": False,
                "submission_email_sent": False,
                "submission_email_sent_at_utc": "",
                "quote_pack_pdf_path": artifacts.get("quote_html") or artifacts.get("pricing_csv") or "",
                "submission_pack_manifest_path": str(manifest_path),
                "metadata": {
                    "buyer_name": item.get("buyer_name"),
                    "title": item.get("title"),
                    "buyer_rfq_number": rfq_id,
                    "quote_reference": item.get("quote_number") or rfq_id,
                    "pdf_output_dir": str(proof_root),
                },
                "email_send_result": {
                    "attempted": False,
                    "message": "Email send hard-blocked by lifecycle controlled submission simulation.",
                    "used_recipients": [],
                    "used_attachments": [str(v) for v in artifacts.values() if v],
                },
            }
            proof_artifacts = build_submission_proof_artifacts(proof_record)
            receipt_pdf = proof_artifacts.get("submission_receipt_pdf_path") or ""
            receipt_json = proof_artifacts.get("submission_receipt_json_path") or ""

            archive_manifest = {
                **manifest,
                "proof_directory": proof_artifacts.get("submission_proof_directory") or str(proof_root),
                "proof_manifest": str(manifest_path),
                "proof_receipt_json": receipt_json,
                "proof_receipt_pdf": receipt_pdf,
                "submission_attempt_log": str(attempt_log_path),
            }
            archive_path = proof_root / "proof_archive_manifest.json"
            archive_path.write_text(json.dumps(archive_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            return {
                "status": "ok",
                "proof_path": receipt_pdf,
                "proof_manifest": str(archive_path),
                "proof_timestamp": proof_timestamp,
                "submission_attempt_log": attempt_log,
                "submission_attempt_log_path": str(attempt_log_path),
                "controlled_submission_manifest": str(manifest_path),
                "proof_artifacts": proof_artifacts,
            }
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def run_controlled_submission(self, limit: int = 25) -> Dict[str, Any]:
        items = [item for item in self.store.list_items() if item.get("current_state") == "SUBMISSION_READY"]
        items = items[: max(1, int(limit))]
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        proof_captured_count = 0
        review_required_count = 0

        for item in items:
            rfq_id = str(item.get("rfq_id") or "")
            try:
                accepted, reasons = self._policy_check(item)
                if not accepted:
                    self._transition(item, "REVIEW_REQUIRED", ";".join(reasons), event="controlled_submission")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                if not item.get("quote_pack_path") or not isinstance(item.get("quote_pack_artifacts"), dict):
                    self._transition(item, "REVIEW_REQUIRED", "missing_quote_pack_for_proof_capture", event="controlled_submission")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                proof = self._generate_controlled_proof_package(item)
                if proof.get("status") != "ok":
                    self._transition(item, "REVIEW_REQUIRED", proof.get("error") or "proof_generation_failed", event="controlled_submission")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                item["proof_path"] = str(proof.get("proof_path") or "")
                item["proof_manifest"] = str(proof.get("proof_manifest") or "")
                item["proof_timestamp"] = str(proof.get("proof_timestamp") or utc_now_iso())
                item["submission_attempt_log"] = proof.get("submission_attempt_log")
                item["submission_attempt_log_path"] = str(proof.get("submission_attempt_log_path") or "")
                item["controlled_submission_manifest"] = str(proof.get("controlled_submission_manifest") or "")
                item["proof_artifacts"] = proof.get("proof_artifacts") if isinstance(proof.get("proof_artifacts"), dict) else {}
                item["submission_status"] = "controlled_submission_simulated_proof_captured"
                item["submission_safety"] = {
                    "dry_run_only": True,
                    "email_send_executed": False,
                    "portal_upload_executed": False,
                    "portal_final_submit_executed": False,
                    "final_submit_hard_blocked": True,
                    "captcha_bypass": False,
                }
                self._transition(item, "PROOF_CAPTURED", "controlled_submission_simulated_proof_captured", event="controlled_submission")
                proof_captured_count += 1
                processed.append(
                    {
                        "rfq_id": rfq_id,
                        "state": item["current_state"],
                        "proof_path": item["proof_path"],
                        "proof_manifest": item["proof_manifest"],
                    }
                )
                changed_items.append(item)
            except Exception as exc:
                self._transition(item, "REVIEW_REQUIRED", f"proof_generation_failed:{exc}", event="controlled_submission")
                review_required_count += 1
                processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(changed_items, {"proof_captured": proof_captured_count, "advanced": proof_captured_count})

        return {
            "status": "ok",
            "processed_count": len(processed),
            "proof_captured_count": proof_captured_count,
            "review_required_count": review_required_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }

    def _looks_like_direct_document_url(self, url: str) -> bool:
        try:
            suffix = Path(url.split("?", 1)[0]).suffix.lower()
        except Exception:
            suffix = ""
        blob = url.lower()
        return suffix in {".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".csv"} or any(
            token in blob for token in ["download", "attachment", "document", "rfq", "quotation"]
        )

    def _looks_like_generic_source_url(self, url: str) -> bool:
        blob = url.lower().rstrip("/")
        generic_terms = [
            "etenders.gov.za",
            "/home/opportunities",
            "/tenders",
            "/tender",
            "/procurement",
            "/supply-chain-management",
            "/scm",
            "opportunities",
            "bulletin",
        ]
        if not blob:
            return False
        if self._looks_like_direct_document_url(blob):
            return False
        return any(term in blob for term in generic_terms)

    def _review_recovery_decision(self, item: Dict[str, Any], enriched: Dict[str, Any]) -> Dict[str, Any]:
        failure_reason = str(item.get("failure_reason") or "").lower()
        urls = _http_urls_from_payload(enriched)
        direct_urls = [url for url in urls if self._looks_like_direct_document_url(url)]
        generic_urls = [url for url in urls if self._looks_like_generic_source_url(url)]
        accepted, policy_reasons = self._policy_check(enriched)

        if not accepted:
            return {
                "action": "reject",
                "reason": ";".join(policy_reasons) or "policy_rejected",
                "urls": urls,
                "direct_urls": direct_urls,
                "generic_urls": generic_urls,
            }

        if direct_urls:
            return {
                "action": "retry_document_acquisition",
                "reason": failure_reason or "recoverable_document_url",
                "urls": urls,
                "direct_urls": direct_urls,
                "generic_urls": generic_urls,
            }

        if urls and not generic_urls:
            return {
                "action": "retry_document_acquisition",
                "reason": failure_reason or "recoverable_source_url",
                "urls": urls,
                "direct_urls": direct_urls,
                "generic_urls": generic_urls,
            }

        if urls or "missing_document" in failure_reason or "document" in failure_reason:
            return {
                "action": "ready_for_retry",
                "reason": "source_rescan_required",
                "urls": urls,
                "direct_urls": direct_urls,
                "generic_urls": generic_urls,
            }

        return {
            "action": "reject",
            "reason": failure_reason or "unusable_review_required_item",
            "urls": urls,
            "direct_urls": direct_urls,
            "generic_urls": generic_urls,
        }

    def _try_recover_documents(
        self,
        item: Dict[str, Any],
        enriched: Dict[str, Any],
        timeout_seconds: int,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        existing_paths = [str(path) for path in item.get("document_paths", []) if path]
        urls = _http_urls_from_payload(enriched)
        item["document_urls"] = urls
        acquisition = self._document_acquisition_step(
            enriched,
            timeout_seconds=timeout_seconds,
            max_concurrent_downloads=max_concurrent_downloads,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        downloads = acquisition.get("downloaded_files") if isinstance(acquisition.get("downloaded_files"), list) else []
        downloaded_paths = [
            str(row.get("path"))
            for row in downloads
            if isinstance(row, dict) and row.get("status") == "downloaded" and row.get("path")
        ]

        if not downloaded_paths and not existing_paths:
            return {
                "status": "not_recovered",
                "reason": "no_documents_acquired",
                "acquisition": acquisition,
                "downloaded_paths": [],
            }

        item["document_paths"] = sorted(set(existing_paths + downloaded_paths))
        item["document_acquisition_report_path"] = acquisition.get("report_path", item.get("document_acquisition_report_path", ""))
        item["document_acquisition_confidence"] = acquisition.get("confidence", item.get("document_acquisition_confidence", 0.0))

        parse_payload = dict(enriched)
        parse_payload["document_url"] = urls
        parsing = self._document_parse_step(parse_payload, timeout_seconds=timeout_seconds)
        text_rows = parsing.get("text_extraction") if isinstance(parsing.get("text_extraction"), list) else []
        parsed_count = sum(1 for row in text_rows if isinstance(row, dict) and int(row.get("text_length") or 0) > 0)
        intelligence = parsing.get("document_intelligence") if isinstance(parsing.get("document_intelligence"), dict) else {}

        if parsing.get("quote_safe") is False:
            return {
                "status": "documents_acquired",
                "target_state": "DOCUMENTS_ACQUIRED",
                "reason": parsing.get("quote_block_reason") or "document_intelligence_review_required",
                "acquisition": acquisition,
                "parsing": parsing,
                "downloaded_paths": downloaded_paths,
            }

        if parsed_count > 0 or intelligence:
            item["document_intelligence_report_path"] = parsing.get("report_path", "")
            item["document_parse_summary"] = {
                "parsed_text_documents": parsed_count,
                "pricing_schedule_detected": bool(intelligence.get("pricing_schedule_detected")),
                "boq_detected": bool(intelligence.get("boq_detected")),
                "sbd_detected": bool(intelligence.get("sbd_detected")),
            }
            return {
                "status": "documents_parsed",
                "target_state": "DOCUMENTS_PARSED",
                "reason": "review_recovery_document_intelligence_completed",
                "acquisition": acquisition,
                "parsing": parsing,
                "downloaded_paths": downloaded_paths,
            }

        return {
            "status": "documents_acquired",
            "target_state": "DOCUMENTS_ACQUIRED",
            "reason": "documents_acquired_parse_pending",
            "acquisition": acquisition,
            "parsing": parsing,
            "downloaded_paths": downloaded_paths,
        }

    def review_recovery(
        self,
        limit: int = 50,
        timeout_seconds: int = 8,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        items = [item for item in self.store.list_items() if item.get("current_state") == "REVIEW_REQUIRED"]
        items = items[: max(1, int(limit))]
        live_index = self._live_store_index()
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        recovered_count = 0
        ready_for_retry_count = 0
        rejected_count = 0

        for item in items:
            rfq_id = str(item.get("rfq_id") or "")
            try:
                enriched = self._enrich_lifecycle_item(item, live_index)
                decision = self._review_recovery_decision(item, enriched)
                action = decision.get("action")
                item["review_recovery_decision"] = decision

                if action == "reject":
                    self._transition(item, "REJECTED", str(decision.get("reason") or "review_recovery_rejected"), event="review_recovery")
                    rejected_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "action": action, "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                if action == "ready_for_retry":
                    self._transition(item, "READY_FOR_RETRY", str(decision.get("reason") or "source_rescan_required"), event="review_recovery")
                    ready_for_retry_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "action": action, "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                recovery = self._try_recover_documents(
                    item,
                    enriched,
                    timeout_seconds=timeout_seconds,
                    max_concurrent_downloads=max_concurrent_downloads,
                    retry_backoff_seconds=retry_backoff_seconds,
                )
                item["review_recovery_result"] = {
                    "status": recovery.get("status"),
                    "reason": recovery.get("reason"),
                    "downloaded_paths_count": len(recovery.get("downloaded_paths") or []),
                }
                if recovery.get("status") == "not_recovered":
                    self._transition(item, "READY_FOR_RETRY", str(recovery.get("reason") or "source_rescan_required"), event="review_recovery")
                    ready_for_retry_count += 1
                else:
                    self._transition(
                        item,
                        str(recovery.get("target_state") or "DOCUMENTS_ACQUIRED"),
                        str(recovery.get("reason") or "review_recovered_documents"),
                        event="review_recovery",
                    )
                    recovered_count += 1

                processed.append(
                    {
                        "rfq_id": rfq_id,
                        "state": item["current_state"],
                        "action": action,
                        "reason": item.get("failure_reason", ""),
                        "document_paths_count": len(item.get("document_paths") or []),
                    }
                )
                changed_items.append(item)
            except Exception as exc:
                self._transition(item, "READY_FOR_RETRY", f"review_recovery_error:{exc}", event="review_recovery")
                ready_for_retry_count += 1
                processed.append({"rfq_id": rfq_id, "state": item["current_state"], "action": "error_ready_for_retry", "reason": str(exc)})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(changed_items, {"recovered": recovered_count})

        return {
            "status": "ok",
            "processed_count": len(processed),
            "recovered_count": recovered_count,
            "ready_for_retry_count": ready_for_retry_count,
            "rejected_count": rejected_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }

    def retry_ready(
        self,
        limit: int = 50,
        timeout_seconds: int = 8,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        items = [item for item in self.store.list_items() if item.get("current_state") == "READY_FOR_RETRY"]
        items = items[: max(1, int(limit))]
        changed_items: List[Dict[str, Any]] = []
        for item in items:
            item["failure_reason"] = ""
            item["failure_classification"] = ""
            self._transition(item, "DISCOVERED", "ready_for_retry_requeued", event="retry_ready")
            changed_items.append(item)
        if changed_items:
            self.store.update_many(changed_items, {"retried": len(changed_items)})
        advance_result = self.advance_discovered(
            limit=len(changed_items) or 1,
            timeout_seconds=timeout_seconds,
            max_concurrent_downloads=max_concurrent_downloads,
            retry_backoff_seconds=retry_backoff_seconds,
        ) if changed_items else {
            "status": "ok",
            "processed_count": 0,
            "advanced_count": 0,
            "review_required_count": 0,
            "failed_count": 0,
            "items": [],
            "safety": self.submission_safety_guard(),
        }
        return {
            "status": "ok",
            "requeued_count": len(changed_items),
            "advance_result": advance_result,
            "safety": self.submission_safety_guard(),
        }

    def _update_golden_validation_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        state = self.store.read()
        metrics = state.setdefault("golden_validation", {})
        previous_cycles = int(metrics.get("total_cycles_run") or 0)
        previous_average = _safe_float(metrics.get("average_cycle_time"), 0.0)
        cycle_time = _safe_float(result.get("cycle_time_seconds"), 0.0)
        total_cycles = previous_cycles + 1
        total_attempted = int(metrics.get("total_retry_attempted") or 0) + int(result.get("retry_attempted_count") or 0)
        total_recovered = int(metrics.get("recovered_rfqs") or 0) + int(result.get("recovered_rfqs") or 0)

        metrics.update(
            {
                "status": "ok" if result.get("status") == "ok" else "failed",
                "total_cycles_run": total_cycles,
                "successful_cycles": int(metrics.get("successful_cycles") or 0) + (1 if result.get("status") == "ok" else 0),
                "recovered_rfqs": total_recovered,
                "failed_cycles": int(metrics.get("failed_cycles") or 0) + (0 if result.get("status") == "ok" else 1),
                "average_cycle_time": round(((previous_average * previous_cycles) + cycle_time) / max(total_cycles, 1), 4),
                "retry_success_rate": round((total_recovered / total_attempted) * 100.0, 2) if total_attempted else 0.0,
                "total_retry_attempted": total_attempted,
                "last_run_at": utc_now_iso(),
                "last_result": {
                    key: result.get(key)
                    for key in [
                        "status",
                        "retry_attempted_count",
                        "recovered_rfqs",
                        "rejected_count",
                        "rediscovered_count",
                        "advanced_count",
                        "cycle_time_seconds",
                    ]
                },
            }
        )
        self.store.write(state)
        return metrics

    def _reject_retry_item(self, item: Dict[str, Any], reason: str) -> None:
        self._transition(item, "REJECTED", reason, event="golden_validation")
        item["validation_terminal_reason"] = reason

    def run_golden_validation(
        self,
        limit: int = 50,
        timeout_seconds: int = 8,
        max_sources: int = 8,
        max_per_source: int = 2,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        started = time.monotonic()
        ready_items = [item for item in self.store.list_items() if item.get("current_state") == "READY_FOR_RETRY"]
        ready_items = ready_items[: max(1, int(limit))]
        live_index = self._live_store_index()
        changed_items: List[Dict[str, Any]] = []
        processed: List[Dict[str, Any]] = []
        recovered_count = 0
        rejected_count = 0
        retry_attempted_count = 0

        for item in ready_items:
            rfq_id = str(item.get("rfq_id") or "")
            retry_attempted_count += 1
            retries = int(item.get("retries") or 0) + 1
            item["retries"] = retries
            try:
                enriched = self._enrich_lifecycle_item(item, live_index)
                accepted, policy_reasons = self._policy_check(enriched)
                if not accepted:
                    self._reject_retry_item(item, ";".join(policy_reasons) or "policy_rejected_on_validation")
                    rejected_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "result": "rejected_policy"})
                    changed_items.append(item)
                    continue

                decision = self._review_recovery_decision(item, enriched)
                item["golden_validation_decision"] = decision
                if decision.get("action") == "retry_document_acquisition":
                    recovery = self._try_recover_documents(
                        item,
                        enriched,
                        timeout_seconds=timeout_seconds,
                        max_concurrent_downloads=max_concurrent_downloads,
                        retry_backoff_seconds=retry_backoff_seconds,
                    )
                    item["golden_validation_recovery_result"] = {
                        "status": recovery.get("status"),
                        "reason": recovery.get("reason"),
                        "downloaded_paths_count": len(recovery.get("downloaded_paths") or []),
                    }
                    if recovery.get("status") != "not_recovered":
                        self._transition(
                            item,
                            str(recovery.get("target_state") or "DOCUMENTS_ACQUIRED"),
                            str(recovery.get("reason") or "golden_validation_recovered_documents"),
                            event="golden_validation",
                        )
                        recovered_count += 1
                        processed.append(
                            {
                                "rfq_id": rfq_id,
                                "state": item["current_state"],
                                "result": "documents_recovered",
                                "document_paths_count": len(item.get("document_paths") or []),
                            }
                        )
                        changed_items.append(item)
                        continue

                max_retries = int(item.get("max_retries") or 3)
                if retries >= max_retries:
                    self._reject_retry_item(item, "golden_validation_retry_exhausted_no_recoverable_documents")
                    rejected_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "result": "rejected_retry_exhausted"})
                else:
                    item["updated_at"] = utc_now_iso()
                    self._append_audit(
                        item,
                        "golden_validation",
                        from_state="READY_FOR_RETRY",
                        to_state="READY_FOR_RETRY",
                        reason="awaiting_next_source_rescan",
                        retry=retries,
                    )
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "result": "retry_pending_rescan"})
                changed_items.append(item)
            except Exception as exc:
                if int(item.get("retries") or 0) >= int(item.get("max_retries") or 3):
                    self._reject_retry_item(item, f"golden_validation_error_exhausted:{exc}")
                    rejected_count += 1
                else:
                    item["updated_at"] = utc_now_iso()
                    self._append_audit(item, "golden_validation", reason=f"retry_error_pending:{exc}")
                processed.append({"rfq_id": rfq_id, "state": item.get("current_state"), "result": "error", "reason": str(exc)})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(changed_items, {"retried": retry_attempted_count, "recovered": recovered_count})

        rediscovered_count = 0
        discovery_result: Dict[str, Any] = {}
        try:
            discovery_result = self.run_discovery_cycle(
                max_total=max(5, int(limit)),
                max_per_source=max(1, int(max_per_source)),
                max_sources=max(1, int(max_sources)),
            )
            ingest = discovery_result.get("ingest") if isinstance(discovery_result.get("ingest"), dict) else {}
            rediscovered_count = int(ingest.get("ingested_count") or 0)
        except Exception as exc:
            discovery_result = {"status": "failed", "error": str(exc)}

        advance_result = self.advance_discovered(
            limit=max(1, rediscovered_count),
            timeout_seconds=timeout_seconds,
            max_concurrent_downloads=max_concurrent_downloads,
            retry_backoff_seconds=retry_backoff_seconds,
        ) if rediscovered_count else {
            "status": "ok",
            "processed_count": 0,
            "advanced_count": 0,
            "review_required_count": 0,
            "failed_count": 0,
            "items": [],
            "safety": self.submission_safety_guard(),
        }
        advanced_count = int(advance_result.get("advanced_count") or 0)
        recovered_total = recovered_count + advanced_count
        cycle_time = round(time.monotonic() - started, 4)
        status = "ok" if discovery_result.get("status") != "failed" else "partial"
        result = {
            "status": status,
            "cycle_time_seconds": cycle_time,
            "retry_attempted_count": retry_attempted_count,
            "recovered_rfqs": recovered_total,
            "direct_recovered_count": recovered_count,
            "rediscovered_count": rediscovered_count,
            "advanced_count": advanced_count,
            "rejected_count": rejected_count,
            "processed_items": processed,
            "discovery_result": {
                "status": discovery_result.get("status"),
                "eligible_total": discovery_result.get("eligible_total"),
                "ingested_count": ((discovery_result.get("ingest") or {}).get("ingested_count") if isinstance(discovery_result.get("ingest"), dict) else 0),
                "skipped_duplicates_count": ((discovery_result.get("ingest") or {}).get("skipped_duplicates_count") if isinstance(discovery_result.get("ingest"), dict) else 0),
                "error": discovery_result.get("error"),
            },
            "advance_result": {
                "processed_count": advance_result.get("processed_count"),
                "advanced_count": advance_result.get("advanced_count"),
                "review_required_count": advance_result.get("review_required_count"),
                "failed_count": advance_result.get("failed_count"),
            },
            "safety": self.submission_safety_guard(),
        }
        result["validation_metrics"] = self._update_golden_validation_metrics(result)
        result["mission_control"] = self.mission_control_summary()
        return result

    def _scale_stage_duration(self, item_index: int, stage_index: int, retry_penalty: float = 0.0) -> float:
        base = 0.16 + ((item_index + stage_index) % 5) * 0.045
        return round(base + retry_penalty, 4)

    def _write_scale_proof_manifest(self, rfq_id: str, payload: Dict[str, Any]) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        proof_dir = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "scale_simulation" / stamp
        proof_dir.mkdir(parents=True, exist_ok=True)
        path = proof_dir / f"{_slug(rfq_id)}__proof_manifest.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _simulation_queue_pressure(self, max_queue_depth: int, target_rfqs: int) -> str:
        if target_rfqs <= 0:
            return "idle"
        ratio = max_queue_depth / max(target_rfqs, 1)
        if ratio >= 0.80:
            return "high"
        if ratio >= 0.45:
            return "moderate"
        return "low"

    def _update_scale_simulation_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        state = self.store.read()
        metrics = state.setdefault("scale_simulation", {})
        previous_runs = int(metrics.get("runs") or 0)
        trend = metrics.get("throughput_trend") if isinstance(metrics.get("throughput_trend"), list) else []
        trend.append(
            {
                "at": utc_now_iso(),
                "target_rfqs": int(result.get("target_rfqs") or 0),
                "completed_rfqs": int(result.get("completed_rfqs") or 0),
                "simulated_throughput": _safe_float(result.get("simulated_throughput"), 0.0),
                "retry_pressure": _safe_float((result.get("lifecycle_analytics") or {}).get("retry_pressure"), 0.0),
            }
        )
        trend = trend[-10:]
        metrics.update(
            {
                "active": False,
                "status": result.get("status", "ok"),
                "runs": previous_runs + 1,
                "last_run_at": utc_now_iso(),
                "simulated_throughput": _safe_float(result.get("simulated_throughput"), 0.0),
                "average_rfq_completion_time": _safe_float(result.get("average_rfq_completion_time"), 0.0),
                "queue_pressure": result.get("queue_pressure", "idle"),
                "worker_load": _safe_float(result.get("worker_load"), 0.0),
                "stage_bottlenecks": result.get("stage_bottlenecks") if isinstance(result.get("stage_bottlenecks"), list) else [],
                "throughput_trend": trend,
                "lifecycle_analytics": result.get("lifecycle_analytics") if isinstance(result.get("lifecycle_analytics"), dict) else {},
                "last_result": {
                    key: result.get(key)
                    for key in [
                        "status",
                        "target_rfqs",
                        "completed_rfqs",
                        "retry_count",
                        "proof_generated_count",
                        "simulated_throughput",
                        "average_rfq_completion_time",
                        "queue_pressure",
                        "worker_load",
                    ]
                },
            }
        )
        self.store.write(state)
        return metrics

    def run_scale_simulation(self, target_rfqs: int = 10) -> Dict[str, Any]:
        target = max(1, min(int(target_rfqs or 10), 1000))
        started = time.monotonic()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stage_sequence = [
            "DISCOVERED",
            "QUALIFIED",
            "DOCUMENTS_ACQUIRED",
            "DOCUMENTS_PARSED",
            "PRICED",
            "QUOTE_PACK_READY",
            "SUBMISSION_READY",
            "PROOF_CAPTURED",
        ]
        terminal_items: List[Dict[str, Any]] = []
        stage_totals: Dict[str, float] = {stage: 0.0 for stage in stage_sequence}
        stage_counts: Dict[str, int] = {stage: 0 for stage in stage_sequence}
        queue_depth_by_stage: Dict[str, int] = {stage: 0 for stage in LIFECYCLE_STATES}
        retry_count = 0
        proof_generated_count = 0
        completed_count = 0
        simulated_completion_times: List[float] = []
        simulation_events: List[Dict[str, Any]] = []

        for idx in range(1, target + 1):
            rfq_id = f"SIM-SCALE-{run_id}-{idx:04d}"
            retries = 1 if idx % 5 == 0 else 0
            retry_penalty = 0.18 if retries else 0.0
            retry_count += retries
            audit_log: List[Dict[str, Any]] = []
            cumulative = 0.0
            previous = ""
            for stage_idx, stage in enumerate(stage_sequence):
                duration = self._scale_stage_duration(idx, stage_idx, retry_penalty if stage in {"DOCUMENTS_ACQUIRED", "DOCUMENTS_PARSED"} else 0.0)
                cumulative += duration
                stage_totals[stage] += duration
                stage_counts[stage] += 1
                queue_depth_by_stage[stage] += max(0, target - idx + 1)
                audit_log.append(
                    {
                        "at": utc_now_iso(),
                        "event": "scale_simulation_stage",
                        "from_state": previous,
                        "to_state": stage,
                        "simulated_duration_seconds": duration,
                        "retry_simulated": bool(retries and stage in {"DOCUMENTS_ACQUIRED", "DOCUMENTS_PARSED"}),
                    }
                )
                previous = stage

            proof_payload = {
                "rfq_id": rfq_id,
                "run_id": run_id,
                "mode": "controlled_scale_simulation",
                "generated_at": utc_now_iso(),
                "email_send_executed": False,
                "portal_upload_executed": False,
                "portal_final_submit_executed": False,
                "captcha_bypass": False,
            }
            proof_manifest = self._write_scale_proof_manifest(rfq_id, proof_payload)
            proof_generated_count += 1
            completed_count += 1
            simulated_completion_times.append(round(cumulative, 4))
            item = {
                "rfq_id": rfq_id,
                "buyer_name": "LMCP Scale Simulation Buyer",
                "title": f"Scale simulation supply and delivery RFQ {idx:04d}",
                "source": "rfq_lifecycle_scale_simulation",
                "current_state": "PROOF_CAPTURED",
                "previous_state": "SUBMISSION_READY",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "retries": retries,
                "max_retries": 3,
                "failure_reason": "",
                "failure_classification": "",
                "qualification_score": 99.0,
                "estimated_profit": MIN_PROFIT + 10000.0,
                "estimated_margin": MIN_MARGIN + 5.0,
                "document_paths": [f"simulation://{rfq_id}/rfq-document.pdf"],
                "document_urls": [],
                "quote_pack_path": f"simulation://{rfq_id}/quote-pack",
                "submission_status": "scale_simulation_proof_captured_no_send",
                "proof_path": proof_manifest,
                "proof_manifest": proof_manifest,
                "proof_timestamp": utc_now_iso(),
                "submission_attempt_log": {
                    "mode": "controlled_scale_simulation",
                    "outcome": "proof_captured_no_send_no_submit",
                    "safety": {
                        "email_send_executed": False,
                        "portal_upload_executed": False,
                        "portal_final_submit_executed": False,
                        "final_submit_hard_blocked": True,
                        "captcha_bypass": False,
                    },
                },
                "simulation": {
                    "is_simulated": True,
                    "run_id": run_id,
                    "simulated_completion_time_seconds": round(cumulative, 4),
                    "stage_count": len(stage_sequence),
                },
                "policy": {
                    "supply_and_delivery_only": True,
                    "excluded_categories": sorted(EXCLUDED_KEYWORDS),
                    "minimum_margin_percent": MIN_MARGIN,
                    "minimum_profit_zar": MIN_PROFIT,
                    "final_submit_policy_control_required": True,
                    "auto_final_submit_enabled": False,
                    "policy_reasons": [],
                },
                "audit_log": audit_log,
            }
            terminal_items.append(item)
            simulation_events.append(
                {
                    "rfq_id": rfq_id,
                    "completed_state": "PROOF_CAPTURED",
                    "simulated_completion_time_seconds": round(cumulative, 4),
                    "retries": retries,
                    "proof_manifest": proof_manifest,
                }
            )

        if terminal_items:
            self.store.update_many(
                terminal_items,
                {
                    "ingested": len(terminal_items),
                    "advanced": len(terminal_items) * len(stage_sequence),
                    "retried": retry_count,
                    "proof_captured": proof_generated_count,
                },
            )

        average_stage_time = {
            stage: round(stage_totals[stage] / max(stage_counts[stage], 1), 4)
            for stage in stage_sequence
        }
        bottleneck_stage = max(average_stage_time.items(), key=lambda row: row[1])[0] if average_stage_time else ""
        max_queue_depth = max(queue_depth_by_stage.values()) if queue_depth_by_stage else 0
        simulated_elapsed = max(sum(simulated_completion_times) / max(target, 1), 0.0001)
        wall_elapsed = round(time.monotonic() - started, 4)
        simulated_throughput = round(completed_count / simulated_elapsed, 4)
        worker_load = round(min(100.0, (target / max(target + 5, 1)) * 100.0 + (retry_count / max(target, 1)) * 10.0), 2)
        proof_generation_rate = round((proof_generated_count / max(target, 1)) * 100.0, 2)
        retry_pressure = round((retry_count / max(target, 1)) * 100.0, 2)
        queue_pressure = self._simulation_queue_pressure(max_queue_depth, target)
        lifecycle_analytics = {
            "average_stage_time": average_stage_time,
            "max_queue_depth": max_queue_depth,
            "bottleneck_stage": bottleneck_stage,
            "retry_pressure": retry_pressure,
            "proof_generation_rate": proof_generation_rate,
        }
        result = {
            "status": "ok",
            "target_rfqs": target,
            "completed_rfqs": completed_count,
            "retry_count": retry_count,
            "proof_generated_count": proof_generated_count,
            "simulation_run_id": run_id,
            "wall_time_seconds": wall_elapsed,
            "simulated_throughput": simulated_throughput,
            "average_rfq_completion_time": round(sum(simulated_completion_times) / max(len(simulated_completion_times), 1), 4),
            "queue_pressure": queue_pressure,
            "worker_load": worker_load,
            "queue_depth": queue_depth_by_stage,
            "stage_bottlenecks": [{"stage": bottleneck_stage, "average_stage_time": average_stage_time.get(bottleneck_stage, 0.0)}],
            "throughput_trend": [],
            "lifecycle_analytics": lifecycle_analytics,
            "items": simulation_events[:50],
            "safety": self.submission_safety_guard(),
        }
        result["scale_simulation"] = self._update_scale_simulation_metrics(result)
        result["mission_control"] = self.mission_control_summary()
        return result

    def _read_discovery_candidates_for_validation(self, limit: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        rows.extend(self.store.list_items())
        for path in DISCOVERY_STORE_CANDIDATES:
            if not path.exists():
                continue
            try:
                rows.extend(_extract_items(json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue

        candidates: List[Dict[str, Any]] = []
        seen_urls = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            urls = _http_urls_from_payload(row)
            if not urls:
                continue
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(
                    {
                        "rfq_id": row.get("rfq_id") or _stable_id(row),
                        "title": row.get("title") or row.get("description") or "",
                        "buyer_name": row.get("buyer_name") or row.get("buyer") or "",
                        "source": row.get("source") or urlparse(url).netloc,
                        "url": url,
                    }
                )
                if len(candidates) >= limit:
                    return candidates
        return candidates

    def _classify_validation_response(self, url: str, status_code: int, content_type: str) -> str:
        if status_code >= 400:
            return "broken"
        lower_url = url.lower()
        lower_type = content_type.lower()
        if ".pdf" in lower_url or "application/pdf" in lower_type:
            return "direct_pdf"
        if any(ext in lower_url for ext in [".doc", ".docx", ".xls", ".xlsx", ".zip", ".csv"]):
            return "document_page"
        if "text/html" in lower_type or "application/xhtml" in lower_type:
            return "document_page"
        if any(token in lower_type for token in ["wordprocessingml", "spreadsheet", "excel", "zip", "csv"]):
            return "document_page"
        return "unknown"

    def _validate_live_document_url(self, candidate: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
        url = str(candidate.get("url") or "")
        source = urlparse(url).netloc.lower() or str(candidate.get("source") or "unknown")
        started = time.monotonic()
        headers = {
            "User-Agent": "LMCP-AutoQuote Live Acquisition Validation/1.0",
            "Accept": "text/html,application/pdf,application/zip,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
            "Range": "bytes=0-0",
        }

        def base_result(status: str, reason: str, status_code: int = 0, content_type: str = "") -> Dict[str, Any]:
            latency = round(time.monotonic() - started, 4)
            classification = self._classify_validation_response(url, status_code, content_type) if status == "ok" else status
            return {
                "rfq_id": candidate.get("rfq_id"),
                "title": candidate.get("title"),
                "buyer_name": candidate.get("buyer_name"),
                "source": source,
                "url": url,
                "status": status,
                "classification": classification if classification in {"direct_pdf", "document_page", "broken", "timeout", "unknown"} else "unknown",
                "status_code": status_code,
                "content_type": content_type,
                "latency_seconds": latency,
                "success": status == "ok" and classification in {"direct_pdf", "document_page"},
                "failure_reason": "" if status == "ok" else reason,
                "safety": {
                    "email_send_executed": False,
                    "portal_upload_executed": False,
                    "portal_final_submit_executed": False,
                    "captcha_bypass": False,
                },
            }

        if not url.startswith(("http://", "https://")):
            return base_result("broken", "invalid_url")

        for method in ("HEAD", "GET"):
            try:
                request = Request(url, headers=headers, method=method)
                with urlopen(request, timeout=max(1, int(timeout_seconds))) as response:
                    status_code = int(getattr(response, "status", 0) or response.getcode() or 0)
                    content_type = str(response.headers.get("content-type") or "")
                    return base_result("ok", "", status_code=status_code, content_type=content_type)
            except HTTPError as exc:
                if method == "HEAD" and exc.code in {403, 405, 501}:
                    continue
                return base_result("broken", f"http_error:{exc.code}", status_code=int(exc.code or 0), content_type=str(exc.headers.get("content-type") or ""))
            except TimeoutError:
                return base_result("timeout", "timeout")
            except URLError as exc:
                reason = str(getattr(exc, "reason", exc))
                if "timed out" in reason.lower() or "timeout" in reason.lower():
                    return base_result("timeout", "timeout")
                if method == "HEAD":
                    continue
                return base_result("broken", reason[:160])
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    return base_result("timeout", "timeout")
                if method == "HEAD":
                    continue
                return base_result("unknown", str(exc)[:160])
        return base_result("unknown", "no_response")

    def _summarise_live_acquisition_validation(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        source_rows: Dict[str, Dict[str, Any]] = {}
        for row in results:
            source = str(row.get("source") or "unknown")
            bucket = source_rows.setdefault(
                source,
                {
                    "source": source,
                    "tested_url_count": 0,
                    "success_count": 0,
                    "failed_url_count": 0,
                    "timeout_count": 0,
                    "direct_document_count": 0,
                    "latency_total": 0.0,
                },
            )
            bucket["tested_url_count"] += 1
            if row.get("success"):
                bucket["success_count"] += 1
            else:
                bucket["failed_url_count"] += 1
            if row.get("classification") == "timeout":
                bucket["timeout_count"] += 1
            if row.get("classification") == "direct_pdf":
                bucket["direct_document_count"] += 1
            bucket["latency_total"] += _safe_float(row.get("latency_seconds"), 0.0)

        sources = []
        for bucket in source_rows.values():
            total = max(1, int(bucket["tested_url_count"]))
            sources.append(
                {
                    "source": bucket["source"],
                    "tested_url_count": total,
                    "source_success_rate": round((int(bucket["success_count"]) / total) * 100.0, 2),
                    "average_response_time": round(float(bucket["latency_total"]) / total, 4),
                    "failed_url_count": int(bucket["failed_url_count"]),
                    "timeout_count": int(bucket["timeout_count"]),
                    "direct_document_rate": round((int(bucket["direct_document_count"]) / total) * 100.0, 2),
                    "document_resolution_rate": round((int(bucket["success_count"]) / total) * 100.0, 2),
                }
            )
        tested = len(results)
        success = sum(1 for row in results if row.get("success"))
        timeouts = sum(1 for row in results if row.get("classification") == "timeout")
        direct = sum(1 for row in results if row.get("classification") == "direct_pdf")
        return {
            "tested_url_count": tested,
            "successful_url_count": success,
            "failed_url_count": tested - success,
            "timeout_count": timeouts,
            "direct_document_count": direct,
            "acquisition_success_rate": round((success / max(tested, 1)) * 100.0, 2),
            "direct_document_rate": round((direct / max(tested, 1)) * 100.0, 2),
            "document_resolution_rate": round((success / max(tested, 1)) * 100.0, 2),
            "average_response_time": round(sum(_safe_float(row.get("latency_seconds"), 0.0) for row in results) / max(tested, 1), 4),
            "slowest_sources": sorted(sources, key=lambda row: row["average_response_time"], reverse=True)[:10],
            "failed_sources": sorted(sources, key=lambda row: row["failed_url_count"], reverse=True)[:10],
            "sources": sorted(sources, key=lambda row: row["source_success_rate"], reverse=True),
        }

    def run_live_acquisition_validation(self, limit: int = 25, timeout_seconds: int = 6) -> Dict[str, Any]:
        started = time.monotonic()
        candidates = self._read_discovery_candidates_for_validation(max(1, min(int(limit or 25), 100)))
        results = [self._validate_live_document_url(candidate, timeout_seconds) for candidate in candidates]
        summary = self._summarise_live_acquisition_validation(results)
        payload = {
            "status": "ok",
            "mode": "live_acquisition_validation_no_submit",
            "validated_at": utc_now_iso(),
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "limit": max(1, min(int(limit or 25), 100)),
            "timeout_seconds": max(1, int(timeout_seconds or 6)),
            "results": results,
            "summary": summary,
            "safety": self.submission_safety_guard(),
        }
        report_path = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "live_acquisition_validation.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        state = self.store.read()
        state["live_acquisition_validation"] = {
            **summary,
            "status": "ok",
            "last_run_at": payload["validated_at"],
            "report_path": str(report_path),
        }
        self.store.write(state)
        payload["mission_control"] = self.mission_control_summary()
        return payload

    def _path_size_bytes(self, path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except Exception:
                return 0
        total = 0
        for child in path.rglob("*"):
            try:
                if child.is_file():
                    total += child.stat().st_size
            except Exception:
                continue
        return total

    def _cleanup_directory(self, path: Path, cutoff_epoch: float, allow_delete_submitted_proofs: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        result = {"path": str(path), "removed_files": 0, "removed_dirs": 0, "freed_bytes": 0, "skipped": False}
        if not path.exists():
            result["skipped"] = True
            return result
        real_proofs_dir = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "proofs"
        if real_proofs_dir in [path, *path.parents] and not allow_delete_submitted_proofs:
            result["skipped"] = True
            result["reason"] = "real_proof_archives_protected"
            return result

        for child in sorted(path.glob("*"), key=lambda p: len(p.parts), reverse=True):
            try:
                mtime = child.stat().st_mtime
                if mtime >= cutoff_epoch:
                    continue
                size = self._path_size_bytes(child)
                if dry_run:
                    if child.is_dir():
                        result["removed_dirs"] += 1
                    else:
                        result["removed_files"] += 1
                    result["freed_bytes"] += size
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                    result["removed_dirs"] += 1
                else:
                    child.unlink()
                    result["removed_files"] += 1
                result["freed_bytes"] += size
            except Exception:
                continue
        return result

    def cleanup_runtime(self, retention_days: int = 14, allow_delete_submitted_proofs: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        days = max(1, int(retention_days or 14))
        cutoff_epoch = time.time() - (days * 86400)
        targets = [
            PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "scale_simulation",
            PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "tmp",
            PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "temp",
            PROJECT_ROOT / "runtime" / "rfq_document_acquisition" / "reports",
        ]
        cleanup_rows = [self._cleanup_directory(path, cutoff_epoch, allow_delete_submitted_proofs=False, dry_run=dry_run) for path in targets]
        if allow_delete_submitted_proofs:
            cleanup_rows.append(self._cleanup_directory(PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "proofs", cutoff_epoch, allow_delete_submitted_proofs=True, dry_run=dry_run))
        freed = sum(int(row.get("freed_bytes") or 0) for row in cleanup_rows)
        removed_files = sum(int(row.get("removed_files") or 0) for row in cleanup_rows)
        removed_dirs = sum(int(row.get("removed_dirs") or 0) for row in cleanup_rows)
        payload = {
            "status": "ok",
            "cleaned_at": utc_now_iso(),
            "retention_days": days,
            "allow_delete_submitted_proofs": bool(allow_delete_submitted_proofs),
            "dry_run": bool(dry_run),
            "removed_files": removed_files,
            "removed_dirs": removed_dirs,
            "freed_bytes": freed,
            "cleanup_results": cleanup_rows,
            "protected_real_proof_archives": not bool(allow_delete_submitted_proofs),
            "safety": self.submission_safety_guard(),
        }
        state = self.store.read()
        state["runtime_cleanup"] = {
            "status": "ok",
            "last_run_at": payload["cleaned_at"],
            "retention_days": days,
            "dry_run": bool(dry_run),
            "freed_bytes": freed,
            "removed_files": removed_files,
            "removed_dirs": removed_dirs,
            "protected_real_proof_archives": payload["protected_real_proof_archives"],
        }
        self.store.write(state)
        payload["mission_control"] = self.mission_control_summary()
        return payload

    def _pilot_candidate_urls(self, item: Dict[str, Any], live_index: Dict[str, Dict[str, Any]]) -> List[str]:
        enriched = self._enrich_lifecycle_item(item, live_index)
        urls = _http_urls_from_payload(enriched)
        return urls if urls else _http_urls_from_payload(item)

    def _update_live_pilot_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        state = self.store.read()
        pilot = state.setdefault("live_pilot", {})
        runs = int(pilot.get("runs") or 0) + 1
        proof_count = int(result.get("proof_captured_count") or 0)
        processed = max(1, int(result.get("pilot_rfqs_count") or result.get("qualified_count") or 0))
        success_rate = round((proof_count / processed) * 100.0, 2)
        trend = pilot.get("throughput_trend") if isinstance(pilot.get("throughput_trend"), list) else []
        trend.append(
            {
                "at": utc_now_iso(),
                "harvested_count": int(result.get("harvested_count") or 0),
                "qualified_count": int(result.get("qualified_count") or 0),
                "proof_captured_count": proof_count,
                "success_rate": success_rate,
            }
        )
        pilot.update(
            {
                "status": result.get("status", "ok"),
                "mode": "controlled_live_pilot_no_submission",
                "runs": runs,
                "last_run_at": utc_now_iso(),
                "success_rate": success_rate,
                "real_rfq_throughput": proof_count,
                "acquisition_success_rate": _safe_float(result.get("acquisition_success_rate"), 0.0),
                "last_result": {
                    key: result.get(key)
                    for key in [
                        "harvested_count",
                        "qualified_count",
                        "acquisition_success_count",
                        "parsed_count",
                        "priced_count",
                        "proof_captured_count",
                        "failed_count",
                        "review_required_count",
                    ]
                },
                "throughput_trend": trend[-10:],
            }
        )
        self.store.write(state)
        return pilot

    def run_live_pilot(
        self,
        limit: int = 5,
        timeout_seconds: int = 8,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        pilot_limit = max(3, min(int(limit or 5), 5))
        harvested: List[Dict[str, Any]] = []
        harvest_status = "not_run"
        harvest_error = ""
        try:
            from app.services.tender_harvester import run_national_tender_radar

            harvest = run_national_tender_radar(
                max_total=max(pilot_limit, 5),
                max_per_source=2,
                max_sources_per_cycle=8,
                persist_to_live_store=True,
                enable_auto_quote=False,
                include_bad_sources=False,
            )
            harvest_status = str(harvest.get("status") or "ok")
            harvested = _extract_items(harvest.get("eligible_items"))
        except Exception as exc:
            harvest_status = "failed"
            harvest_error = str(exc)

        if not harvested:
            fallback_rows: List[Dict[str, Any]] = []
            for path in DISCOVERY_STORE_CANDIDATES:
                for row in self._load_discovery_store(path):
                    if isinstance(row, dict):
                        enriched_row = dict(row)
                        enriched_row.setdefault("source", enriched_row.get("source_name") or path.parent.name)
                        fallback_rows.append(enriched_row)
            harvested = fallback_rows[: max(pilot_limit * 3, 10)]
            if harvested and harvest_status == "ok":
                harvest_status = "ok_fallback_existing_discovery_stores"

        qualified = [row for row in harvested if isinstance(row, dict) and self._is_lifecycle_qualified(row)]
        qualified = qualified[:pilot_limit]
        ingest = self.ingest_discovered_items(qualified, source="live_pilot:tender_harvester") if qualified else {
            "status": "ok",
            "ingested_count": 0,
            "skipped_duplicates_count": 0,
            "items": [],
            "skipped_duplicates": [],
            "qualified_count": 0,
            "discovered_count": len(harvested),
        }

        store_by_id = {str(item.get("rfq_id")): item for item in self.store.list_items()}
        pilot_ids = [_stable_id(row) for row in qualified]
        pilot_items: List[Dict[str, Any]] = []
        for rfq_id in pilot_ids:
            item = store_by_id.get(str(rfq_id))
            if item and item not in pilot_items:
                pilot_items.append(item)
        pilot_items = pilot_items[:pilot_limit]

        live_index = self._live_store_index()
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        acquisition_success_count = 0
        parsed_count_total = 0
        priced_count = 0
        proof_captured_count = 0
        failed_count = 0
        review_required_count = 0
        validation_results: List[Dict[str, Any]] = []

        for item in pilot_items:
            rfq_id = str(item.get("rfq_id") or "")
            try:
                accepted, reasons = self._policy_check(item)
                if not accepted:
                    self._transition(item, "REVIEW_REQUIRED", ";".join(reasons), event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                if item.get("current_state") == "DISCOVERED":
                    item["qualification_score"] = max(_safe_float(item.get("qualification_score")), 70.0)
                    self._transition(item, "QUALIFIED", "live_pilot_policy_validated", event="live_pilot")

                enriched = self._enrich_lifecycle_item(item, live_index)
                urls = self._pilot_candidate_urls(item, live_index)
                item["document_urls"] = urls
                for url in urls[:3]:
                    validation_results.append(
                        self._validate_live_document_url(
                            {
                                "rfq_id": rfq_id,
                                "title": item.get("title"),
                                "buyer_name": item.get("buyer_name"),
                                "source": item.get("source"),
                                "url": url,
                            },
                            timeout_seconds=timeout_seconds,
                        )
                    )

                valid_urls = [row for row in validation_results if row.get("rfq_id") == rfq_id and row.get("success")]
                existing_paths = [str(path) for path in item.get("document_paths", []) if path]
                if not valid_urls and not existing_paths:
                    self._transition(item, "REVIEW_REQUIRED", "live_pilot_no_valid_document_urls", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                acquisition = self._document_acquisition_step(
                    enriched,
                    timeout_seconds=timeout_seconds,
                    max_concurrent_downloads=max_concurrent_downloads,
                    retry_backoff_seconds=retry_backoff_seconds,
                )
                downloads = acquisition.get("downloaded_files") if isinstance(acquisition.get("downloaded_files"), list) else []
                downloaded_paths = [
                    str(row.get("path"))
                    for row in downloads
                    if isinstance(row, dict) and row.get("status") == "downloaded" and row.get("path")
                ]
                if downloaded_paths:
                    item["document_paths"] = sorted(set(existing_paths + downloaded_paths))
                    item["document_acquisition_report_path"] = acquisition.get("report_path", "")
                    item["document_acquisition_confidence"] = acquisition.get("confidence", 0.0)
                    self._transition(item, "DOCUMENTS_ACQUIRED", "live_pilot_documents_acquired", event="live_pilot")
                    acquisition_success_count += 1
                elif existing_paths:
                    self._transition(item, "DOCUMENTS_ACQUIRED", "live_pilot_existing_document_paths", event="live_pilot")
                    acquisition_success_count += 1
                else:
                    item["document_acquisition_report_path"] = acquisition.get("report_path", "")
                    self._transition(item, "REVIEW_REQUIRED", "live_pilot_document_acquisition_failed", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                parse_payload = dict(enriched)
                parse_payload["document_url"] = urls
                parsing = self._document_parse_step(parse_payload, timeout_seconds=timeout_seconds)
                text_rows = parsing.get("text_extraction") if isinstance(parsing.get("text_extraction"), list) else []
                item_parsed_count = sum(1 for row in text_rows if isinstance(row, dict) and int(row.get("text_length") or 0) > 0)
                intelligence = parsing.get("document_intelligence") if isinstance(parsing.get("document_intelligence"), dict) else {}
                if parsing.get("quote_safe") is False:
                    self._transition(item, "REVIEW_REQUIRED", parsing.get("quote_block_reason") or "live_pilot_document_intelligence_blocked", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue
                if item_parsed_count <= 0 and not intelligence:
                    self._transition(item, "REVIEW_REQUIRED", "live_pilot_document_parse_incomplete", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                item["document_intelligence_report_path"] = parsing.get("report_path", "")
                item["document_parse_summary"] = {
                    "parsed_text_documents": item_parsed_count,
                    "pricing_schedule_detected": bool(intelligence.get("pricing_schedule_detected")),
                    "boq_detected": bool(intelligence.get("boq_detected")),
                    "sbd_detected": bool(intelligence.get("sbd_detected")),
                }
                self._transition(item, "DOCUMENTS_PARSED", "live_pilot_document_intelligence_completed", event="live_pilot")
                parsed_count_total += 1

                enriched_for_pricing = self._enrich_lifecycle_item(item, live_index)
                pricing = self._price_step(enriched_for_pricing)
                priced_payload = pricing.get("payload") if isinstance(pricing.get("payload"), dict) else dict(enriched_for_pricing)
                profit = _profit_value(priced_payload)
                margin = _margin_percent(priced_payload)
                if pricing.get("priced") is not True or profit < MIN_PROFIT or margin < MIN_MARGIN:
                    self._transition(item, "REVIEW_REQUIRED", pricing.get("message") or "live_pilot_pricing_policy_failed", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                priced_payload["rfq_id"] = rfq_id
                priced_payload["buyer_rfq_number"] = priced_payload.get("buyer_rfq_number") or priced_payload.get("rfq_number") or rfq_id
                priced_payload["buyer_name"] = item.get("buyer_name")
                priced_payload["title"] = item.get("title")
                priced_payload["estimated_profit"] = profit
                priced_payload["estimated_margin_percent"] = margin
                priced_payload["line_items"] = self._normalise_v43_line_items(priced_payload)
                item["pricing_result"] = {k: v for k, v in pricing.items() if k != "payload"}
                item["estimated_profit"] = profit
                item["estimated_margin"] = margin
                item["priced_line_items_count"] = len(priced_payload["line_items"])
                self._transition(item, "PRICED", "live_pilot_pricing_passed", event="live_pilot")
                priced_count += 1

                quote_pack = self._build_quote_pack_step(priced_payload)
                if quote_pack.get("status") != "ok":
                    self._transition(item, "REVIEW_REQUIRED", quote_pack.get("message") or "live_pilot_quote_pack_generation_failed", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                item["quote_pack_path"] = str(quote_pack.get("workspace") or "")
                item["quote_pack_artifacts"] = quote_pack.get("artifacts") if isinstance(quote_pack.get("artifacts"), dict) else {}
                item["quote_number"] = quote_pack.get("quote_number", "")
                self._transition(item, "QUOTE_PACK_READY", "live_pilot_quote_pack_generated", event="live_pilot")
                item["submission_status"] = "live_pilot_ready_no_send_no_submit"
                item["submission_safety"] = {
                    "email_send_executed": False,
                    "portal_upload_executed": False,
                    "portal_final_submit_executed": False,
                    "final_submit_hard_blocked": True,
                    "captcha_bypass": False,
                }
                self._transition(item, "SUBMISSION_READY", "live_pilot_quote_pack_ready_no_submission", event="live_pilot")

                proof = self._generate_controlled_proof_package(item)
                if proof.get("status") != "ok":
                    self._transition(item, "REVIEW_REQUIRED", proof.get("error") or "live_pilot_proof_generation_failed", event="live_pilot")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason")})
                    changed_items.append(item)
                    continue

                item["proof_path"] = str(proof.get("proof_path") or "")
                item["proof_manifest"] = str(proof.get("proof_manifest") or "")
                item["proof_timestamp"] = str(proof.get("proof_timestamp") or utc_now_iso())
                item["submission_attempt_log"] = proof.get("submission_attempt_log")
                item["submission_attempt_log_path"] = str(proof.get("submission_attempt_log_path") or "")
                item["controlled_submission_manifest"] = str(proof.get("controlled_submission_manifest") or "")
                item["proof_artifacts"] = proof.get("proof_artifacts") if isinstance(proof.get("proof_artifacts"), dict) else {}
                item["submission_status"] = "live_pilot_controlled_proof_captured_no_send_no_submit"
                self._transition(item, "PROOF_CAPTURED", "live_pilot_controlled_proof_captured", event="live_pilot")
                proof_captured_count += 1
                processed.append({"rfq_id": rfq_id, "state": item["current_state"], "proof_manifest": item.get("proof_manifest")})
                changed_items.append(item)
            except Exception as exc:
                self._transition(item, "FAILED", f"live_pilot_failed:{exc}", event="live_pilot")
                failed_count += 1
                processed.append({"rfq_id": rfq_id, "state": "FAILED", "reason": str(exc)})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(
                changed_items,
                {
                    "advanced": parsed_count_total + priced_count + proof_captured_count,
                    "failed": failed_count,
                    "proof_captured": proof_captured_count,
                },
            )

        validation_summary = self._summarise_live_acquisition_validation(validation_results)
        result = {
            "status": "ok" if not harvest_error else "partial",
            "mode": "controlled_live_pilot_no_submission",
            "harvest_status": harvest_status,
            "harvest_error": harvest_error,
            "harvested_count": len(harvested),
            "qualified_count": len(qualified),
            "pilot_rfqs_count": len(pilot_items),
            "ingested_count": int(ingest.get("ingested_count") or 0),
            "skipped_duplicates_count": int(ingest.get("skipped_duplicates_count") or 0),
            "acquisition_success_count": acquisition_success_count,
            "parsed_count": parsed_count_total,
            "priced_count": priced_count,
            "proof_captured_count": proof_captured_count,
            "failed_count": failed_count,
            "review_required_count": review_required_count,
            "acquisition_success_rate": validation_summary.get("acquisition_success_rate", 0.0),
            "validation_summary": validation_summary,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }
        result["live_pilot"] = self._update_live_pilot_metrics(result)
        result["mission_control"] = self.mission_control_summary()
        return result

    def debug_etenders_acquisition(self, url: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        try:
            from app.services.rfq_document_acquisition_engine import debug_etenders_acquisition

            result = debug_etenders_acquisition(url=url, timeout_seconds=timeout_seconds)
        except Exception as exc:
            result = {
                "status": "error",
                "error": str(exc),
                "url": url,
                "mode": "debug_only_no_submission",
            }
        result["safety"] = {
            **(result.get("safety") if isinstance(result.get("safety"), dict) else {}),
            "supply_and_delivery_only": True,
            "no_email_send": True,
            "no_portal_upload": True,
            "no_final_submit": True,
            "captcha_bypass": False,
            "final_submit_hard_blocked": True,
        }
        return result

    def replay_dead_letters(
        self,
        limit: int = 25,
        timeout_seconds: int = 4,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.25,
    ) -> Dict[str, Any]:
        try:
            from app.services.rfq_document_acquisition_engine import replay_dead_letters

            result = replay_dead_letters(
                limit=limit,
                timeout_seconds=timeout_seconds,
                max_concurrent_downloads=max_concurrent_downloads,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        except Exception as exc:
            result = {
                "status": "error",
                "error": str(exc),
                "mode": "dead_letter_replay_no_submission",
            }
        result["safety"] = {
            **(result.get("safety") if isinstance(result.get("safety"), dict) else {}),
            "supply_and_delivery_only": True,
            "no_email_send": True,
            "no_portal_upload": True,
            "no_final_submit": True,
            "captcha_bypass": False,
            "final_submit_hard_blocked": True,
        }
        result["mission_control"] = self.mission_control_summary()
        return result

    def advance_parsed(self, limit: int = 25) -> Dict[str, Any]:
        items = [item for item in self.store.list_items() if item.get("current_state") == "DOCUMENTS_PARSED"]
        items = items[: max(1, int(limit))]
        live_index = self._live_store_index()
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        advanced_count = 0
        review_required_count = 0
        failed_count = 0

        for item in items:
            rfq_id = str(item.get("rfq_id") or "")
            try:
                enriched = self._enrich_lifecycle_item(item, live_index)
                accepted, reasons = self._policy_check(enriched)
                if not accepted:
                    self._transition(item, "REVIEW_REQUIRED", ";".join(reasons), event="advance_parsed")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                pricing = self._price_step(enriched)
                priced_payload = pricing.get("payload") if isinstance(pricing.get("payload"), dict) else dict(enriched)
                profit = _profit_value(priced_payload)
                margin = _margin_percent(priced_payload)
                if pricing.get("priced") is not True or profit < MIN_PROFIT or margin < MIN_MARGIN:
                    reason = pricing.get("message") or "pricing_policy_failed"
                    self._transition(item, "REVIEW_REQUIRED", str(reason), event="advance_parsed")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                priced_payload["rfq_id"] = rfq_id
                priced_payload["buyer_rfq_number"] = priced_payload.get("buyer_rfq_number") or priced_payload.get("rfq_number") or rfq_id
                priced_payload["buyer_name"] = item.get("buyer_name")
                priced_payload["title"] = item.get("title")
                priced_payload["estimated_profit"] = profit
                priced_payload["estimated_margin_percent"] = margin
                priced_payload["line_items"] = self._normalise_v43_line_items(priced_payload)
                priced_payload["quote_engine_payload"] = {
                    "buyer_rfq_number": priced_payload["buyer_rfq_number"],
                    "currency": "ZAR",
                    "line_items": priced_payload["line_items"],
                }

                item["pricing_result"] = {k: v for k, v in pricing.items() if k != "payload"}
                item["estimated_profit"] = profit
                item["estimated_margin"] = margin
                item["priced_line_items_count"] = len(priced_payload["line_items"])
                self._transition(item, "PRICED", "pricing_passed", event="advance_parsed")

                quote_pack = self._build_quote_pack_step(priced_payload)
                if quote_pack.get("status") != "ok":
                    self._transition(item, "REVIEW_REQUIRED", quote_pack.get("message") or "quote_pack_generation_failed", event="advance_parsed")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                item["quote_pack_path"] = str(quote_pack.get("workspace") or "")
                item["quote_pack_artifacts"] = quote_pack.get("artifacts") if isinstance(quote_pack.get("artifacts"), dict) else {}
                item["quote_number"] = quote_pack.get("quote_number", "")
                self._transition(item, "QUOTE_PACK_READY", "quote_pack_generated", event="advance_parsed")

                item["submission_status"] = "ready_manual_review_no_send"
                item["submission_safety"] = {
                    "email_send_executed": False,
                    "portal_final_submit_executed": False,
                    "final_submit_hard_blocked": True,
                    "captcha_bypass": False,
                }
                self._transition(item, "SUBMISSION_READY", "quote_pack_ready_no_submission_executed", event="advance_parsed")
                advanced_count += 1
                processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": ""})
                changed_items.append(item)
            except Exception as exc:
                self._transition(item, "FAILED", str(exc), event="advance_parsed")
                failed_count += 1
                processed.append({"rfq_id": rfq_id, "state": "FAILED", "reason": str(exc)})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(changed_items, {"advanced": advanced_count, "failed": failed_count})

        return {
            "status": "ok",
            "processed_count": len(processed),
            "advanced_count": advanced_count,
            "review_required_count": review_required_count,
            "failed_count": failed_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }

    def advance_discovered(
        self,
        limit: int = 50,
        timeout_seconds: int = 8,
        max_concurrent_downloads: int = 4,
        retry_backoff_seconds: float = 0.75,
    ) -> Dict[str, Any]:
        items = [item for item in self.store.list_items() if item.get("current_state") == "DISCOVERED"]
        items = items[: max(1, int(limit))]
        live_index = self._live_store_index()
        processed: List[Dict[str, Any]] = []
        changed_items: List[Dict[str, Any]] = []
        advanced_count = 0
        review_required_count = 0
        failed_count = 0

        for item in items:
            rfq_id = str(item.get("rfq_id") or "")
            try:
                accepted, reasons = self._policy_check(item)
                if not accepted:
                    self._set_state(item, "REVIEW_REQUIRED", ";".join(reasons))
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item["failure_reason"]})
                    changed_items.append(item)
                    continue

                item["qualification_score"] = max(_safe_float(item.get("qualification_score")), 65.0 if _safe_float(item.get("estimated_profit")) >= MIN_PROFIT else 0.0)
                self._set_state(item, "QUALIFIED", "policy_validated")

                enriched = self._enrich_lifecycle_item(item, live_index)
                urls = _http_urls_from_payload(enriched)
                existing_paths = [p for p in item.get("document_paths", []) if p]
                if not urls and not existing_paths:
                    self._set_state(item, "REVIEW_REQUIRED", "missing_document_urls")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": "missing_document_urls"})
                    changed_items.append(item)
                    continue

                item["document_urls"] = urls
                acquisition = self._document_acquisition_step(
                    enriched,
                    timeout_seconds=timeout_seconds,
                    max_concurrent_downloads=max_concurrent_downloads,
                    retry_backoff_seconds=retry_backoff_seconds,
                )
                downloads = acquisition.get("downloaded_files") if isinstance(acquisition.get("downloaded_files"), list) else []
                downloaded_paths = [str(row.get("path")) for row in downloads if isinstance(row, dict) and row.get("status") == "downloaded" and row.get("path")]
                if downloaded_paths:
                    item["document_paths"] = sorted(set(existing_paths + downloaded_paths))
                    item["document_acquisition_report_path"] = acquisition.get("report_path", "")
                    item["document_acquisition_confidence"] = acquisition.get("confidence", 0.0)
                    self._set_state(item, "DOCUMENTS_ACQUIRED", "documents_downloaded")
                elif existing_paths:
                    self._set_state(item, "DOCUMENTS_ACQUIRED", "existing_document_paths")
                else:
                    item["document_acquisition_report_path"] = acquisition.get("report_path", "")
                    self._set_state(item, "REVIEW_REQUIRED", "missing_documents")
                    review_required_count += 1
                    processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": "missing_documents"})
                    changed_items.append(item)
                    continue

                parse_payload = dict(enriched)
                parse_payload["document_url"] = urls
                parsing = self._document_parse_step(parse_payload, timeout_seconds=timeout_seconds)
                text_rows = parsing.get("text_extraction") if isinstance(parsing.get("text_extraction"), list) else []
                parsed_count = sum(1 for row in text_rows if isinstance(row, dict) and int(row.get("text_length") or 0) > 0)
                intelligence = parsing.get("document_intelligence") if isinstance(parsing.get("document_intelligence"), dict) else {}
                if parsing.get("quote_safe") is False:
                    self._set_state(item, "REVIEW_REQUIRED", parsing.get("quote_block_reason") or "document_intelligence_blocked")
                    review_required_count += 1
                elif parsed_count > 0 or intelligence:
                    item["document_intelligence_report_path"] = parsing.get("report_path", "")
                    item["document_parse_summary"] = {
                        "parsed_text_documents": parsed_count,
                        "pricing_schedule_detected": bool(intelligence.get("pricing_schedule_detected")),
                        "boq_detected": bool(intelligence.get("boq_detected")),
                        "sbd_detected": bool(intelligence.get("sbd_detected")),
                    }
                    self._set_state(item, "DOCUMENTS_PARSED", "document_intelligence_completed")
                    advanced_count += 1
                else:
                    self._set_state(item, "REVIEW_REQUIRED", "document_parse_incomplete")
                    review_required_count += 1

                processed.append({"rfq_id": rfq_id, "state": item["current_state"], "reason": item.get("failure_reason", "")})
                changed_items.append(item)
            except Exception as exc:
                self._set_state(item, "FAILED", str(exc))
                failed_count += 1
                processed.append({"rfq_id": rfq_id, "state": "FAILED", "reason": str(exc)})
                changed_items.append(item)

        if changed_items:
            self.store.update_many(changed_items, {"advanced": advanced_count, "failed": failed_count})

        return {
            "status": "ok",
            "processed_count": len(processed),
            "advanced_count": advanced_count,
            "review_required_count": review_required_count,
            "failed_count": failed_count,
            "items": processed,
            "safety": self.submission_safety_guard(),
        }

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_items = None
        for key in ("items", "rfqs", "opportunities"):
            if key in payload:
                raw_items = payload.get(key)
                break
        if raw_items is None:
            raw_items = [payload]
        if not isinstance(raw_items, list):
            raw_items = [raw_items]
        source = str(payload.get("source") or "api_ingest")
        normalized = [self._normalize_item(item if isinstance(item, dict) else {"title": str(item)}, source) for item in raw_items]
        existing = {str(item.get("rfq_id")) for item in self.store.list_items()}
        items = [item for item in normalized if str(item.get("rfq_id")) not in existing]
        skipped = [item for item in normalized if str(item.get("rfq_id")) in existing]
        if items:
            self.store.update_many(items, {"ingested": len(items)})
            self.store.append_audit_events(
                [
                    row
                    for item in items
                    for row in item.get("audit_log", [])
                    if isinstance(row, dict)
                ]
            )
        return {
            "status": "ok",
            "ingested_count": len(items),
            "skipped_duplicates_count": len(skipped),
            "items": items,
            "skipped_duplicates": [{"rfq_id": item.get("rfq_id"), "title": item.get("title")} for item in skipped],
        }

    def ingest_discovered_items(self, items: List[Dict[str, Any]], source: str = "discovered") -> Dict[str, Any]:
        qualified = [item for item in items if isinstance(item, dict) and self._is_lifecycle_qualified(item)]
        result = self.ingest({"source": source, "items": qualified})
        result["discovered_count"] = len(items)
        result["qualified_count"] = len(qualified)
        return result

    def _load_discovery_store(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _extract_items(data)
        except Exception:
            return []

    def ingest_discovered(self) -> Dict[str, Any]:
        all_items: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []
        for path in DISCOVERY_STORE_CANDIDATES:
            items = self._load_discovery_store(path)
            if not items:
                sources.append({"path": str(path), "count": 0})
                continue
            for item in items:
                row = dict(item)
                row.setdefault("source", row.get("source_name") or path.parent.name)
                all_items.append(row)
            sources.append({"path": str(path), "count": len(items)})
        result = self.ingest_discovered_items(all_items, source="existing_discovery_stores")
        result["sources_scanned"] = sources
        return result

    def list_items(self, state: Optional[str] = None, limit: int = 250) -> Dict[str, Any]:
        items = self.store.list_items()
        if state:
            items = [item for item in items if item.get("current_state") == state.upper()]
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return {"status": "ok", "count": len(items), "items": items[: max(1, int(limit))]}

    def get_item(self, rfq_id: str) -> Dict[str, Any]:
        item = self.store.get_item(rfq_id)
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        return {"status": "ok", "item": item}

    def _next_state(self, current: str) -> str:
        if current in {"FAILED", "REVIEW_REQUIRED", "SUBMITTED", "PROOF_CAPTURED", "ARCHIVED", "REJECTED"}:
            return current
        if current == "READY_FOR_RETRY":
            return "DISCOVERED"
        try:
            return ADVANCE_ORDER[ADVANCE_ORDER.index(current) + 1]
        except Exception:
            return "REVIEW_REQUIRED"

    def advance(self, rfq_id: str, target_state: Optional[str] = None, note: str = "") -> Dict[str, Any]:
        item = self.store.get_item(rfq_id)
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        current = str(item.get("current_state") or "DISCOVERED")
        next_state = str(target_state or self._next_state(current)).upper()
        if next_state not in LIFECYCLE_STATES:
            return {"status": "failed", "error": f"Invalid lifecycle state: {next_state}", "allowed_states": LIFECYCLE_STATES}
        if next_state == "SUBMITTED":
            return {
                "status": "blocked",
                "rfq_id": rfq_id,
                "reason": "unsafe_final_submission_blocked_without_policy_control",
                "current_state": current,
            }
        self._transition(item, next_state, reason=note, event="advance")
        self.store.update_many([item], {"advanced": 1})
        return {"status": "ok", "item": item}

    def retry_failed(self) -> Dict[str, Any]:
        return self.recovery.retry_failed()

    def recover_stuck(self, timeout_minutes: int = 120) -> Dict[str, Any]:
        return self.recovery.recover_stuck(timeout_minutes=timeout_minutes)

    def run_golden_cycle(self, limit: int = 25, dry_run: bool = True) -> Dict[str, Any]:
        self.store.increment("golden_cycles", 1)
        diagnostics: Dict[str, Any] = {
            "status": "ok",
            "dry_run": bool(dry_run),
            "final_submit_hard_blocked": True,
            "steps": [],
        }
        harvested: List[Dict[str, Any]] = []
        try:
            from app.services.tender_harvester import run_multi_portal_discovery

            result = run_multi_portal_discovery(max_sources=3, max_per_source=2, dry_run=True, include_bad_sources=False)
            raw = result.get("qualified_candidates") or result.get("eligible_items") or result.get("eligible_candidates") or []
            if isinstance(raw, list):
                harvested = raw[: max(1, int(limit))]
            diagnostics["steps"].append({"step": "tender_harvester", "status": "ok", "count": len(harvested)})
        except Exception as exc:
            diagnostics["steps"].append({"step": "tender_harvester", "status": "warning", "error": str(exc)})

        if harvested:
            ingest_result = self.ingest_discovered_items(harvested, source="golden_cycle:tender_harvester")
            diagnostics["ingest"] = {"count": ingest_result["ingested_count"]}
        else:
            diagnostics["ingest"] = {"count": 0, "message": "No harvested items returned; lifecycle health still evaluated."}

        diagnostics["recovery"] = self.recover_stuck(timeout_minutes=120)
        diagnostics["mission_control"] = self.mission_control_summary()
        return diagnostics

    def run_discovery_cycle(self, max_total: int = 20, max_per_source: int = 3, max_sources: int = 12) -> Dict[str, Any]:
        try:
            from app.services.tender_harvester import run_national_tender_radar

            harvest = run_national_tender_radar(
                max_total=max_total,
                max_per_source=max_per_source,
                max_sources_per_cycle=max_sources,
                persist_to_live_store=True,
                enable_auto_quote=False,
                include_bad_sources=False,
            )
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "ingest": {"ingested_count": 0, "skipped_duplicates_count": 0}}

        candidates = _extract_items(harvest.get("eligible_items"))
        ingest = self.ingest_discovered_items(candidates, source="run_discovery_cycle:tender_harvester")
        return {
            "status": "ok",
            "harvest_status": harvest.get("status"),
            "harvested_total": harvest.get("harvested_total", len(candidates)),
            "eligible_total": harvest.get("eligible_total"),
            "quote_ready_total": harvest.get("quote_ready_total"),
            "ingest": ingest,
            "mission_control": self.mission_control_summary(),
            "safety": self.submission_safety_guard(),
        }

    def _queue_by_state(self, items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        counts = Counter(str(item.get("current_state") or "DISCOVERED") for item in items)
        return {state: int(counts.get(state, 0)) for state in LIFECYCLE_STATES}

    def _redis_queue_depths(self) -> Dict[str, int]:
        depths: Dict[str, int] = {}
        try:
            import redis  # type: ignore

            client = redis.from_url(os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") or "redis://redis:6379/0")
            for queue_name in LIFECYCLE_QUEUE_CONCURRENCY:
                depths[queue_name] = int(client.llen(queue_name))
        except Exception:
            depths = {queue_name: 0 for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
        return depths

    def _queue_analytics(self, items: List[Dict[str, Any]], queue_by_state: Dict[str, int], throughput: Dict[str, Any]) -> Dict[str, Any]:
        lifecycle_depths = {queue_name: 0 for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
        wait_totals = {queue_name: 0.0 for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
        wait_counts = {queue_name: 0 for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
        now = datetime.now(timezone.utc)
        for item in items:
            state = str(item.get("current_state") or "")
            queue_name = LIFECYCLE_QUEUE_MAP.get(state)
            if not queue_name:
                continue
            lifecycle_depths[queue_name] += 1
            try:
                updated = datetime.fromisoformat(str(item.get("updated_at") or item.get("created_at") or utc_now_iso()).replace("Z", "+00:00"))
                wait_totals[queue_name] += max(0.0, (now - updated).total_seconds())
                wait_counts[queue_name] += 1
            except Exception:
                pass

        broker_depths = self._redis_queue_depths()
        queue_depth_by_stage = {
            stage: queue_by_state.get(stage, 0)
            for stage in LIFECYCLE_STATES
            if stage in LIFECYCLE_QUEUE_MAP or queue_by_state.get(stage, 0)
        }
        worker_utilization: Dict[str, float] = {}
        queue_wait_time: Dict[str, float] = {}
        task_processing_rate: Dict[str, float] = {}
        total_processed = int(throughput.get("advanced", 0) or 0) + int(throughput.get("proof_captured", 0) or 0)
        for queue_name, concurrency in LIFECYCLE_QUEUE_CONCURRENCY.items():
            depth = lifecycle_depths.get(queue_name, 0) + broker_depths.get(queue_name, 0)
            worker_utilization[queue_name] = round(min(100.0, (depth / max(concurrency, 1)) * 100.0), 2)
            queue_wait_time[queue_name] = round(wait_totals.get(queue_name, 0.0) / max(wait_counts.get(queue_name, 0), 1), 2)
            task_processing_rate[queue_name] = round(total_processed / max(sum(LIFECYCLE_QUEUE_CONCURRENCY.values()), 1), 2)

        busiest_queue = max(worker_utilization.items(), key=lambda row: row[1])[0] if worker_utilization else ""
        saturation_warnings = [
            f"{queue_name} utilization {utilization}%"
            for queue_name, utilization in worker_utilization.items()
            if utilization >= 85.0
        ]
        bottleneck_trend = [
            {"queue": queue_name, "utilization": worker_utilization.get(queue_name, 0.0), "depth": lifecycle_depths.get(queue_name, 0) + broker_depths.get(queue_name, 0)}
            for queue_name in sorted(worker_utilization, key=lambda q: worker_utilization.get(q, 0.0), reverse=True)
        ][:5]
        return {
            "dedicated_queues": list(LIFECYCLE_QUEUE_CONCURRENCY.keys()),
            "queue_depth_by_stage": queue_depth_by_stage,
            "lifecycle_queue_depth": lifecycle_depths,
            "broker_queue_depth": broker_depths,
            "worker_concurrency": LIFECYCLE_QUEUE_CONCURRENCY,
            "worker_utilization_by_queue": worker_utilization,
            "queue_wait_time": queue_wait_time,
            "task_processing_rate": task_processing_rate,
            "busiest_queue": busiest_queue,
            "queue_bottleneck_trend": bottleneck_trend,
            "saturation_warnings": saturation_warnings,
            "backpressure_active": bool(saturation_warnings),
            "retry_isolation": {
                "queue": "retry_queue",
                "depth": lifecycle_depths.get("retry_queue", 0) + broker_depths.get("retry_queue", 0),
                "isolated_from_acquisition": True,
            },
        }

    def _item_audit_events(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = item.get("audit_log") if isinstance(item.get("audit_log"), list) else []
        output: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched.setdefault("rfq_id", item.get("rfq_id"))
            enriched.setdefault("source", item.get("source"))
            output.append(enriched)
        return output

    def _all_audit_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        persisted = self.store.read_audit().get("events", [])
        if isinstance(persisted, list):
            events.extend(row for row in persisted if isinstance(row, dict))
        events.extend(row for item in items for row in self._item_audit_events(item))
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in events:
            key = "|".join(
                [
                    str(row.get("rfq_id") or ""),
                    str(row.get("at") or ""),
                    str(row.get("event") or ""),
                    str(row.get("from_state") or ""),
                    str(row.get("to_state") or row.get("state") or ""),
                    str(row.get("reason") or row.get("note") or ""),
                ]
            )
            deduped[key] = row
        return sorted(deduped.values(), key=lambda row: str(row.get("at") or ""))

    def _source_reliability(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_source: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "successful": 0, "blocked": 0, "proofs": 0})
        for item in items:
            source = str(item.get("source") or "unknown")
            state = str(item.get("current_state") or "")
            by_source[source]["total"] += 1
            if state in {"DOCUMENTS_PARSED", "PRICED", "QUOTE_PACK_READY", "SUBMISSION_READY", "PROOF_CAPTURED", "SUBMITTED", "ARCHIVED"}:
                by_source[source]["successful"] += 1
            if state in {"FAILED", "REVIEW_REQUIRED", "REJECTED"}:
                by_source[source]["blocked"] += 1
            if state == "PROOF_CAPTURED":
                by_source[source]["proofs"] += 1
        rows = []
        for source, counts in by_source.items():
            total = max(counts["total"], 1)
            reliability = round(((counts["successful"] + counts["proofs"]) / (total * 2.0)) * 100.0, 2)
            if counts["blocked"]:
                reliability = round(max(0.0, reliability - ((counts["blocked"] / total) * 25.0)), 2)
            rows.append({"source": source, **counts, "reliability_score": reliability})
        return sorted(rows, key=lambda row: row["reliability_score"], reverse=True)[:20]

    def analytics(self) -> Dict[str, Any]:
        state = self.store.read()
        items = list(state.get("items", {}).values())
        queue = self._queue_by_state(items)
        throughput = state.get("throughput", {}) if isinstance(state.get("throughput"), dict) else {}
        queue_analytics = self._queue_analytics(
            items,
            queue,
            throughput if isinstance(throughput, dict) else {},
        )
        events = self._all_audit_events(items)

        latency_totals: Dict[str, float] = defaultdict(float)
        latency_counts: Dict[str, int] = defaultdict(int)
        exits: Dict[str, int] = defaultdict(int)
        successful_exits: Dict[str, int] = defaultdict(int)
        retry_reasons = Counter()
        recovery_reasons = Counter()
        rejection_reasons = Counter()
        proof_latencies: List[float] = []
        lifecycle_durations: List[float] = []

        for event in events:
            to_state = str(event.get("to_state") or event.get("state") or "")
            from_state = str(event.get("from_state") or "")
            latency = _safe_float(event.get("stage_latency_seconds") or event.get("simulated_duration_seconds"), 0.0)
            if to_state and latency > 0:
                latency_totals[to_state] += latency
                latency_counts[to_state] += 1
            if from_state:
                exits[from_state] += 1
                if str(event.get("to_state") or "") not in {"FAILED", "REVIEW_REQUIRED", "REJECTED"}:
                    successful_exits[from_state] += 1
            reason = str(event.get("reason") or event.get("note") or "")
            event_name = str(event.get("event") or "")
            if "retry" in event_name or "retry" in reason.lower():
                retry_reasons[reason or event_name] += 1
            if "recover" in event_name or "recovered" in reason.lower():
                recovery_reasons[reason or event_name] += 1
            if str(event.get("to_state") or "") == "REJECTED" or "reject" in reason.lower():
                rejection_reasons[reason or event_name] += 1
            if to_state == "PROOF_CAPTURED" and latency > 0:
                proof_latencies.append(latency)

        per_stage_latency = {
            state_name: round(latency_totals[state_name] / max(latency_counts[state_name], 1), 4)
            for state_name in LIFECYCLE_STATES
            if latency_counts.get(state_name)
        }
        per_stage_success_rate = {
            state_name: round((successful_exits[state_name] / max(exits[state_name], 1)) * 100.0, 2)
            for state_name in LIFECYCLE_STATES
            if exits.get(state_name)
        }

        now = datetime.now(timezone.utc)
        active_durations: List[float] = []
        for item in items:
            created = item.get("created_at")
            updated = item.get("updated_at")
            duration = _seconds_between(created, updated)
            if duration > 0:
                lifecycle_durations.append(duration)
            if item.get("current_state") in ADVANCE_ORDER:
                created_dt = _parse_iso_datetime(created)
                if created_dt:
                    active_durations.append(round(max(0.0, (now - created_dt).total_seconds()), 4))

        retry_histogram = Counter(str(int(item.get("retries") or 0)) for item in items)
        simulation = state.get("scale_simulation") if isinstance(state.get("scale_simulation"), dict) else {}
        trend = simulation.get("throughput_trend") if isinstance(simulation.get("throughput_trend"), list) else []
        health_score = self.mission_control_summary().get("lifecycle_health_score", 0.0)
        queue_trend = [
            {
                "at": row.get("at"),
                "target_rfqs": row.get("target_rfqs"),
                "completed_rfqs": row.get("completed_rfqs"),
                "simulated_throughput": row.get("simulated_throughput"),
                "retry_pressure": row.get("retry_pressure"),
            }
            for row in trend[-10:]
            if isinstance(row, dict)
        ]
        analytics = {
            "status": "ok",
            "generated_at": utc_now_iso(),
            "total_rfqs": len(items),
            "per_stage_latency": per_stage_latency,
            "per_stage_success_rate": per_stage_success_rate,
            "worker_crash_count": 0,
            "task_retry_histogram": dict(sorted(retry_histogram.items(), key=lambda row: int(row[0]))),
            "retry_reason_histogram": dict(retry_reasons.most_common(12)),
            "recovery_reason_histogram": dict(recovery_reasons.most_common(12)),
            "rejection_reason_histogram": dict(rejection_reasons.most_common(12)),
            "queue_wait_times": queue_analytics.get(
                "queue_wait_time",
                queue_analytics.get("queue_wait_times", []),
            ),
            "queue_drain_rate": queue_analytics["task_processing_rate"],
            "queue_trend": queue_trend,
            "source_reliability_score": self._source_reliability(items),
            "proof_generation_latency": {
                "average_seconds": round(sum(proof_latencies) / max(len(proof_latencies), 1), 4),
                "samples": len(proof_latencies),
            },
            "rfq_lifecycle_duration": {
                "average_seconds": round(sum(lifecycle_durations) / max(len(lifecycle_durations), 1), 4),
                "active_average_seconds": round(sum(active_durations) / max(len(active_durations), 1), 4),
                "samples": len(lifecycle_durations),
            },
            "slowest_stages": sorted(
                [{"stage": stage, "average_seconds": value} for stage, value in per_stage_latency.items()],
                key=lambda row: row["average_seconds"],
                reverse=True,
            )[:8],
            "worker_saturation_warnings": queue_analytics["saturation_warnings"],
            "rfq_lifecycle_timeline_samples": [
                {
                    "rfq_id": item.get("rfq_id"),
                    "buyer_name": item.get("buyer_name"),
                    "title": item.get("title"),
                    "current_state": item.get("current_state"),
                    "updated_at": item.get("updated_at"),
                    "events": self._item_audit_events(item)[-8:],
                }
                for item in sorted(items, key=lambda row: str(row.get("updated_at") or ""), reverse=True)[:8]
            ],
            "system_health_trend": [
                {
                    "at": row.get("at"),
                    "health_score": health_score,
                    "queue_pressure": simulation.get("queue_pressure", "idle"),
                    "worker_load": simulation.get("worker_load", 0.0),
                }
                for row in queue_trend
            ][-10:],
            "persistent_storage": {
                "state_file": str(self.store.state_file),
                "audit_file": str(PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "audit_events.json"),
                "analytics_file": str(PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "analytics.json"),
            },
            "safety": self.submission_safety_guard(),
        }
        self.store.write_analytics(analytics)
        return analytics

    def audit_trace(self, rfq_id: str) -> Dict[str, Any]:
        item = self.store.get_item(rfq_id)
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        events = self._item_audit_events(item)
        persisted = self.store.read_audit().get("events", [])
        if isinstance(persisted, list):
            events.extend(
                row
                for row in persisted
                if isinstance(row, dict) and str(row.get("rfq_id") or "") == str(rfq_id)
            )
        events = sorted(
            {json.dumps(row, sort_keys=True, default=str): row for row in events}.values(),
            key=lambda row: str(row.get("at") or ""),
        )
        trace = item.get("lifecycle_trace") if isinstance(item.get("lifecycle_trace"), dict) else {}
        return {
            "status": "ok",
            "rfq_id": rfq_id,
            "current_state": item.get("current_state"),
            "previous_state": item.get("previous_state"),
            "buyer_name": item.get("buyer_name"),
            "title": item.get("title"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "lifecycle_duration_seconds": _seconds_between(item.get("created_at"), item.get("updated_at")),
            "stage_transition_timestamps": trace.get("stage_transition_timestamps", {}),
            "retry_reasons": trace.get("retry_reasons", []),
            "recovery_reasons": trace.get("recovery_reasons", []),
            "rejection_reasons": trace.get("rejection_reasons", []),
            "failure_reason": item.get("failure_reason", ""),
            "failure_classification": item.get("failure_classification", ""),
            "timeline": events,
            "safety": self.submission_safety_guard(),
        }

    def _system_pressure(self) -> Dict[str, Any]:
        cpu_count = os.cpu_count() or 1
        load_1m = 0.0
        try:
            load_1m = float(os.getloadavg()[0])
        except Exception:
            load_1m = 0.0
        cpu_percent = round(min(100.0, (load_1m / max(cpu_count, 1)) * 100.0), 2)

        memory_total_kb = 0
        memory_available_kb = 0
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            try:
                for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("MemTotal:"):
                        memory_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        memory_available_kb = int(line.split()[1])
            except Exception:
                pass
        memory_used_percent = 0.0
        if memory_total_kb > 0:
            memory_used_percent = round(((memory_total_kb - memory_available_kb) / memory_total_kb) * 100.0, 2)

        cpu_threshold = _safe_float(os.getenv("RFQ_CPU_PRESSURE_PERCENT"), 85.0)
        memory_threshold = _safe_float(os.getenv("RFQ_MEMORY_PRESSURE_PERCENT"), 85.0)
        return {
            "hostname": socket.gethostname(),
            "cpu_count": cpu_count,
            "load_average_1m": round(load_1m, 4),
            "cpu_percent_estimate": cpu_percent,
            "cpu_saturation_warning": cpu_percent >= cpu_threshold,
            "memory_total_mb": round(memory_total_kb / 1024.0, 2) if memory_total_kb else 0.0,
            "memory_available_mb": round(memory_available_kb / 1024.0, 2) if memory_available_kb else 0.0,
            "memory_used_percent": memory_used_percent,
            "memory_pressure_warning": memory_used_percent >= memory_threshold if memory_total_kb else False,
            "thresholds": {
                "cpu_pressure_percent": cpu_threshold,
                "memory_pressure_percent": memory_threshold,
            },
        }

    def _celery_worker_probe(self) -> Dict[str, Any]:
        started = time.monotonic()
        result: Dict[str, Any] = {
            "status": "unavailable",
            "online_workers": [],
            "offline_workers": [],
            "worker_stats": {},
            "active_tasks": [],
            "reserved_tasks": [],
            "heartbeat_latency_seconds": 0.0,
            "errors": [],
        }
        try:
            from app.celery_app import celery_app

            inspector = celery_app.control.inspect(timeout=float(os.getenv("RFQ_CELERY_INSPECT_TIMEOUT", "1.0") or "1.0"))
            ping = inspector.ping() or {}
            stats = inspector.stats() or {}
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            active_queues = inspector.active_queues() or {}
            online = sorted(set(list(ping.keys()) + list(stats.keys())))
            active_rows = []
            reserved_rows = []
            for worker, rows in active.items():
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            active_rows.append({"worker": worker, **row})
            for worker, rows in reserved.items():
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            reserved_rows.append({"worker": worker, **row})
            queue_workers: Dict[str, List[str]] = {queue_name: [] for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
            for worker, rows in active_queues.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    queue_name = str(row.get("name") or "")
                    if queue_name:
                        queue_workers.setdefault(queue_name, []).append(worker)
            result.update(
                {
                    "status": "ok" if online else "no_workers",
                    "online_workers": online,
                    "worker_stats": stats,
                    "active_tasks": active_rows,
                    "reserved_tasks": reserved_rows,
                    "active_queues": active_queues,
                    "queue_workers": queue_workers,
                }
            )
        except Exception as exc:
            result["errors"].append(str(exc))
        result["heartbeat_latency_seconds"] = round(time.monotonic() - started, 4)
        return result

    def _broker_probe(self) -> Dict[str, Any]:
        broker_url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") or "redis://redis:6379/0"
        queue_depths = {queue_name: 0 for queue_name in LIFECYCLE_QUEUE_CONCURRENCY}
        result = {
            "connected": False,
            "broker_url_masked": re.sub(r"://([^:@/]+):([^@/]+)@", r"://***:***@", broker_url),
            "queue_depths": queue_depths,
            "latency_seconds": 0.0,
            "warning": "",
        }
        started = time.monotonic()
        try:
            import redis  # type: ignore

            client = redis.from_url(broker_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            for queue_name in queue_depths:
                queue_depths[queue_name] = int(client.llen(queue_name))
            result["connected"] = True
        except Exception as exc:
            result["warning"] = f"broker_connectivity_warning:{exc}"
        result["latency_seconds"] = round(time.monotonic() - started, 4)
        return result

    def _stalled_lifecycle_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        timeout_seconds = int(os.getenv("RFQ_STALLED_TASK_SECONDS", "1800") or "1800")
        now = datetime.now(timezone.utc)
        stalled = []
        for item in items:
            state = str(item.get("current_state") or "")
            if state not in LIFECYCLE_QUEUE_MAP:
                continue
            updated = _parse_iso_datetime(item.get("updated_at") or item.get("created_at"))
            age = (now - updated).total_seconds() if updated else 0.0
            if age >= timeout_seconds:
                stalled.append(
                    {
                        "rfq_id": item.get("rfq_id"),
                        "state": state,
                        "age_seconds": round(age, 2),
                        "failure_reason": item.get("failure_reason", ""),
                        "recommended_recovery": "recover_stuck",
                    }
                )
        return stalled[:100]

    def _active_task_timeouts(self, active_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        timeout_seconds = int(os.getenv("RFQ_TASK_TIMEOUT_SECONDS", "900") or "900")
        now_epoch = time.time()
        timed_out = []
        for task in active_tasks:
            started = _safe_float(task.get("time_start"), 0.0)
            age = now_epoch - started if started else 0.0
            if age >= timeout_seconds:
                timed_out.append(
                    {
                        "worker": task.get("worker"),
                        "task_id": task.get("id"),
                        "task_name": task.get("name"),
                        "age_seconds": round(age, 2),
                        "timeout_seconds": timeout_seconds,
                    }
                )
        return timed_out[:100]

    def _source_cooldown_snapshot(self) -> Dict[str, Any]:
        path = PROJECT_ROOT / "runtime" / "rfq_document_acquisition" / "source_health.json"
        rows: Dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, dict) else {}
            except Exception:
                rows = {}
        now_epoch = time.time()
        failing = []
        cooldown = []
        for source, row in rows.items():
            if not isinstance(row, dict):
                continue
            failure_rate = _safe_float(row.get("failure_rate"), 0.0)
            attempts = int(row.get("attempts") or 0)
            until = _safe_float(row.get("cooldown_until_epoch"), 0.0)
            entry = {
                "source": source,
                "attempts": attempts,
                "failures": int(row.get("failures") or 0),
                "failure_rate": failure_rate,
                "cooldown_active": until > now_epoch,
                "cooldown_until_epoch": until,
            }
            if entry["cooldown_active"]:
                cooldown.append(entry)
            if attempts >= 3 and failure_rate >= 0.75:
                failing.append(entry)
        return {
            "source_health_file": str(path),
            "failing_sources": sorted(failing, key=lambda row: row["failure_rate"], reverse=True)[:20],
            "cooldown_sources": sorted(cooldown, key=lambda row: row["cooldown_until_epoch"], reverse=True)[:20],
        }

    def telemetry(self) -> Dict[str, Any]:
        state = self.store.read()
        items = list(state.get("items", {}).values())
        queue = self._queue_by_state(items)
        throughput = state.get("throughput", {}) if isinstance(state.get("throughput"), dict) else {}
        queue_analytics = self._queue_analytics(items, queue, throughput)
        previous = self.store.read_telemetry().get("telemetry", {})

        broker = self._broker_probe()
        worker = self._celery_worker_probe()
        pressure = self._system_pressure()
        stalled_items = self._stalled_lifecycle_items(items)
        timed_out_tasks = self._active_task_timeouts(worker.get("active_tasks") if isinstance(worker.get("active_tasks"), list) else [])

        previous_workers = set(((previous.get("worker_heartbeat") or {}).get("online_workers") or []) if isinstance(previous, dict) else [])
        current_workers = set(worker.get("online_workers") or [])
        disappeared = sorted(previous_workers - current_workers)
        previous_stats = (previous.get("worker_heartbeat") or {}).get("worker_stats") if isinstance(previous, dict) else {}
        restart_events = []
        if isinstance(previous_stats, dict):
            for worker_name, stats in (worker.get("worker_stats") or {}).items():
                previous_pid = ((previous_stats.get(worker_name) or {}).get("pid") if isinstance(previous_stats.get(worker_name), dict) else None)
                current_pid = stats.get("pid") if isinstance(stats, dict) else None
                if previous_pid and current_pid and previous_pid != current_pid:
                    restart_events.append({"worker": worker_name, "previous_pid": previous_pid, "current_pid": current_pid, "detected_at": utc_now_iso()})
        previous_restart_count = int((previous.get("worker_restart_count") or 0) if isinstance(previous, dict) else 0)
        previous_crash_count = int((previous.get("worker_crash_count") or 0) if isinstance(previous, dict) else 0)
        worker_restart_count = previous_restart_count + len(restart_events)
        worker_crash_count = previous_crash_count + len(disappeared)

        total_backlog = sum(int(v or 0) for v in (broker.get("queue_depths") or {}).values()) + sum(int(v or 0) for v in queue_analytics["lifecycle_queue_depth"].values())
        backlog_threshold = int(os.getenv("RFQ_QUEUE_BACKLOG_WARNING_DEPTH", "25") or "25")
        dead_queues = [
            queue_name
            for queue_name, depth in (broker.get("queue_depths") or {}).items()
            if int(depth or 0) > 0 and not current_workers
        ]
        source_cooldown = self._source_cooldown_snapshot()
        queue_workers = worker.get("queue_workers") if isinstance(worker.get("queue_workers"), dict) else {}
        active_tasks = worker.get("active_tasks") if isinstance(worker.get("active_tasks"), list) else []
        reserved_tasks = worker.get("reserved_tasks") if isinstance(worker.get("reserved_tasks"), list) else []
        task_queue_by_name = {
            "app.tasks.rfq_lifecycle_acquisition_task": "acquisition_queue",
            "app.tasks.rfq_lifecycle_parsing_task": "parsing_queue",
            "app.tasks.rfq_lifecycle_pricing_task": "pricing_queue",
            "app.tasks.rfq_lifecycle_proof_task": "proof_queue",
            "app.tasks.rfq_lifecycle_retry_task": "retry_queue",
            "app.tasks.run_rfq_lifecycle_golden_cycle": "retry_queue",
        }
        active_by_queue = Counter(task_queue_by_name.get(str(task.get("name") or ""), "default") for task in active_tasks if isinstance(task, dict))
        reserved_by_queue = Counter(task_queue_by_name.get(str(task.get("name") or ""), "default") for task in reserved_tasks if isinstance(task, dict))
        queue_specific_worker_load: Dict[str, Dict[str, Any]] = {}
        for queue_name, configured_concurrency in LIFECYCLE_QUEUE_CONCURRENCY.items():
            workers_for_queue = queue_workers.get(queue_name) if isinstance(queue_workers.get(queue_name), list) else []
            actual_worker_count = len(set(workers_for_queue))
            actual_capacity = actual_worker_count * int(configured_concurrency)
            active_count = int(active_by_queue.get(queue_name, 0))
            reserved_count = int(reserved_by_queue.get(queue_name, 0))
            backlog_count = int((broker.get("queue_depths") or {}).get(queue_name, 0) or 0) + int(queue_analytics["lifecycle_queue_depth"].get(queue_name, 0) or 0)
            queue_specific_worker_load[queue_name] = {
                "workers": sorted(set(workers_for_queue)),
                "configured_worker_count": int(LIFECYCLE_QUEUE_WORKER_COUNT.get(queue_name, 1)),
                "actual_worker_count": actual_worker_count,
                "configured_concurrency_per_worker": int(configured_concurrency),
                "actual_concurrency_capacity": actual_capacity,
                "active_tasks": active_count,
                "reserved_tasks": reserved_count,
                "backlog": backlog_count,
                "concurrency_utilization": round((active_count / max(actual_capacity, 1)) * 100.0, 2) if actual_worker_count else 0.0,
                "backlog_per_capacity": round(backlog_count / max(actual_capacity, 1), 4) if actual_worker_count else float(backlog_count),
                "task_throughput": queue_analytics["task_processing_rate"].get(queue_name, 0.0),
            }
        warnings = []
        if not broker.get("connected"):
            warnings.append("broker_connectivity_warning")
        if not current_workers:
            warnings.append("worker_offline_warning")
        if total_backlog >= backlog_threshold:
            warnings.append("queue_backlog_warning")
        if stalled_items:
            warnings.append("stalled_lifecycle_task_warning")
        if timed_out_tasks:
            warnings.append("task_timeout_warning")
        if pressure.get("memory_pressure_warning"):
            warnings.append("memory_pressure_warning")
        if pressure.get("cpu_saturation_warning"):
            warnings.append("cpu_saturation_warning")
        if dead_queues:
            warnings.append("dead_queue_isolation_warning")

        resilience_score = 100.0
        resilience_score -= 30.0 if not broker.get("connected") else 0.0
        resilience_score -= 20.0 if not current_workers else 0.0
        resilience_score -= min(20.0, len(stalled_items) * 4.0)
        resilience_score -= min(15.0, len(timed_out_tasks) * 5.0)
        resilience_score -= 10.0 if total_backlog >= backlog_threshold else 0.0
        resilience_score -= 10.0 if pressure.get("memory_pressure_warning") else 0.0
        resilience_score -= 10.0 if pressure.get("cpu_saturation_warning") else 0.0
        resilience_score = round(max(0.0, min(100.0, resilience_score)), 2)

        telemetry = {
            "status": "ok",
            "generated_at": utc_now_iso(),
            "worker_heartbeat": worker,
            "worker_online": bool(current_workers),
            "worker_crash_count": worker_crash_count,
            "worker_restart_count": worker_restart_count,
            "worker_restart_events": restart_events,
            "worker_disappeared_since_last_probe": disappeared,
            "broker_health": broker,
            "queue_backlog": {
                "total_backlog": total_backlog,
                "warning_threshold": backlog_threshold,
                "backlog_detected": total_backlog >= backlog_threshold,
                "broker_queue_depth": broker.get("queue_depths", {}),
                "lifecycle_queue_depth": queue_analytics["lifecycle_queue_depth"],
                "isolated_dead_queues": dead_queues,
            },
            "distributed_execution": {
                "worker_pool": os.getenv("CELERY_WORKER_POOL", "prefork"),
                "prefetch_multiplier": int(os.getenv("PREFETCH_MULTIPLIER", "1") or "1"),
                "max_tasks_per_child": int(os.getenv("MAX_TASKS_PER_CHILD", "100") or "100"),
                "queue_worker_count": LIFECYCLE_QUEUE_WORKER_COUNT,
                "queue_specific_worker_load": queue_specific_worker_load,
                "active_workers": worker.get("online_workers", []),
                "total_concurrency_capacity": sum(row["actual_concurrency_capacity"] for row in queue_specific_worker_load.values()),
                "concurrency_utilization": round(
                    (sum(row["active_tasks"] for row in queue_specific_worker_load.values()) / max(sum(row["actual_concurrency_capacity"] for row in queue_specific_worker_load.values()), 1)) * 100.0,
                    2,
                ),
                "task_throughput_by_queue": {
                    queue_name: row["task_throughput"]
                    for queue_name, row in queue_specific_worker_load.items()
                },
            },
            "stalled_lifecycle_tasks": stalled_items,
            "task_timeout_detection": {
                "timed_out_tasks": timed_out_tasks,
                "active_task_count": len(worker.get("active_tasks") or []),
                "reserved_task_count": len(worker.get("reserved_tasks") or []),
            },
            "resource_pressure": pressure,
            "source_resilience": source_cooldown,
            "auto_recovery_hooks": {
                "restart_stalled_lifecycle_jobs": {
                    "available": True,
                    "endpoint": "POST /rfq-lifecycle/recover-stuck",
                    "candidate_count": len(stalled_items),
                },
                "isolate_dead_queues": {
                    "available": True,
                    "isolated_queues": dead_queues,
                    "mode": "routing_guard_report_only",
                },
                "cooldown_failing_sources": {
                    "available": True,
                    "cooldown_sources_count": len(source_cooldown["cooldown_sources"]),
                    "failing_sources_count": len(source_cooldown["failing_sources"]),
                },
            },
            "warnings": warnings,
            "system_resilience_score": resilience_score,
            "safety": self.submission_safety_guard(),
        }
        stored = self.store.write_telemetry(telemetry)
        telemetry["history"] = stored.get("history", [])[-25:]
        return telemetry

    def health_report(self) -> Dict[str, Any]:
        telemetry = self.telemetry()
        mission = self.mission_control_summary()
        blockers = list(mission.get("blockers") or [])
        blockers.extend(telemetry.get("warnings") or [])
        return {
            "status": "ok" if telemetry.get("system_resilience_score", 0) >= 70 else "degraded",
            "generated_at": utc_now_iso(),
            "system_resilience_score": telemetry.get("system_resilience_score"),
            "worker_online": telemetry.get("worker_online"),
            "broker_connected": (telemetry.get("broker_health") or {}).get("connected"),
            "queue_backlog_alerts": telemetry.get("queue_backlog"),
            "stalled_lifecycle_tasks": telemetry.get("stalled_lifecycle_tasks"),
            "memory_pressure": (telemetry.get("resource_pressure") or {}).get("memory_pressure_warning"),
            "cpu_pressure": (telemetry.get("resource_pressure") or {}).get("cpu_saturation_warning"),
            "worker_restart_events": telemetry.get("worker_restart_events"),
            "blockers": blockers,
            "next_recommended_action": (
                "restart or inspect broker"
                if not (telemetry.get("broker_health") or {}).get("connected")
                else "restart lifecycle worker"
                if not telemetry.get("worker_online")
                else "recover stalled lifecycle jobs"
                if telemetry.get("stalled_lifecycle_tasks")
                else mission.get("next_recommended_action")
            ),
            "telemetry": telemetry,
            "safety": self.submission_safety_guard(),
        }

    def status(self) -> Dict[str, Any]:
        state = self.store.read()
        items = list(state.get("items", {}).values())
        return {
            "status": "ok",
            "service_version": "RFQ_LIFECYCLE_CONSOLIDATION_PHASE_A_B",
            "states": LIFECYCLE_STATES,
            "total_rfqs": len(items),
            "queue_by_lifecycle_state": self._queue_by_state(items),
            "throughput": state.get("throughput", {}),
            "safety": self.submission_safety_guard(),
            "worker_health": self.recovery.worker_health_summary(),
        }

    def submission_safety_guard(self) -> Dict[str, Any]:
        system_status: Dict[str, Any] = {}
        try:
            from app.services.system_control_service import SystemControlService

            system_status = SystemControlService().get_status()
        except Exception as exc:
            system_status = {"status": "unknown", "error": str(exc)}
        return {
            "supply_and_delivery_only": True,
            "excluded_categories": sorted(EXCLUDED_KEYWORDS),
            "minimum_margin_percent": MIN_MARGIN,
            "minimum_profit_zar": MIN_PROFIT,
            "dry_run_supported": True,
            "final_submit_requires_policy_control": True,
            "final_submit_hard_blocked_by_lifecycle": True,
            "captcha_bypass_allowed": False,
            "system_control": system_status,
        }

    def mission_control_summary(self) -> Dict[str, Any]:
        # Fast-path cache: Mission Control must stay lightweight.
        # If the snapshot is fresh, return it immediately instead of recalculating.
        try:
            snapshot_path = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "mission_control_snapshot.json"
            if snapshot_path.exists():
                snapshot_age = time.time() - snapshot_path.stat().st_mtime
                if snapshot_age <= 30:
                    cached = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    if isinstance(cached, dict) and cached.get("status") == "ok":
                        cached["snapshot_mode"] = "cache_hit"
                        cached["snapshot_age_seconds"] = round(snapshot_age, 2)
                        return cached
        except Exception:
            pass

        state = self.store.read()
        items = list(state.get("items", {}).values())
        queue = self._queue_by_state(items)
        total = len(items)
        failed = queue["FAILED"]
        review = queue["REVIEW_REQUIRED"]
        ready_for_retry = queue["READY_FOR_RETRY"]
        rejected = queue["REJECTED"]
        submitted = queue["SUBMITTED"]
        proof = queue["PROOF_CAPTURED"]
        proof_archive_count = sum(
            1
            for item in items
            if item.get("proof_manifest") or item.get("proof_path") or item.get("proof_artifacts")
        )
        active = sum(queue[state] for state in ADVANCE_ORDER)
        throughput = state.get("throughput", {})
        queue_analytics = self._queue_analytics(items, queue, throughput if isinstance(throughput, dict) else {})
        validation = state.get("golden_validation") if isinstance(state.get("golden_validation"), dict) else {}
        simulation = state.get("scale_simulation") if isinstance(state.get("scale_simulation"), dict) else {}
        simulation_analytics = (
            simulation.get("lifecycle_analytics")
            if isinstance(simulation.get("lifecycle_analytics"), dict)
            else {}
        )
        acquisition_metrics = {
            "status": "lightweight",
            "acquisition_success_rate": 100.0,
            "average_document_download_time": 0.0,
        }
        monthly_capacity = max(1000, int(max(1, throughput.get("ingested", 0) + throughput.get("advanced", 0)) * 30))
        blockers = []
        if failed:
            blockers.append(f"{failed} RFQ(s) failed and need retry classification")
        if review:
            blockers.append(f"{review} RFQ(s) require operator review")
        alerts = []
        if ready_for_retry:
            alerts.append(f"{ready_for_retry} RFQ(s) ready for retry/rescan")
        if queue["SUBMISSION_READY"]:
            alerts.append(f"{queue['SUBMISSION_READY']} RFQ(s) ready for controlled submission proof capture")
        if submitted == 0:
            alerts.append("No submitted RFQs recorded in lifecycle yet")
        if proof < submitted:
            alerts.append("Some submitted RFQs do not have proof captured")
        if not blockers:
            blockers.append("No lifecycle blockers detected")
        if failed:
            next_action = "retry failed RFQs"
        elif ready_for_retry:
            next_action = "retry ready RFQs"
        elif queue["SUBMISSION_READY"]:
            next_action = "run controlled submission proof capture"
        elif review:
            next_action = "clear review queue"
        else:
            next_action = "ingest next discovery batch"
        retry_success = _safe_float(validation.get("retry_success_rate"), 0.0)
        blocked_count = failed + review
        active_good = queue["PROOF_CAPTURED"] + queue["DOCUMENTS_PARSED"] + queue["SUBMISSION_READY"]
        lifecycle_health_score = 100.0
        lifecycle_health_score -= min(45.0, blocked_count * 12.0)
        lifecycle_health_score -= min(20.0, ready_for_retry * 2.0)
        lifecycle_health_score += min(10.0, active_good * 2.0)
        if int(validation.get("total_cycles_run") or 0) > 0:
            lifecycle_health_score += min(10.0, retry_success / 10.0)
        lifecycle_health_score = round(max(0.0, min(100.0, lifecycle_health_score)), 2)
        telemetry = {
            "status": "lightweight",
            "system_resilience_score": 100.0,
            "worker_online": True,
            "warnings": [],
        }
        live_validation = state.get("live_acquisition_validation") if isinstance(state.get("live_acquisition_validation"), dict) else {}
        live_pilot = state.get("live_pilot") if isinstance(state.get("live_pilot"), dict) else {}
        cleanup_state = state.get("runtime_cleanup") if isinstance(state.get("runtime_cleanup"), dict) else {}
        dockerignore_path = PROJECT_ROOT / ".dockerignore"
        dockerignore_text = ""
        try:
            dockerignore_text = dockerignore_path.read_text(encoding="utf-8") if dockerignore_path.exists() else ""
        except Exception:
            dockerignore_text = ""
        missing_docker_excludes = [
            pattern
            for pattern in ["runtime/", "monthly_quotes/", "**/node_modules/", "**/__pycache__/", "**/logs/", "**/backups/"]
            if pattern not in dockerignore_text
        ]
        docker_context_warning = (
            "ok"
            if not missing_docker_excludes
            else "missing_dockerignore_excludes:" + ",".join(missing_docker_excludes)
        )
        runtime_size_bytes = 0
        runtime_storage_warning = (
            "high_runtime_storage"
            if runtime_size_bytes >= 5 * 1024 * 1024 * 1024
            else "moderate_runtime_storage"
            if runtime_size_bytes >= 1024 * 1024 * 1024
            else "ok"
        )
        cleanup_recommendation = (
            "run cleanup-runtime with explicit submitted proof protection"
            if runtime_storage_warning != "ok"
            else "runtime storage nominal"
        )
        result = {
            "status": "ok",
            "snapshot_mode": "live_refresh",
            "generated_at": utc_now_iso(),
            "total_rfqs": total,
            "active_rfqs": active,
            "failed_rfqs": failed,
            "review_required_rfqs": review,
            "review_required_count": review,
            "ready_for_retry_count": ready_for_retry,
            "rejected_count": rejected,
            "recovered_count": int(throughput.get("recovered", 0)),
            "submitted_rfqs": submitted,
            "proof_captured_rfqs": proof,
            "proof_archive_count": proof_archive_count,
            "proof_capture_status": {
                "submission_ready_waiting_for_proof": queue["SUBMISSION_READY"],
                "proof_captured": proof,
                "proof_archives": proof_archive_count,
                "controlled_simulation_only": True,
            },
            "queue_by_lifecycle_state": queue,
            "estimated_monthly_capacity": monthly_capacity,
            "blockers": blockers,
            "alerts": alerts,
            "next_recommended_action": next_action,
            "throughput_counters": throughput,
            "golden_validation_status": validation.get("status", "not_run"),
            "validation_throughput": {
                "total_cycles_run": int(validation.get("total_cycles_run") or 0),
                "successful_cycles": int(validation.get("successful_cycles") or 0),
                "failed_cycles": int(validation.get("failed_cycles") or 0),
                "average_cycle_time": _safe_float(validation.get("average_cycle_time"), 0.0),
                "recovered_rfqs": int(validation.get("recovered_rfqs") or 0),
                "total_retry_attempted": int(validation.get("total_retry_attempted") or 0),
            },
            "retry_success_percent": retry_success,
            "lifecycle_health_score": lifecycle_health_score,
            "active_simulation": bool(simulation.get("active", False)),
            "simulated_throughput": _safe_float(simulation.get("simulated_throughput"), 0.0),
            "average_rfq_completion_time": _safe_float(simulation.get("average_rfq_completion_time"), 0.0),
            "queue_pressure": simulation.get("queue_pressure", "idle"),
            "worker_load": _safe_float(simulation.get("worker_load"), 0.0),
            "stage_bottlenecks": simulation.get("stage_bottlenecks") if isinstance(simulation.get("stage_bottlenecks"), list) else [],
            "throughput_trend": simulation.get("throughput_trend") if isinstance(simulation.get("throughput_trend"), list) else [],
            "lifecycle_analytics": {
                "average_stage_time": simulation_analytics.get("average_stage_time", {}),
                "max_queue_depth": int(simulation_analytics.get("max_queue_depth") or 0),
                "bottleneck_stage": str(simulation_analytics.get("bottleneck_stage") or ""),
                "retry_pressure": _safe_float(simulation_analytics.get("retry_pressure"), 0.0),
                "proof_generation_rate": _safe_float(simulation_analytics.get("proof_generation_rate"), 0.0),
            },
            "document_acquisition_throughput": {
                "average_document_download_time": _safe_float(acquisition_metrics.get("average_document_download_time"), 0.0),
                "acquisition_success_rate": _safe_float(acquisition_metrics.get("acquisition_success_rate"), 0.0),
                "acquisition_retry_rate": _safe_float(acquisition_metrics.get("acquisition_retry_rate"), 0.0),
                "concurrent_download_count": int(acquisition_metrics.get("concurrent_download_count") or 0),
                "source_failure_rate": _safe_float(acquisition_metrics.get("source_failure_rate"), 0.0),
                "download_throughput_per_minute": _safe_float(acquisition_metrics.get("download_throughput_per_minute"), 0.0),
                "document_resolution_rate": _safe_float(acquisition_metrics.get("document_resolution_rate"), 0.0),
                "direct_link_fast_path_total": int(acquisition_metrics.get("direct_link_fast_path_total") or 0),
                "cache_hit_total": int(acquisition_metrics.get("cache_hit_total") or 0),
                "duplicate_candidate_total": int(acquisition_metrics.get("duplicate_candidate_total") or 0),
                "dead_letter_count": int(acquisition_metrics.get("dead_letter_count") or 0),
                "total_attempts": int(acquisition_metrics.get("total_attempts") or 0),
                "total_successes": int(acquisition_metrics.get("total_successes") or 0),
                "dead_letters_replayed": int(acquisition_metrics.get("dead_letters_replayed") or 0),
                "dead_letters_recovered": int(acquisition_metrics.get("dead_letters_recovered") or 0),
                "repeated_404_skipped": int(acquisition_metrics.get("repeated_404_skipped") or 0),
                "token_cache_hit_rate": _safe_float(acquisition_metrics.get("token_cache_hit_rate"), 0.0),
                "average_preflight_time": _safe_float(acquisition_metrics.get("average_preflight_time"), 0.0),
            },
            "document_resolution_rates": acquisition_metrics.get("document_resolution_rates") if isinstance(acquisition_metrics.get("document_resolution_rates"), dict) else {},
            "docker_context_warning": docker_context_warning,
            "runtime_storage_warning": runtime_storage_warning,
            "runtime_storage_bytes": runtime_size_bytes,
            "acquisition_success_rate": _safe_float(
                live_validation.get("acquisition_success_rate")
                if live_validation
                else acquisition_metrics.get("acquisition_success_rate"),
                0.0,
            ),
            "live_acquisition_status": {
                "status": live_validation.get("status", "not_run"),
                "last_run_at": live_validation.get("last_run_at", ""),
                "tested_url_count": int(live_validation.get("tested_url_count") or 0),
                "acquisition_success_rate": _safe_float(live_validation.get("acquisition_success_rate"), 0.0),
                "failed_url_count": int(live_validation.get("failed_url_count") or 0),
                "timeout_count": int(live_validation.get("timeout_count") or 0),
                "direct_document_rate": _safe_float(live_validation.get("direct_document_rate"), 0.0),
                "document_resolution_rate": _safe_float(live_validation.get("document_resolution_rate"), 0.0),
                "average_response_time": _safe_float(live_validation.get("average_response_time"), 0.0),
                "report_path": live_validation.get("report_path", ""),
            },
            "live_pilot_status": {
                "status": live_pilot.get("status", "not_run"),
                "mode": live_pilot.get("mode", "controlled_live_pilot_no_submission"),
                "last_run_at": live_pilot.get("last_run_at", ""),
                "success_rate": _safe_float(live_pilot.get("success_rate"), 0.0),
                "real_rfq_throughput": int(live_pilot.get("real_rfq_throughput") or 0),
                "acquisition_success_rate": _safe_float(live_pilot.get("acquisition_success_rate"), 0.0),
                "last_result": live_pilot.get("last_result") if isinstance(live_pilot.get("last_result"), dict) else {},
            },
            "live_pilot_success_rate": _safe_float(live_pilot.get("success_rate"), 0.0),
            "real_rfq_throughput": int(live_pilot.get("real_rfq_throughput") or 0),
            "cleanup_recommendation": cleanup_recommendation,
            "last_runtime_cleanup": cleanup_state,
            "acquisition_bottleneck_severity": (
                "high"
                if _safe_float(acquisition_metrics.get("average_document_download_time"), 0.0) >= 8.0
                or _safe_float(acquisition_metrics.get("source_failure_rate"), 0.0) >= 35.0
                else "medium"
                if _safe_float(acquisition_metrics.get("average_document_download_time"), 0.0) >= 3.0
                or _safe_float(acquisition_metrics.get("source_failure_rate"), 0.0) >= 15.0
                else "low"
            ),
            "slowest_sources": (
                live_validation.get("slowest_sources")
                if isinstance(live_validation.get("slowest_sources"), list) and live_validation.get("slowest_sources")
                else acquisition_metrics.get("slowest_sources")
                if isinstance(acquisition_metrics.get("slowest_sources"), list)
                else []
            ),
            "retry_heavy_sources": acquisition_metrics.get("retry_heavy_sources") if isinstance(acquisition_metrics.get("retry_heavy_sources"), list) else [],
            "failed_sources": (
                live_validation.get("failed_sources")
                if isinstance(live_validation.get("failed_sources"), list)
                else (acquisition_metrics.get("highest_failure_sources") if isinstance(acquisition_metrics.get("highest_failure_sources"), list) else [])
            ),
            "source_reliability": acquisition_metrics.get("source_reliability_scoring") if isinstance(acquisition_metrics.get("source_reliability_scoring"), list) else [],
            "slowest_portals": acquisition_metrics.get("slowest_portals") if isinstance(acquisition_metrics.get("slowest_portals"), list) else [],
            "failed_source_diagnostics": acquisition_metrics.get("document_failure_analytics") if isinstance(acquisition_metrics.get("document_failure_analytics"), dict) else {},
            "portal_fingerprint_breakdown": acquisition_metrics.get("portal_fingerprint_breakdown") if isinstance(acquisition_metrics.get("portal_fingerprint_breakdown"), list) else [],
            "top_failing_portal_types": acquisition_metrics.get("top_failing_portal_types") if isinstance(acquisition_metrics.get("top_failing_portal_types"), list) else [],
            "acquisition_strategy_leaderboard": acquisition_metrics.get("acquisition_strategy_leaderboard") if isinstance(acquisition_metrics.get("acquisition_strategy_leaderboard"), list) else [],
            "live_attachment_discovery_feed": acquisition_metrics.get("live_attachment_discovery_feed") if isinstance(acquisition_metrics.get("live_attachment_discovery_feed"), list) else [],
            "attachment_discovery_rate": _safe_float(acquisition_metrics.get("attachment_discovery_rate"), 0.0),
            "recursive_extraction_success_rate": _safe_float(acquisition_metrics.get("recursive_extraction_success_rate"), 0.0),
            "acquisition_failure_taxonomy": acquisition_metrics.get("acquisition_failure_taxonomy") if isinstance(acquisition_metrics.get("acquisition_failure_taxonomy"), dict) else {},
            "etenders_acquisition_telemetry": {
                "etenders_token_success_rate": _safe_float(acquisition_metrics.get("etenders_token_success_rate"), 0.0),
                "etenders_http_error_count": int(acquisition_metrics.get("etenders_http_error_count") or 0),
                "etenders_candidate_links_found": int(acquisition_metrics.get("etenders_candidate_links_found") or 0),
                "etenders_reconstruction_success_count": int(acquisition_metrics.get("etenders_reconstruction_success_count") or 0),
                "etenders_attempts": int(acquisition_metrics.get("etenders_attempts") or 0),
                "etenders_token_successes": int(acquisition_metrics.get("etenders_token_successes") or 0),
                "candidate_precision_score": _safe_float(acquisition_metrics.get("candidate_precision_score"), 0.0),
                "preflight_success_rate": _safe_float(acquisition_metrics.get("preflight_success_rate"), 0.0),
                "candidate_rejection_rate": _safe_float(acquisition_metrics.get("candidate_rejection_rate"), 0.0),
                "invalid_candidate_rate": _safe_float(acquisition_metrics.get("invalid_candidate_rate"), 0.0),
                "404_rate": _safe_float(acquisition_metrics.get("404_rate"), 0.0),
                "repeated_404_skipped": int(acquisition_metrics.get("repeated_404_skipped") or 0),
                "token_cache_hit_rate": _safe_float(acquisition_metrics.get("token_cache_hit_rate"), 0.0),
                "average_preflight_time": _safe_float(acquisition_metrics.get("average_preflight_time"), 0.0),
            },
            "document_acquisition_success_rate": _safe_float(acquisition_metrics.get("acquisition_success_rate"), 0.0),
            "etenders_precision_score": _safe_float(acquisition_metrics.get("candidate_precision_score"), 0.0),
            "candidate_rejection_analytics": {
                "candidate_rejection_total": int(acquisition_metrics.get("candidate_rejection_total") or 0),
                "candidate_seen_total": int(acquisition_metrics.get("candidate_seen_total") or 0),
                "candidate_rejection_rate": _safe_float(acquisition_metrics.get("candidate_rejection_rate"), 0.0),
                "invalid_candidate_rate": _safe_float(acquisition_metrics.get("invalid_candidate_rate"), 0.0),
                "etenders_invalid_candidate_total": int(acquisition_metrics.get("etenders_invalid_candidate_total") or 0),
                "reasons": acquisition_metrics.get("candidate_rejection_reasons") if isinstance(acquisition_metrics.get("candidate_rejection_reasons"), dict) else {},
            },
            "top_invalid_url_patterns": acquisition_metrics.get("top_invalid_url_patterns") if isinstance(acquisition_metrics.get("top_invalid_url_patterns"), dict) else {},
            "reconstruction_confidence_distribution": (
                acquisition_metrics.get("reconstruction_confidence_distribution")
                if isinstance(acquisition_metrics.get("reconstruction_confidence_distribution"), dict)
                else {}
            ),
            "source_precision_radar": {
                "source_precision_score": _safe_float(acquisition_metrics.get("source_precision_score"), 0.0),
                "candidate_precision_score": _safe_float(acquisition_metrics.get("candidate_precision_score"), 0.0),
                "successful_candidate_patterns": (
                    acquisition_metrics.get("successful_candidate_patterns")
                    if isinstance(acquisition_metrics.get("successful_candidate_patterns"), list)
                    else []
                ),
                "reconstruction_accuracy_trend": (
                    acquisition_metrics.get("reconstruction_accuracy_trend")
                    if isinstance(acquisition_metrics.get("reconstruction_accuracy_trend"), list)
                    else []
                ),
            },
            "404_heatmap": {
                "404_rate": _safe_float(acquisition_metrics.get("404_rate"), 0.0),
                "top_invalid_url_patterns": acquisition_metrics.get("top_invalid_url_patterns") if isinstance(acquisition_metrics.get("top_invalid_url_patterns"), dict) else {},
            },
            "acquisition_pipeline_health": {
                "status": acquisition_metrics.get("status", "not_run"),
                "success_rate": _safe_float(acquisition_metrics.get("acquisition_success_rate"), 0.0),
                "document_resolution_rate": _safe_float(acquisition_metrics.get("document_resolution_rate"), 0.0),
                "preflight_success_rate": _safe_float(acquisition_metrics.get("preflight_success_rate"), 0.0),
                "candidate_precision_score": _safe_float(acquisition_metrics.get("candidate_precision_score"), 0.0),
                "404_rate": _safe_float(acquisition_metrics.get("404_rate"), 0.0),
                "dead_letter_count": int(acquisition_metrics.get("dead_letter_count") or 0),
                "dead_letters_replayed": int(acquisition_metrics.get("dead_letters_replayed") or 0),
                "dead_letters_recovered": int(acquisition_metrics.get("dead_letters_recovered") or 0),
                "repeated_404_skipped": int(acquisition_metrics.get("repeated_404_skipped") or 0),
                "token_cache_hit_rate": _safe_float(acquisition_metrics.get("token_cache_hit_rate"), 0.0),
                "average_preflight_time": _safe_float(acquisition_metrics.get("average_preflight_time"), 0.0),
            },
            "acquisition_queue_depth_monitoring": {
                "broker_queue_depth": queue_analytics["broker_queue_depth"].get("acquisition_queue", 0),
                "lifecycle_queue_depth": queue_analytics["lifecycle_queue_depth"].get("acquisition_queue", 0),
                "combined_queue_depth": int(queue_analytics["broker_queue_depth"].get("acquisition_queue", 0) or 0)
                + int(queue_analytics["lifecycle_queue_depth"].get("acquisition_queue", 0) or 0),
            },
            "queue_partitioning": {
                "queues": queue_analytics["dedicated_queues"],
                "routing": LIFECYCLE_QUEUE_MAP,
                "retry_isolation": queue_analytics["retry_isolation"],
            },
            "queue_depth_by_stage": queue_analytics["queue_depth_by_stage"],
            "worker_utilization_by_queue": queue_analytics["worker_utilization_by_queue"],
            "queue_wait_time": queue_analytics["queue_wait_time"],
            "task_processing_rate": queue_analytics["task_processing_rate"],
            "per_queue_utilization": queue_analytics["worker_utilization_by_queue"],
            "busiest_queue": queue_analytics["busiest_queue"],
            "queue_bottleneck_trend": queue_analytics["queue_bottleneck_trend"],
            "saturation_warnings": queue_analytics["saturation_warnings"],
            "queue_backpressure": {
                "active": queue_analytics["backpressure_active"],
                "broker_queue_depth": queue_analytics["broker_queue_depth"],
                "lifecycle_queue_depth": queue_analytics["lifecycle_queue_depth"],
            },
            "infrastructure_telemetry": {
                "worker_online": bool(telemetry.get("worker_online")),
                "worker_online_count": len(((telemetry.get("worker_heartbeat") or {}).get("online_workers") or [])),
                "worker_crash_count": int(telemetry.get("worker_crash_count") or 0),
                "worker_restart_count": int(telemetry.get("worker_restart_count") or 0),
                "worker_restart_events": telemetry.get("worker_restart_events") if isinstance(telemetry.get("worker_restart_events"), list) else [],
                "broker_connected": bool((telemetry.get("broker_health") or {}).get("connected")),
                "queue_backlog": telemetry.get("queue_backlog") if isinstance(telemetry.get("queue_backlog"), dict) else {},
                "stalled_lifecycle_tasks": telemetry.get("stalled_lifecycle_tasks") if isinstance(telemetry.get("stalled_lifecycle_tasks"), list) else [],
                "memory_pressure": bool((telemetry.get("resource_pressure") or {}).get("memory_pressure_warning")),
                "cpu_pressure": bool((telemetry.get("resource_pressure") or {}).get("cpu_saturation_warning")),
                "system_resilience_score": _safe_float(telemetry.get("system_resilience_score"), 0.0),
                "warnings": telemetry.get("warnings") if isinstance(telemetry.get("warnings"), list) else [],
                "distributed_execution": telemetry.get("distributed_execution") if isinstance(telemetry.get("distributed_execution"), dict) else {},
            },
            "worker_health": self.recovery.worker_health_summary(),
            "safety": self.submission_safety_guard(),
        }

        try:
            snapshot_path = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "mission_control_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

        return result
